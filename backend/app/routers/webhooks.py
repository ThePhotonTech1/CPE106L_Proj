from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, AnyHttpUrl
from app.core.security import get_current_user, require_scopes
from app.core.db import db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

class HookIn(BaseModel):
    url: AnyHttpUrl
    enabled: bool = True

@router.post("/", dependencies=[Depends(require_scopes(["webhooks:manage"]))])
async def create_webhook(h: HookIn, user=Depends(get_current_user)):
    doc = {"org_id": user["org_id"], "url": str(h.url), "enabled": h.enabled}
    await db.webhooks.insert_one(doc)
    return {"created": True}

@router.get("/")
async def list_webhooks(user=Depends(get_current_user)):
    cur = db.webhooks.find({"org_id": user["org_id"]})
    return [ { "id": str(d["_id"]), "url": d["url"], "enabled": d.get("enabled", True) } async for d in cur ]

@router.delete("/{hook_id}", dependencies=[Depends(require_scopes(["webhooks:manage"]))])
async def delete_webhook(hook_id: str, user=Depends(get_current_user)):
    res = await db.webhooks.delete_one({"_id": hook_id, "org_id": user["org_id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}
