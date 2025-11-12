# app/services/matching.py
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone
from math import radians, sin, cos, asin, sqrt

from bson import ObjectId

from app.core.db import get_db
from app.services.units import to_kg
from app.schemas import MatchAllocation

EARTH_RADIUS_KM = 6371.0

def oid_to_str(x) -> str:
    if isinstance(x, ObjectId):
        return str(x)
    return str(x)

def haversine_km(lat1, lng1, lat2, lng2) -> float:
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    c = 2 * asin(sqrt(a))
    return EARTH_RADIUS_KM * c

def time_windows_overlap(pickup_window: Optional[dict], ready_after: Optional[datetime],
                         delivery_window: Optional[dict]) -> bool:
    """
    If any is None => treat as flexible.
    Otherwise check rough overlap between pickup (ready_after -> pickup_window.end) and delivery window.
    """
    if delivery_window is None:
        return True
    # Derive pickup start: max(ready_after, pickup_window.start or ready_after)
    pickup_start = ready_after
    pickup_end = None
    if pickup_window:
        s = pickup_window.get("start")
        e = pickup_window.get("end")
        if s and (pickup_start is None or s > pickup_start):
            pickup_start = s
        pickup_end = e
    # If we still have neither, consider flexible
    if pickup_start is None and pickup_end is None:
        return True
    d_start = delivery_window.get("start")
    d_end = delivery_window.get("end")
    # Basic overlap tests
    if pickup_start and d_end and pickup_start > d_end:
        return False
    if d_start and pickup_end and d_start > pickup_end:
        return False
    return True

def qty_fit_ratio(need_qty: float, offer_qty: float) -> float:
    if need_qty <= 0 or offer_qty <= 0:
        return 0.0
    m = min(need_qty, offer_qty)
    return m / max(need_qty, offer_qty)

def compute_score(distance_km: float, qty_fit: float, hours_to_expiry: Optional[float], priority: int) -> float:
    dist_term = max(0.0, 1.0 - (distance_km / 20.0))     # prefer closer; fade after ~20km
    qty_term = max(0.0, min(1.0, qty_fit))               # [0..1]
    expiry_term = 0.0
    if hours_to_expiry is not None:
        expiry_term = max(0.0, 1.0 - min(hours_to_expiry, 72.0)/72.0)  # urgent if <72h
    priority_term = min(1.0, max(0.0, (priority or 0)/5.0))
    return 0.35*qty_term + 0.30*dist_term + 0.20*expiry_term + 0.15*priority_term

def earliest_expiry_hours(items: List[dict], label: str, now: datetime) -> Optional[float]:
    # If any donation item for this label has an expiry_dt, use the earliest
    exps = [
        it["expiry_dt"] for it in items
        if (it.get("name", "").strip().lower() == label and it.get("expiry_dt"))
    ]
    if not exps:
        return None
    earliest = min(exps)
    return (earliest - now).total_seconds() / 3600.0

def canon_label(name: str) -> str:
    return (name or "").strip().lower()

def sum_qty_kg(items: List[dict]) -> float:
    return sum(to_kg(float(it.get("qty", 0.0)), it.get("unit", "kg")) for it in items)

async def fetch_open(db):
    donations = await db.donations.find({"status": "open"}).to_list(length=10000)
    requests = await db.requests.find({"status": "open"}).to_list(length=10000)
    return donations, requests

def materialize_remaining(donations, requests):
    """
    Build per-label (item name) remaining maps in kg for donations (supply) and requests (need).
    """
    for d in donations:
        rem: Dict[str, float] = {}
        for it in d.get("items", []):
            label = canon_label(it.get("name", ""))
            rem[label] = rem.get(label, 0.0) + to_kg(float(it.get("qty", 0.0)), it.get("unit", "kg"))
        d["_remaining_kg"] = rem

    for r in requests:
        need: Dict[str, float] = {}
        for it in r.get("needs", []):
            label = canon_label(it.get("name", ""))
            need[label] = need.get(label, 0.0) + to_kg(float(it.get("qty", 0.0)), it.get("unit", "kg"))
        r["_remaining_kg"] = need

