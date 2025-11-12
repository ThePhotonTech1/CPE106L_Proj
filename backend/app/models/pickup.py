from pydantic import BaseModel
from typing import Optional, List, Literal, Any
from datetime import datetime

Status = Literal["created","scheduled","en_route","picked_up","delivered","verified","closed","canceled"]

class PickupCreate(BaseModel):
    address: str
    window: Optional[str] = None
    notes: Optional[str] = None

class StatusEvent(BaseModel):
    at: datetime
    by_user: str
    from_status: Optional[Status]
    to_status: Status
    note: Optional[str] = None
    meta: Optional[dict[str, Any]] = None

class PickupOut(BaseModel):
    id: str
    org_id: str
    status: Status
    driver_id: Optional[str] = None
    version: int
    history: List[StatusEvent] = []
