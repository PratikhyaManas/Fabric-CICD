from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from azure.identity import AzureCliCredential
from fabric_cicd import (
    FabricWorkspace,
    append_feature_flag,
    change_log_level,
    publish_all_items,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy Fabric workspace items via fabric-cicd")
    parser.add_argument("--workspace_id", required=True, type=str)
    parser.add_argument("--environment", required=True, type=str)
    parser.add_argument("--repository_directory", required=True, type=str)
    parser.add_argument("--item_type_in_scope", required=True, type=str)
    return parser.parse_args()


def main() -> None:
    sys.stdout.reconfigure(line_buffering=True, write_through=True)
    sys.stderr.reconfigure(line_buffering=True, write_through=True)

    if os.getenv("SYSTEM_DEBUG", "false").lower() == "true":
        change_log_level("DEBUG")

    append_feature_flag("enable_shortcut_publish")

    args = parse_args()
    repository_directory = Path(args.repository_directory)
    if not repository_directory.exists():
        raise RuntimeError(f"Repository directory not found: {repository_directory}")

    token_credential = AzureCliCredential()
    workspace = FabricWorkspace(
        workspace_id=args.workspace_id,
        environment=args.environment,
        repository_directory=str(repository_directory),
        item_type_in_scope=[x.strip() for x in args.item_type_in_scope.split(",") if x.strip()],
        token_credential=token_credential,
    )

    publish_all_items(workspace)


if __name__ == "__main__":
    main()
