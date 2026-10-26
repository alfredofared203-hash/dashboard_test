from typing import Any, Literal, Protocol


DependencyType = Literal["rds", "elasticache"]


class DependencyProviderError(Exception):
    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


class DependencyObservabilityProvider(Protocol):
    name: str

    def list_dependencies(
        self,
        resource_type: DependencyType | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_impact_dependencies(self) -> list[dict[str, Any]]: ...
