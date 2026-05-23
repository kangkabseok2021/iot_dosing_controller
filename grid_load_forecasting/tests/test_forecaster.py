"""Math-accuracy tests for SMA and anomaly detection — no infrastructure required."""

import statistics

import pytest

from app.workers.forecaster import compute_anomalies, compute_sma


def test_sma_known_values():
    result = compute_sma([1.0, 2.0, 3.0, 4.0, 5.0], k=3)
    assert result[:2] == [None, None]
    assert result[2] == pytest.approx(2.0)
    assert result[3] == pytest.approx(3.0)
    assert result[4] == pytest.approx(4.0)


def test_sma_constant_series():
    series = [10.0] * 20
    result = compute_sma(series, k=5)
    for v in result[4:]:
        assert v == pytest.approx(10.0)


def test_sma_window_larger_than_data():
    result = compute_sma([1.0, 2.0, 3.0, 4.0, 5.0], k=10)
    assert all(v is None for v in result)


def test_sma_k_1_is_identity():
    series = [3.0, 7.0, 2.0, 9.0]
    result = compute_sma(series, k=1)
    assert result == pytest.approx(series)


@pytest.mark.parametrize("k", [3, 5, 12, 24, 96])
def test_sma_sliding_sum_matches_naive(k):
    import random

    random.seed(42)
    series = [random.uniform(1, 100) for _ in range(1000)]
    result = compute_sma(series, k)
    for i in range(k - 1, len(series)):
        naive = statistics.mean(series[i - k + 1 : i + 1])
        assert result[i] == pytest.approx(naive, abs=1e-9)


def test_anomaly_detection_flags_spike():
    base = [20.0] * 50
    spiked = base[:25] + [200.0] + base[25:]
    sma = compute_sma(spiked, k=5)
    flags = compute_anomalies(spiked, sma)
    flagged_indices = [f["index"] for f in flags]
    assert 25 in flagged_indices


def test_anomaly_no_flags_stable_series():
    series = [10.0 + 0.1 * i for i in range(50)]
    sma = compute_sma(series, k=5)
    flags = compute_anomalies(series, sma)
    assert flags == []


def test_sma_edge_k_equals_n():
    series = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = compute_sma(series, k=5)
    assert result[:4] == [None, None, None, None]
    assert result[4] == pytest.approx(3.0)


def test_sma_k_zero_returns_all_none():
    result = compute_sma([1.0, 2.0, 3.0], k=0)
    assert all(v is None for v in result)


def test_sma_empty_series():
    result = compute_sma([], k=3)
    assert result == []


def test_sma_single_element_k1():
    result = compute_sma([42.0], k=1)
    assert result == [pytest.approx(42.0)]


def test_anomaly_short_series_no_crash():
    flags = compute_anomalies([5.0], [None])
    assert flags == []


def test_anomaly_zscore_populated():
    base = [10.0] * 30
    spike = base[:15] + [100.0] + base[15:]
    sma = compute_sma(spike, k=3)
    flags = compute_anomalies(spike, sma)
    for f in flags:
        assert "zscore" in f
        assert f["zscore"] > 2.0
