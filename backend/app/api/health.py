from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health_check() -> dict:
    """健康檢查端點（需於 10 秒內回應，需求 9.2）"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
