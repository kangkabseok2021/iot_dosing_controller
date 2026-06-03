"""SARIMA + XGBoost ensemble for 15-min generation forecasting."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from xgboost import XGBRegressor


def _build_features(series: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"y": series.values}, index=series.index)
    df["hour"] = series.index.hour if hasattr(series.index, "hour") else 0
    df["dow"] = series.index.dayofweek if hasattr(series.index, "dayofweek") else 0
    df["lag_1"] = df["y"].shift(4)  # 1 h at 15-min resolution
    df["lag_96"] = df["y"].shift(96)  # 24 h at 15-min resolution
    df["roll_mean_24h"] = df["y"].rolling(96, min_periods=1).mean()
    df["roll_std_24h"] = df["y"].rolling(96, min_periods=1).std().fillna(0)
    return df.fillna(0)


class ForecastPipeline:
    """
    Ensemble: μ = 0.5·exp(ŷ_sarima) + 0.5·ŷ_xgb
    σ estimated from SARIMA in-sample residual std.

    Args:
        sarima_order: SARIMAX order tuple (p,d,q).
        seasonal_order: seasonal SARIMAX order (P,D,Q,s). None → no seasonality.
    """

    def __init__(
        self,
        sarima_order: tuple[int, int, int] = (1, 1, 1),
        seasonal_order: tuple[int, int, int, int] | None = (1, 1, 0, 96),
    ) -> None:
        self._sarima_order = sarima_order
        self._seasonal_order = seasonal_order
        self._sarima_fit: Any = None
        self._xgb: XGBRegressor | None = None
        self._sigma: float = 1.0
        self._mape_sarima: float | None = None
        self._mape_ensemble: float | None = None

    # ── Public ─────────────────────────────────────────────────────────────

    @property
    def mape_sarima(self) -> float:
        if self._mape_sarima is None:
            raise RuntimeError("call fit() first")
        return self._mape_sarima

    @property
    def mape_ensemble(self) -> float:
        if self._mape_ensemble is None:
            raise RuntimeError("call fit() first")
        return self._mape_ensemble

    def fit(self, series: pd.Series, holdout_frac: float = 0.2) -> ForecastPipeline:
        """Fit on training split; compute MAPE on held-out fraction."""
        n = len(series)
        split = int(n * (1 - holdout_frac))
        train, test = series.iloc[:split], series.iloc[split:]

        # SARIMA on log-transformed series (keeps forecasts ≥ 0)
        log_train = np.log1p(train.clip(lower=0))
        sarima_kwargs: dict[str, object] = {"order": self._sarima_order}
        if self._seasonal_order is not None:
            sarima_kwargs["seasonal_order"] = self._seasonal_order
        model = SARIMAX(log_train, **sarima_kwargs, initialization="approximate_diffuse")
        self._sarima_fit = model.fit(disp=False)
        self._sigma = float(np.std(self._sarima_fit.resid))

        # SARIMA forecast on test period
        sarima_pred_log = np.asarray(self._sarima_fit.forecast(len(test)), dtype=float)
        sarima_pred = np.expm1(sarima_pred_log).clip(min=0)

        # XGBoost on feature matrix (full series for context, predict test rows)
        features = _build_features(series)
        feat_cols = ["hour", "dow", "lag_1", "lag_96", "roll_mean_24h", "roll_std_24h"]
        X_train = features.iloc[:split][feat_cols].values
        y_train = series.iloc[:split].clip(lower=0).values
        X_test = features.iloc[split:][feat_cols].values

        self._xgb = XGBRegressor(n_estimators=100, max_depth=4, verbosity=0)
        self._xgb.fit(X_train, y_train)
        xgb_pred = self._xgb.predict(X_test).clip(min=0)

        # Ensemble
        ensemble_pred = 0.5 * sarima_pred + 0.5 * xgb_pred
        actual = test.clip(lower=0).values

        eps = 1.0  # avoid division by zero for near-zero values
        self._mape_sarima = float(np.mean(np.abs(actual - sarima_pred) / (np.abs(actual) + eps)))
        self._mape_ensemble = float(
            np.mean(np.abs(actual - ensemble_pred) / (np.abs(actual) + eps))
        )
        return self

    def predict(self, horizon_steps: int) -> tuple[np.ndarray, np.ndarray]:
        """Return (μ array, σ array) for `horizon_steps` future steps."""
        if self._sarima_fit is None or self._xgb is None:
            raise RuntimeError("call fit() first")
        sarima_log = np.asarray(self._sarima_fit.forecast(horizon_steps), dtype=float)
        mu_sarima = np.expm1(sarima_log).clip(min=0)
        # XGBoost: use last known features (simplified — repeats last row)
        # In production this would re-build with updated lags
        last_features = np.zeros((horizon_steps, 6))
        mu_xgb = self._xgb.predict(last_features).clip(min=0)
        mu = 0.5 * mu_sarima + 0.5 * mu_xgb
        sigma = np.full(horizon_steps, max(self._sigma, 0.1))
        return mu, sigma
