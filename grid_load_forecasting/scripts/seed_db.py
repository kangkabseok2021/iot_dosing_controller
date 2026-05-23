"""Seed the database with synthetic load readings.

Usage: python scripts/seed_db.py --nodes 10 --days 90
"""

import argparse
import asyncio
import math
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import settings
from app.db.models import Base, LoadReading, Node


async def main(num_nodes: int, num_days: int) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    intervals_per_day = 96
    total_intervals = num_days * intervals_per_day
    now = datetime.now(tz=timezone.utc)

    async with SessionLocal() as session:
        for n in range(num_nodes):
            node_id = f"NODE-{n+1:03d}"
            node = Node(node_id=node_id, meter_type="commercial")
            session.add(node)
            await session.flush()

            readings = []
            for i in range(total_intervals):
                ts = now - timedelta(minutes=15 * (total_intervals - i))
                hour = ts.hour + ts.minute / 60.0
                kwh = 20 + 15 * math.sin(2 * math.pi * hour / 24) + random.gauss(0, 2)
                kwh = max(0.1, kwh)
                readings.append(
                    LoadReading(
                        node_id=node_id,
                        ts=ts,
                        kwh=round(kwh, 3),
                        meter_type="commercial",
                        accepted_at=datetime.now(tz=timezone.utc),
                    )
                )
            session.add_all(readings)
            await session.commit()
            print(f"  seeded {node_id}: {len(readings)} readings")

    await engine.dispose()
    print(f"Done: {num_nodes} nodes × {total_intervals} intervals = {num_nodes * total_intervals} rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=10)
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()
    asyncio.run(main(args.nodes, args.days))
