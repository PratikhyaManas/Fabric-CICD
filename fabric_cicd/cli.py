from __future__ import annotations

import argparse
import os

from fabric_cicd.commands import (
    export_workspace,
    graph,
    lint_config,
    preflight,
    promote_items,
    rollback_items,
    validate_only,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Code-first CI/CD utilities for Microsoft Fabric")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--tenant-id", default=os.getenv("FABRIC_TENANT_ID"), required=False)
    common.add_argument("--client-id", default=os.getenv("FABRIC_CLIENT_ID"), required=False)
    common.add_argument("--client-secret", default=os.getenv("FABRIC_CLIENT_SECRET"), required=False)

    export_p = sub.add_parser("export", parents=[common], help="Export workspace metadata")
    export_p.add_argument("--env-config", required=True, help="Path to environment YAML")
    export_p.add_argument("--out-dir", default="artifacts/exported", help="Export output directory")

    promote_p = sub.add_parser("promote", parents=[common], help="Promote items between environments")
    promote_p.add_argument("--source-config", required=True, help="Path to source environment YAML")
    promote_p.add_argument("--target-config", required=True, help="Path to target environment YAML")
    promote_p.add_argument(
        "--only",
        nargs="+",
        help="Optional list of artifact logical names to deploy (dependencies included automatically)",
    )

    validate_p = sub.add_parser("validate", parents=[common], help="Run validation checks only")
    validate_p.add_argument("--source-config", required=True, help="Path to source environment YAML")
    validate_p.add_argument("--target-config", required=True, help="Path to target environment YAML")

    rollback_p = sub.add_parser("rollback", parents=[common], help="Rollback target using manifest")
    rollback_p.add_argument("--target-config", required=True, help="Path to target environment YAML")
    rollback_p.add_argument("--manifest", required=True, help="Rollback manifest JSON file")

    lint_p = sub.add_parser("lint-config", help="Lint an environment configuration YAML")
    lint_p.add_argument("--env-config", required=True, help="Path to environment YAML")

    graph_p = sub.add_parser("graph", help="Render artifact dependency graph")
    graph_p.add_argument("--env-config", required=True, help="Path to environment YAML")
    graph_p.add_argument(
        "--format",
        choices=["json", "mermaid"],
        default="mermaid",
        help="Graph output format",
    )

    preflight_p = sub.add_parser("preflight", parents=[common], help="Run lint + remote validation checks")
    preflight_p.add_argument("--source-config", required=True, help="Path to source environment YAML")
    preflight_p.add_argument("--target-config", required=True, help="Path to target environment YAML")

    return parser


def _validate_auth(args: argparse.Namespace) -> None:
    missing = []
    if not args.tenant_id:
        missing.append("FABRIC_TENANT_ID / --tenant-id")
    if not args.client_id:
        missing.append("FABRIC_CLIENT_ID / --client-id")
    if not args.client_secret:
        missing.append("FABRIC_CLIENT_SECRET / --client-secret")

    if missing:
        raise SystemExit(f"Missing required auth values: {', '.join(missing)}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in {"export", "promote", "validate", "rollback", "preflight"}:
        _validate_auth(args)

    if args.command == "export":
        export_workspace(
            env_config_file=args.env_config,
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
            out_dir=args.out_dir,
        )
    elif args.command == "promote":
        promote_items(
            source_env_config_file=args.source_config,
            target_env_config_file=args.target_config,
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
            selected_logical_names=args.only,
        )
    elif args.command == "validate":
        validate_only(
            source_env_config_file=args.source_config,
            target_env_config_file=args.target_config,
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
        )
    elif args.command == "rollback":
        rollback_items(
            target_env_config_file=args.target_config,
            rollback_manifest_path=args.manifest,
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
        )
    elif args.command == "lint-config":
        lint_config(
            env_config_file=args.env_config,
        )
    elif args.command == "graph":
        graph(
            env_config_file=args.env_config,
            format_name=args.format,
        )
    elif args.command == "preflight":
        preflight(
            source_env_config_file=args.source_config,
            target_env_config_file=args.target_config,
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
        )


if __name__ == "__main__":
    main()
