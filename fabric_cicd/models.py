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


@dataclass
class DeploymentWindow:
    start_hour_utc: int = 0
    end_hour_utc: int = 24


@dataclass
class EnterprisePolicy:
    allowed_artifact_types: list[str] = field(default_factory=list)
    required_artifact_types: list[str] = field(default_factory=list)
    name_patterns: dict[str, str] = field(default_factory=dict)
    protected_environments: list[str] = field(default_factory=lambda: ["prod"])
    freeze: bool = False
    deployment_window: DeploymentWindow = field(default_factory=DeploymentWindow)
    require_backup_workspace_for_protected: bool = True
    disallow_target_name_override_in_protected: bool = True
    require_all_artifacts_required_in_protected: bool = True
