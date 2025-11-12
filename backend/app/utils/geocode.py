# app/utils/geocode.py
import requests

def geocode_address(addr: str):
    if not addr or not addr.strip():
        return None
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": addr, "format": "json", "limit": 1},
            timeout=8,
            headers={"User-Agent": "foodbridge/1.0"}
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
    except Exception:
        return None
