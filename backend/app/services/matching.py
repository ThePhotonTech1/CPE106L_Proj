# app/services/matching.py
from math import radians, sin, cos, atan2

def haversine(a: dict, b: dict) -> float:
    """
    a, b: dicts like {"lat": float, "lng": float}
    returns distance in km
    """
    R = 6371.0
    dlat = radians(b["lat"] - a["lat"])
    dlon = radians(b["lng"] - a["lng"])
    s = sin(dlat/2)**2 + cos(radians(a["lat"])) * cos(radians(b["lat"])) * sin(dlon/2)**2
    return 2 * R * atan2(s**0.5, (1 - s)**0.5)

def overlap_score(donation_items, request_needs) -> float:
    """
    donation_items / request_needs: lists like [{"name":..., "qty":..., "unit":...}]
    """
    d = {i["name"].lower(): i["qty"] for i in donation_items}
    r = {i["name"].lower(): i["qty"] for i in request_needs}
    score = 0.0
    for k, q in r.items():
        score += min(q, d.get(k, 0))
    return score

def greedy_match(donations: list, requests: list):
    """
    donations / requests: dicts from repo with fields:
      - items / needs (lists)
      - location (dict with lat/lng)
      - _id (str)
    returns list of {"donation": d, "request": r, "score": float}
    """
    results = []
    used = set()
    for dn in donations:
        best = None
        best_s = -1e9
        for rq in requests:
            if rq["_id"] in used:
                continue
            s = overlap_score(dn["items"], rq["needs"]) - 0.2 * haversine(dn["location"], rq["location"])
            if s > best_s:
                best_s = s
                best = rq
        if best:
            used.add(best["_id"])
            results.append({"donation": dn, "request": best, "score": float(best_s)})
    return results
