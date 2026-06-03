"""Shared pytest fixtures — uses in-memory SQLite for fast, isolated tests."""

from __future__ import annotations

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models.orm import Base

_PG_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://dispatch:dispatch@localhost:5432/dispatch",
)


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    SessionLocal = async_sessionmaker(db_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    SessionLocal = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncSession:  # type: ignore[override]
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def pg_client():
    """FastAPI test client backed by real PostgreSQL with TimescaleDB.

    Used only by test_hypertable_partitioning_query (skipped if USE_TIMESCALEDB != '1').
    Creates tables and the hypertable; truncates on teardown.
    """
    engine = create_async_engine(_PG_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # TimescaleDB: all unique constraints must include the partition column.
        # Recreate the telemetry PK as (id, measured_at) before create_hypertable.
        await conn.execute(
            text(
                """
                ALTER TABLE telemetry DROP CONSTRAINT IF EXISTS telemetry_pkey;
                ALTER TABLE telemetry ADD PRIMARY KEY (id, measured_at);
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
                    ) THEN
                        PERFORM create_hypertable(
                            'telemetry', 'measured_at',
                            chunk_time_interval => INTERVAL '7 days',
                            if_not_exists => TRUE
                        );
                    END IF;
                END
                $$;
                """
            )
        )

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncSession:  # type: ignore[override]
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

    # Clean up for test isolation
    async with engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            await conn.execute(tbl.delete())
    await engine.dispose()
