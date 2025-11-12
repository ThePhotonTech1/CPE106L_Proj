from fastapi import APIRouter
from app.db import get_db

router = APIRouter(prefix="/optimize", tags=["optimize"])

@router.post("")
async def optimize(body: dict):
    cap = float(body.get("vehicle_capacity", 50))
    db = get_db()
    items = [d async for d in db.donations.find({"status": "available"})]

    # simple greedy by earliest expiry, assume each item has "weight" or fall back to 1
    items.sort(key=lambda d: d.get("expires", "9999-12-31"))
    load, stops = 0.0, []
    for d in items:
        w = float(d.get("weight", 1))
        if load + w <= cap:
            load += w
            stops.append({"name": d.get("item_name", "Donation"), "load": load})

    return {"stops": stops, "capacity": cap, "used": load}
