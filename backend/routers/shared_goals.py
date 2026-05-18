from fastapi import APIRouter

router = APIRouter(prefix="/shared-goals", tags=["shared-goals"])


@router.get("/health")
def shared_goals_health():
    return {"status": "ok", "router": "shared_goals"}
