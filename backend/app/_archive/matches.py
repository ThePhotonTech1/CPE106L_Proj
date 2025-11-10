from fastapi import APIRouter, Depends
from app.core.db import db
from ..services.matching import greedy_match
from typing import Optional, List

router = APIRouter(prefix="/matches", tags=["matches"])

def col(db, name): return db[name]

@router.post("/run")
async def run_matching(lot_ids: Optional[List[str]] = None, db=Depends(get_db)):
    # get available lots
    lots = [d async for d in col(db,"donations").find({"status": "available"}, {"_id":0})]
    if lot_ids:
        lots = [l for l in lots if l["id"] in lot_ids]
    recs = [r async for r in col(db,"recipients").find({}, {"_id":0})]

    m_objs = greedy_match(lots, recs)
    if not m_objs:
        return {"created": 0}

    await col(db,"matches").insert_many([m.dict() for m in m_objs])
    # mark the matched lots as reserved
    ids = list({m.lot_id for m in m_objs})
    await col(db,"donations").update_many({"id": {"$in": ids}}, {"$set": {"status": "reserved"}})
    return {"created": len(m_objs)}

@router.get("/")
async def list_matches(db=Depends(get_db)):
    cursor = db["matches"].find({}, {"_id": 0})
    return [m async for m in cursor]
