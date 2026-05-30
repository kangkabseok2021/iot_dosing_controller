def test_login_success(client):
    r = client.post(
        "/api/v1/auth/token",
        json={"username": "dispatcher1", "password": "dispatch123"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert r.json()["token_type"] == "bearer"


def test_wrong_password_returns_401(client):
    r = client.post(
        "/api/v1/auth/token",
        json={"username": "dispatcher1", "password": "wrongpassword"},
    )
    assert r.status_code == 401


def test_missing_token_returns_403(client):
    r = client.post("/api/v1/deliveries", json={"description": "x", "vehicle_id": 1})
    assert r.status_code == 403


def test_viewer_on_dispatcher_endpoint_returns_403(client, viewer_token):
    r = client.post(
        "/api/v1/deliveries",
        json={"description": "x", "vehicle_id": 1},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r.status_code == 403


def test_invalid_token_returns_401(client):
    r = client.post(
        "/api/v1/deliveries",
        json={"description": "x", "vehicle_id": 1},
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert r.status_code == 401
