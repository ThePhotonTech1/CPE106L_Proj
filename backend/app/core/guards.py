from fastapi import HTTPException

def ensure_same_org(resource_org_id, user_org_id):
    if resource_org_id != user_org_id:
        raise HTTPException(status_code=403, detail="Cross-org access denied")
