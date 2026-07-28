import asyncio
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.dependencies import AppState
from app.models.alert import ServiceAlert
from app.models.enums import ErrorType
from app.models.errors import PlatformError, ValidationError
from app.models.route import RoutePlanDTO

router = APIRouter()

SEARCH_TIMEOUT_SECONDS = 5.0


class RouteSearchRequest(BaseModel):
    origin: str = Field(..., description="起點站 ID 或名稱")
    destination: str = Field(..., description="終點站 ID 或名稱")
    departure_time: Optional[datetime] = Field(None, description="出發時間，預設為當前時間")


class RouteSearchResponse(BaseModel):
    routes: List[RoutePlanDTO]
    alerts: List[ServiceAlert]
    cached: bool = Field(True, description="是否使用快取之靜態站點/路網資料")
    data_possibly_outdated: bool = Field(False, description="靜態資料快取是否已超過 24 小時（需求 9.4）")


def _require_field(value: str, field_name: str, label: str) -> None:
    if not value or not value.strip():
        raise ValidationError(
            PlatformError(
                error_type=ErrorType.VALIDATION_ERROR,
                message=f"{label}為必填欄位",
                details={"field": field_name},
            )
        )


@router.post("/api/routes/search", response_model=RouteSearchResponse)
async def search_routes(payload: RouteSearchRequest, request: Request) -> RouteSearchResponse:
    """跨運具路線查詢（需求 1.1, 1.2, 1.6, 1.7, 7.5, 7.7, 7.8）"""
    state: AppState = request.app.state.platform

    _require_field(payload.origin, "origin", "起點")
    _require_field(payload.destination, "destination", "終點")

    departure_time = payload.departure_time or datetime.now()

    try:
        routes = await asyncio.wait_for(
            state.planner.plan_routes(payload.origin, payload.destination, departure_time),
            timeout=SEARCH_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="查詢逾時，請重試")

    alerts = await state.alert_manager.get_active_alerts()

    async def risk_fn(route: RoutePlanDTO):
        return await state.risk_predictor.predict_route_risks(route, departure_time)

    routes = await state.planner.ensure_non_severe_alternative(
        routes, payload.origin, payload.destination, departure_time, risk_fn
    )

    is_stale = await state.cache.is_stale("network_graph_loaded_at", max_age_seconds=86400)

    return RouteSearchResponse(routes=routes, alerts=alerts, cached=True, data_possibly_outdated=is_stale)
