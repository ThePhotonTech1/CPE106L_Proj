# app/routers/admin_fix.py
from fastapi import APIRouter
from app.db import get_db
from app.services.geo_enrich import ensure_location_and_geo

router = APIRouter(prefix="/admin/fix", tags=["admin"])

@router.post("/geos")
async def fix_geos():
    db = get_db()
    fixed = {"donations": 0, "requests": 0}

    async def fix_col(col_name):
        count = 0
        col = getattr(db, col_name)
        # candidates: geo missing or equals [0,0]
        cur = col.find({
            "$or": [
                {"geo": {"$exists": False}},
                {"geo.coordinates": [0,0]}
            ]
        })
        async for doc in cur:
            new_doc = ensure_location_and_geo(doc.copy())
            if new_doc.get("geo") and new_doc.get("location"):
                await col.update_one({"_id": doc["_id"]}, {
                    "$set": {
                        "location": new_doc["location"],
                        "geo": new_doc["geo"]
                    },
                    "$unset": {"_geocode_error": ""}
                })
                count += 1
        return count

    fixed["donations"] = await fix_col("donations")
    fixed["requests"]  = await fix_col("requests")
    return {"fixed": fixed}
