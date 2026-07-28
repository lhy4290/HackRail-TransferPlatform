from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.dependencies import AppState

router = APIRouter()


class MetricsDTO(BaseModel):
    total_calls_last_7_days: int
    avg_response_time_ms: float
    error_rate: float


@router.get("/api/metrics", response_model=MetricsDTO)
async def get_metrics(request: Request) -> MetricsDTO:
    """最近 7 日 API 回應時間與錯誤率統計（需求 9.5）"""
    state: AppState = request.app.state.platform
    async with state.db.connect() as conn:
        cursor = await conn.execute(
            """
            SELECT COUNT(*),
                   COALESCE(AVG(response_time_ms), 0),
                   COALESCE(SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END), 0)
            FROM api_call_logs
            WHERE called_at >= datetime('now', '-7 days')
            """
        )
        row = await cursor.fetchone()

    total_calls, avg_response_ms, error_count = row
    error_rate = (error_count / total_calls) if total_calls else 0.0

    return MetricsDTO(
        total_calls_last_7_days=total_calls,
        avg_response_time_ms=avg_response_ms,
        error_rate=error_rate,
    )
