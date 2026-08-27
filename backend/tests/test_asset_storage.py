from pathlib import Path

import pytest

from app.services.asset_storage import LocalAssetStorage


def test_local_asset_storage_scopes_read_and_deletion_by_owner(tmp_path: Path):
    storage = LocalAssetStorage(tmp_path)
    stored = storage.put_bytes(
        owner_id=41,
        namespace="garments",
        filename="shirt.png",
        content=b"image-data",
        content_type="image/png",
    )
    assert stored.object_key.startswith("owners/41/garments/")
    assert stored.uri.startswith("/uploads/owners/41/garments/")
    assert storage.signed_read_url(owner_id=41, object_key=stored.object_key) == stored.uri
    with pytest.raises(PermissionError):
        storage.signed_read_url(owner_id=42, object_key=stored.object_key)
    assert storage.delete_owner_prefix(owner_id=41, namespace="garments") == 1
    assert not (tmp_path / stored.object_key).exists()
