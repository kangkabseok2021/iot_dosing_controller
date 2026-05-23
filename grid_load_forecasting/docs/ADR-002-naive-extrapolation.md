# ADR-002: Naive SMA extrapolation for short-horizon forecast

**Date:** 2026-05-23  
**Status:** Accepted

## Context

`GET /api/v1/forecast/{node_id}?horizon_steps=N` projects load forward N 15-minute steps.

## Decision

Project forward by repeating the last computed SMA value for all horizon steps.

## Reasons

1. **Operational horizon**: The stated use case is 15–60 minute load planning, not day-ahead
   forecasting. At sub-hour horizons, the SMA is a reasonable proxy for near-term load.
2. **Scope**: This project demonstrates API design, async workers, PostgreSQL optimization,
   and CI discipline — not ML forecasting. An ARIMA or LSTM model is out of scope.
3. **Honesty**: The API returns a `confidence` field (`low`/`medium`/`high` based on data
   volume) so callers understand the reliability of the projection.

## Consequences

The `horizon` array in the forecast response carries a constant `projected_kwh` for all steps.
Callers requiring better accuracy should integrate an external forecasting service.
