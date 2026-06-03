"""Phase 3 — 8 tests: CVXPY LP optimizer + Fahrplan CRUD + Blob archival."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.optimizer.dispatch import AssetSpec, DispatchOptimiser

# ── LP unit tests (no DB needed) ─────────────────────────────────────────────

def _two_asset_specs() -> list[AssetSpec]:
    return [
        AssetSpec(asset_id=1, capacity_mw=100.0, ramp_rate_mw_per_min=5.0),
        AssetSpec(asset_id=2, capacity_mw=80.0,  ramp_rate_mw_per_min=4.0),
    ]


def _flat_price(t: int = 24, price: float = 50.0) -> list[float]:
    return [price] * t


def _flat_forecast(n_assets: int, t: int = 24, mu: float = 60.0) -> list[list[float]]:
    return [[mu] * t for _ in range(n_assets)]


@pytest.mark.asyncio
async def test_lp_feasible_2asset_portfolio():
    result = DispatchOptimiser().optimise(
        _two_asset_specs(), _flat_price(), _flat_forecast(2), imbalance_tol_mwh=30.0
    )
    assert result.status == "optimal"
    assert len(result.schedule_per_asset) == 2
    assert len(result.schedule_per_asset[0]) == 24


@pytest.mark.asyncio
async def test_lp_respects_ramp_constraints():
    assets = _two_asset_specs()
    result = DispatchOptimiser().optimise(
        assets, _flat_price(), _flat_forecast(2), imbalance_tol_mwh=50.0
    )
    for i, asset in enumerate(assets):
        schedule = result.schedule_per_asset[i]
        ramp_limit = asset.ramp_rate_mw_per_min * 60.0  # MW/h
        for t in range(1, len(schedule)):
            delta = abs(schedule[t] - schedule[t - 1])
            assert delta <= ramp_limit + 1e-3, (
                f"Asset {i} ramp violation at t={t}: {delta:.3f} > {ramp_limit:.1f}"
            )


@pytest.mark.asyncio
async def test_lp_balance_group_netting():
    assets = _two_asset_specs()
    imbalance_tol = 20.0
    result = DispatchOptimiser().optimise(
        assets, _flat_price(), _flat_forecast(2, mu=40.0), imbalance_tol_mwh=imbalance_tol
    )
    forecasts = _flat_forecast(2, mu=40.0)
    for t in range(24):
        portfolio_t = sum(result.schedule_per_asset[i][t] for i in range(len(assets)))
        forecast_t = sum(forecasts[i][t] for i in range(len(assets)))
        assert abs(portfolio_t - forecast_t) <= imbalance_tol + 1e-2


@pytest.mark.asyncio
async def test_lp_infeasible_raises():
    """Force infeasibility: forecast far exceeds capacity with zero imbalance tolerance."""
    assets = [AssetSpec(asset_id=1, capacity_mw=10.0, ramp_rate_mw_per_min=999.0)]
    # Forecast = 500 MW, capacity = 10 MW, imbalance_tol = 0 → infeasible
    forecasts = [[500.0] * 6]
    with pytest.raises(ValueError, match="infeasible"):
        DispatchOptimiser().optimise(
            assets, [50.0] * 6, forecasts, imbalance_tol_mwh=0.0
        )


# ── Fahrplan CRUD (DB needed) ─────────────────────────────────────────────────

def _make_fahrplan(schedule_id: uuid.UUID | None = None) -> dict:
    sid = schedule_id or uuid.uuid4()
    t0 = datetime(2024, 6, 1, tzinfo=UTC)
    return {
        "schedule_id": str(sid),
        "portfolio_id": 1,
        "date": "2024-06-01",
        "created_at": t0.isoformat(),
        "intervals": [
            {
                "asset_id": 1,
                "interval_start": (t0 + timedelta(hours=h)).isoformat(),
                "interval_end": (t0 + timedelta(hours=h + 1)).isoformat(),
                "scheduled_mw": float(50 + h),
                "status": "DRAFT",
            }
            for h in range(3)
        ],
    }


@pytest.mark.asyncio
async def test_fahrplan_post_persists_to_db(client):
    resp = await client.post("/api/fahrplan", json=_make_fahrplan())
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["intervals"]) == 3


@pytest.mark.asyncio
async def test_fahrplan_get_returns_correct_intervals(client):
    sid = uuid.uuid4()
    await client.post("/api/fahrplan", json=_make_fahrplan(sid))
    resp = await client.get(f"/api/fahrplan/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["portfolio_id"] == 1
    assert len(data["intervals"]) == 3


@pytest.mark.asyncio
async def test_fahrplan_patch_updates_status(client):
    sid = uuid.uuid4()
    await client.post("/api/fahrplan", json=_make_fahrplan(sid))
    resp = await client.patch(f"/api/fahrplan/{sid}", json={"status": "SUBMITTED"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(i["status"] == "SUBMITTED" for i in data["intervals"])


@pytest.mark.asyncio
async def test_blob_archive_called_on_submit(client):
    """Verifies the blob store archive() is called when POST /api/fahrplan is hit."""
    from app.fahrplan.blob_store import get_blob_store
    from app.main import app as fastapi_app

    mock_store = MagicMock()
    mock_store.archive = AsyncMock(return_value="mock/path.json")

    fastapi_app.dependency_overrides[get_blob_store] = lambda: mock_store

    resp = await client.post("/api/fahrplan", json=_make_fahrplan())
    assert resp.status_code == 201
    mock_store.archive.assert_called_once()

    del fastapi_app.dependency_overrides[get_blob_store]
