# app/services/stats.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO

async def compute_overview(repo):
    """
    Returns a dict that matches the StatsOverview schema.
    Repo must implement:
      - count_donations()
      - count_requests()
      - count_delivered()
      - count_fulfilled()
      - top_donors(limit)
    """
    return {
        "total_donations": await repo.count_donations(),
        "total_requests": await repo.count_requests(),
        "delivered_count": await repo.count_delivered(),
        "fulfilled_count": await repo.count_fulfilled(),
        "top_donors": await repo.top_donors(5),
    }

async def plot_food_saved_png(repo):
    """
    Builds a simple bar chart of delivered donations per donor.
    Uses repo.top_donors(10). Returns a BytesIO PNG buffer.
    """
    top = await repo.top_donors(10)
    labels = [t["donor_id"] for t in top] or ["No data"]
    values = [t["count"] for t in top] or [0]

    fig = plt.figure()
    plt.bar(labels, values)
    plt.xticks(rotation=30, ha="right")
    plt.title("Delivered Donations by Donor")
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf
