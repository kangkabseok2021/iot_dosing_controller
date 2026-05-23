"""Integration tests — require docker compose stack to be running.

Run with: pytest tests/test_integration.py -v -m integration
Spun up automatically by the CI integration-tests job.
"""

import subprocess
import time
from datetime import datetime, timedelta, timezone

import pytest
import httpx


BASE_URL = "http://localhost:8099"


@pytest.fixture(scope="session")
def docker_compose_up():
    import os

    compose_file = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d", "--wait"],
        check=True,
        timeout=120,
    )
    time.sleep(3)
    yield
    subprocess.run(
        ["docker", "compose", "-f", compose_file, "down", "-v"],
        check=True,
        timeout=60,
    )


def _ts(delta_s: float = 0) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(seconds=delta_s)).isoformat()


@pytest.mark.integration
def test_ingest_and_retrieve_round_trip(docker_compose_up):
    for i in range(10):
        r = httpx.post(
            f"{BASE_URL}/api/v1/readings",
            json={"node_id": "IT-NODE-001", "timestamp": _ts(-i * 60), "kwh": 10.0 + i},
        )
        assert r.status_code == 201

    r = httpx.get(f"{BASE_URL}/api/v1/readings/IT-NODE-001?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 10


@pytest.mark.integration
def test_batch_ingest_1000_readings(docker_compose_up):
    readings = [
        {"node_id": "IT-NODE-002", "timestamp": _ts(-i * 15), "kwh": 5.0 + (i % 10)}
        for i in range(1000)
    ]
    r = httpx.post(
        f"{BASE_URL}/api/v1/readings/batch",
        json={"readings": readings},
        timeout=30,
    )
    assert r.status_code == 201
    assert r.json()["accepted"] == 1000

    r2 = httpx.get(f"{BASE_URL}/api/v1/readings/IT-NODE-002?limit=1000")
    assert r2.status_code == 200
    assert len(r2.json()) == 1000


@pytest.mark.integration
def test_forecast_returned_after_sufficient_data(docker_compose_up):
    for i in range(48):
        httpx.post(
            f"{BASE_URL}/api/v1/readings",
            json={"node_id": "IT-NODE-003", "timestamp": _ts(-i * 15 * 60), "kwh": 20.0 + i % 5},
        )

    r = httpx.get(f"{BASE_URL}/api/v1/forecast/IT-NODE-003")
    assert r.status_code == 200
    body = r.json()
    assert body["node_id"] == "IT-NODE-003"
    assert body["confidence"] in ("low", "medium", "high")


@pytest.mark.integration
def test_nodes_list_includes_ingested_node(docker_compose_up):
    httpx.post(
        f"{BASE_URL}/api/v1/readings",
        json={"node_id": "IT-NODE-004", "timestamp": _ts(-30), "kwh": 7.0},
    )
    r = httpx.get(f"{BASE_URL}/api/v1/nodes")
    assert r.status_code == 200
    node_ids = [n["node_id"] for n in r.json()]
    assert "IT-NODE-004" in node_ids


@pytest.mark.integration
def test_health_endpoint(docker_compose_up):
    r = httpx.get(f"{BASE_URL}/api/v1/health")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"
