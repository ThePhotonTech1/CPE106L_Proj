from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Literal
from app.db import _db

router = APIRouter(prefix="/api", tags=["offers"])
offers_collection = _db["offers"]

# Allowed units: kilograms, pounds, pieces, liters
Unit = Literal["kg", "lb", "pcs", "L"]

class OfferItem(BaseModel):
    name: str
    quantity: float = Field(..., ge=0)
    unit: Unit = "kg"

class OfferIn(BaseModel):
    donor_name: str
    items: List[OfferItem]

@router.get("/offers")
async def list_offers():
    docs = []
    async for doc in offers_collection.find(
        {}, {"_id": 1, "donor_name": 1, "items": 1, "status": 1}
    ):
        doc["id"] = str(doc.pop("_id"))
        doc["status"] = doc.get("status", "open")
        docs.append(doc)
    return docs

@router.post("/offers", status_code=201)
async def create_offer(body: OfferIn):
    doc = {
        "donor_name": body.donor_name.strip(),
        "items": [i.dict() for i in body.items],
        "status": "open",
    }
    res = await offers_collection.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    return doc
