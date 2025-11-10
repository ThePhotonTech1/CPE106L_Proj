# app/routers/route_planning.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from app.core.security import get_current_user
from app.services.routing import plan_route as plan_route_service  # << alias to avoid name collision

router = APIRouter(prefix="/routes", tags=["routes"])

Coord = List[float]  # [lon, lat]

class Stop(BaseModel):
    id: str
    coord: Coord = Field(..., description="[lon, lat]")
    kind: Literal["donor","recipient","hub"] = "recipient"
    demand: Optional[float] = None

class PlanRequest(BaseModel):
    depot: Coord
    stops: List[Stop]
    vehicle_capacity: Optional[float] = None
    max_distance_km: Optional[float] = None
    objective: Literal["shortest_path","min_time","balanced"] = "shortest_path"

class Leg(BaseModel):
    from_id: str
    to_id: str
    distance_km: float
    eta_min: Optional[float] = None

class PlanResponse(BaseModel):
    ordered_stop_ids: List[str]
    legs: List[Leg]
    total_distance_km: float
    objective: str

def _plan_route(req: PlanRequest) -> PlanResponse:
    """
    Adapter: call your service and normalize to PlanResponse.
    Update the mapping if your service returns a different shape.
    """
    # Pass a plain dict; easier for services
    plan = plan_route_service(req.model_dump())

    # Accept either of these shapes from the service:
    #  A) {"ordered_stop_ids": [...], "legs":[{"from_id":...,"to_id":...,"distance_km":...,"eta_min":...}], "total_distance_km": ...}
    #  B) {"order": [...], "legs":[...], "total_km": ...}
    ordered = plan.get("ordered_stop_ids") or plan.get("order") or []
    raw_legs = plan.get("legs") or []
    total_km = plan.get("total_distance_km", plan.get("total_km", 0.0))

    legs: List[Leg] = []
    for lg in raw_legs:
        legs.append(
            Leg(
                from_id=lg.get("from_id"),
                to_id=lg.get("to_id"),
                distance_km=float(lg.get("distance_km", lg.get("km", 0.0))),
                eta_min=lg.get("eta_min"),
            )
        )

    return PlanResponse(
        ordered_stop_ids=ordered,
        legs=legs,
        total_distance_km=float(total_km),
        objective=req.objective,
    )

@router.post("/plan", response_model=PlanResponse)
async def plan_route_endpoint(body: PlanRequest, user=Depends(get_current_user)):
    if not body.stops:
        raise HTTPException(400, "No stops provided")
    return _plan_route(body)
