# app/core/geocode.py
from __future__ import annotations
import os
import httpx
from typing import Optional, Tuple

# Choose provider via env:
# GEOCODER = nominatim | opencage | google
GEOCODER = os.getenv("GEOCODER", "nominatim").lower()

# Optional keys
OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")
GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_KEY")

# Global timeout
_CLIENT = httpx.Client(timeout=12)

class GeocodeError(Exception):
    pass

def geocode_address(address: str) -> Tuple[float, float]:
    """
    Returns (lat, lng). Raises GeocodeError on failure.
    """
    a = (address or "").strip()
    if not a:
        raise GeocodeError("Empty address")

    if GEOCODER == "opencage":
        if not OPENCAGE_KEY:
            raise GeocodeError("OPENCAGE_KEY not set")
        url = "https://api.opencagedata.com/geocode/v1/json"
        r = _CLIENT.get(url, params={"q": a, "key": OPENCAGE_KEY, "limit": 1})
        r.raise_for_status()
        js = r.json()
        if not js.get("results"):
            raise GeocodeError("No results")
        g = js["results"][0]["geometry"]
        return float(g["lat"]), float(g["lng"])

    if GEOCODER == "google":
        if not GOOGLE_MAPS_KEY:
            raise GeocodeError("GOOGLE_MAPS_KEY not set")
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        r = _CLIENT.get(url, params={"address": a, "key": GOOGLE_MAPS_KEY})
        r.raise_for_status()
        js = r.json()
        if not js.get("results"):
            raise GeocodeError("No results")
        loc = js["results"][0]["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"])

    # Default: Nominatim (no key). Respect their policy: include a UA + email if possible.
    headers = {
        "User-Agent": f"FoodBridge/1.0 (+{os.getenv('ADMIN_CONTACT','mailto:admin@example.com')})"
    }
    url = "https://nominatim.openstreetmap.org/search"
    r = _CLIENT.get(url, params={"q": a, "format": "json", "limit": 1}, headers=headers)
    r.raise_for_status()
    js = r.json()
    if not js:
        raise GeocodeError("No results")
    return float(js[0]["lat"]), float(js[0]["lon"])
