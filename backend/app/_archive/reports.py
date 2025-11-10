from fastapi import APIRouter, Depends
from app.core.db import db

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/impact")
async def impact(db=Depends(get_db)):
    cursor = db["matches"].aggregate([
        {"$group": {"_id": None, "kg_saved": {"$sum": "$allocated_kg"}, "rescues": {"$sum": 1}}}
    ])
    rows = [r async for r in cursor]
    return rows[0] if rows else {"kg_saved": 0, "rescues": 0}
