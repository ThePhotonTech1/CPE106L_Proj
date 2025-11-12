from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request
from app.core.db import db
import hashlib, json, time

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in SAFE_METHODS:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)

        # tie to path+method to avoid cross-endpoint collisions
        scope_key = f"{request.method}:{request.url.path}:{key}"
        digest = hashlib.sha256(scope_key.encode()).hexdigest()

        found = await db.idempotency.find_one({"_id": digest})
        if found:
            return JSONResponse(found["resp"], status_code=found["status"])

        # run once, store
        response = await call_next(request)

        # Only cache successful 2xx responses
        if 200 <= response.status_code < 300:
            # We need body content: clone if possible
            body = getattr(response, "body_iterator", None)
            try:
                # best-effort: use Response.body if available (most FastAPI JSON)
                content = b""
                if hasattr(response, "body"):
                    content = response.body or b""
                elif body:
                    # consume iterator into bytes (rarely needed)
                    chunks = [chunk async for chunk in body]
                    content = b"".join(chunks)
                    response.body_iterator = iter([content])  # re-inject
                try:
                    payload = json.loads(content.decode() or "{}")
                except Exception:
                    payload = {"raw": content.decode(errors="ignore")}
                await db.idempotency.insert_one({
                    "_id": digest,
                    "status": response.status_code,
                    "resp": payload,
                    "ts": time.time(),
                    "path": request.url.path,
                    "method": request.method,
                })
            except Exception:
                pass
        return response
