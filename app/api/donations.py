# app/api/donations.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pymongo.database import Database
from pymongo.collection import Collection
from app.services.geo_enrich import ensure_location_and_geo


# ----- DB dependency (wired in app.main via dependency_overrides)
def get_db() -> Database:
    # this gets overridden in app.main
    raise RuntimeError("get_db() not wired")

# ----- Models
class Item(BaseModel):
    name: str
    qty: float
    unit: str

class Location(BaseModel):
    lat: float = 0
    lng: float = 0

class DonationIn(BaseModel):
    donor_name: str
    items: List[Item]
    address: Optional[str] = None
    location: Optional[Location] = None
    ready_after: Optional[str] = None

class DonationOut(BaseModel):
    id: str = Field(..., alias="id")
    donor_name: Optional[str] = None
    items: List[Item]
    address: Optional[str] = None
    location: Optional[Location] = None
    ready_after: Optional[str] = None
    created_at: Optional[datetime] = None
    status: Optional[str] = None
    driver_id: Optional[str] = None

router = APIRouter(prefix="/api/donations", tags=["donations"])

def col(db: Database) -> Collection:
    return db["donations"]

def _str_id(v) -> str:
    try:
        return str(v)
    except Exception:
        return ""

def _as_dt(v) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None

def _serialize(doc: dict) -> dict:
    if not doc:
        return {}
    return {
        "id": _str_id(doc.get("_id")),
        "donor_name": doc.get("donor_name") if isinstance(doc.get("donor_name"), (str, type(None))) else str(doc.get("donor_name")),
        "items": doc.get("items", []) or [],
        "address": doc.get("address"),
        "location": doc.get("location"),
        "ready_after": doc.get("ready_after"),
        "created_at": _as_dt(doc.get("created_at")),
        "status": doc.get("status"),
        "driver_id": _str_id(doc.get("driver_id")) if doc.get("driver_id") else None,
    }

@router.post("", status_code=status.HTTP_201_CREATED)
def create_donation(body: DonationIn, db: Database = Depends(get_db)):
    c = col(db)
    doc = {
        "donor_name": body.donor_name,
        "items": [i.model_dump() for i in body.items],
        "address": getattr(body, "address", None),  # ✅ keep address text
        "location": body.location.model_dump() if body.location else None,
        "ready_after": body.ready_after,
        "status": "open",
        "created_at": datetime.utcnow(),
    }

    # ✅ NEW: Convert address → coordinates if needed
    doc = ensure_location_and_geo(doc)

    ins = c.insert_one(doc)
    saved = c.find_one({"_id": ins.inserted_id})
    return {"donation": _serialize(saved)}

@router.get("", response_model=List[DonationOut])
def list_donations(db: Database = Depends(get_db)):
    data = list(col(db).find({}).sort("created_at", -1))
    return [_serialize(d) for d in data]

# ---------- Delivery ops ----------
@router.patch("/{donation_id}/assign_driver")
def assign_driver(
    donation_id: str,
    driver_id: str = Query(..., description="ObjectId of driver"),
    db: Database = Depends(get_db),
):
    try:
        _id = ObjectId(donation_id)
        _driver = ObjectId(driver_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid donation_id or driver_id")

    c = col(db)
    res = c.update_one({"_id": _id}, {"$set": {"driver_id": _driver, "status": "assigned"}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Donation not found")
    doc = c.find_one({"_id": _id})
    return {"ok": True, "donation": _serialize(doc)}

ValidStatus = {"planned", "assigned", "picked_up", "in_transit", "delivered", "canceled", "open", "closed"}

@router.patch("/{donation_id}/status")
def update_status(
    donation_id: str,
    status_q: str = Query(..., alias="status"),
    db: Database = Depends(get_db),
):
    if status_q not in ValidStatus:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {sorted(ValidStatus)}")
    try:
        _id = ObjectId(donation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid donation_id")

    c = col(db)
    res = c.update_one({"_id": _id}, {"$set": {"status": status_q}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Donation not found")
    doc = c.find_one({"_id": _id})
    return {"ok": True, "donation": _serialize(doc)}
