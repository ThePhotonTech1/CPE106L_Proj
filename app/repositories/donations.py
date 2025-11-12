# app/repositories/donations.py
from typing import Any, Dict, List
from app.db import get_db
from bson import ObjectId

def _oid(id_str: str) -> ObjectId:
    return ObjectId(id_str)

async def create_donation(doc: Dict[str, Any]) -> str:
    db = get_db()
    res = await db.donations.insert_one(doc)
    return str(res.inserted_id)

async def list_my_donations(user_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    cur = db.donations.find({"donor_id": user_id}).sort("created_at", -1)
    return [ {**d, "id": str(d["_id"])} async for d in cur ]

async def list_available() -> List[Dict[str, Any]]:
    db = get_db()
    cur = db.donations.find({"status": "available"}).sort("expires", 1)
    return [ {**d, "id": str(d["_id"])} async for d in cur ]
