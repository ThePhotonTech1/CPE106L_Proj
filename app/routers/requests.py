# app/routers/requests.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from app.utils.geocode import geocode_address
from app.db import insert_request, list_requests
from app.services.geo_enrich import ensure_location_and_geo  # ✅ NEW

router = APIRouter(prefix="/api/requests", tags=["requests"])


class NeedItem(BaseModel):
    name: str
    qty: float
    unit: str


class Location(BaseModel):
    lat: float = 0
    lng: float = 0


class RequestIn(BaseModel):
    ngo_name: str
    needs: List[NeedItem]
    address: Optional[str] = None
    # You can keep this default (0,0) — ensure_location_and_geo treats 0,0 as invalid and will geocode.
    # If you prefer, make it Optional[Location] = None.
    location: Location = Field(default_factory=Location)


from app.utils.geocode import geocode_address

@router.post("", status_code=201)
async def create_request(body: RequestIn):
    loc = body.location.model_dump() if body.location else None
    if (not loc) or (float(loc.get("lat", 0)) == 0 and float(loc.get("lng", 0)) == 0):
        g = geocode_address(body.address or "")
        if g:
            loc = g

    doc = {
        "ngo_name": body.ngo_name,
        "needs": [n.model_dump() for n in body.needs],
        "address": body.address,
        "location": loc or {"lat": None, "lng": None},
        "status": "open",                       # <-- ensure open
        "created_at": datetime.utcnow(),        # optional but nice
    }
    created = await insert_request(doc)
    return {
        "request": {
            "id": created.get("id"),
            "ngo_name": created["ngo_name"],
            "needs": created["needs"],
            "address": created.get("address"),
            "location": created["location"],
            "status": created.get("status", "open"),
            "created_at": created.get("created_at"),
        }
    }


@router.get("")
async def get_requests():
    docs = await list_requests()
    out = []
    for r in docs:
        out.append({
            "id": r.get("id"),
            "ngo_name": r.get("ngo_name"),
            "needs": r.get("needs", []),
            "address": r.get("address"),
            "location": r.get("location", {}),
            "created_at": r.get("created_at"),
        })
    return out
