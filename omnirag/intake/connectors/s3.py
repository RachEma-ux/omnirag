"""AWS S3 / MinIO connector — upgraded to 7-method interface."""

from __future__ import annotations

import hashlib
from typing import AsyncIterator

from omnirag.intake.connectors.base import BaseConnector
from omnirag.intake.models import ObjectKind, RawContent, SourceObject


class S3Connector(BaseConnector):
    name = "s3"

    def supports(self, source: str) -> bool:
        return source.startswith("s3://")

    async def discover(self, source: str, config: dict, cursor: str | None = None) -> list[SourceObject]:
        try:
            import boto3
        except ImportError:
            raise ImportError("Install boto3: pip install omnirag[intake-cloud]")

        path = source.removeprefix("s3://")
        bucket = path.split("/", 1)[0]
        prefix = path.split("/", 1)[1] if "/" in path else ""
        max_files = config.get("max_files", 1000)
        max_size = config.get("max_size_mb", 100) * 1024 * 1024

        client_kwargs = self._build_client_kwargs(config)
        s3 = boto3.client("s3", **client_kwargs)
        paginator = s3.get_paginator("list_objects_v2")

        objects = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if len(objects) >= max_files:
                    break
                key = obj["Key"]
                size = obj["Size"]
                if size == 0 or size > max_size or key.endswith("/"):
                    continue
                objects.append(SourceObject(
                    connector_id=self.name,
                    external_id=f"s3://{bucket}/{key}",
                    object_kind=ObjectKind.BLOB,
                    source_url=f"s3://{bucket}/{key}",
                    metadata={"bucket": bucket, "key": key, "size": size,
                              "filename": key.rsplit("/", 1)[-1]},
                ))
        return objects

    async def fetch(self, source_object: SourceObject, config: dict) -> RawContent | None:
        try:
            import boto3
        except ImportError:
            return None

        meta = source_object.metadata
        bucket = meta.get("bucket", "")
        key = meta.get("key", "")
        if not bucket or not key:
            return None

        client_kwargs = self._build_client_kwargs(config)
        s3 = boto3.client("s3", **client_kwargs)

        response = s3.get_object(Bucket=bucket, Key=key)
        data = response["Body"].read()

        source_object.checksum = hashlib.sha256(data).hexdigest()

        return RawContent(
            data=data,
            source_uri=source_object.external_id,
            filename=meta.get("filename", key.rsplit("/", 1)[-1]),
            mime_type=response.get("ContentType"),
            metadata=meta,
        )

    @staticmethod
    def _build_client_kwargs(config: dict) -> dict:
        kwargs: dict = {}
        if "endpoint_url" in config:
            kwargs["endpoint_url"] = config["endpoint_url"]
        creds = config.get("credentials", {})
        if "aws_access_key" in creds:
            kwargs["aws_access_key_id"] = creds["aws_access_key"]
            kwargs["aws_secret_access_key"] = creds["aws_secret_key"]
        if "region" in config:
            kwargs["region_name"] = config["region"]
        return kwargs
