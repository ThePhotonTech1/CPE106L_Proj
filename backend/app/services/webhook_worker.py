import asyncio
from datetime import datetime, timedelta
import httpx
from app.core.db import db

async def deliver_one(rec: dict):
    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        headers = {
            "Content-Type": "application/json",
            "X-FoodBridge-Signature": rec["sig"]
        }
        r = await client.post(rec["target"], json=rec["body"], headers=headers)
        return r.status_code

async def run_outbox_loop():
    while True:
        now = datetime.utcnow()
        rec = await db.outbox.find_one_and_update(
            {"status": "pending", "next_try_at": {"$lte": now}},
            {"$set": {"status": "delivering"}},
        )
        if not rec:
            await asyncio.sleep(0.5)
            continue

        status = None
        try:
            status = await deliver_one(rec)
        except Exception:
            status = None

        if status and 200 <= status < 300:
            await db.outbox.update_one({"_id": rec["_id"]}, {"$set": {"status": "delivered", "delivered_at": datetime.utcnow()}})
        else:
            attempts = rec.get("attempts", 0) + 1
            delay = min(60, 2 ** attempts)  # backoff up to 60s
            await db.outbox.update_one({"_id": rec["_id"]}, {
                "$set": {
                    "status": "pending",
                    "attempts": attempts,
                    "next_try_at": datetime.utcnow() + timedelta(seconds=delay)
                }
            })
