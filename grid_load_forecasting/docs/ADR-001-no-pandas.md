# ADR-001: No pandas for SMA computation

**Date:** 2026-05-23  
**Status:** Accepted

## Context

The SMA forecasting worker needs to compute rolling averages over lists of float readings.
`pandas` was considered (`pd.Series.rolling(k).mean()`).

## Decision

Do not use pandas.

## Reasons

1. **Dependency weight**: `pandas` + `numpy` add ~10 MB to the container image for a 15-line
   sliding-sum that adds zero value from DataFrames.
2. **Testability**: A pure `compute_sma(readings: list[float], k: int) -> list[Optional[float]]`
   function is trivially unit-testable with exact expected values. A pandas Series output requires
   more ceremony to assert equality.
3. **Readability**: The sliding-sum implementation is self-documenting and matches the mathematical
   definition exactly: `SMA_k[i] = (1/k) * Σ p_{i-k+1..i}`.

## Consequences

The `math-accuracy` CI job runs `tests/test_forecaster.py` in isolation with no infrastructure.
This is only possible because the function has no external dependencies.
