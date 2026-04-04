"""AWS S3 / MinIO connector."""

from __future__ import annotations

import os
from typing import AsyncIterator

from omnirag.intake.connectors.base import BaseConnector
from omnirag.intake.models import RawContent


class S3Connector(BaseConnector):
    """Fetches files from S3-compatible storage (AWS S3, MinIO)."""

    name = "s3"

    def supports(self, source: str) -> bool:
        return source.startswith("s3://")

    async def fetch(self, source: str, config: dict) -> AsyncIterator[RawContent]:
        try:
            import boto3
        except ImportError:
            raise ImportError("Install boto3: pip install omnirag[intake-cloud]")

        path = source.removeprefix("s3://")
        bucket = path.split("/", 1)[0]
        prefix = path.split("/", 1)[1] if "/" in path else ""
        max_files = config.get("max_files", 1000)
        max_size = config.get("max_size_mb", 100) * 1024 * 1024

        client_kwargs: dict = {}
        if "endpoint_url" in config:
            client_kwargs["endpoint_url"] = config["endpoint_url"]
        credentials = config.get("credentials", {})
        if "aws_access_key" in credentials:
            client_kwargs["aws_access_key_id"] = credentials["aws_access_key"]
            client_kwargs["aws_secret_access_key"] = credentials["aws_secret_key"]
        if "region" in config:
            client_kwargs["region_name"] = config["region"]

        s3 = boto3.client("s3", **client_kwargs)
        paginator = s3.get_paginator("list_objects_v2")

        count = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if count >= max_files:
                    return
                key = obj["Key"]
                size = obj["Size"]
                if size == 0 or size > max_size:
                    continue
                if key.endswith("/"):
                    continue

                response = s3.get_object(Bucket=bucket, Key=key)
                data = response["Body"].read()
                filename = key.rsplit("/", 1)[-1]

                yield RawContent(
                    data=data,
                    source_uri=f"s3://{bucket}/{key}",
                    filename=filename,
                    mime_type=response.get("ContentType"),
                    metadata={"bucket": bucket, "key": key, "size": size},
                )
                count += 1
