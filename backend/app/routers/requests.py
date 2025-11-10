# app/routers/requests.py
from fastapi import APIRouter
from app.schemas import RequestIn, RequestOut
from ..db import insert_request, list_requests

router = APIRouter()

def _serialize(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "recipient_id": doc.get("recipient_id"),
        "ngo_name": doc.get("ngo_name"),           # always returned
        "needs": doc.get("needs", []),
        "location": doc.get("location"),
        "status": doc.get("status", "open"),
    }

@router.post("/requests", response_model=RequestOut)
def create_request(payload: RequestIn):
    doc = payload.model_dump()

    # 🧰 Back-compat / safety: accept either "ngo_name" or legacy "ngo"
    if not doc.get("ngo_name"):
        # if some older client sends {"ngo": "..."} we still store it
        legacy = doc.pop("ngo", None) if isinstance(doc, dict) else None
        if legacy:
            doc["ngo_name"] = legacy

    saved = insert_request(doc)
    return _serialize(saved)

@router.get("/requests", response_model=list[RequestOut])
def get_requests():
    return [_serialize(x) for x in list_requests()]
