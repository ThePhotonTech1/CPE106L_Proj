# app/routers/dispatch.py
from fastapi import APIRouter, Depends, HTTPException, Body
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from typing import Any, Iterable

from app.db import get_db

router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])

def _utcnow():
    return datetime.now(timezone.utc)

def _maybe_oid(x: Any) -> ObjectId | None:
    if isinstance(x, ObjectId):
        return x
    if isinstance(x, str) and ObjectId.is_valid(x):
        return ObjectId(x)
    return None

def _id_filter(any_id: str) -> dict:
    """
    Match route by Mongo _id or by custom 'id' field.
    """
    oid = _maybe_oid(any_id)
    conds = []
    if oid:
        conds.append({"_id": oid})
    conds.append({"id": any_id})
    return {"$or": conds}

def _to_oid_list(values: Iterable[Any]) -> list[ObjectId]:
    out: list[ObjectId] = []
    for v in (values or []):
        oid = _maybe_oid(v)
        if oid:
            out.append(oid)
    return out

@router.post("/routes/{rid}/start")
async def start_route(
    rid: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    q = _id_filter(rid)
    upd = {
        "$set": {"status": "in_progress", "started_at": _utcnow()},
        "$push": {"events": {"ts": _utcnow(), "type": "start"}},
    }
    res = await db.routes.update_one(q, upd)
    if not res.matched_count:
        raise HTTPException(404, "Route not found")

    # Lock any lingering planned matches that point to this route’s donors/recips (defensive)
    route = await db.routes.find_one(q)
    if route:
        # Attach any matching planned matches to this route
        donor_ids = route.get("donation_ids") or []
        recip_ids = route.get("request_ids") or []
        cond = {"status": "planned"}
        if donor_ids:
            cond["donation_id"] = {"$in": [ _maybe_oid(x) or x for x in donor_ids ]}
        if recip_ids:
            cond["request_id"] = {"$in": [ _maybe_oid(x) or x for x in recip_ids ]}
        await db.matches.update_many(cond, {"$set": {"status": "in_progress", "route_id": route["_id"], "locked_at": _utcnow()}})

    return {"ok": True, "status": "in_progress"}

@router.post("/routes/{rid}/checkpoint")
async def checkpoint_route(
    rid: str,
    payload: dict | None = Body(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    q = _id_filter(rid)
    evt = {"ts": _utcnow(), "type": "checkpoint"}
    if payload and "kg_override" in payload:
        try:
            evt["kg_override"] = float(payload["kg_override"])
        except Exception:
            raise HTTPException(400, "kg_override must be a number")
    res = await db.routes.update_one(q, {"$push": {"events": evt}})
    if not res.matched_count:
        raise HTTPException(404, "Route not found")
    return {"ok": True}

@router.post("/routes/{rid}/complete")
async def complete_route(
    rid: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    # fetch route by either _id or string id
    q = _id_filter(rid)
    route = await db.routes.find_one(q)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Pull lists (accept strings or ObjectIds)
    donation_ids = _to_oid_list(route.get("donation_ids") or [])
    request_ids  = _to_oid_list(route.get("request_ids")  or [])

    # 1) Mark route completed
    await db.routes.update_one(
        q,
        {
            "$set": {"status": "completed", "completed_at": _utcnow()},
            "$push": {"events": {"ts": _utcnow(), "type": "complete"}},
        },
    )

    # 2) Mark donations delivered (if you use that status)
    if donation_ids:
        await db.donations.update_many(
            {"_id": {"$in": donation_ids}},
            {"$set": {"status": "delivered"}}
        )

    # 3) Close requests (optional)
    if request_ids:
        await db.requests.update_many(
            {"_id": {"$in": request_ids}},
            {"$set": {"status": "closed"}}
        )

    # 4) Mark matches tied to this route as completed
    await db.matches.update_many(
        {"route_id": route.get("_id")},
        {"$set": {"status": "completed", "completed_at": _utcnow()}}
    )

    # 5) Free driver (if stored)
    driver_id = route.get("driver_id")
    driver_oid = _maybe_oid(driver_id)
    if driver_oid:
        await db.drivers.update_one({"_id": driver_oid}, {"$set": {"available": True}})

    return {"ok": True, "route_id": str(route.get("_id") or route.get("id") or rid)}
