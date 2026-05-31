"""5 tests for S3Archiver using moto @mock_aws."""

import json
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws

from app.archival import S3Archiver
from tests.conftest import TEST_BUCKET, TEST_REGION


async def test_archive_uploads_to_s3(s3_bucket):
    archiver = S3Archiver(bucket=s3_bucket, region=TEST_REGION)
    payload = {"plant_id": "PLT-001", "value": 42.0}
    key = await archiver.archive(str(uuid4()), "PLT-001", payload)
    assert key is not None
    # Verify object exists in mocked S3
    client = boto3.client("s3", region_name=TEST_REGION)
    obj = client.get_object(Bucket=s3_bucket, Key=key)
    data = json.loads(obj["Body"].read())
    assert data["plant_id"] == "PLT-001"


async def test_archive_key_contains_date_and_plant_id(s3_bucket):
    archiver = S3Archiver(bucket=s3_bucket, region=TEST_REGION)
    event_id = str(uuid4())
    key = await archiver.archive(event_id, "PLT-XYZ", {"v": 1})
    assert key is not None
    assert "PLT-XYZ" in key
    assert event_id in key
    assert key.startswith("events/")


async def test_get_raw_returns_original_payload(s3_bucket):
    archiver = S3Archiver(bucket=s3_bucket, region=TEST_REGION)
    payload = {"plant_id": "PLT-001", "value": 99.9, "unit": "bar"}
    key = await archiver.archive(str(uuid4()), "PLT-001", payload)
    assert key is not None
    retrieved = await archiver.get_raw(key)
    assert retrieved["value"] == 99.9
    assert retrieved["unit"] == "bar"


async def test_archive_failure_returns_none():
    # Non-existent bucket → botocore exception → returns None
    archiver = S3Archiver(bucket="nonexistent-bucket-xyz", region=TEST_REGION)
    with mock_aws():
        key = await archiver.archive(str(uuid4()), "PLT-001", {"v": 1})
    assert key is None


async def test_archive_key_format_includes_json_extension(s3_bucket):
    archiver = S3Archiver(bucket=s3_bucket, region=TEST_REGION)
    key = await archiver.archive(str(uuid4()), "PLT-001", {})
    assert key is not None
    assert key.endswith(".json")
