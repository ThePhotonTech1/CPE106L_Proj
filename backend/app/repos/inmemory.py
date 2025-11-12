# app/repos/inmemory.py
import uuid
from collections import defaultdict
from typing import Optional, List, Dict

def _id() -> str:
    return uuid.uuid4().hex

class InMemoryRepo:
    def __init__(self):
        self.users: Dict[str, dict] = {}
        self.users_by_email: Dict[str, str] = {}
        self.donations: Dict[str, dict] = {}
        self.requests: Dict[str, dict] = {}
        self.matches: Dict[str, dict] = {}

    # Users
    async def create_user(self, email: str, password_hash: str, role: str, name: str) -> dict:
        if email in self.users_by_email:
            raise ValueError("Email exists")
        uid = _id()
        doc = {"_id": uid, "email": email, "password_hash": password_hash, "role": role, "name": name}
        self.users[uid] = doc
        self.users_by_email[email] = uid
        return doc

    async def find_user_by_email(self, email: str) -> Optional[dict]:
        uid = self.users_by_email.get(email)
        return self.users.get(uid) if uid else None

    # Donations
    async def create_donation(self, donor_id: str, items: list, location: dict, ready_after) -> dict:
        did = _id()
        doc = {"_id": did, "donor_id": donor_id, "items": items, "location": location,
               "ready_after": ready_after, "status": "open"}
        self.donations[did] = doc
        return doc

    async def list_donations(self, status: Optional[str] = None) -> List[dict]:
        vals = self.donations.values()
        return [d for d in vals if (status is None or d["status"] == status)]

    async def update_donation_status(self, donation_id: str, status: str):
        if donation_id in self.donations:
            self.donations[donation_id]["status"] = status

    # Requests
    async def create_request(self, recipient_id: str, needs: list, location: dict) -> dict:
        rid = _id()
        doc = {"_id": rid, "recipient_id": recipient_id, "needs": needs, "location": location,
               "status": "open"}
        self.requests[rid] = doc
        return doc

    async def list_requests(self, status: Optional[str] = None) -> List[dict]:
        vals = self.requests.values()
        return [r for r in vals if (status is None or r["status"] == status)]

    async def update_request_status(self, request_id: str, status: str):
        if request_id in self.requests:
            self.requests[request_id]["status"] = status

    # Matches
    async def insert_match(self, donation_id: str, request_id: str, score: float) -> dict:
        mid = _id()
        doc = {"_id": mid, "donation_id": donation_id, "request_id": request_id, "score": score}
        self.matches[mid] = doc
        return doc

    # Stats
    async def count_donations(self) -> int: return len(self.donations)
    async def count_requests(self) -> int: return len(self.requests)
    async def count_delivered(self) -> int:
        return sum(1 for d in self.donations.values() if d["status"] == "delivered")
    async def count_fulfilled(self) -> int:
        return sum(1 for r in self.requests.values() if r["status"] == "fulfilled")
    async def top_donors(self, limit=5) -> list:
        by = defaultdict(int)
        for d in self.donations.values(): by[d["donor_id"]] += 1
        top = sorted(([k,v] for k,v in by.items()), key=lambda x: x[1], reverse=True)[:limit]
        return [{"donor_id": k, "count": v} for k,v in top]
