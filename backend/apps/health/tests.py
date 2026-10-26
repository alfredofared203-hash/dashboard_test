from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.test import Client, SimpleTestCase, override_settings


class FrontendProductionRoutingTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_spa_fallback_serves_index_for_frontend_routes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "index.html"
            index_path.write_text("<html><body>dcc app</body></html>", encoding="utf-8")
            with self.settings(STATIC_ROOT=temp_dir):
                response = Client().get("/tasks-resources/")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "dcc app")

    @override_settings(DEBUG=False)
    def test_api_routes_are_not_routed_to_the_spa(self) -> None:
        response = Client().get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "dcc-backend")

    @override_settings(ALLOWED_HOSTS=["dcc-app.dcc-test.internal"])
    def test_health_check_accepts_load_balancer_target_host(self) -> None:
        response = Client().get(
            "/api/health/",
            HTTP_HOST="10.80.37.217:8000",
            HTTP_X_FORWARDED_HOST="untrusted.example",
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(ALLOWED_HOSTS=["dcc-app.dcc-test.internal"])
    def test_other_routes_still_reject_unlisted_hosts(self) -> None:
        response = Client().get(
            "/",
            HTTP_HOST="untrusted.example",
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(DEBUG=False)
    def test_static_assets_are_served_in_production(self) -> None:
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir) / "assets"
            assets_dir.mkdir()
            asset_path = assets_dir / "app.js"
            asset_path.write_text("window.dccReady = true;", encoding="utf-8")
            with self.settings(
                STATIC_ROOT=temp_dir,
                MIDDLEWARE=list(settings.MIDDLEWARE),
            ):
                response = Client(HTTP_HOST="localhost").get("/assets/app.js")
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, "window.dccReady = true;")
                finally:
                    response.close()
