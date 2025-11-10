# app/db.py
from typing import Dict, List
import itertools
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB", "foodbridge")

# simple in-memory stores (replace with Mongo later)
_donation_seq = itertools.count(1)
_request_seq  = itertools.count(1)

_client: AsyncIOMotorClient | None = None

def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGODB_URI)
    return _client

def get_db():
    return get_client()[DB_NAME]


DONATIONS: List[Dict] = []
REQUESTS:  List[Dict] = []

# ---- donations ----
def insert_donation(doc: Dict) -> Dict:
    doc = dict(doc)
    doc["_id"] = str(next(_donation_seq))
    # default status if not set
    doc.setdefault("status", "open")
    DONATIONS.append(doc)
    return doc

def list_donations() -> List[Dict]:
    return list(DONATIONS)

# ---- requests ----
def insert_request(doc: Dict) -> Dict:
    doc = dict(doc)
    doc["_id"] = str(next(_request_seq))
    doc.setdefault("status", "open")
    REQUESTS.append(doc)
    return doc

def list_requests() -> List[Dict]:
    return list(REQUESTS)

