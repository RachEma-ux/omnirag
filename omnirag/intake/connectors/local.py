"""Local filesystem connector — upgraded to 7-method interface."""

from __future__ import annotations

import glob
import hashlib
import os
from typing import AsyncIterator

from omnirag.intake.connectors.base import BaseConnector
from omnirag.intake.models import ACL, ObjectKind, RawContent, SourceObject, Visibility


class LocalConnector(BaseConnector):
    """Fetches files from local filesystem, mounted drives, network shares."""

    name = "local"

    def supports(self, source: str) -> bool:
        if source.startswith("file://"):
            return True
        if source.startswith("/") or source.startswith("./") or source.startswith("~"):
            return True
        if len(source) > 2 and source[1] == ":":
            return True
        return False

    async def discover(self, source: str, config: dict, cursor: str | None = None) -> list[SourceObject]:
        path = source.removeprefix("file://")
        path = os.path.expanduser(path)
        recursive = config.get("recursive", True)
        max_files = config.get("max_files", 10000)
        max_size = config.get("max_size_mb", 100) * 1024 * 1024

        if os.path.isfile(path):
            files = [path]
        elif "*" in path or "?" in path:
            files = sorted(glob.glob(path, recursive=recursive))
        elif os.path.isdir(path):
            files = []
            for root, _, filenames in os.walk(path):
                for fname in sorted(filenames):
                    files.append(os.path.join(root, fname))
                if not recursive:
                    break
        else:
            return []

        objects: list[SourceObject] = []
        for fpath in files[:max_files]:
            if not os.path.isfile(fpath):
                continue
            size = os.path.getsize(fpath)
            if size == 0 or size > max_size:
                continue

            stat = os.stat(fpath)
            abs_path = os.path.abspath(fpath)
            objects.append(SourceObject(
                connector_id=self.name,
                external_id=abs_path,
                object_kind=ObjectKind.BLOB,
                source_url=f"file://{abs_path}",
                checksum=None,  # computed on fetch
                timestamps={
                    "created_at": str(stat.st_ctime),
                    "updated_at": str(stat.st_mtime),
                    "discovered_at": str(os.times().elapsed if hasattr(os.times(), 'elapsed') else 0),
                },
                metadata={"path": abs_path, "size": size, "filename": os.path.basename(fpath)},
            ))
        return objects

    async def fetch(self, source_object: SourceObject, config: dict) -> RawContent | None:
        path = source_object.external_id
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "rb") as f:
                data = f.read()
        except (OSError, PermissionError):
            return None

        source_object.checksum = hashlib.sha256(data).hexdigest()
        return RawContent(
            data=data,
            source_uri=f"file://{path}",
            filename=os.path.basename(path),
            metadata=source_object.metadata,
        )

    async def fetch_batch(self, source: str, config: dict) -> AsyncIterator[RawContent]:
        objects = await self.discover(source, config)
        for obj in objects:
            raw = await self.fetch(obj, config)
            if raw:
                yield raw

    async def permissions(self, source_object: SourceObject, config: dict) -> ACL:
        return ACL(visibility=Visibility.TENANT)

    async def version(self, source_object: SourceObject, config: dict) -> str | None:
        path = source_object.external_id
        if os.path.isfile(path):
            return str(os.path.getmtime(path))
        return None
