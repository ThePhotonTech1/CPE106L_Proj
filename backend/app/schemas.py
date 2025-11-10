from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr
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

class LatLng(BaseModel):
    lat: float
    lng: float

# --------------------------
# Donations
# --------------------------
class DonationIn(BaseModel):
    donor_name: Optional[str] = None   # ✅ added
    items: List[Item]
    location: LatLng
    ready_after: datetime

class DonationOut(BaseModel):
    id: str
    donor_id: Optional[str] = None
    donor_name: Optional[str] = None   # ✅ include in output too
    items: List[Item]
    location: LatLng
    ready_after: datetime
    status: Literal["open", "matched", "picked_up", "delivered"]

# --------------------------
# Requests
# --------------------------
class RequestIn(BaseModel):
    ngo_name: Optional[str] = None     # ✅ added
    needs: List[Item]
    location: LatLng

class RequestOut(BaseModel):
    id: str
    recipient_id: Optional[str] = None
    ngo_name: Optional[str] = None     # ✅ include in output too
    needs: List[Item]
    location: LatLng
    status: Literal["open", "matched", "fulfilled"]

# --------------------------
# Matching
# --------------------------
class MatchOut(BaseModel):
    id: str
    donation_id: str
    request_id: str
    score: float

# --------------------------
# Routing
# --------------------------
class RouteStop(BaseModel):
    lat: float
    lng: float
    label: Optional[str] = None

class RoutePlanReq(BaseModel):
    stops: List[RouteStop]

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
