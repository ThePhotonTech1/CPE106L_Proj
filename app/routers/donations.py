# app/routers/donations.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from app.db import insert_donation, list_donations
from app.utils.geocode import geocode_address

router = APIRouter(prefix="/api/donations", tags=["donations"])


class DonationItem(BaseModel):
    name: str
    qty: float
    unit: str


class Location(BaseModel):
    lat: float = 0
    lng: float = 0


class DonationIn(BaseModel):
    donor_name: str
    items: List[DonationItem]
    address: Optional[str] = None
    location: Location = Field(default_factory=Location)
    ready_after: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_donation(body: DonationIn, db: Database = Depends(get_db)):
    c = col(db)
    loc = body.location.model_dump() if body.location else None
    # if no coords or (0,0), try geocode
    if (not loc) or (float(loc.get("lat", 0)) == 0 and float(loc.get("lng", 0)) == 0):
        g = geocode_address(body.address or "")
        if g: 
            loc = g

    doc = {
        "donor_name": body.donor_name,
        "items": [i.model_dump() for i in body.items],
        "address": body.address,
        "location": loc or {"lat": None, "lng": None},
        "ready_after": body.ready_after,
        "status": "open",
        "created_at": datetime.utcnow(),
    }
    ins = c.insert_one(doc)
    saved = c.find_one({"_id": ins.inserted_id})
    return {"donation": _serialize(saved)}


@router.get("")
async def get_donations():
    docs = await list_donations()
    out = []
    for d in docs:
        out.append({
            "id": d.get("id"),
            "donor_name": d.get("donor_name"),
            "items": d.get("items", []),
            "address": d.get("address"),
            "location": d.get("location", {}),
            "ready_after": d.get("ready_after"),
            "created_at": d.get("created_at"),
        })
    return out
