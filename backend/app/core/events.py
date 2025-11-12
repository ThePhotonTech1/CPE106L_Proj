from datetime import datetime
import hmac, hashlib, json
from typing import Any, Dict
from app.core.db import db
from app.core.config import settings

def _sign(body: Dict[str, Any]) -> str:
    secret = settings.jwt_secret.encode()
    msg = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()

async def emit_event(org_id: str, type_: str, data: Dict[str, Any]):
    evt = {
        "org_id": org_id,
        "type": type_,
        "data": data,
        "created_at": datetime.utcnow(),
    }
    await db.events.insert_one(evt)

    # fan-out to webhooks via outbox
    hooks = db.webhooks.find({"org_id": org_id, "enabled": True})
    async for h in hooks:
        body = {
            "type": type_,
            "org_id": org_id,
            "data": data,
            "created_at": evt["created_at"].isoformat() + "Z"
        }
        await db.outbox.insert_one({
            "org_id": org_id,
            "target": h["url"],
            "body": body,
            "sig": _sign(body),
            "attempts": 0,
            "max_attempts": 6,
            "next_try_at": datetime.utcnow(),
            "status": "pending"
        })
