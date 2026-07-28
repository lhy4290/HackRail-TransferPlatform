from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.enums import TransportMode

ACTIVE_STATUS = "進行中"
RESOLVED_STATUSES = {"已恢復", "已結束"}


class ServiceAlert(BaseModel):
    """營運通報"""

    alert_id: str
    transport_mode: TransportMode
    title: str
    description: str = ""
    severity: str = Field(..., description="停駛/延誤/路線異動")
    affected_stations: List[str] = Field(default_factory=list)
    affected_routes: List[str] = Field(default_factory=list)
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = Field(ACTIVE_STATUS, description="進行中/已恢復/已結束")
    source: str = Field("TDX", description="資料來源")

    @property
    def is_active(self) -> bool:
        return self.status not in RESOLVED_STATUSES
