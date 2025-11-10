# app/routers/routes.py
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.maps_ors import (
    ors_geocode,
    ors_matrix,
    ors_directions,
    greedy_order,
)

router = APIRouter(prefix="/api/routes", tags=["routes"])

class OptimizeByAddressRequest(BaseModel):
    addresses: List[str] = Field(..., min_items=2, description="Origin first, then stops")

@router.get("/history")
async def history(limit: int = 20):
    # TODO: read from Mongo if you have it; simple empty for now
    return {"routes": []}

@router.post("/optimize_by_address")
async def optimize_by_address(body: OptimizeByAddressRequest):
    addresses = body.addresses

    # 1) geocode each address (origin first)
    coords = []
    for addr in addresses:
        c = await ors_geocode(addr)
        if not c:
            raise HTTPException(status_code=400, detail=f"Cannot geocode: {addr}")
        coords.append((c["lat"], c["lng"], addr))

    # 2) build distance matrix (meters, seconds) using straight-line * factor
    matrix = await ors_matrix([(lat, lng) for (lat, lng, _) in coords])
    if not matrix:
        raise HTTPException(status_code=400, detail="Distance matrix failed")

    # 3) route order via greedy (origin index 0 fixed)
    order = greedy_order(matrix)

    ordered = [coords[i] for i in order]
    ordered_labels = [lab for (_, _, lab) in ordered]

    # 4) “directions” summary (sum)
    summary = await ors_directions([(lat, lng) for (lat, lng, _) in ordered])

    return {
        "ordered_labels": ordered_labels,
        "distance_m": summary["distance_m"],
        "duration_s": summary["duration_s"],
        # map image is optional (GUI checks existence)
        "map_png_base64": summary.get("map_png_base64"),
    }
