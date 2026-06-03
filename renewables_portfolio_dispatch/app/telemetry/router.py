from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.orm import Asset, Telemetry
from app.models.schemas import AssetCreate, AssetRead, TelemetryBulk

router = APIRouter(prefix="/api", tags=["telemetry"])


@router.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def create_asset(body: AssetCreate, db: AsyncSession = Depends(get_db)) -> Asset:
    asset = Asset(**body.model_dump())
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@router.get("/assets/{asset_id}", response_model=AssetRead)
async def get_asset(asset_id: int, db: AsyncSession = Depends(get_db)) -> Asset:
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.post("/telemetry", status_code=status.HTTP_200_OK)
async def ingest_telemetry(
    body: TelemetryBulk, db: AsyncSession = Depends(get_db)
) -> dict[str, int]:
    # Validate power_mw ≤ capacity_mw per asset
    asset_ids = {r.asset_id for r in body.rows}
    assets_result = await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))
    capacity_map = {a.id: a.capacity_mw for a in assets_result.scalars()}

    for row in body.rows:
        cap = capacity_map.get(row.asset_id)
        if cap is None:
            raise HTTPException(status_code=404, detail=f"Asset {row.asset_id} not found")
        if row.power_mw > cap:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"power_mw {row.power_mw} exceeds capacity {cap} for asset {row.asset_id}",
            )

    rows_data = [
        {"asset_id": r.asset_id, "measured_at": r.measured_at, "power_mw": r.power_mw}
        for r in body.rows
    ]
    await db.execute(insert(Telemetry), rows_data)
    await db.commit()
    return {"inserted": len(rows_data)}


@router.get("/telemetry/chunks")
async def get_chunk_count(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    """Returns TimescaleDB chunk count — 0 when running on plain PostgreSQL/SQLite."""
    try:
        result = await db.execute(
            text(
                "SELECT count(*) FROM timescaledb_information.chunks"
                " WHERE hypertable_name = 'telemetry'"
            )
        )
        count = result.scalar_one()
    except Exception:
        count = 0
    return {"chunk_count": int(count)}
