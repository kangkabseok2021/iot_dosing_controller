import os

import boto3
import pytest
from httpx import ASGITransport, AsyncClient
from moto import mock_aws
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.session import get_session
from app.main import app

# moto requires fake AWS credentials
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_BUCKET = "oem-sensor-events-test"
TEST_REGION = "eu-central-1"

_engine = create_async_engine(TEST_DB_URL, echo=False)
_SessionLocal = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def override_session():
    async def _get_test_session():
        async with _SessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client(override_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def db_session():
    async with _SessionLocal() as session:
        yield session


@pytest.fixture
def s3_bucket():
    with mock_aws():
        boto3.client("s3", region_name=TEST_REGION).create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": TEST_REGION},
        )
        yield TEST_BUCKET
