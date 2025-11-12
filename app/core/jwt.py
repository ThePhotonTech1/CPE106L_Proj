# app/core/jwt.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from jose import jwt

# Use env vars in real use; hardcoded here for dev.
SECRET_KEY = "dev-secret-change-me"            # os.getenv("SECRET_KEY", "...")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def create_access_token(data: Dict[str, Any],
                        expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
