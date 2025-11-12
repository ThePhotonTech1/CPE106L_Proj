# app/services/units.py
def to_kg(qty: float, unit: str) -> float:
    if qty is None:
        return 0.0
    u = (unit or "").strip().lower()
    if u in ("kg", "kilogram", "kilograms"):
        return float(qty)
    if u in ("g", "gram", "grams"):
        return float(qty) / 1000.0
    if u in ("lb", "lbs", "pound", "pounds"):
        return float(qty) * 0.45359237
    # fallback: treat as kg
    return float(qty)