def request_sort_key(r):
    prio = r.get("priority", 0) or 0
    dwin = r.get("delivery_window") or {}
    start = dwin.get("start")
    total_need = sum(r.get("_remaining_kg", {}).values())
    # Sort: higher prio first, earlier start first, more total need first
    return (-prio, start or datetime.max.replace(tzinfo=timezone.utc), -total_need)

async def apply_allocations(db, allocations: List[MatchAllocation]):
    if not allocations:
        return

    # Insert matches
    docs = [a.model_dump() for a in allocations]
    if docs:
        await db.matches.insert_many(docs)

    # Group decrements (kg) by (doc_id, item_label)
    dec_don: Dict[Tuple[str, str], float] = {}
    dec_req: Dict[Tuple[str, str], float] = {}
    for a in allocations:
        key_d = (a.donation_id, a.item_label)
        key_r = (a.request_id, a.item_label)
        dec_don[key_d] = dec_don.get(key_d, 0.0) - float(a.qty)  # negative for $inc on kg
        dec_req[key_r] = dec_req.get(key_r, 0.0) - float(a.qty)

    # Decrement array items by matching name; use arrayFilters to target label
    # We keep the original units in DB; we decrement in kg-equivalent proportionally via a helper pass:
    # Simpler approach: decrement the first matching item in kg->native unit conversion proportionally.
    # To avoid complex proportional splits, we’ll do a small loop per affected doc.

    # Donations
    for (don_id, label), total_dec_kg in dec_don.items():
        doc = await db.donations.find_one({"_id": ObjectId(don_id)})
        if not doc:
            continue
        remaining = float(-total_dec_kg)  # positive amount to take (kg)
        items = doc.get("items", [])
        changed = False
        for it in items:
            if remaining <= 0:
                break
            if canon_label(it.get("name","")) != label:
                continue
            item_kg = to_kg(float(it.get("qty", 0.0)), it.get("unit", "kg"))
            take_kg = min(item_kg, remaining)
            if take_kg <= 0:
                continue
            # convert back to item's unit to decrement
            unit = (it.get("unit") or "kg").lower()
            if unit in ("kg", "kilogram", "kilograms"):
                it["qty"] = float(it.get("qty", 0.0)) - take_kg
            elif unit in ("g", "gram", "grams"):
                it["qty"] = float(it.get("qty", 0.0)) - (take_kg * 1000.0)
            elif unit in ("lb", "lbs", "pound", "pounds"):
                it["qty"] = float(it.get("qty", 0.0)) - (take_kg / 0.45359237)
            else:
                it["qty"] = float(it.get("qty", 0.0)) - take_kg  # assume kg
            remaining -= take_kg
            changed = True
        if changed:
            await db.donations.update_one({"_id": doc["_id"]}, {"$set": {"items": items, "status": "matched"}})

    # Requests
    for (req_id, label), total_dec_kg in dec_req.items():
        doc = await db.requests.find_one({"_id": ObjectId(req_id)})
        if not doc:
            continue
        remaining = float(-total_dec_kg)
        needs = doc.get("needs", [])
        changed = False
        for it in needs:
            if remaining <= 0:
                break
            if canon_label(it.get("name","")) != label:
                continue
            item_kg = to_kg(float(it.get("qty", 0.0)), it.get("unit", "kg"))
            take_kg = min(item_kg, remaining)
            if take_kg <= 0:
                continue
            unit = (it.get("unit") or "kg").lower()
            if unit in ("kg", "kilogram", "kilograms"):
                it["qty"] = float(it.get("qty", 0.0)) - take_kg
            elif unit in ("g", "gram", "grams"):
                it["qty"] = float(it.get("qty", 0.0)) - (take_kg * 1000.0)
            elif unit in ("lb", "lbs", "pound", "pounds"):
                it["qty"] = float(it.get("qty", 0.0)) - (take_kg / 0.45359237)
            else:
                it["qty"] = float(it.get("qty", 0.0)) - take_kg
            remaining -= take_kg
            changed = True
        if changed:
            await db.requests.update_one({"_id": doc["_id"]}, {"$set": {"needs": needs, "status": "matched"}})

