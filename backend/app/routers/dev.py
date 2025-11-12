from fastapi import APIRouter, Request

router = APIRouter(prefix="/dev", tags=["dev"])

@router.post("/webhook-sink")
async def webhook_sink(req: Request):
    body = await req.json()
    sig  = req.headers.get("X-FoodBridge-Signature")
    print("[WEBHOOK SINK] sig=", sig, " body=", body)
    return {"ok": True}
