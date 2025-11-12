# ---- donations (Mongo) ----
from datetime import datetime
from bson import ObjectId

async def insert_donation(doc: Dict) -> Dict:
    doc = dict(doc)
    doc.setdefault("status", "open")
    doc.setdefault("created_at", datetime.utcnow())
    res = await donations_col().insert_one(doc)
    # Normalize id for frontend (keep same shape as before if you used "id")
    return {**doc, "id": str(res.inserted_id)}

async def list_donations() -> List[Dict]:
    cur = donations_col().find().sort("created_at", -1)
    out: List[Dict] = []
    async for d in cur:
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out

# ---- requests (Mongo) ----
async def insert_request(doc: Dict) -> Dict:
    doc = dict(doc)
    doc.setdefault("status", "open")
    doc.setdefault("created_at", datetime.utcnow())
    res = await requests_col().insert_one(doc)
    return {**doc, "id": str(res.inserted_id)}

async def list_requests() -> List[Dict]:
    cur = requests_col().find().sort("created_at", -1)
    out: List[Dict] = []
    async for r in cur:
        r["id"] = str(r.pop("_id"))
        out.append(r)
    return out
