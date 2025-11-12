from datetime import datetime, timedelta
from typing import List, Dict, Any
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.db import db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hash_password(password: str) -> str:
    return pwd_context.hash((password or "")[:72])

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify((password or "")[:72], hashed)

def create_token(payload: Dict[str, Any], minutes: int):
    payload = dict(payload)
    payload["exp"] = datetime.utcnow() + timedelta(minutes=minutes)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)

def decode_token(token: str):
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    data = decode_token(token)
    user = await db.users.find_one({"_id": data["sub"]})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_scopes(required: List[str]):
    async def checker(user=Depends(get_current_user)):
        user_scopes = user.get("scopes", [])
        if "*" not in user_scopes and not set(required).issubset(set(user_scopes)):
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return user
    return checker
