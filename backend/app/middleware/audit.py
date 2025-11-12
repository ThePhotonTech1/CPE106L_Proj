from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.db import db
import time

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        try:
            user_id = getattr(request.state, "user_id", None)
        except Exception:
            user_id = None
        entry = {
            "ts": time.time(),
            "path": request.url.path,
            "method": request.method,
            "status": response.status_code,
            "user_id": user_id,
            "ip": request.client.host if request.client else None,
            "ua": request.headers.get("user-agent"),
            "latency_ms": int((time.time() - start) * 1000),
        }
        await db.audit.insert_one(entry)
        return response
