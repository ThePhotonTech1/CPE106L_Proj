from pydantic import BaseModel, EmailStr
from typing import List, Literal

OrgType = Literal["donor", "recipient", "logistics", "admin"]

class OrgIn(BaseModel):
    name: str
    type: OrgType

# EITHER:
from pydantic import BaseModel, EmailStr, SecretStr
class UserCreate(BaseModel):
    email: EmailStr
    password: SecretStr
    org_id: str
    roles: list[str] = []

