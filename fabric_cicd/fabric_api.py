from __future__ import annotations

import json
from pathlib import Path

import requests

from fabric_cicd.models import ArtifactType, FabricAuth

FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"
AAD_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
SCOPE = "https://api.fabric.microsoft.com/.default"


class FabricApiClient:
    def __init__(self, auth: FabricAuth) -> None:
        self.auth = auth
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
            }
        )
        self._set_access_token()

    def _set_access_token(self) -> None:
        token_url = AAD_TOKEN_URL.format(tenant_id=self.auth.tenant_id)
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.auth.client_id,
            "client_secret": self.auth.client_secret,
            "scope": SCOPE,
        }
        response = requests.post(token_url, data=payload, timeout=30)
        response.raise_for_status()
        access_token = response.json()["access_token"]
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def list_workspace_items(self, workspace_id: str) -> dict:
        response = self.session.get(f"{FABRIC_API_BASE}/workspaces/{workspace_id}/items", timeout=60)
        response.raise_for_status()
        return response.json()

    def list_workspace_items_flat(self, workspace_id: str) -> list[dict]:
        return self.list_workspace_items(workspace_id).get("value", [])

    def export_workspace_items(self, workspace_id: str, out_dir: str | Path) -> None:
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        items = self.list_workspace_items(workspace_id)
        (out_path / "items.json").write_text(
            json.dumps(items, indent=2),
            encoding="utf-8",
        )

    def resolve_item_id_by_name(self, workspace_id: str, item_name: str) -> str | None:
        payload = self.list_workspace_items(workspace_id)
        for item in payload.get("value", []):
            if item.get("displayName") == item_name:
                return item.get("id")
        return None

    def resolve_item_by_name_and_type(
        self,
        workspace_id: str,
        item_name: str,
        artifact_type: ArtifactType,
    ) -> dict | None:
        for item in self.list_workspace_items_flat(workspace_id):
            if item.get("displayName") == item_name and item.get("type") == artifact_type:
                return item
        return None

    def copy_item_between_workspaces(
        self,
        source_workspace_id: str,
        target_workspace_id: str,
        item_id: str,
        target_item_name: str | None = None,
    ) -> dict:
        url = f"{FABRIC_API_BASE}/workspaces/{source_workspace_id}/items/{item_id}/copy"
        body = {
            "targetWorkspaceId": target_workspace_id,
        }
        if target_item_name:
            body["targetItemDisplayName"] = target_item_name
        response = self.session.post(url, data=json.dumps(body), timeout=120)
        response.raise_for_status()
        return response.json() if response.content else {}
