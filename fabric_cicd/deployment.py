from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from fabric_cicd.fabric_api import FabricApiClient
from fabric_cicd.models import (
    ArtifactConfig,
    EnvironmentConfig,
    RollbackEntry,
    SUPPORTED_ARTIFACT_TYPES,
    ValidationResult,
)


def _artifact_order_priority(artifact: ArtifactConfig) -> int:
    # Deploy upstream dependencies first to avoid broken references.
    priorities = {
        "VariableLibrary": 5,
        "Environment": 10,
        "Lakehouse": 15,
        "Notebook": 20,
        "Pipeline": 30,
        "Dataflow": 35,
        "CopyJob": 40,
        "SemanticModel": 50,
        "Report": 60,
    }
    return priorities.get(artifact.artifact_type, 100)


def _sort_artifacts_for_deploy(artifacts: list[ArtifactConfig]) -> list[ArtifactConfig]:
    return sorted(artifacts, key=lambda a: (_artifact_order_priority(a), a.logical_name))


def build_dependency_graph(environment_cfg: EnvironmentConfig) -> dict[str, list[str]]:
    return {
        artifact.logical_name: list(artifact.depends_on)
        for artifact in environment_cfg.items.values()
    }


def render_dependency_graph_mermaid(environment_cfg: EnvironmentConfig) -> str:
    lines = ["graph TD"]
    for logical_name, artifact in environment_cfg.items.items():
        lines.append(f"  {logical_name}[\"{artifact.name}\\n({artifact.artifact_type})\"]")

    graph = build_dependency_graph(environment_cfg)
    for node, deps in graph.items():
        for dep in deps:
            lines.append(f"  {dep} --> {node}")

    return "\n".join(lines)


def _visit_for_closure(
    node: str,
    graph: dict[str, list[str]],
    visited: set[str],
    stack: set[str],
) -> None:
    if node in stack:
        raise RuntimeError(f"Dependency cycle detected at '{node}'.")
    if node in visited:
        return

    stack.add(node)
    for dep in graph.get(node, []):
        _visit_for_closure(dep, graph, visited, stack)
    stack.remove(node)
    visited.add(node)


def expand_selected_artifacts(
    environment_cfg: EnvironmentConfig,
    selected_logical_names: list[str],
) -> list[ArtifactConfig]:
    graph = build_dependency_graph(environment_cfg)
    selected: set[str] = set()
    for logical_name in selected_logical_names:
        if logical_name not in environment_cfg.items:
            raise RuntimeError(f"Unknown selected artifact logical name: '{logical_name}'")
        _visit_for_closure(logical_name, graph, selected, set())

    return _sort_artifacts_for_deploy([environment_cfg.items[name] for name in selected])


def lint_environment_config(environment_cfg: EnvironmentConfig) -> ValidationResult:
    result = ValidationResult()

    if not environment_cfg.name:
        result.errors.append("Environment name is required.")
    if not environment_cfg.workspace_id:
        result.errors.append("workspace_id is required.")
    if not environment_cfg.capacity_id:
        result.errors.append("capacity_id is required.")
    if not environment_cfg.items:
        result.errors.append("At least one artifact under items is required.")

    for logical_name, artifact in environment_cfg.items.items():
        if artifact.artifact_type not in SUPPORTED_ARTIFACT_TYPES:
            result.errors.append(
                f"Artifact '{logical_name}' uses unsupported type '{artifact.artifact_type}'."
            )
        if not artifact.name:
            result.errors.append(f"Artifact '{logical_name}' must define a non-empty name.")
        if logical_name in artifact.depends_on:
            result.errors.append(f"Artifact '{logical_name}' cannot depend on itself.")
        for dep in artifact.depends_on:
            if dep not in environment_cfg.items:
                result.errors.append(
                    f"Artifact '{logical_name}' depends on unknown artifact '{dep}'."
                )

    graph = build_dependency_graph(environment_cfg)
    seen: set[str] = set()
    for node in graph:
        _visit_for_closure(node, graph, seen, set())

    return result


def apply_enterprise_policy(
    environment_cfg: EnvironmentConfig,
    target_environment_name: str,
    policy,
) -> ValidationResult:
    result = ValidationResult()

    if policy.freeze:
        result.errors.append("Deployment freeze is enabled by enterprise policy.")

    now_hour = datetime.now(timezone.utc).hour
    start = policy.deployment_window.start_hour_utc
    end = policy.deployment_window.end_hour_utc
    if not (start <= now_hour < end):
        result.errors.append(
            f"Current UTC hour {now_hour} is outside allowed deployment window [{start}, {end})."
        )

    if target_environment_name in policy.protected_environments:
        result.warnings.append(
            f"Target '{target_environment_name}' is protected; enforce reviewer approvals in CI environment rules."
        )

    configured_types = {a.artifact_type for a in environment_cfg.items.values()}
    if policy.allowed_artifact_types:
        disallowed = configured_types - set(policy.allowed_artifact_types)
        if disallowed:
            result.errors.append(
                "Disallowed artifact types in configuration: " + ", ".join(sorted(disallowed))
            )

    for req_type in policy.required_artifact_types:
        if req_type not in configured_types:
            result.errors.append(f"Missing required artifact type '{req_type}' in configuration.")

    for logical_name, artifact in environment_cfg.items.items():
        pattern = policy.name_patterns.get(artifact.artifact_type)
        if not pattern:
            continue
        if not re.match(pattern, artifact.name):
            result.errors.append(
                f"Artifact '{logical_name}' ({artifact.artifact_type}) with name '{artifact.name}' does not match policy pattern '{pattern}'."
            )

    return result