async def run_matching() -> Dict:
    """
    Greedy matcher by item label (Item.name):
      - Sort requests by priority, earliest delivery window start, and total need
      - For each needed label, choose best donation by score (fit, distance, expiry, priority)
      - Allocate partially across multiple donations
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    donations, requests = await fetch_open(db)
    materialize_remaining(donations, requests)

    # Precompute locations
    for d in donations:
        d["_lat"] = d.get("location", {}).get("lat")
        d["_lng"] = d.get("location", {}).get("lng")
    for r in requests:
        r["_lat"] = r.get("location", {}).get("lat")
        r["_lng"] = r.get("location", {}).get("lng")

    # Sort requests by urgency/need
    requests_sorted = sorted(requests, key=request_sort_key)

    allocations: List[MatchAllocation] = []

    for r in requests_sorted:
        r_loc = (r.get("_lat"), r.get("_lng"))
        r_need = r.get("_remaining_kg", {}) or {}
        prio = r.get("priority", 0) or 0
        dwin = r.get("delivery_window")
        for label, need_kg in list(r_need.items()):
            if need_kg <= 0:
                continue

            # candidate donations that have remaining for this label and time-window overlap
            cands = []
            for d in donations:
                offer_kg = d.get("_remaining_kg", {}).get(label, 0.0)
                if offer_kg <= 0:
                    continue
                if not time_windows_overlap(d.get("pickup_window"), d.get("ready_after"), dwin):
                    continue
                d_loc = (d.get("_lat"), d.get("_lng"))
                if None in (*r_loc, *d_loc):
                    continue
                dist = haversine_km(r_loc[0], r_loc[1], d_loc[0], d_loc[1])
                fit = qty_fit_ratio(need_kg, offer_kg)
                hours = earliest_expiry_hours(d.get("items", []), label, now)
                score = compute_score(dist, fit, hours, prio)
                if score > 0:
                    cands.append((score, dist, offer_kg, d))

            if not cands:
                continue

            cands.sort(key=lambda x: x[0], reverse=True)

            remaining_need = need_kg
            for score, dist, offer_kg, d in cands:
                if remaining_need <= 0:
                    break
                take = min(remaining_need, offer_kg)
                if take <= 0:
                    continue

                allocations.append(MatchAllocation(
                    donation_id=oid_to_str(d.get("_id")),
                    request_id=oid_to_str(r.get("_id")),
                    item_label=label,
                    category=None,   # if you standardize categories later, fill here
                    qty=round(float(take), 3),
                    unit="kg",
                    distance_km=round(float(dist), 3),
                    score=round(float(score), 4),
                ))
                # Update in-memory residuals
                d["_remaining_kg"][label] -= take
                r["_remaining_kg"][label] -= take
                remaining_need -= take

    # Persist allocations & adjust quantities
    await apply_allocations(db, allocations)

    # Build summary
    totals_by_item: Dict[str, float] = {}
    totals_by_category: Dict[str, float] = {}
    touched_don = set()
    touched_req = set()

    for a in allocations:
        totals_by_item[a.item_label] = totals_by_item.get(a.item_label, 0.0) + a.qty
        # category is optional; keep filled if you start using it
        if a.category:
            totals_by_category[a.category] = totals_by_category.get(a.category, 0.0) + a.qty
        touched_don.add(a.donation_id)
        touched_req.add(a.request_id)

    return {
        "run_id": f"run-{now.timestamp()}",
        "created_at": now,
        "allocations": [x for x in allocations],
        "totals_by_item": totals_by_item,
        "totals_by_category": totals_by_category,
        "summary": {
            "donations_touched": len(touched_don),
            "requests_touched": len(touched_req),
            "allocations": len(allocations),
        }
    }
