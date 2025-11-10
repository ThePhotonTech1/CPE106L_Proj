from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from ..deps import get_repo
from ..schemas import StatsOverview
from ..services.stats import compute_overview, plot_food_saved_png

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/overview", response_model=StatsOverview)
async def overview(repo=Depends(get_repo)):
    return await compute_overview(repo)

@router.get("/plots/food_saved.png")
async def food_saved(repo=Depends(get_repo)):
    buf = await plot_food_saved_png(repo)
    return StreamingResponse(buf, media_type="image/png")
