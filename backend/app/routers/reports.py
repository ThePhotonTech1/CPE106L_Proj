from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.db import get_db
import os, io
import matplotlib.pyplot as plt

router = APIRouter(prefix="/reports", tags=["reports"])

CHART_DIR = "charts"
os.makedirs(CHART_DIR, exist_ok=True)

@router.get("/chart-urls")
async def chart_urls():
    # ensure charts exist before returning urls
    await food_saved_chart()
    await donor_participation_chart()
    return {
        "food_saved": "/reports/img/food_saved.png",
        "donor_participation": "/reports/img/donor_participation.png",
    }

@router.get("/img/{name}.png")
async def chart_image(name: str):
    path = os.path.join(CHART_DIR, f"{name}.png")
    return FileResponse(path, media_type="image/png")

async def food_saved_chart():
    db = get_db()
    total = await db.donations.count_documents({})
    fig, ax = plt.subplots(figsize=(6,3))
    ax.bar(["Total Saved"], [total])
    ax.set_title("Food Saved (count of donations)")
    fig.tight_layout()
    path = os.path.join(CHART_DIR, "food_saved.png")
    fig.savefig(path)
    plt.close(fig)

async def donor_participation_chart():
    db = get_db()
    agg = db.donations.aggregate([
        {"$group":{"_id":"$donor_id","cnt":{"$sum":1}}},
        {"$sort":{"cnt":-1}}, {"$limit":5}
    ])
    labels, vals = [], []
    async for row in agg:
        labels.append(str(row["_id"])[-4:])
        vals.append(row["cnt"])
    if not labels:
        labels, vals = ["N/A"], [0]
    fig, ax = plt.subplots(figsize=(6,3))
    ax.bar(labels, vals)
    ax.set_title("Top Donors (last 5)")
    fig.tight_layout()
    path = os.path.join(CHART_DIR, "donor_participation.png")
    fig.savefig(path)
    plt.close(fig)
