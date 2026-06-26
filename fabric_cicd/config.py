from __future__ import annotations

from pathlib import Path
import yaml

from fabric_cicd.models import ArtifactConfig, EnvironmentConfig


def _coerce_artifacts(raw_items: dict) -> dict[str, ArtifactConfig]:
    artifacts: dict[str, ArtifactConfig] = {}
    for logical_name, value in raw_items.items():
        if isinstance(value, str):
            artifacts[logical_name] = ArtifactConfig(
                logical_name=logical_name,
                name=value,
                artifact_type="Notebook",
            )
            continue

        artifact_type = value.get("type", "Notebook")
        artifacts[logical_name] = ArtifactConfig(
            logical_name=logical_name,
            name=value["name"],
            artifact_type=artifact_type,
            target_name=value.get("target_name"),
            depends_on=value.get("depends_on", []),
            required=value.get("required", True),
        )
    return artifacts


def load_environment_config(path: str | Path) -> EnvironmentConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    return EnvironmentConfig(
        name=raw["name"],
        workspace_id=raw["workspace_id"],
        capacity_id=raw["capacity_id"],
        backup_workspace_id=raw.get("backup_workspace_id"),
        items=_coerce_artifacts(raw.get("items", {})),
    )
