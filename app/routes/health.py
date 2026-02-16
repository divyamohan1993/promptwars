from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return {"status": "healthy", "service": "QuestForge"}
