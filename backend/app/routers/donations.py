from fastapi import APIRouter, Depends
from app.repositories.donations import create_donation, list_my_donations, list_available
from datetime import datetime

router = APIRouter(prefix="/donations", tags=["donations"])

@router.get("/mine")
async def mine(current_user=Depends(...)):     # your auth dep
    return await list_my_donations(current_user["id"])

@router.get("/available")
async def available():
    return await list_available()

@router.post("")
async def create(payload: dict, current_user=Depends(...)):
    doc = {
        "donor_id": current_user["id"],
        "item_name": payload["item_name"],
        "quantity": payload["quantity"],
        "expires": payload["expires"],
        "pickup_window": payload.get("pickup_window", {}),
        "status": "available",
        "created_at": datetime.utcnow(),
    }
    new_id = await create_donation(doc)
    return {"id": new_id}