def run_preflight_checks(
    client: FabricApiClient,
    source_cfg: EnvironmentConfig,
    target_cfg: EnvironmentConfig,
) -> ValidationResult:
    lint_source = lint_environment_config(source_cfg)
    lint_target = lint_environment_config(target_cfg)

    merged = ValidationResult(
        errors=list(lint_source.errors) + list(lint_target.errors),
        warnings=list(lint_source.warnings) + list(lint_target.warnings),
    )
    if merged.errors:
        return merged

    promote_validation = validate_promotion(client, source_cfg, target_cfg)
    merged.errors.extend(promote_validation.errors)
    merged.warnings.extend(promote_validation.warnings)
    return merged


def write_release_evidence(
    source_cfg: EnvironmentConfig,
    target_cfg: EnvironmentConfig,
    deployed_artifacts: list[ArtifactConfig],
    out_path: str | Path,
) -> None:
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_environment": source_cfg.name,
        "target_environment": target_cfg.name,
        "artifacts": [
            {
                "logical_name": a.logical_name,
                "name": a.name,
                "type": a.artifact_type,
                "target_name": a.target_name or a.name,
            }
            for a in deployed_artifacts
        ],
    }
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def validate_promotion(
    client: FabricApiClient,
    source_cfg: EnvironmentConfig,
    target_cfg: EnvironmentConfig,
) -> ValidationResult:
    result = ValidationResult()

    if source_cfg.workspace_id == target_cfg.workspace_id:
        result.errors.append("Source and target workspace IDs must be different.")

    if not source_cfg.items:
        result.errors.append(f"No artifacts configured for source environment '{source_cfg.name}'.")

    source_items = client.list_workspace_items_flat(source_cfg.workspace_id)
    target_items = client.list_workspace_items_flat(target_cfg.workspace_id)

    source_index = {
        (item.get("displayName"), item.get("type")): item
        for item in source_items
    }
    target_index = {
        (item.get("displayName"), item.get("type")): item
        for item in target_items
    }

    for artifact in source_cfg.items.values():
        key = (artifact.name, artifact.artifact_type)
        source_item = source_index.get(key)
        if artifact.required and not source_item:
            result.errors.append(
                f"Missing required source artifact '{artifact.name}' ({artifact.artifact_type})."
            )
            continue

        if not source_item:
            result.warnings.append(
                f"Optional source artifact '{artifact.name}' ({artifact.artifact_type}) not found and will be skipped."
            )
            continue

        target_name = artifact.target_name or artifact.name
        target_key = (target_name, artifact.artifact_type)
        if target_key not in target_index:
            result.warnings.append(
                f"Target does not yet contain '{target_name}' ({artifact.artifact_type}); copy will create it."
            )

        for dep in artifact.depends_on:
            if dep not in source_cfg.items:
                result.errors.append(
                    f"Artifact '{artifact.logical_name}' depends on unknown logical artifact '{dep}'."
                )

    return result


def _copy_with_handler(
    client: FabricApiClient,
    source_workspace_id: str,
    target_workspace_id: str,
    artifact: ArtifactConfig,
    source_item_id: str,
) -> None:
    # Per-type branch gives us room to add type-specific payloads when APIs diverge.
    if artifact.artifact_type == "VariableLibrary":
        client.copy_item_between_workspaces(
            source_workspace_id,
            target_workspace_id,
            source_item_id,
            target_item_name=artifact.target_name,
        )
        return

    if artifact.artifact_type == "Environment":
        client.copy_item_between_workspaces(
            source_workspace_id,
            target_workspace_id,
            source_item_id,
            target_item_name=artifact.target_name,
        )
        return

    if artifact.artifact_type == "Lakehouse":
        client.copy_item_between_workspaces(
            source_workspace_id,
            target_workspace_id,
            source_item_id,
            target_item_name=artifact.target_name,
        )
        return

    if artifact.artifact_type == "Notebook":
        client.copy_item_between_workspaces(
            source_workspace_id,
            target_workspace_id,
            source_item_id,
            target_item_name=artifact.target_name,
        )
        return

    if artifact.artifact_type == "Pipeline":
        client.copy_item_between_workspaces(
            source_workspace_id,
            target_workspace_id,
            source_item_id,
            target_item_name=artifact.target_name,
        )
        return

    if artifact.artifact_type == "Dataflow":
        client.copy_item_between_workspaces(
            source_workspace_id,
            target_workspace_id,
            source_item_id,
            target_item_name=artifact.target_name,
        )
        return

    if artifact.artifact_type == "CopyJob":
        client.copy_item_between_workspaces(
            source_workspace_id,
            target_workspace_id,
            source_item_id,
            target_item_name=artifact.target_name,
        )
        return

    if artifact.artifact_type == "SemanticModel":
        client.copy_item_between_workspaces(
            source_workspace_id,
            target_workspace_id,
            source_item_id,
            target_item_name=artifact.target_name,
        )
        return

    if artifact.artifact_type == "Report":
        client.copy_item_between_workspaces(
            source_workspace_id,
            target_workspace_id,
            source_item_id,
            target_item_name=artifact.target_name,
        )
        return

    raise RuntimeError(f"Unsupported artifact type: {artifact.artifact_type}")


