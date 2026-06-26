from __future__ import annotations

from pathlib import Path

from fabric_cicd.config import load_environment_config
from fabric_cicd.deployment import (
    build_dependency_graph,
    lint_environment_config,
    promote_with_validation,
    render_dependency_graph_mermaid,
    run_preflight_checks,
    run_rollback,
    validate_promotion,
)
from fabric_cicd.fabric_api import FabricApiClient
from fabric_cicd.models import FabricAuth


def make_client(tenant_id: str, client_id: str, client_secret: str) -> FabricApiClient:
    return FabricApiClient(
        FabricAuth(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
    )


def export_workspace(
    env_config_file: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    out_dir: str = "artifacts/exported",
) -> None:
    cfg = load_environment_config(env_config_file)
    client = make_client(tenant_id, client_id, client_secret)
    target = Path(out_dir) / cfg.name
    client.export_workspace_items(cfg.workspace_id, target)
    print(f"Exported workspace items to {target}")


def promote_items(
    source_env_config_file: str,
    target_env_config_file: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    selected_logical_names: list[str] | None = None,
) -> None:
    source_cfg = load_environment_config(source_env_config_file)
    target_cfg = load_environment_config(target_env_config_file)
    client = make_client(tenant_id, client_id, client_secret)

    rollback_manifest = (
        Path("artifacts")
        / "rollback"
        / f"{source_cfg.name}-to-{target_cfg.name}-rollback.json"
    )
    promote_with_validation(
        client,
        source_cfg,
        target_cfg,
        rollback_manifest,
        selected_logical_names=selected_logical_names,
    )


def validate_only(
    source_env_config_file: str,
    target_env_config_file: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> None:
    source_cfg = load_environment_config(source_env_config_file)
    target_cfg = load_environment_config(target_env_config_file)
    client = make_client(tenant_id, client_id, client_secret)
    validation = validate_promotion(client, source_cfg, target_cfg)

    for warning in validation.warnings:
        print(f"[WARN] {warning}")

    if validation.errors:
        for error in validation.errors:
            print(f"[ERROR] {error}")
        validation.ensure_valid()

    print("Validation checks passed.")


def rollback_items(
    target_env_config_file: str,
    rollback_manifest_path: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> None:
    target_cfg = load_environment_config(target_env_config_file)
    client = make_client(tenant_id, client_id, client_secret)
    run_rollback(client, target_cfg, rollback_manifest_path)


def lint_config(env_config_file: str) -> None:
    cfg = load_environment_config(env_config_file)
    result = lint_environment_config(cfg)

    for warning in result.warnings:
        print(f"[WARN] {warning}")
    for error in result.errors:
        print(f"[ERROR] {error}")

    result.ensure_valid()
    print(f"Lint checks passed for {env_config_file}")


def preflight(
    source_env_config_file: str,
    target_env_config_file: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> None:
    source_cfg = load_environment_config(source_env_config_file)
    target_cfg = load_environment_config(target_env_config_file)
    client = make_client(tenant_id, client_id, client_secret)

    result = run_preflight_checks(client, source_cfg, target_cfg)
    for warning in result.warnings:
        print(f"[WARN] {warning}")
    for error in result.errors:
        print(f"[ERROR] {error}")

    result.ensure_valid()
    print("Preflight checks passed.")


def graph(env_config_file: str, format_name: str) -> None:
    cfg = load_environment_config(env_config_file)
    if format_name == "json":
        print(build_dependency_graph(cfg))
        return

    if format_name == "mermaid":
        print(render_dependency_graph_mermaid(cfg))
        return

    raise RuntimeError(f"Unsupported graph format: {format_name}")
