# app/services/maps_ors.py
# Offline-friendly stubs so the app runs now. You can swap to real ORS/Google later.
import math
import hashlib
from typing import List, Tuple, Optional

def _hash_to_coord(s: str) -> Tuple[float, float]:
    """Deterministic pseudo-geocode near Metro Manila (lat ~14.x, lng ~121.x)."""
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    a = int(h[0:8], 16) / 0xFFFFFFFF
    b = int(h[8:16], 16) / 0xFFFFFFFF
    lat = 14.3 + (a - 0.5) * 0.6   # 14.0 .. 14.6
    lng = 121.0 + (b - 0.5) * 0.8  # 120.6 .. 121.4
    return (lat, lng)

async def ors_geocode(query: str) -> Optional[dict]:
    lat, lng = _hash_to_coord(query)
    return {"lat": lat, "lng": lng}

def _haversine_m(p1: Tuple[float,float], p2: Tuple[float,float]) -> float:
    R = 6371000.0
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

async def ors_matrix(points: List[Tuple[float,float]]) -> List[List[float]]:
    """Return a symmetric 'cost' matrix (seconds). Use straight-line * factor."""
    # distance seconds ~ (meters / 7.0 m/s) * fudge
    sec_matrix = []
    for i in range(len(points)):
        row = []
        for j in range(len(points)):
            if i == j:
                row.append(0.0)
            else:
                m = _haversine_m(points[i], points[j])
                s = (m / 7.0) * 1.35  # ~25 km/h avg + fudge
                row.append(s)
        sec_matrix.append(row)
    return sec_matrix

def greedy_order(sec_matrix: List[List[float]]) -> List[int]:
    """Nearest-neighbor tour starting at 0."""
    n = len(sec_matrix)
    unvisited = set(range(1, n))
    order = [0]
    cur = 0
    while unvisited:
        nxt = min(unvisited, key=lambda j: sec_matrix[cur][j])
        order.append(nxt)
        unvisited.remove(nxt)
        cur = nxt
    return order

async def ors_directions(points: List[Tuple[float,float]]) -> dict:
    """Summarize distance/duration by summing segment haversine (no real map)."""
    dist_m = 0.0
    for i in range(len(points)-1):
        dist_m += _haversine_m(points[i], points[i+1])
    dur_s = (dist_m / 7.0) * 1.35
    return {"distance_m": dist_m, "duration_s": dur_s}
