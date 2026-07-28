from typing import List

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.api.dependencies import AppState

router = APIRouter()


class StationSuggestionDTO(BaseModel):
    station_id: str
    name_zh: str
    name_en: str | None = None
    transport_mode: str


@router.get("/api/stations", response_model=List[StationSuggestionDTO])
async def list_stations(request: Request) -> List[StationSuggestionDTO]:
    """取得所有站點，供前端「先選運具、再選站名」之下拉選單使用"""
    state: AppState = request.app.state.platform
    stations = state.stations_by_id.values()
    if state.visible_station_ids is not None:
        stations = [s for s in stations if s.station_id in state.visible_station_ids]
    return [
        StationSuggestionDTO(
            station_id=s.station_id,
            name_zh=s.name_zh,
            name_en=s.name_en,
            transport_mode=s.transport_mode.value,
        )
        for s in stations
    ]


@router.get("/api/stations/suggest", response_model=List[StationSuggestionDTO])
async def suggest_stations(
    request: Request,
    q: str = Query(..., min_length=2, description="站名關鍵字（至少 2 字元）"),
    limit: int = Query(10, le=10),
) -> List[StationSuggestionDTO]:
    """站名模糊搜尋與自動完成（需求 7.1, 7.2, 7.6）"""
    state: AppState = request.app.state.platform
    query_lower = q.lower()

    matches = [
        station
        for station in state.stations_by_id.values()
        if q in station.name_zh or (station.name_en and query_lower in station.name_en.lower())
    ]

    return [
        StationSuggestionDTO(
            station_id=s.station_id,
            name_zh=s.name_zh,
            name_en=s.name_en,
            transport_mode=s.transport_mode.value,
        )
        for s in matches[:limit]
    ]
