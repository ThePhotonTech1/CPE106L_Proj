from fastapi import APIRouter, Depends
from ..schemas import RecipientCreate
from app.core.db import db
import uuid

router = APIRouter(prefix="/recipients", tags=["recipients"])

def col(db):
    return db["recipients"]

@router.post("/")
async def create_recipient(payload: RecipientCreate, db=Depends(get_db)):
    doc = {"id": uuid.uuid4().hex, **payload.dict()}
    await col(db).insert_one(doc)
    return {"id": doc["id"]}

@router.get("/")
async def list_recipients(db=Depends(get_db)):
    cursor = col(db).find({}, {"_id": 0})
    return [d async for d in cursor]
