from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "service": "rig-control-center",
    }
