from __future__ import annotations

from pathlib import Path

import yaml

from fabric_cicd.models import (
    ArtifactConfig,
    DeploymentWindow,
    EnterprisePolicy,
    EnvironmentConfig,
)


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


def load_enterprise_policy(path: str | Path) -> EnterprisePolicy:
    policy_path = Path(path)
    raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))

    window_raw = raw.get("deployment_window", {})
    deployment_window = DeploymentWindow(
        start_hour_utc=int(window_raw.get("start_hour_utc", 0)),
        end_hour_utc=int(window_raw.get("end_hour_utc", 24)),
    )

    return EnterprisePolicy(
        allowed_artifact_types=list(raw.get("allowed_artifact_types", [])),
        required_artifact_types=list(raw.get("required_artifact_types", [])),
        name_patterns=dict(raw.get("name_patterns", {})),
        protected_environments=list(raw.get("protected_environments", ["prod"])),
        freeze=bool(raw.get("freeze", False)),
        deployment_window=deployment_window,
        require_backup_workspace_for_protected=bool(
            raw.get("require_backup_workspace_for_protected", True)
        ),
        disallow_target_name_override_in_protected=bool(
            raw.get("disallow_target_name_override_in_protected", True)
        ),
        require_all_artifacts_required_in_protected=bool(
            raw.get("require_all_artifacts_required_in_protected", True)
        ),
    )
