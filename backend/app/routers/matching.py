# app/routers/matching.py
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone
from collections import defaultdict
from app.db import get_db

router = APIRouter(prefix="/api/matching", tags=["matching"])

def _utcnow():
    return datetime.now(timezone.utc)

def _oid(s):
    return ObjectId(s) if isinstance(s, str) and ObjectId.is_valid(s) else None

ACTIVE_DONATION_STAT = {"open", "assigned", "picked_up", "in_transit"}
ACTIVE_REQUEST_STAT = {"open"}

@router.get("/run")
async def run_matching(db: AsyncIOMotorDatabase = Depends(get_db)):
    # 0) Clear ONLY 'planned' (do NOT touch in_progress/completed)
    await db.matches.delete_many({"status": "planned"})

    # 1) Load active donations & requests
    donations = [d async for d in db.donations.find({"status": {"$in": list(ACTIVE_DONATION_STAT)}})]
    requests  = [r async for r in db.requests.find({"status": {"$in": list(ACTIVE_REQUEST_STAT)}})]

    # 2) Preload already reserved quantities (planned + in_progress)
    committed = defaultdict(float)   # (donation_id, item) -> allocated sum
    demanded  = defaultdict(float)   # (request_id,  item) -> allocated sum
    async for m in db.matches.find({"status": {"$in": ["planned", "in_progress"]}}):
        di = str(m.get("donation_id") or "")
        ri = str(m.get("request_id")  or "")
        item = (m.get("item") or "").strip().lower()
        a = float(m.get("allocated") or 0)
        if di: committed[(di, item)] += a
        if ri: demanded[(ri, item)]  += a

    # 3) Remaining supply
    supply = defaultdict(float)              # (did,item)->remaining
    for d in donations:
        did = str(d.get("_id") or d.get("id") or "")
        for it in (d.get("items") or []):
            item = (it.get("name") or "").strip().lower()
            qty  = float(it.get("qty") or 0)
            rem  = qty - committed[(did, item)]
            if rem > 0:
                supply[(did, item)] += rem

    # 4) Remaining demand
    demand = defaultdict(float)              # (rid,item)->remaining
    for r in requests:
        rid = str(r.get("_id") or r.get("id") or "")
        for nd in (r.get("needs") or []):
            item = (nd.get("name") or "").strip().lower()
            qty  = float(nd.get("qty") or nd.get("quantity") or 0)
            rem  = qty - demanded[(rid, item)]
            if rem > 0:
                demand[(rid, item)] += rem

    # 5) Greedy match
    from collections import defaultdict as dd2
    req_by_item = dd2(list)
    for (rid, item), need in demand.items():
        req_by_item[item].append((rid, need))

    planned_docs = []
    batch_tag = int(_utcnow().timestamp())

    for (did, item), avail in supply.items():
        if avail <= 0: continue
        rows = req_by_item.get(item, [])
        for i, (rid, need) in enumerate(rows):
            if need <= 0 or avail <= 0: continue
            take = min(avail, need)
            avail -= take
            rows[i] = (rid, need - take)
            planned_docs.append({
                "donation_id": _oid(did) or did,
                "request_id":  _oid(rid) or rid,
                "item": item,
                "allocated": float(take),
                "status": "planned",
                "batch_index": batch_tag,
                "created_at": _utcnow(),
            })
            if avail <= 0: break

    count = 0
    if planned_docs:
        res = await db.matches.insert_many(planned_docs)
        count = len(res.inserted_ids)

    return {"ok": True, "planned": count}

@router.get("/plan")
async def list_planned(db: AsyncIOMotorDatabase = Depends(get_db)):
    out = []
    async for m in db.matches.find({"status": "planned"}):
        did = m.get("donation_id")
        rid = m.get("request_id")
        ddoc = await db.donations.find_one({"_id": did}) if isinstance(did, ObjectId) else None
        rdoc = await db.requests.find_one({"_id": rid}) if isinstance(rid, ObjectId) else None
        out.append({
            "donor": (ddoc or {}).get("donor_name", ""),
            "item": m.get("item", ""),
            "allocated": m.get("allocated", 0),
            "ngo": (rdoc or {}).get("ngo_name", ""),
            "status": m.get("status", "planned"),
        })
    return out
