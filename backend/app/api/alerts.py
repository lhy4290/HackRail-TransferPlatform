from typing import List, Optional

from fastapi import APIRouter, Request

from app.api.dependencies import AppState
from app.models.alert import ServiceAlert

router = APIRouter()


@router.get("/api/alerts", response_model=List[ServiceAlert])
async def get_alerts(request: Request, transport_mode: Optional[str] = None) -> List[ServiceAlert]:
    """取得營運通報，可依運具類型篩選（需求 8.4）"""
    state: AppState = request.app.state.platform
    alerts = await state.alert_manager.get_active_alerts()
    if transport_mode:
        alerts = [a for a in alerts if a.transport_mode.value == transport_mode]
    return alerts
