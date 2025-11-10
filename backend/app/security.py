# app/security.py
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
import os

SECRET = os.getenv("JWT_SECRET", "dev")
ALG = os.getenv("JWT_ALG", "HS256")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p: str) -> str:
    return pwd_ctx.hash(p)

def verify_password(p: str, h: str) -> bool:
    return pwd_ctx.verify(p, h)

def create_token(sub: str, minutes: int = 120) -> str:
    now = datetime.utcnow()
    payload = {"sub": sub, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, SECRET, algorithm=ALG)

def decode_token(token: str) -> Optional[str]:
    try:
        data = jwt.decode(token, SECRET, algorithms=[ALG])
        return data.get("sub")
    except JWTError:
        return None
