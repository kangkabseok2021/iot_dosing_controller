import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    # Depending on how client/mounting behaves in test client, try /api/v1/metrics/ or /api/v1/metrics
    response = await client.get("/api/v1/metrics")
    # Starlette's mount can redirect to /api/v1/metrics/ or serve it directly. Let's support either
    if response.status_code == 307:
        response = await client.get(response.headers["location"])
    assert response.status_code == 200
    # Prometheus metrics usually contain system/process metrics or python metrics
    assert "python_info" in response.text or "process_start_time_seconds" in response.text
