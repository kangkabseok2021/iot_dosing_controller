"""CVXPY LP dispatch optimiser for renewable portfolio scheduling."""
from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np


@dataclass
class AssetSpec:
    asset_id: int
    capacity_mw: float
    ramp_rate_mw_per_min: float  # MW/min → MW/h = * 60


@dataclass
class ScheduleResult:
    status: str
    objective_eur: float
    schedule_per_asset: list[list[float]]  # [n_assets][n_intervals]


class DispatchOptimiser:
    """
    LP formulation:
        maximise  Σ_{i,t} price[t] · p[i,t]  −  penalty · Σ_t |Σ_i p[i,t] − Σ_i μ[i,t]|

        subject to:
            0 ≤ p[i,t] ≤ capacity[i]                        (capacity)
            |p[i,t] − p[i,t−1]| ≤ ramp_rate[i] · Δt        (ramp)
            ‖ Σ_i p[:,t] − Σ_i μ[:,t] ‖₁ ≤ imbalance_tol   (balance-group)
    """

    def optimise(
        self,
        assets: list[AssetSpec],
        price_curve: list[float],
        forecasts: list[list[float]],  # [n_assets][n_intervals]
        imbalance_tol_mwh: float = 10.0,
        penalty: float = 10.0,
    ) -> ScheduleResult:
        N = len(assets)
        T = len(price_curve)
        dt_h = 1.0  # 1-hour intervals

        prices = np.array(price_curve, dtype=float)
        mu = np.array(forecasts, dtype=float)  # (N, T)

        p = cp.Variable((N, T), nonneg=True)

        # Objective: revenue minus balance penalty
        revenue = cp.sum(cp.multiply(prices, cp.sum(p, axis=0)))
        portfolio = cp.sum(p, axis=0)
        forecast_sum = mu.sum(axis=0)
        imbalance_vec = portfolio - forecast_sum
        objective = cp.Maximize(revenue - penalty * cp.norm(imbalance_vec, 1))

        constraints: list[cp.Constraint] = []

        for i, asset in enumerate(assets):
            # Capacity
            constraints.append(p[i, :] <= asset.capacity_mw)
            # Ramp: |Δp| ≤ ramp_rate_mw_per_min * 60 min/h * dt_h
            ramp_limit = asset.ramp_rate_mw_per_min * 60.0 * dt_h
            if T > 1:
                constraints.append(cp.abs(cp.diff(p[i, :])) <= ramp_limit)

        # Balance-group netting hard constraint
        constraints.append(cp.norm(imbalance_vec, 1) <= imbalance_tol_mwh)

        prob = cp.Problem(objective, constraints)
        prob.solve(solver=cp.OSQP, eps_abs=1e-4, eps_rel=1e-4)

        if prob.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            raise ValueError(
                f"LP infeasible or unbounded (status={prob.status}). "
                "Check capacity, ramp, and imbalance_tol constraints."
            )

        schedule = p.value.tolist() if p.value is not None else [[0.0] * T] * N
        return ScheduleResult(
            status="optimal",
            objective_eur=float(prob.value) if prob.value is not None else 0.0,
            schedule_per_asset=schedule,
        )
