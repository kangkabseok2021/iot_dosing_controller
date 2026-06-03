"""Azure Blob Storage adapter for Fahrplan archival."""

from __future__ import annotations

from typing import Protocol

from app.models.schemas import Fahrplan


class BlobStore(Protocol):
    async def archive(self, fahrplan: Fahrplan) -> str: ...


class AzureBlobStore:
    """Archives Fahrplan JSON to Azure Blob Storage."""

    def __init__(self, connection_string: str, container: str) -> None:
        from azure.storage.blob.aio import (
            BlobServiceClient,  # type: ignore[import-untyped,unused-ignore]
        )

        self._client: BlobServiceClient = BlobServiceClient.from_connection_string(
            connection_string
        )
        self._container = container

    async def archive(self, fahrplan: Fahrplan) -> str:
        key = f"{fahrplan.portfolio_id}/{fahrplan.date}/{fahrplan.schedule_id}.json"
        blob_client = self._client.get_blob_client(self._container, key)
        await blob_client.upload_blob(fahrplan.model_dump_json(), overwrite=True)
        return key


class NullBlobStore:
    """No-op blob store used when Azure credentials are absent."""

    async def archive(self, fahrplan: Fahrplan) -> str:
        return f"null/{fahrplan.portfolio_id}/{fahrplan.date}/{fahrplan.schedule_id}.json"


def get_blob_store() -> BlobStore:
    from app.config import settings

    if settings.azure_storage_connection_string:
        return AzureBlobStore(
            settings.azure_storage_connection_string,
            settings.azure_storage_container,
        )
    return NullBlobStore()
