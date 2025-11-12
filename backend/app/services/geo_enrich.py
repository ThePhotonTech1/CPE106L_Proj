# app/services/geo_enrich.py
from typing import Dict, Any
from app.core.geocode import geocode_address, GeocodeError

def ensure_location_and_geo(doc: Dict[str, Any]) -> Dict[str, Any]:
    addr = (doc.get("address") or "").strip()
    loc = doc.get("location") or {}
    lat = loc.get("lat"); lng = loc.get("lng")

    def valid(x, y):
        try:
            x = float(x); y = float(y)
            return x is not None and y is not None and not (x == 0.0 and y == 0.0)
        except Exception:
            return False

    # If coords are invalid → try geocoding from address
    if not valid(lat, lng):
        if addr:
            try:
                glat, glng = geocode_address(addr)
                doc["location"] = {"lat": float(glat), "lng": float(glng)}
                doc["geo"] = {"type": "Point", "coordinates": [float(glng), float(glat)]}
                doc.pop("_geocode_error", None)
                return doc
            except GeocodeError as ex:
                # No good geocode: DO NOT set geo to [0,0]
                doc.setdefault("_geocode_error", str(ex))
                doc.pop("geo", None)
                return doc
        else:
            # No address to geocode: keep as-is, but ensure no bogus geo
            doc.pop("geo", None)
            return doc

    # If coords are valid, normalize & set geo
    lat = float(lat); lng = float(lng)
    doc["location"] = {"lat": lat, "lng": lng}
    doc["geo"] = {"type": "Point", "coordinates": [lng, lat]}
    doc.pop("_geocode_error", None)
    return doc
