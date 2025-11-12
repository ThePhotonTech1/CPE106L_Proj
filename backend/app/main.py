# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ASCENDING, GEOSPHERE

# ---- Async Motor DB (used for indexes/backfill and other async routers)
from app.db import get_client
from app.db import get_db as mongo_get_db  # Motor-async DB

# ---- Existing routers
from app.api import auth
from app.routers import requests as requests_router
from app.routers import routes as routes_router
from app.routers import matching as matching_router
from app.routers import reports as reports_router
from app.routers import dispatch as dispatch_ro
from app.routers import admin_fix as admin_fix_router
from app.routers import dispatch as dispatch_router
from app.api import drivers

# (Optional) optimize router
try:
    from app.routers import optimize as optimize_router
    HAS_OPTIMIZE = True
except Exception:
    HAS_OPTIMIZE = False

# ======================================================================
# Donations API uses sync PyMongo under /api/donations
# Key point: import BOTH the module and the ORIGINAL dependency function.
# ======================================================================
import os
from pymongo import MongoClient
import app.api.donations as donations_api                    # router lives here
from app.api.donations import get_db as donations_dep_func   # ORIGINAL placeholder func object

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB  = os.getenv("MONGODB_DB", "foodbridge")

_sync_client = MongoClient(MONGODB_URI)

def get_db_sync():
    """Return a sync (pymongo) Database for donations endpoints."""
    return _sync_client[MONGODB_DB]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Use Motor async DB here (works with 'await')
    db = mongo_get_db()

    async def ensure_index(col, keys, name: str, **kwargs):
        existing = [ix["name"] async for ix in col.list_indexes()]
        if name in existing:
            return
        await col.create_index(keys, name=name, **kwargs)

    async def backfill_geo(col):
        cursor = col.find({
            "$or": [
                {"geo": {"$exists": False}},
                {"geo.type": {"$ne": "Point"}},
                {"geo.coordinates": {"$not": {"$type": "array"}}},
            ]
        })
        async for doc in cursor:
            loc = doc.get("location") or {}
            lat = loc.get("lat"); lng = loc.get("lng")
            def valid(x, y):
                try:
                    x = float(x); y = float(y)
                    return not (x == 0.0 and y == 0.0)
                except Exception:
                    return False

            if valid(lat, lng):
                geo = {"type": "Point", "coordinates": [float(lng), float(lat)]}
                await col.update_one({"_id": doc["_id"]}, {"$set": {"geo": geo}})
            else:
                # try geocoding if address exists
                addr = (doc.get("address") or "").strip()
                if addr:
                    from app.core.geocode import geocode_address, GeocodeError
                    try:
                        glat, glng = geocode_address(addr)
                        await col.update_one({"_id": doc["_id"]}, {
                            "$set": {
                                "location": {"lat": float(glat), "lng": float(glng)},
                                "geo": {"type": "Point", "coordinates": [float(glng), float(glat)]},
                            },
                            "$unset": {"_geocode_error": ""}
                        })
                    except GeocodeError as ex:
                        await col.update_one({"_id": doc["_id"]}, {
                            "$unset": {"geo": ""},
                            "$set": {"_geocode_error": str(ex)}
                        })
                else:
                    # no address; ensure we don't leave a bogus geo
                    await col.update_one({"_id": doc["_id"]}, {"$unset": {"geo": ""}})


    # Backfill legacy docs first (so 2dsphere can build)
    await backfill_geo(db.donations)
    await backfill_geo(db.requests)

    # Indexes
    await ensure_index(db.donations, [("status", ASCENDING)], "status_1")
    await ensure_index(db.donations, [("expires", ASCENDING)], "expires_1", sparse=True)
    await ensure_index(db.donations, [("geo", GEOSPHERE)], "geo_2dsphere")
    await ensure_index(db.requests,  [("geo", GEOSPHERE)], "geo_2dsphere")
    await ensure_index(db.transfers, [("timestamp", ASCENDING)], "timestamp_1")

    yield
    get_client().close()


# --- Create app FIRST ---
app = FastAPI(lifespan=lifespan, title="FoodBridge API")

# CRUCIAL: override the ORIGINAL dependency callable used in Depends(...)
# Don't override donations_api.get_db (that may be a different function object).
app.dependency_overrides[donations_dep_func] = get_db_sync

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Include routers ----------------
app.include_router(auth.router)

# IMPORTANT: include ONLY the new donations router (with PATCH).
# Do NOT include app.routers.donations anywhere else.
app.include_router(donations_api.router)        # /api/donations
app.include_router(dispatch_router.router)
app.include_router(requests_router.router)      # /api/requests
app.include_router(routes_router.router)        # /api/routes
app.include_router(matching_router.router)      # /api/matching
app.include_router(drivers.router)              # /drivers or /api/drivers (as defined)
app.include_router(admin_fix_router.router)
app.include_router(reports_router.router)       # /reports
if HAS_OPTIMIZE:
    app.include_router(optimize_router.router)  # /optimize

# ---------- Compatibility shims (OLD paths) ----------
from app.db import insert_request as _ins_req, list_requests as _list_req

@app.post("/requests", status_code=201)
async def _compat_create_request(body: dict):
    created = await _ins_req(body)
    return {
        "request": {
            "id": created.get("id"),
            "ngo_name": created.get("ngo_name"),
            "needs": created.get("needs", []),
            "address": created.get("address"),
            "location": created.get("location", {}),
            "created_at": created.get("created_at"),
        }
    }

@app.get("/requests")
async def _compat_get_requests():
    return await _list_req()
# -----------------------------------------------------

# Health
@app.get("/health")
def health():
    return {"ok": True}
