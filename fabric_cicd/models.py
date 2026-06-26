from dataclasses import dataclass, field
from typing import Literal

ArtifactType = Literal[
    "Notebook",
    "Pipeline",
    "Lakehouse",
    "Environment",
    "CopyJob",
    "Dataflow",
    "VariableLibrary",
    "SemanticModel",
    "Report",
]

SUPPORTED_ARTIFACT_TYPES = {
    "Notebook",
    "Pipeline",
    "Lakehouse",
    "Environment",
    "CopyJob",
    "Dataflow",
    "VariableLibrary",
    "SemanticModel",
    "Report",
}


@dataclass
class FabricAuth:
    tenant_id: str
    client_id: str
    client_secret: str


@dataclass
class EnvironmentConfig:
    name: str
    workspace_id: str
    capacity_id: str
    backup_workspace_id: str | None = None
    items: dict[str, "ArtifactConfig"] = field(default_factory=dict)


@dataclass
class ArtifactConfig:
    logical_name: str
    name: str
    artifact_type: ArtifactType
    target_name: str | None = None
    depends_on: list[str] = field(default_factory=list)
    required: bool = True


@dataclass
class RollbackEntry:
    logical_name: str
    target_name: str
    artifact_type: ArtifactType
    backup_workspace_id: str
    backup_item_id: str


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def ensure_valid(self) -> None:
        if self.errors:
            raise RuntimeError("Validation failed:\n- " + "\n- ".join(self.errors))
