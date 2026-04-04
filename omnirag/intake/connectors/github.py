"""GitHub connector — repos, files, issues, PRs."""

from __future__ import annotations

import base64
from typing import AsyncIterator

from omnirag.intake.connectors.base import BaseConnector
from omnirag.intake.models import RawContent


class GitHubConnector(BaseConnector):
    """Fetches files from GitHub repositories."""

    name = "github"

    def supports(self, source: str) -> bool:
        return source.startswith("github://")

    async def fetch(self, source: str, config: dict) -> AsyncIterator[RawContent]:
        import httpx

        path = source.removeprefix("github://")
        parts = path.split("/")
        if len(parts) < 2:
            return

        owner, repo = parts[0], parts[1]
        sub_path = "/".join(parts[2:]) if len(parts) > 2 else ""
        branch = config.get("branch", "main")
        token = config.get("token") or config.get("credentials", {}).get("token")
        max_files = config.get("max_files", 500)

        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            # Get tree recursively
            url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            resp = await client.get(url)
            resp.raise_for_status()
            tree = resp.json().get("tree", [])

            count = 0
            for item in tree:
                if count >= max_files:
                    break
                if item["type"] != "blob":
                    continue
                if sub_path and not item["path"].startswith(sub_path):
                    continue
                if item.get("size", 0) > 10 * 1024 * 1024:  # 10MB limit
                    continue

                # Fetch file content
                file_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{item['path']}?ref={branch}"
                file_resp = await client.get(file_url)
                if file_resp.status_code != 200:
                    continue

                file_data = file_resp.json()
                content = file_data.get("content", "")
                encoding = file_data.get("encoding", "")

                if encoding == "base64":
                    data = base64.b64decode(content)
                else:
                    data = content.encode()

                filename = item["path"].rsplit("/", 1)[-1]

                yield RawContent(
                    data=data,
                    source_uri=f"github://{owner}/{repo}/{item['path']}",
                    filename=filename,
                    metadata={
                        "repo": f"{owner}/{repo}",
                        "path": item["path"],
                        "sha": item.get("sha"),
                        "branch": branch,
                    },
                )
                count += 1
