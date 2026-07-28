from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import TransportMode
from app.models.risk import RiskPredictionDTO
from app.models.station import Station
from app.models.transfer import TransferStation


class RouteSegment(BaseModel):
    """路線中的一段乘車區間"""

    segment_id: str
    transport_mode: TransportMode
    trip_id: str = Field(..., min_length=1, description="車次/班次編號")
    from_station: Station
    to_station: Station
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int


class RoutePlanDTO(BaseModel):
    """完整路線規劃結果"""

    route_id: str
    segments: List[RouteSegment]
    transfers: List[TransferStation] = Field(default_factory=list)
    total_time_minutes: int
    transfer_count: int
    transport_modes_used: List[TransportMode]
    risk_predictions: Optional[List[RiskPredictionDTO]] = None
