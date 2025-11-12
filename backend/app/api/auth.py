# app/api/auth.py
from fastapi import APIRouter, HTTPException, Form
from pydantic import BaseModel, EmailStr
from passlib.hash import pbkdf2_sha256 as hasher
from pymongo.errors import DuplicateKeyError

from app.db import users_collection
from app.core.jwt import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ---------- Models ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    role: str = "donor"
    org_name: str | None = None

# ---------- Shared impl ----------
async def _do_register(email: str, password: str, role: str, org_name: str | None):
    # Ensure unique index for email (safe to call repeatedly)
    await users_collection.create_index("email", unique=True)

    try:
        await users_collection.insert_one({
            "email": email,
            "password_hash": hasher.hash(password),
            "role": role,
            "org_name": org_name or ""
        })
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Email already registered")

    token = create_access_token({"sub": email, "role": role, "email": email})
    return {"access_token": token, "token_type": "bearer", "role": role, "email": email}

# ---------- Register (JSON) — shown in Swagger ----------
@router.post("/register")
async def register_json(body: RegisterIn):
    return await _do_register(body.email, body.password, body.role, body.org_name)

# ---------- Register (Form) — hidden from Swagger; used by Flet ----------
@router.post("/register", include_in_schema=False)
async def register_form(
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("donor"),
    org_name: str = Form(None)
):
    return await _do_register(email, password, role, org_name)

# ---------- Login (Form) ----------
@router.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    user = await users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored = user.get("password_hash", "")
    try:
        ok = hasher.verify(password, stored)
    except Exception:
        # covers empty/legacy/invalid hash formats
        ok = False

    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role = user.get("role", "donor")
    token = create_access_token({"sub": email, "role": role, "email": email})
    return {"access_token": token, "token_type": "bearer", "role": role, "email": email}
