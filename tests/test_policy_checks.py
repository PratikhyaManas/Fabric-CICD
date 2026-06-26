from __future__ import annotations

from fabric_cicd.deployment import apply_enterprise_policy, lint_environment_config
from fabric_cicd.models import (
    ArtifactConfig,
    DeploymentWindow,
    EnterprisePolicy,
    EnvironmentConfig,
)


def _base_config(env_name: str = "prod") -> EnvironmentConfig:
    return EnvironmentConfig(
        name=env_name,
        workspace_id="workspace-id",
        capacity_id="capacity-id",
        backup_workspace_id="backup-id",
        items={
            "notebook_ingest": ArtifactConfig(
                logical_name="notebook_ingest",
                name="NotebookIngest",
                artifact_type="Notebook",
            )
        },
    )


def test_lint_detects_policy_sensitive_issues() -> None:
    cfg = _base_config()
    cfg.backup_workspace_id = None
    cfg.items["notebook_ingest"].required = False

    result = lint_environment_config(cfg)

    assert any("backup_workspace_id" in error for error in result.errors)
    assert any("must be required" in error for error in result.errors)


def test_policy_blocks_unsafe_prod_deployments() -> None:
    cfg = _base_config("prod")
    cfg.items["notebook_ingest"].target_name = "NotebookIngestProd"

    policy = EnterprisePolicy(
        protected_environments=["prod"],
        require_backup_workspace_for_protected=True,
        disallow_target_name_override_in_protected=True,
        deployment_window=DeploymentWindow(start_hour_utc=0, end_hour_utc=24),
    )

    result = apply_enterprise_policy(cfg, "prod", policy)

    assert any("target_name override" in error for error in result.errors)
