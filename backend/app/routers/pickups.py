from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime
from bson import ObjectId
from app.core.events import emit_event

from app.core.security import require_scopes, get_current_user
from app.core.db import db
from app.core.guards import ensure_same_org
from app.core.states import PICKUP_STATES, can_transition
from app.models.pickup import PickupCreate

router = APIRouter(prefix="/pickups", tags=["pickups"])

def oid() -> str:
    return str(ObjectId())

@router.post("/", dependencies=[Depends(require_scopes(["pickups:create"]))])
async def create_pickup(data: PickupCreate, user=Depends(get_current_user)):
    doc = {
        "_id": oid(),
        "org_id": user["org_id"],
        "status": "created",
        "driver_id": None,
        "address": data.address,
        "window": data.window,
        "notes": data.notes,
        "version": 1,
        "history": [{
            "at": datetime.utcnow(), "by_user": user["_id"],
            "from_status": None, "to_status": "created", "note": "created"
        }],
        "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
    }
    await db.pickups.insert_one(doc)
    return {"id": doc["_id"], "ok": True}

@router.get("/{pickup_id}")
async def get_pickup(pickup_id: str, user=Depends(get_current_user)):
    pickup = await db.pickups.find_one({"_id": pickup_id})
    if not pickup:
        raise HTTPException(404, "Pickup not found")
    ensure_same_org(pickup["org_id"], user["org_id"])
    return {
        "id": pickup["_id"],
        "org_id": pickup["org_id"],
        "status": pickup["status"],
        "driver_id": pickup.get("driver_id"),
        "version": pickup["version"],
        "history_count": len(pickup.get("history", []))
    }

# Assign by EMAIL to avoid hunting for driver_id
@router.post("/{pickup_id}/assign", dependencies=[Depends(require_scopes(["pickups:assign"]))])
async def assign_driver_by_email(
    pickup_id: str,
    driver_email: str = Body(..., embed=True),
    user=Depends(get_current_user)
):
    pickup = await db.pickups.find_one({"_id": pickup_id})
    if not pickup:
        raise HTTPException(404, "Pickup not found")
    ensure_same_org(pickup["org_id"], user["org_id"])

    driver = await db.users.find_one({"email": driver_email})
    if not driver:
        raise HTTPException(404, "Driver not found")
    ensure_same_org(driver["org_id"], user["org_id"])

    await db.pickups.update_one(
        {"_id": pickup_id},
        {"$set": {"driver_id": driver["_id"], "updated_at": datetime.utcnow()}}
    )
    return {"ok": True}

@router.post("/{pickup_id}/transition", dependencies=[Depends(require_scopes(["pickups:update_status"]))])
async def transition_status(
    pickup_id: str,
    to_status: str = Body(..., embed=True),
    note: str | None = Body(None, embed=True),
    version: int = Body(..., embed=True),
    user=Depends(get_current_user)
):
    if to_status not in PICKUP_STATES:
        raise HTTPException(400, "Invalid status")

    pickup = await db.pickups.find_one({"_id": pickup_id})
    if not pickup:
        raise HTTPException(404, "Pickup not found")
    ensure_same_org(pickup["org_id"], user["org_id"])

    # Drivers can only update their own assigned pickups
    if "driver" in user.get("roles", []) and pickup.get("driver_id") != user["_id"]:
        raise HTTPException(403, "Driver can only update assigned pickups")

    src = pickup["status"]
    if not can_transition(src, to_status, user.get("roles", [])):
        raise HTTPException(403, f"Transition {src} -> {to_status} not allowed for your role")

    res = await db.pickups.update_one(
        {"_id": pickup_id, "version": version},
        {
            "$set": {"status": to_status, "updated_at": datetime.utcnow()},
            "$inc": {"version": 1},
            "$push": {
                "history": {
                    "at": datetime.utcnow(), "by_user": user["_id"],
                    "from_status": src, "to_status": to_status, "note": note
                }
            },
        },
    )
    if res.modified_count == 0:
        raise HTTPException(409, "Version conflict. Refresh and retry.")
    await emit_event(
        org_id=pickup["org_id"],
        type_="pickup.status.changed",
        data={
            "pickup_id": pickup_id,
            "from": src,
            "to": to_status,
            "by_user": user["_id"]
        }
    )
    return {"ok": True}
