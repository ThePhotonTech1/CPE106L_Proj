import pytest
from httpx import AsyncClient
from app.core.db import db

pytestmark = pytest.mark.anyio

async def _seed_demo():
    await db.donors.delete_many({"_id": {"$in": ["D1"]}})
    await db.recipients.delete_many({"_id": {"$in": ["R1", "R2"]}})
    await db.users.delete_many({"email": "paolosy1605@gmail.com"})

    await db.donors.insert_one({
        "_id": "D1",
        "org_id": "org1",
        "name": "Donor A",
        "coord": [120.98, 14.60],
        "categories": ["produce", "bread"],
        "qty": 25
    })
    await db.recipients.insert_many([
        {"_id": "R1", "org_id": "org1", "name": "Recipient One", "coord": [121.00, 14.61], "needs": ["produce"], "capacity": 50},
        {"_id": "R2", "org_id": "org1", "name": "Recipient Two", "coord": [121.03, 14.62], "needs": ["bread"], "capacity": 10},
    ])

async def _auth_headers(ac: AsyncClient):
    # register (ignore 400 if exists)
    await ac.post("/auth/register", json={
        "email": "paolosy1605@gmail.com",
        "password": "1234",
        "org_id": "org1",
        "roles": ["dispatcher"]
    })
    tok = (await ac.post("/auth/token", data={
        "username": "paolosy1605@gmail.com", "password": "1234"
    })).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}

async def test_matching_run(test_client: AsyncClient):
    await _seed_demo()
    headers = await _auth_headers(test_client)
    r = await test_client.post("/matching/run", headers=headers, json={
        "donor_id": "D1",
        "candidate_recipient_ids": ["R1", "R2"],
        "constraints": {"max_distance_km": 10}
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["donor_id"] == "D1"
    assert {res["recipient_id"] for res in data["results"]} == {"R1", "R2"}

async def test_routes_plan(test_client: AsyncClient):
    headers = await _auth_headers(test_client)
    r = await test_client.post("/routes/plan", headers=headers, json={
        "depot": [120.9842, 14.5995],
        "stops": [
            {"id": "D1", "coord": [120.98, 14.60], "kind": "donor"},
            {"id": "R1", "coord": [121.00, 14.61], "kind": "recipient"},
            {"id": "R2", "coord": [121.03, 14.62], "kind": "recipient"}
        ],
        "objective": "shortest_path"
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ordered_stop_ids"] == ["D1", "R1", "R2"]
    assert data["total_distance_km"] >= 0
    assert data["legs"][0]["from_id"] == "DEPOT"
