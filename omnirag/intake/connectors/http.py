"""HTTP/HTTPS connector — upgraded to 7-method interface."""

from __future__ import annotations

import hashlib
import urllib.parse
from typing import AsyncIterator

from omnirag.intake.connectors.base import BaseConnector
from omnirag.intake.models import ObjectKind, RawContent, SourceObject


class HttpConnector(BaseConnector):
    """Fetches content from HTTP/HTTPS URLs."""

    name = "http"

    def supports(self, source: str) -> bool:
        return source.startswith("http://") or source.startswith("https://")

    async def discover(self, source: str, config: dict, cursor: str | None = None) -> list[SourceObject]:
        parsed = urllib.parse.urlparse(source)
        filename = parsed.path.rsplit("/", 1)[-1] or "index.html"
        return [SourceObject(
            connector_id=self.name,
            external_id=source,
            object_kind=ObjectKind.BLOB,
            source_url=source,
            metadata={"filename": filename, "url": source},
        )]

    async def fetch(self, source_object: SourceObject, config: dict) -> RawContent | None:
        import httpx

        source = source_object.source_url or source_object.external_id
        headers = config.get("headers", {})
        auth = config.get("auth")
        timeout = config.get("timeout", 30)
        max_size = config.get("max_size_mb", 50) * 1024 * 1024

        if auth:
            auth_type = auth.get("type", "bearer")
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {auth['token']}"
            elif auth_type == "basic":
                import base64
                cred = base64.b64encode(f"{auth['username']}:{auth['password']}".encode()).decode()
                headers["Authorization"] = f"Basic {cred}"
            elif auth_type == "api_key":
                headers[auth.get("header", "X-API-Key")] = auth["key"]

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(source, headers=headers)
            response.raise_for_status()

            data = response.content
            if len(data) > max_size:
                return None

            content_type = response.headers.get("content-type", "")
            parsed = urllib.parse.urlparse(source)
            filename = parsed.path.rsplit("/", 1)[-1] or "index.html"

            source_object.checksum = hashlib.sha256(data).hexdigest()
            source_object.mime_type = content_type.split(";")[0].strip()

            return RawContent(
                data=data,
                source_uri=source,
                filename=filename,
                mime_type=content_type.split(";")[0].strip(),
                metadata={"url": source, "status_code": response.status_code, "content_type": content_type},
            )
