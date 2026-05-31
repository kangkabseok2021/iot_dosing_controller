"""S3 archival for raw sensor event JSON.

Uses boto3 (sync) wrapped in asyncio.to_thread — avoids the aioboto3 dependency
while remaining non-blocking on the event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

import boto3

from app.config import settings

logger = logging.getLogger(__name__)


class S3Archiver:
    def __init__(
        self,
        bucket: str = settings.s3_bucket,
        region: str = settings.aws_region,
    ) -> None:
        self.bucket = bucket
        self.region = region

    def _s3_key(self, plant_id: str, event_id: str) -> str:
        today = date.today().isoformat()
        return f"events/{today}/{plant_id}/{event_id}.json"

    async def archive(self, event_id: str, plant_id: str, payload: dict) -> str | None:
        """Upload event JSON to S3; return the key, or None on failure."""
        key = self._s3_key(plant_id, event_id)
        body = json.dumps(payload, default=str).encode()

        def _put() -> None:
            client = boto3.client("s3", region_name=self.region)
            client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType="application/json",
                ServerSideEncryption="AES256",
            )

        try:
            await asyncio.to_thread(_put)
            return key
        except Exception as exc:
            logger.error("S3 archival failed for event %s: %s", event_id, exc)
            return None

    async def get_raw(self, key: str) -> dict:
        """Download and deserialise a previously archived event."""

        def _get() -> bytes:
            client = boto3.client("s3", region_name=self.region)
            return client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

        body = await asyncio.to_thread(_get)
        return json.loads(body)