def promote_with_validation(
    client: FabricApiClient,
    source_cfg: EnvironmentConfig,
    target_cfg: EnvironmentConfig,
    rollback_manifest_path: str | Path,
    selected_logical_names: list[str] | None = None,
) -> None:
    validation = run_preflight_checks(client, source_cfg, target_cfg)
    for warning in validation.warnings:
        print(f"[WARN] {warning}")
    validation.ensure_valid()

    manifest_entries: list[RollbackEntry] = []
    if selected_logical_names:
        artifacts = expand_selected_artifacts(source_cfg, selected_logical_names)
    else:
        artifacts = _sort_artifacts_for_deploy(list(source_cfg.items.values()))

    if not target_cfg.backup_workspace_id:
        raise RuntimeError(
            f"Target environment '{target_cfg.name}' must define backup_workspace_id for rollback support."
        )

    for artifact in artifacts:
        source_item = client.resolve_item_by_name_and_type(
            source_cfg.workspace_id,
            artifact.name,
            artifact.artifact_type,
        )
        if not source_item:
            if artifact.required:
                raise RuntimeError(
                    f"Required source artifact '{artifact.name}' ({artifact.artifact_type}) not found."
                )
            print(
                f"[WARN] Skipping optional missing source artifact '{artifact.name}' ({artifact.artifact_type})."
            )
            continue

        target_name = artifact.target_name or artifact.name
        target_item = client.resolve_item_by_name_and_type(
            target_cfg.workspace_id,
            target_name,
            artifact.artifact_type,
        )
        if target_item:
            backup_result = client.copy_item_between_workspaces(
                source_workspace_id=target_cfg.workspace_id,
                target_workspace_id=target_cfg.backup_workspace_id,
                item_id=target_item["id"],
            )
            backup_item_id = backup_result.get("id", "")
            if not backup_item_id:
                print(
                    f"[WARN] Backup copy for '{target_name}' did not return a new item id. Rollback may be limited."
                )
            manifest_entries.append(
                RollbackEntry(
                    logical_name=artifact.logical_name,
                    target_name=target_name,
                    artifact_type=artifact.artifact_type,
                    backup_workspace_id=target_cfg.backup_workspace_id,
                    backup_item_id=backup_item_id,
                )
            )

        _copy_with_handler(
            client,
            source_cfg.workspace_id,
            target_cfg.workspace_id,
            artifact,
            source_item["id"],
        )
        print(
            f"Promoted '{artifact.name}' ({artifact.artifact_type}) from {source_cfg.name} to {target_cfg.name}"
        )

    rollback_path = Path(rollback_manifest_path)
    rollback_path.parent.mkdir(parents=True, exist_ok=True)
    rollback_payload = [entry.__dict__ for entry in manifest_entries]
    rollback_path.write_text(json.dumps(rollback_payload, indent=2), encoding="utf-8")
    print(f"Rollback manifest written to {rollback_path}")

    evidence_path = (
        Path("artifacts")
        / "releases"
        / f"{source_cfg.name}-to-{target_cfg.name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    write_release_evidence(source_cfg, target_cfg, artifacts, evidence_path)
    print(f"Release evidence written to {evidence_path}")


def run_rollback(
    client: FabricApiClient,
    target_cfg: EnvironmentConfig,
    rollback_manifest_path: str | Path,
) -> None:
    manifest_path = Path(rollback_manifest_path)
    if not manifest_path.exists():
        raise RuntimeError(f"Rollback manifest not found: {manifest_path}")

    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in entries:
        backup_item_id = entry.get("backup_item_id")
        if not backup_item_id:
            print(
                f"[WARN] Skipping rollback for '{entry.get('target_name')}' due to missing backup_item_id."
            )
            continue

        client.copy_item_between_workspaces(
            source_workspace_id=entry["backup_workspace_id"],
            target_workspace_id=target_cfg.workspace_id,
            item_id=backup_item_id,
            target_item_name=entry.get("target_name"),
        )
        print(
            f"Rolled back '{entry.get('target_name')}' ({entry.get('artifact_type')}) into {target_cfg.name}"
        )
