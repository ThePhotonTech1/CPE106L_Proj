# app/services/routing.py
import os
import httpx
from .matching import haversine  # re-use our distance helper

GOOGLE_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OSRM_BASE = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")

def internal_plan(stops: list) -> dict:
    """
    Offline fallback. Expects stops = [{"lat":..,"lng":..}, ...]
    Returns rough distance (km) via Haversine segments and ETA at ~25 km/h.
    """
    if len(stops) < 2:
        return {"distance_km": 0.0, "duration_min": 0.0, "steps": []}
    dist = 0.0
    for i in range(len(stops) - 1):
        dist += haversine(stops[i], stops[i + 1])
    duration_min = (dist / 25.0) * 60.0
    return {
        "distance_km": round(dist, 3),
        "duration_min": round(duration_min, 1),
        "steps": [],
    }

async def google_plan(stops: list) -> dict:
    """
    Google Directions API. Requires GOOGLE_MAPS_API_KEY in env.
    """
    if not GOOGLE_KEY or len(stops) < 2:
        return internal_plan(stops)

    origin = f'{stops[0]["lat"]},{stops[0]["lng"]}'
    destination = f'{stops[-1]["lat"]},{stops[-1]["lng"]}'
    waypoints = "|".join(f'{s["lat"]},{s["lng"]}' for s in stops[1:-1])

    params = {"origin": origin, "destination": destination, "key": GOOGLE_KEY}
    if waypoints:
        params["waypoints"] = waypoints

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get("https://maps.googleapis.com/maps/api/directions/json", params=params)
        r.raise_for_status()
        data = r.json()

    if not data.get("routes"):
        return internal_plan(stops)

    legs = data["routes"][0]["legs"]
    dist_km = sum(leg["distance"]["value"] for leg in legs) / 1000
    dur_min = sum(leg["duration"]["value"] for leg in legs) / 60
    return {
        "distance_km": round(dist_km, 3),
        "duration_min": round(dur_min, 1),
        "steps": legs,
    }

async def osrm_plan(stops: list) -> dict:
    """
    OSRM public instance (free). No key needed.
    """
    if len(stops) < 2:
        return internal_plan(stops)

    coords = ";".join(f'{s["lng"]},{s["lat"]}' for s in stops)
    url = f"{OSRM_BASE}/route/v1/driving/{coords}"
    params = {"overview": "false", "steps": "false", "geometries": "polyline"}

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    if not data.get("routes"):
        return internal_plan(stops)

    route = data["routes"][0]
    dist_km = route["distance"] / 1000
    dur_min = route["duration"] / 60
    return {
        "distance_km": round(dist_km, 3),
        "duration_min": round(dur_min, 1),
        "steps": [],
    }
