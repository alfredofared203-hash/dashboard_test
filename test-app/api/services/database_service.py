from decimal import Decimal
from threading import Lock

from api.config import get_settings
from api.dependencies import (
    DependencyUnavailable,
    database_connection,
    timed_database_operation,
)


_SCHEMA_INITIALIZED = False
_SCHEMA_LOCK = Lock()


def initialize_schema() -> None:
    global _SCHEMA_INITIALIZED
    with _SCHEMA_LOCK:
        if _SCHEMA_INITIALIZED:
            return

        def create_schema() -> None:
            with database_connection() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS products (
                        sku TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        price NUMERIC(10, 2) NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS orders (
                        order_id TEXT PRIMARY KEY,
                        product_sku TEXT NOT NULL REFERENCES products(sku),
                        quantity INTEGER NOT NULL CHECK (quantity > 0),
                        status TEXT NOT NULL
                    )
                    """
                )
                with connection.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO products (sku, name, price)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (sku) DO NOTHING
                        """,
                        [
                            ("test-book", "Test Book", Decimal("12.50")),
                            ("test-mug", "Test Mug", Decimal("8.00")),
                        ],
                    )
                    cursor.executemany(
                        """
                        INSERT INTO orders (order_id, product_sku, quantity, status)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (order_id) DO NOTHING
                        """,
                        [
                            ("test-order-001", "test-book", 1, "ready"),
                            ("test-order-002", "test-mug", 2, "processing"),
                        ],
                    )

        timed_database_operation("initialize_schema", create_schema)
        _SCHEMA_INITIALIZED = True


def list_products(limit: int) -> list[dict[str, object]]:
    if not get_settings().database_url:
        raise DependencyUnavailable("postgres")
    initialize_schema()

    def query() -> list[dict[str, object]]:
        with database_connection() as connection:
            rows = connection.execute(
                "SELECT sku, name, price FROM products ORDER BY sku LIMIT %s",
                (limit,),
            ).fetchall()
        return [
            {"sku": sku, "name": name, "price": float(price)}
            for sku, name, price in rows
        ]

    return timed_database_operation("list_products", query)


def list_orders(limit: int) -> list[dict[str, object]]:
    if not get_settings().database_url:
        raise DependencyUnavailable("postgres")
    initialize_schema()

    def query() -> list[dict[str, object]]:
        with database_connection() as connection:
            rows = connection.execute(
                """
                SELECT order_id, product_sku, quantity, status
                FROM orders
                ORDER BY order_id
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "order_id": order_id,
                "product_sku": product_sku,
                "quantity": quantity,
                "status": order_status,
            }
            for order_id, product_sku, quantity, order_status in rows
        ]

    return timed_database_operation("list_orders", query)


def readiness_database_probe() -> None:
    with database_connection() as connection:
        connection.execute("SELECT 1").fetchone()
