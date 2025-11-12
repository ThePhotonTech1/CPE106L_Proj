# app/api/drivers.py
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Literal
from pydantic import BaseModel
from bson import ObjectId
from app.db import donations_col, drivers_col   # we’ll use your db helper

router = APIRouter(prefix="/drivers", tags=["drivers"])

# ---------- Pydantic models ----------
class DriverIn(BaseModel):
    name: str
    contact: str
    vehicle: str
    availability: bool = True

class DriverOut(DriverIn):
    id: str

# helper to convert Mongo docs to DriverOut
def to_out(doc) -> DriverOut:
    return DriverOut(
        id=str(doc["_id"]),
        name=doc["name"],
        contact=doc["contact"],
        vehicle=doc["vehicle"],
        availability=doc.get("availability", True)
    )

# ---------- Routes ----------
@router.get("/", response_model=List[DriverOut])
async def list_drivers(available: Optional[bool] = Query(None)):
    query = {}
    if available is not None:
        query["availability"] = available
    cursor = drivers_col().find(query).sort("name", 1)
    return [to_out(doc) async for doc in cursor]

@router.post("/", response_model=DriverOut)
async def add_driver(driver: DriverIn):
    res = await drivers_col().insert_one(driver.dict())
    doc = await drivers_col().find_one({"_id": res.inserted_id})
    return to_out(doc)

@router.patch("/{driver_id}/availability")
async def set_availability(driver_id: str, available: bool):
    try:
        _id = ObjectId(driver_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    res = await drivers_col().update_one({"_id": _id}, {"$set": {"availability": available}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Driver not found")
    return {"updated": True}

@router.delete("/{driver_id}")
async def delete_driver(driver_id: str):
    try:
        _id = ObjectId(driver_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    res = await drivers_col().delete_one({"_id": _id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Driver not found")
    return {"deleted": True}

@router.patch("/{donation_id}/assign_driver")
async def assign_driver(donation_id: str, driver_id: str):
    """Assign a driver to a donation and mark as Assigned."""
    try:
        _don_id = ObjectId(donation_id)
        _drv_id = ObjectId(driver_id)
    except Exception:
        raise HTTPException(400, "Invalid ID format")

    driver = await drivers_col().find_one({"_id": _drv_id})
    if not driver:
        raise HTTPException(404, "Driver not found")

    donation = await donations_col().find_one({"_id": _don_id})
    if not donation:
        raise HTTPException(404, "Donation not found")

    # update donation with driver and status
    await donations_col().update_one(
        {"_id": _don_id},
        {"$set": {"driver_id": str(_drv_id), "status": "Assigned"}}
    )

    # mark driver unavailable
    await drivers_col().update_one({"_id": _drv_id}, {"$set": {"availability": False}})

    return {"assigned": True, "driver": driver["name"]}


# ----------- STATUS UPDATE -----------
ValidStatus = Literal[
    "Pending", "Assigned", "Picked Up", "In Transit", "Delivered", "Completed", "Cancelled"
]

@router.patch("/{donation_id}/status")
async def update_status(donation_id: str, status: ValidStatus):
    """Update donation status and free driver if completed/cancelled."""
    try:
        _don_id = ObjectId(donation_id)
    except Exception:
        raise HTTPException(400, "Invalid ID format")

    donation = await donations_col().find_one({"_id": _don_id})
    if not donation:
        raise HTTPException(404, "Donation not found")

    await donations_col().update_one({"_id": _don_id}, {"$set": {"status": status}})

    # free driver when done
    if status in ("Completed", "Cancelled") and donation.get("driver_id"):
        try:
            _drv_id = ObjectId(donation["driver_id"])
            await drivers_col().update_one({"_id": _drv_id}, {"$set": {"availability": True}})
        except Exception:
            pass

    return {"updated": True, "status": status}