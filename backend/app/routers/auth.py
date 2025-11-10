from fastapi import APIRouter, Depends, HTTPException, Header
from ..deps import get_repo
from ..schemas import UserCreate, UserOut, LoginIn, TokenOut
from ..security import hash_password, verify_password, create_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserOut)
async def register(user: UserCreate, repo=Depends(get_repo)):
    exists = await repo.find_user_by_email(user.email)
    if exists:
        raise HTTPException(400, "Email already registered")
    doc = await repo.create_user(user.email, hash_password(user.password), user.role, user.name)
    return {"id": doc["_id"], "email": doc["email"], "role": doc["role"], "name": doc["name"]}

@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, repo=Depends(get_repo)):
    user = await repo.find_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(user["_id"])
    return {"access_token": token}

async def get_user_id(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing token")
    sub = decode_token(authorization.split(" ",1)[1])
    if not sub:
        raise HTTPException(401, "Invalid token")
    return sub
