# app/db.py
from __future__ import annotations

import os
import itertools
from datetime import datetime
from typing import Dict, List, Iterable, Union
from functools import lru_cache

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

# --------------------------------------------------
# MongoDB Connection (env with safe defaults)
# --------------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
MONGODB_DB  = os.getenv("MONGODB_DB", "foodbridge")  # single source of truth

@lru_cache(maxsize=1)
def get_client() -> AsyncIOMotorClient:
    # Cached to play nicely with uvicorn --reload
    return AsyncIOMotorClient(MONGODB_URI)

def get_db():
    return get_client()[MONGODB_DB]

# --------------------------------------------------
# Collections (helpers; no work at import time)
# --------------------------------------------------
def col(name: str):
    return get_db()[name]

def users_col():
    return col("users")

def donors_col():
    return col("donors")

def recipients_col():
    return col("recipients")

def donations_col():
    return col("donations")

def requests_col():
    return col("requests")

def transfers_col():
    return col("transfers")

def drivers_col():
    return col("drivers")

# --------------------------------------------------
# In-memory fallback (legacy; kept for compatibility)
# --------------------------------------------------
_donation_seq = itertools.count(1)
_request_seq  = itertools.count(1)

DONATIONS: List[Dict] = []
REQUESTS: List[Dict] = []

# --------------------------------------------------
# Donations
# --------------------------------------------------
async def insert_donation(doc: Dict) -> Dict:
    """Insert donation to MongoDB and return the inserted document."""
    doc = dict(doc)
    doc.setdefault("status", "open")
    doc.setdefault("created_at", datetime.utcnow())

    res = await donations_col().insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return doc

async def list_donations() -> List[Dict]:
    """List all donations (most recent first)."""
    items: List[Dict] = []
    cur = donations_col().find().sort("created_at", -1)
    async for d in cur:
        d["id"] = str(d.pop("_id"))
        items.append(d)
    return items

# --------------------------------------------------
# Requests
# --------------------------------------------------
async def insert_request(doc: Dict) -> Dict:
    """Insert request to MongoDB and return the inserted document."""
    doc = dict(doc)
    doc.setdefault("status", "open")
    doc.setdefault("created_at", datetime.utcnow())

    res = await requests_col().insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return doc

async def list_requests() -> List[Dict]:
    """List all requests (most recent first)."""
    items: List[Dict] = []
    cur = requests_col().find().sort("created_at", -1)
    async for r in cur:
        r["id"] = str(r.pop("_id"))
        items.append(r)
    return items

# --------------------------------------------------
# Transfers
# --------------------------------------------------
async def insert_transfers(docs: Union[Dict, Iterable[Dict], List[Dict]]) -> int:
    """
    Robust bulk insert:
      - Accepts dict, list of dicts, or any iterable of dicts.
      - Adds timestamp if missing.
      - Returns number of inserted docs.
    """
    if isinstance(docs, dict):
        docs = [docs]
    else:
        try:
            docs = list(docs)  # handles list or any iterable
        except TypeError:
            return 0

    docs = [d for d in docs if isinstance(d, dict)]

    now = datetime.utcnow()
    for d in docs:
        d.setdefault("timestamp", now)

    if not docs:
        return 0

    res = await transfers_col().insert_many(docs)
    return len(res.inserted_ids)

async def list_transfers() -> List[Dict]:
    """Return all transfers sorted by timestamp (newest first)."""
    items: List[Dict] = []
    cur = transfers_col().find().sort("timestamp", -1)
    async for t in cur:
        t["id"] = str(t.pop("_id"))
        items.append(t)
    return items

async def decrement_donation_items(donation_id: str, items: List[Dict]) -> None:
    """
    Subtract matched quantities from a donation's items.
    Closes the donation (status='closed') if all item qty <= 0.
    """
    try:
        _oid = ObjectId(donation_id)
    except Exception:
        return  # invalid id format; noop

    doc = await donations_col().find_one({"_id": _oid})
    if not doc:
        return

    # build name -> qty_to_subtract
    to_sub: Dict[str, float] = {}
    for it in items:
        name = str(it.get("name", "")).lower()
        to_sub[name] = to_sub.get(name, 0.0) + float(it.get("qty", 0) or 0)

    new_items: List[Dict] = []
    for it in doc.get("items", []):
        name = str(it.get("name", "")).lower()
        qty = float(it.get("qty", 0) or 0) - float(to_sub.get(name, 0.0))
        if qty < 0:
            qty = 0.0
        new_items.append({**it, "qty": qty})

    all_zero = all(float(i.get("qty", 0) or 0) <= 0 for i in new_items) 

    await donations_col().update_one(
        {"_id": _oid},
        {"$set": {"items": new_items, "status": new_status}}
    )

# --- Back-compat lazy collection shims (avoid import-time DB work) ---
class _LazyCol:
    def __init__(self, name: str):
        self._name = name
    def __getattr__(self, attr):
        # defer attribute access to the real Motor collection at call time
        return getattr(col(self._name), attr)

# legacy names some modules might import
users_collection     = _LazyCol("users")
donations_collection = _LazyCol("donations")
requests_collection  = _LazyCol("requests")
transfers_collection = _LazyCol("transfers")
drivers_collection   = _LazyCol("drivers")  # future-proof

# --------------------------------------------------
# Exports
# --------------------------------------------------
__all__ = [
    "get_client",
    "get_db",
    # collection helpers
    "users_col",
    "donors_col",
    "recipients_col",
    "donations_col",
    "requests_col",
    "transfers_col",
    "drivers_col",
    # ops
    "insert_donation",
    "list_donations",
    "insert_request",
    "list_requests",
    "insert_transfers",
    "list_transfers",
    "decrement_donation_items",
]
