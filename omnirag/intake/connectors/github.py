"""GitHub connector — upgraded to 7-method interface."""

from __future__ import annotations

import base64
import hashlib

from omnirag.intake.connectors.base import BaseConnector
from omnirag.intake.models import ObjectKind, RawContent, SourceObject


class GitHubConnector(BaseConnector):
    name = "github"

    def supports(self, source: str) -> bool:
        return source.startswith("github://")

    async def discover(self, source: str, config: dict, cursor: str | None = None) -> list[SourceObject]:
        import httpx

        path = source.removeprefix("github://")
        parts = path.split("/")
        if len(parts) < 2:
            return []

        owner, repo = parts[0], parts[1]
        sub_path = "/".join(parts[2:]) if len(parts) > 2 else ""
        branch = config.get("branch", "main")
        token = config.get("token") or config.get("credentials", {}).get("token")
        max_files = config.get("max_files", 500)

        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            resp = await client.get(url)
            resp.raise_for_status()
            tree = resp.json().get("tree", [])

        objects = []
        for item in tree:
            if len(objects) >= max_files:
                break
            if item["type"] != "blob":
                continue
            if sub_path and not item["path"].startswith(sub_path):
                continue
            if item.get("size", 0) > 10 * 1024 * 1024:
                continue

            objects.append(SourceObject(
                connector_id=self.name,
                external_id=f"github://{owner}/{repo}/{item['path']}",
                object_kind=ObjectKind.BLOB,
                source_url=f"github://{owner}/{repo}/{item['path']}",
                metadata={
                    "repo": f"{owner}/{repo}", "path": item["path"],
                    "sha": item.get("sha"), "branch": branch,
                    "filename": item["path"].rsplit("/", 1)[-1],
                },
            ))
        return objects

    async def fetch(self, source_object: SourceObject, config: dict) -> RawContent | None:
        import httpx

        meta = source_object.metadata
        repo = meta.get("repo", "")
        path = meta.get("path", "")
        branch = meta.get("branch", "main")
        token = config.get("token") or config.get("credentials", {}).get("token")

        if not repo or not path:
            return None

        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
            resp = await client.get(url)
            if resp.status_code != 200:
                return None

            file_data = resp.json()
            content = file_data.get("content", "")
            encoding = file_data.get("encoding", "")
            data = base64.b64decode(content) if encoding == "base64" else content.encode()

        source_object.checksum = hashlib.sha256(data).hexdigest()

        return RawContent(
            data=data,
            source_uri=source_object.external_id,
            filename=meta.get("filename", path.rsplit("/", 1)[-1]),
            metadata=meta,
        )
