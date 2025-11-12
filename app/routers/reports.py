# app/routers/reports.py
from fastapi import APIRouter, Response, Query
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
import io
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

from app.db import get_db

router = APIRouter(prefix="/reports", tags=["reports"])

def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()

@router.get("/food_saved.png", response_class=Response)
async def food_saved(days: int = Query(30, ge=1, le=365)):
    """Bar chart: total allocated kg by item label in the last N days (from matches)."""
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = db.matches.find({"created_at": {"$gte": since}})
    totals = defaultdict(float)
    async for m in cursor:
        label = str(m.get("item") or "").lower()
        kg = float(m.get("allocated", 0) or 0)
        totals[label] += kg
    labels = list(totals.keys()) or ["none"]
    values = [totals[k] for k in labels] or [0.0]

    fig = plt.figure(figsize=(8, 4.5))
    plt.bar(labels, values)
    plt.title(f"Food Saved by Item (last {days} days)")
    plt.ylabel("kg")
    plt.xticks(rotation=30, ha="right")
    return Response(content=_png(fig), media_type="image/png")

@router.get("/matches_per_day.png", response_class=Response)
async def matches_per_day(days: int = Query(30, ge=1, le=365)):
    """Line chart: number of match rows per day."""
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = db.matches.find({"created_at": {"$gte": since}}, {"created_at": 1})
    by_day = Counter()
    async for m in cursor:
        dt = m.get("created_at")
        if not dt:
            continue
        d = dt.astimezone(timezone.utc).date()
        by_day[d] += 1
    xs = sorted(by_day.keys())
    ys = [by_day[d] for d in xs]
    if not xs:
        xs = [datetime.now(timezone.utc).date()]
        ys = [0]

    fig = plt.figure(figsize=(8, 4.5))
    plt.plot(xs, ys, marker="o")
    plt.title(f"Matches per Day (last {days} days)")
    plt.ylabel("count")
    plt.xlabel("date (UTC)")
    plt.grid(True)
    return Response(content=_png(fig), media_type="image/png")

@router.get("/kpi")
async def kpi(days: int = 30):
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    matches = await db.matches.count_documents({"created_at": {"$gte": since}})
    routes  = await db.routes.count_documents({"created_at": {"$gte": since}})
    drops   = await db.transfers.count_documents({"action": "drop", "timestamp": {"$gte": since}})
    pickups = await db.transfers.count_documents({"action": "pickup", "timestamp": {"$gte": since}})
    return {
        "window_days": days,
        "matches_created": matches,
        "routes_planned": routes,
        "pickups_logged": pickups,
        "drops_logged": drops
    }

@router.get("/deliveries_per_driver.png", response_class=Response)
async def deliveries_per_driver(days: int = Query(30, ge=1, le=365)):
    """
    Bar chart: deliveries per driver from transfers collection (if you mark deliveries there).
    Fallback: use routes (one bar per saved plan) if transfers not available.
    """
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Prefer transfers
    cur = db.transfers.find({"timestamp": {"$gte": since}}, {"driver_id": 1})
    counts = Counter()
    async for t in cur:
        drv = str(t.get("driver_id") or "unassigned")
        counts[drv] += 1

    # Fallback to routes if no transfers
    if not counts:
        cur = db.routes.find({"created_at": {"$gte": since}}, {"driver_id": 1})
        async for r in cur:
            drv = str(r.get("driver_id") or "batch")
            counts[drv] += 1

    labels = list(counts.keys()) or ["none"]
    values = [counts[k] for k in labels] or [0]

    fig = plt.figure(figsize=(8, 4.5))
    plt.bar(labels, values)
    plt.title(f"Deliveries per Driver (last {days} days)")
    plt.ylabel("deliveries")
    plt.xticks(rotation=30, ha="right")
    return Response(content=_png(fig), media_type="image/png")
