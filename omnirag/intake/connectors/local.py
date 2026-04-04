"""Local filesystem connector."""

from __future__ import annotations

import glob
import os
from typing import AsyncIterator

from omnirag.intake.connectors.base import BaseConnector
from omnirag.intake.models import RawContent


class LocalConnector(BaseConnector):
    """Fetches files from local filesystem, mounted drives, network shares."""

    name = "local"

    def supports(self, source: str) -> bool:
        if source.startswith("file://"):
            return True
        if source.startswith("/") or source.startswith("./") or source.startswith("~"):
            return True
        # Windows paths
        if len(source) > 2 and source[1] == ":":
            return True
        return False

    async def fetch(self, source: str, config: dict) -> AsyncIterator[RawContent]:
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
            return

        count = 0
        for fpath in files:
            if count >= max_files:
                break
            if not os.path.isfile(fpath):
                continue

            size = os.path.getsize(fpath)
            if size > max_size:
                continue
            if size == 0:
                continue

            try:
                with open(fpath, "rb") as f:
                    data = f.read()
            except (OSError, PermissionError):
                continue

            yield RawContent(
                data=data,
                source_uri=f"file://{os.path.abspath(fpath)}",
                filename=os.path.basename(fpath),
                metadata={"path": os.path.abspath(fpath), "size": size},
            )
            count += 1
