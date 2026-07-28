from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models.enums import TransportMode


class TimetableEntry(BaseModel):
    """班表時刻"""

    trip_id: str = Field(..., description="車次/班次編號")
    station_id: str
    transport_mode: TransportMode
    arrival_time: Optional[datetime] = None
    departure_time: Optional[datetime] = None
    destination: str = Field(..., description="終點站名稱")
    direction: int = Field(..., description="行駛方向 0/1")


class LiveBoardEntry(BaseModel):
    """即時到離站資訊"""

    trip_id: str
    station_id: str
    transport_mode: TransportMode
    estimated_arrival: Optional[datetime] = None
    estimated_departure: Optional[datetime] = None
    scheduled_arrival: Optional[datetime] = None
    scheduled_departure: Optional[datetime] = None
    delay_minutes: int = Field(0, description="延誤分鐘數，正值為延誤，負值為提前")
    status: str = Field("準點", description="提前/準點/延誤")
    destination: str

    @model_validator(mode="after")
    def _compute_delay_and_status(self) -> "LiveBoardEntry":
        """依 estimated_arrival 與 scheduled_arrival 之差計算 delay_minutes 與 status（Property 7）"""
        if self.estimated_arrival is not None and self.scheduled_arrival is not None:
            delta = self.estimated_arrival - self.scheduled_arrival
            self.delay_minutes = round(delta.total_seconds() / 60)
        if self.delay_minutes < 0:
            self.status = "提前"
        elif self.delay_minutes == 0:
            self.status = "準點"
        else:
            self.status = "延誤"
        return self
