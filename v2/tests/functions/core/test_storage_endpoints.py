"""Pillar: Stable Core / Phase: 6 — tests for functions/core/storage_endpoints.py."""

import pytest

from backend.core.settings import StorageSettings
from functions.core.storage_endpoints import resolve_storage_endpoints


def test_derives_public_cloud_urls_from_account_name() -> None:
    storage = StorageSettings(storage_account_name="stcwyddev")
    blob, queue = resolve_storage_endpoints(storage)
    assert blob == "https://stcwyddev.blob.core.windows.net"
    assert queue == "https://stcwyddev.queue.core.windows.net"


def test_explicit_blob_endpoint_overrides_account_name() -> None:
    storage = StorageSettings(
        storage_account_name="stignored",
        storage_blob_endpoint="https://stcwyd.blob.core.usgovcloudapi.net",
    )
    blob, queue = resolve_storage_endpoints(storage)
    assert blob == "https://stcwyd.blob.core.usgovcloudapi.net"
    assert queue == "https://stcwyd.queue.core.usgovcloudapi.net"


def test_sovereign_cloud_queue_endpoint_preserves_suffix() -> None:
    storage = StorageSettings(
        storage_blob_endpoint="https://stcwyd.blob.core.chinacloudapi.cn",
    )
    _, queue = resolve_storage_endpoints(storage)
    assert queue == "https://stcwyd.queue.core.chinacloudapi.cn"


def test_only_first_blob_segment_swapped_to_queue() -> None:
    # Container or path segments that contain ".blob." must not be touched
    # (very unlikely in practice, but the replace count guards against it).
    storage = StorageSettings(
        storage_blob_endpoint="https://acct.blob.core.windows.net",
    )
    blob, queue = resolve_storage_endpoints(storage)
    assert blob.count(".queue.") == 0
    assert queue.count(".blob.") == 0
    assert queue.count(".queue.") == 1


def test_empty_settings_raises_value_error() -> None:
    storage = StorageSettings()  # both fields default to ""
    with pytest.raises(ValueError, match="Cannot resolve storage endpoints"):
        resolve_storage_endpoints(storage)
