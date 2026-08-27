from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class AssetStorageConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredAsset:
    object_key: str
    uri: str
    content_type: str
    size_bytes: int


class AssetStorage(Protocol):
    def put_bytes(self, *, owner_id: int, namespace: str, filename: str, content: bytes, content_type: str) -> StoredAsset:
        """Store an owner-scoped immutable object and return its stable storage identity."""

    def signed_read_url(self, *, owner_id: int, object_key: str, expires_seconds: int = 300) -> str:
        """Return short-lived read access after caller ownership has been checked by the workflow layer."""

    def delete_owner_prefix(self, *, owner_id: int, namespace: str) -> int:
        """Delete objects for a retention/deletion workflow; caller records audit evidence separately."""


class LocalAssetStorage:
    """Local demo adapter. URIs remain mounted static paths and are never presented as signed production links."""

    def __init__(self, root: Path, public_prefix: str = "/uploads"):
        self.root = root
        self.public_prefix = public_prefix.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _key(self, owner_id: int, namespace: str, filename: str) -> str:
        suffix = Path(filename).suffix.lower() or ".bin"
        return f"owners/{owner_id}/{namespace}/{uuid4().hex}{suffix}"

    def put_bytes(self, *, owner_id: int, namespace: str, filename: str, content: bytes, content_type: str) -> StoredAsset:
        key = self._key(owner_id, namespace, filename)
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return StoredAsset(key, f"{self.public_prefix}/{key}", content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream", len(content))

    def signed_read_url(self, *, owner_id: int, object_key: str, expires_seconds: int = 300) -> str:
        expected = f"owners/{owner_id}/"
        if not object_key.startswith(expected):
            raise PermissionError("Owner may not read another owner's local asset")
        return f"{self.public_prefix}/{object_key}"

    def delete_owner_prefix(self, *, owner_id: int, namespace: str) -> int:
        target = self.root / "owners" / str(owner_id) / namespace
        if not target.exists():
            return 0
        files = [path for path in target.rglob("*") if path.is_file()]
        for path in files:
            path.unlink()
        for path in sorted((path for path in target.rglob("*") if path.is_dir()), reverse=True):
            path.rmdir()
        target.rmdir()
        return len(files)


class S3CompatibleAssetStorage:
    """Optional production adapter. Import boto3 lazily so local demo never requires provider credentials."""

    def __init__(self, *, bucket: str, endpoint_url: str | None, region_name: str | None, key_prefix: str = "ai-stylist"):
        try:
            import boto3
        except ImportError as error:
            raise AssetStorageConfigurationError("Install boto3 to enable AI_STYLIST_STORAGE_BACKEND=s3") from error
        self.bucket = bucket
        self.key_prefix = key_prefix.strip("/")
        self.client = boto3.client("s3", endpoint_url=endpoint_url, region_name=region_name)

    def _key(self, owner_id: int, namespace: str, filename: str) -> str:
        suffix = Path(filename).suffix.lower() or ".bin"
        return f"{self.key_prefix}/owners/{owner_id}/{namespace}/{uuid4().hex}{suffix}"

    def put_bytes(self, *, owner_id: int, namespace: str, filename: str, content: bytes, content_type: str) -> StoredAsset:
        key = self._key(owner_id, namespace, filename)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type or "application/octet-stream", Metadata={"owner_id": str(owner_id), "namespace": namespace})
        return StoredAsset(key, f"s3://{self.bucket}/{key}", content_type or "application/octet-stream", len(content))

    def signed_read_url(self, *, owner_id: int, object_key: str, expires_seconds: int = 300) -> str:
        expected = f"{self.key_prefix}/owners/{owner_id}/"
        if not object_key.startswith(expected):
            raise PermissionError("Owner may not read another owner's object")
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": object_key}, ExpiresIn=expires_seconds)

    def delete_owner_prefix(self, *, owner_id: int, namespace: str) -> int:
        prefix = f"{self.key_prefix}/owners/{owner_id}/{namespace}/"
        deleted = 0
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if objects:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects, "Quiet": True})
                deleted += len(objects)
        return deleted


def storage_from_environment(upload_root: Path) -> AssetStorage:
    backend = os.getenv("AI_STYLIST_STORAGE_BACKEND", "local").strip().lower()
    if backend == "local":
        return LocalAssetStorage(upload_root)
    if backend != "s3":
        raise AssetStorageConfigurationError("AI_STYLIST_STORAGE_BACKEND must be local or s3")
    bucket = os.getenv("AI_STYLIST_S3_BUCKET", "").strip()
    if not bucket:
        raise AssetStorageConfigurationError("AI_STYLIST_S3_BUCKET is required for S3-compatible storage")
    return S3CompatibleAssetStorage(
        bucket=bucket,
        endpoint_url=os.getenv("AI_STYLIST_S3_ENDPOINT_URL") or None,
        region_name=os.getenv("AI_STYLIST_S3_REGION") or None,
        key_prefix=os.getenv("AI_STYLIST_S3_KEY_PREFIX", "ai-stylist"),
    )
