def test_create_delivery_success(client, dispatcher_token, vehicle):
    r = client.post(
        "/api/v1/deliveries",
        json={"description": "Parcel to depot B", "vehicle_id": vehicle},
        headers={"Authorization": f"Bearer {dispatcher_token}"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["description"] == "Parcel to depot B"
    assert data["status"] == "pending"


def test_create_delivery_unauthenticated(client, vehicle):
    r = client.post(
        "/api/v1/deliveries",
        json={"description": "Parcel", "vehicle_id": vehicle},
    )
    assert r.status_code == 403


def test_get_delivery_by_id(client, dispatcher_token, vehicle):
    create_r = client.post(
        "/api/v1/deliveries",
        json={"description": "Get-me delivery", "vehicle_id": vehicle},
        headers={"Authorization": f"Bearer {dispatcher_token}"},
    )
    assert create_r.status_code == 201
    delivery_id = create_r.json()["id"]

    r = client.get(
        f"/api/v1/deliveries/{delivery_id}",
        headers={"Authorization": f"Bearer {dispatcher_token}"},
    )
    assert r.status_code == 200
    assert r.json()["id"] == delivery_id


def test_get_nonexistent_delivery_returns_404(client, dispatcher_token):
    r = client.get(
        "/api/v1/deliveries/999999",
        headers={"Authorization": f"Bearer {dispatcher_token}"},
    )
    assert r.status_code == 404
