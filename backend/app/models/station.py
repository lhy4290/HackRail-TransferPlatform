from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import TransportMode


class Station(BaseModel):
    """統一站點格式"""

    station_id: str = Field(..., description="平台內部統一站點 ID")
    original_id: str = Field(..., description="原始機關站點 ID")
    name_zh: str = Field(..., description="中文站名")
    name_en: Optional[str] = Field(None, description="英文站名")
    transport_mode: TransportMode
    latitude: float
    longitude: float
    address: Optional[str] = None
