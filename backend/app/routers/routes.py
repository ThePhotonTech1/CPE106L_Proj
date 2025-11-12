# app/routers/routes.py
from fastapi import APIRouter, Body
from typing import List, Dict, Any, Tuple
from math import radians, sin, cos, asin
from datetime import datetime, timezone
from bson import ObjectId
from app.db import get_db

router = APIRouter(prefix="/api/routes", tags=["routes"])

def _utcnow():
    return datetime.now(timezone.utc)

def _try_obj(s):
    try:
        return ObjectId(s)
    except Exception:
        return None

def _maybe_oid(x) -> ObjectId | None:
    if isinstance(x, ObjectId):
        return x
    if isinstance(x, str) and ObjectId.is_valid(x):
        return ObjectId(x)
    return None

def _to_pair(lat: float, lng: float) -> Tuple[float, float]:
    return (float(lat), float(lng))

def _hav_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lng1 = a
    lat2, lng2 = b
    # Haversine
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    x = sin(dlat/2.0)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2.0)**2
    return 6371.0 * 2.0 * asin(x**0.5)

def _nn_order(depot: Tuple[float, float], points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not points:
        return []
    un = points[:]
    cur = depot
    out = []
    while un:
        nxt = min(un, key=lambda p: _hav_km(cur, (p["lat"], p["lng"])))
        out.append(nxt)
        cur = (nxt["lat"], nxt["lng"])
        un.remove(nxt)
    return out

def _pack_batches(stops: List[Dict[str, Any]], capacity_kg: float) -> List[List[Dict[str, Any]]]:
    """Greedy bin packing by descending weight (kg)."""
    if capacity_kg is None or capacity_kg <= 0:
        return [stops] if stops else []
    arr = sorted(stops, key=lambda s: float(s.get("kg", 0) or 0), reverse=True)
    bins: List[List[Dict[str, Any]]] = []
    loads: List[float] = []
    for s in arr:
        w = float(s.get("kg", 0) or 0)
        placed = False
        for i, load in enumerate(loads):
            if load + w <= capacity_kg:
                bins[i].append(s)
                loads[i] += w
                placed = True
                break
        if not placed:
            bins.append([s])
            loads.append(w)
    return bins

@router.post("/plan_from_matches")
async def plan_from_matches(
    depot: Dict[str, float] = Body(..., example={"lat": 14.5547, "lng": 121.0244}),
    capacity_kg: float = Body(80.0),
    max_rows: int = Body(500),
):
    """
    Build route plans from *planned* matches. For each route we:
      - compute steps (start → pickups → drops → end)
      - include donation_ids/request_ids inside the route
      - lock only the matches belonging to that route: status=in_progress + route_id
    """
    db = get_db()
    dep = _to_pair(depot["lat"], depot["lng"])

    # 1) Pull planned matches
    matches = []
    cur = db.matches.find({"status": "planned"}).limit(max_rows)
    async for m in cur:
        matches.append(m)

    if not matches:
        return {"count": 0, "plans": []}

    # 2) Aggregate pickups by donor, drops by recipient; track which match-ids contribute to each node
    donors: Dict[str, Dict[str, Any]] = {}
    recips: Dict[str, Dict[str, Any]] = {}

    # Also prepare reverse-index: for (donor_id, recipient_id) collect match _id’s (so we can tag per-route later)
    by_pair: Dict[Tuple[str, str], List[ObjectId]] = {}

    for m in matches:
        mid = m.get("_id")
        item_kg = float(m.get("allocated", 0) or 0)

        # ------------------ DONATION (pickup) ------------------
        ddoc = await db.donations.find_one({
            "$or": [
                {"id": m.get("donation_id")},
                {"_id": _try_obj(m.get("donation_id"))},
                {"_id": m.get("donation_id")}
            ]
        })
        dkey = None
        dloc = None
        if ddoc:
            dkey = str(ddoc.get("id") or ddoc.get("_id"))
            loc = ddoc.get("location") or {}
            lat = loc.get("lat"); lng = loc.get("lng")
            if lat is not None and lng is not None:
                node = donors.setdefault(dkey, {
                    "type": "pickup",
                    "label": ddoc.get("donor_name", "Donor"),
                    "lat": float(lat), "lng": float(lng),
                    "kg": 0.0, "donation_id": dkey,
                    "match_ids": []  # all matches touching this donor
                })
                node["kg"] += item_kg
                node["match_ids"].append(mid)
                dloc = (float(lat), float(lng))

        # ------------------ REQUEST (drop) ------------------
        rdoc = await db.requests.find_one({
            "$or": [
                {"id": m.get("request_id")},
                {"_id": _try_obj(m.get("request_id"))},
                {"_id": m.get("request_id")}
            ]
        })
        rkey = None
        if rdoc:
            rkey = str(rdoc.get("id") or rdoc.get("_id"))
            loc = rdoc.get("location") or {}
            lat = loc.get("lat"); lng = loc.get("lng")
            if lat is not None and lng is not None:
                node = recips.setdefault(rkey, {
                    "type": "drop",
                    "label": rdoc.get("ngo_name", "Recipient"),
                    "lat": float(lat), "lng": float(lng),
                    "kg": 0.0, "request_id": rkey,
                    "match_ids": []  # all matches touching this recipient
                })
                node["kg"] += item_kg
                node["match_ids"].append(mid)

        # Pair mapping (for later per-route tagging)
        if dkey and rkey and isinstance(mid, ObjectId):
            by_pair.setdefault((dkey, rkey), []).append(mid)

    pickups = list(donors.values())
    drops   = list(recips.values())

    # 3) Pack into capacity-batches independently, then pair batches by index
    pick_batches = _pack_batches(pickups, capacity_kg)
    drop_batches = _pack_batches(drops, capacity_kg)

    n = max(len(pick_batches), len(drop_batches))
    plan_docs: List[Dict[str, Any]] = []
    # For mapping route index -> sets of donor_ids & request_ids (strings)
    route_donor_ids: List[List[str]] = []
    route_request_ids: List[List[str]] = []

    for i in range(n):
        picks = pick_batches[i] if i < len(pick_batches) else []
        drps  = drop_batches[i] if i < len(drop_batches) else []

        ordered_picks = _nn_order(dep, picks)
        curpos = dep if not ordered_picks else (ordered_picks[-1]["lat"], ordered_picks[-1]["lng"])
        ordered_drops = _nn_order(curpos, drps)

        steps = [{"action": "start", "lat": dep[0], "lng": dep[1], "label": "Depot"}]
        for s in ordered_picks:
            steps.append({"action": "pickup", "lat": s["lat"], "lng": s["lng"], "label": s["label"], "kg": round(float(s["kg"]), 3)})
        for s in ordered_drops:
            steps.append({"action": "drop", "lat": s["lat"], "lng": s["lng"], "label": s["label"], "kg": round(float(s["kg"]), 3)})
        steps.append({"action": "end", "lat": dep[0], "lng": dep[1], "label": "Depot"})

        # distance & ETA
        dist = 0.0
        coords = [(st["lat"], st["lng"]) for st in steps]
        for a, b in zip(coords, coords[1:]):
            dist += _hav_km(a, b)
        duration_min = (dist / 25.0) * 60.0

        # collect ids present in this batch (strings; later we’ll convert to ObjectIds)
        donor_ids = list({s.get("donation_id") for s in picks if s.get("donation_id")})
        recip_ids = list({s.get("request_id") for s in drps  if s.get("request_id")})

        # route doc (we include donation_ids/request_ids inside the route)
        plan_docs.append({
            "batch_index": i,
            "capacity_kg": capacity_kg,
            "total_distance_km": round(dist, 3),
            "duration_min": round(duration_min, 1),
            "steps": steps,
            "donation_ids": [ _maybe_oid(x) or x for x in donor_ids ],
            "request_ids":  [ _maybe_oid(x) or x for x in recip_ids ],
            "status": "planned",
            "created_at": _utcnow(),
        })
        route_donor_ids.append(donor_ids)
        route_request_ids.append(recip_ids)

    # 4) Persist routes; get ids in order
    if plan_docs:
        res = await db.routes.insert_many(plan_docs)
        route_ids = res.inserted_ids  # aligned with plan_docs order
    else:
        return {"count": 0, "plans": []}

    # 5) Lock matches belonging to each route: status → in_progress, route_id set
    for idx, rid in enumerate(route_ids):
        dids = set(route_donor_ids[idx])
        rids = set(route_request_ids[idx])
        if not dids and not rids:
            continue

        donor_filter = []
        if dids:
            donor_filter.append({"donation_id": {"$in": [ _maybe_oid(x) or x for x in dids ]}})
        recip_filter = []
        if rids:
            recip_filter.append({"request_id": {"$in": [ _maybe_oid(x) or x for x in rids ]}})

        # Only planned matches that join a donor in this route and a recipient in this route
        match_query = {
            "status": "planned",
            "$and": donor_filter + recip_filter if (donor_filter and recip_filter) else donor_filter or recip_filter
        }

        await db.matches.update_many(
            match_query,
            {"$set": {"status": "in_progress", "route_id": rid, "locked_at": _utcnow()}}
        )

    # 6) Prepare safe response (ObjectId → str)
    safe_plans: List[Dict[str, Any]] = []
    for p, rid in zip(plan_docs, route_ids):
        q = dict(p)
        q["_id"] = str(rid)
        # Convert any ObjectIds inside arrays to strings
        q["donation_ids"] = [str(x) if isinstance(x, ObjectId) else x for x in q.get("donation_ids", [])]
        q["request_ids"]  = [str(x) if isinstance(x, ObjectId) else x for x in q.get("request_ids", [])]
        safe_plans.append(q)

    return {"count": len(safe_plans), "plans": safe_plans}
