from typing import List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.dependencies import AppState
from app.models.timetable import LiveBoardEntry

router = APIRouter()


class LiveBoardDTO(BaseModel):
    station_id: str
    entries: List[LiveBoardEntry]
    is_realtime: bool


@router.get("/api/liveboard/{station_id}", response_model=LiveBoardDTO)
async def get_liveboard(station_id: str, request: Request) -> LiveBoardDTO:
    """取得特定站點之即時到離站資訊（需求 3.2, 3.4）"""
    state: AppState = request.app.state.platform
    station = state.stations_by_id.get(station_id)
    if station is None:
        raise HTTPException(status_code=404, detail=f"無法識別站名：{station_id}")

    if station.transport_mode not in state.liveboard_service.adapters_by_mode:
        return LiveBoardDTO(station_id=station_id, entries=[], is_realtime=False)

    entries, is_realtime = await state.liveboard_service.get_liveboard(station_id, station.transport_mode)
    return LiveBoardDTO(station_id=station_id, entries=entries, is_realtime=is_realtime)
