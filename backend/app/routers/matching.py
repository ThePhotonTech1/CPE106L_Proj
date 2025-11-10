from fastapi import APIRouter, Depends
from ..deps import get_repo
from ..services.matching import greedy_match

router = APIRouter(prefix="/matching", tags=["matching"])

@router.post("/run")
async def run_matching(repo=Depends(get_repo)) -> dict:
    donations = await repo.list_donations(status="open")
    requests = await repo.list_requests(status="open")
    results = greedy_match(donations, requests)
    out = []
    for m in results:
        md = await repo.insert_match(m["donation"]["_id"], m["request"]["_id"], m["score"])
        await repo.update_donation_status(m["donation"]["_id"], "matched")
        await repo.update_request_status(m["request"]["_id"], "matched")
        out.append({"id": md["_id"], "donation_id": md["donation_id"], "request_id": md["request_id"], "score": md["score"]})
    return {"matches": out}
