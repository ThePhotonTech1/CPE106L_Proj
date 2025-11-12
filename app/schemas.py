# app/schemas.py
from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

# --------------------------
# User & Auth Models
# --------------------------
Role = Literal["donor", "recipient", "driver", "admin"]

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: Role
    name: str

class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: Role
    name: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

# --------------------------
# Shared Submodels
# --------------------------
class Item(BaseModel):
    name: str
    qty: float
    unit: str
    # 🔽 Optional hints for matching (non-breaking)
    category: Optional[str] = None
    expiry_dt: Optional[datetime] = None
    perishable: Optional[bool] = None

class LatLng(BaseModel):
    lat: float
    lng: float

class TimeWindow(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None

# --------------------------
# Donations
# --------------------------
class DonationIn(BaseModel):
    donor_name: Optional[str] = None
    address: Optional[str] = None 
    items: List[Item]
    location: LatLng
    ready_after: datetime
    # 🔽 Optional pickup window (soft constraint)
    pickup_window: Optional[TimeWindow] = None

class DonationOut(BaseModel):
    id: str
    donor_id: Optional[str] = None
    donor_name: Optional[str] = None
    items: List[Item]
    location: LatLng
    ready_after: datetime
    status: Literal["open", "matched", "picked_up", "delivered"]
    pickup_window: Optional[TimeWindow] = None

# --------------------------
# Requests
# --------------------------
class RequestIn(BaseModel):
    ngo_name: Optional[str] = None
    address: Optional[str] = None
    needs: List[Item]
    location: LatLng
    # 🔽 Optional urgency/window
    priority: Optional[int] = 0
    delivery_window: Optional[TimeWindow] = None

class RequestOut(BaseModel):
    id: str
    recipient_id: Optional[str] = None
    ngo_name: Optional[str] = None
    needs: List[Item]
    location: LatLng
    status: Literal["open", "matched", "fulfilled"]
    priority: Optional[int] = 0
    delivery_window: Optional[TimeWindow] = None

# --------------------------
# Matching
# --------------------------
class MatchAllocation(BaseModel):
    donation_id: str
    request_id: str
    item_label: str                 # typically from Item.name
    category: Optional[str] = None
    qty: float                      # normalized (kg) or your canonical unit
    unit: str                       # canonical unit label (e.g., "kg")
    distance_km: float
    score: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MatchOut(BaseModel):
    id: str
    donation_id: str
    request_id: str
    score: float

class MatchRunResult(BaseModel):
    run_id: str
    created_at: datetime
    allocations: List[MatchAllocation]
    totals_by_item: Dict[str, float]
    totals_by_category: Dict[str, float] = {}
    summary: Dict[str, int]

# --------------------------
# Routing
# --------------------------
class RouteStop(BaseModel):
    lat: float
    lng: float
    label: Optional[str] = None

RouteType = Literal["pickup_then_drop", "pickup_only", "drop_only"]

class RoutePlanReq(BaseModel):
    stops: List[RouteStop]
    route_type: Optional[RouteType] = "pickup_then_drop"

class RoutePlanOut(BaseModel):
    distance_km: float
    duration_min: float
    steps: List[dict] = []

# --------------------------
# Stats
# --------------------------
class StatsOverview(BaseModel):
    total_donations: int
    total_requests: int
    delivered_count: int
    fulfilled_count: int
    top_donors: List[dict]


