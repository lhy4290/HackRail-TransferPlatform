from pydantic import BaseModel, Field

from app.models.station import Station

DEFAULT_BUFFER_TIME_MIN = 10


class TransferStation(BaseModel):
    """轉乘站資訊"""

    transfer_id: str
    from_station: Station
    to_station: Station
    from_platform: str = Field(..., min_length=1, description="起點運具月台/出口名稱")
    to_platform: str = Field(..., min_length=1, description="終點運具月台/入口名稱")
    walking_distance_m: int = Field(..., ge=1, le=5000, description="步行距離（公尺）")
    walking_time_min: int | None = Field(None, ge=1, le=30, description="步行時間（分鐘），缺失時以預設緩衝時間計算")
    buffer_time_min: int = Field(default=DEFAULT_BUFFER_TIME_MIN, description="緩衝時間（分鐘）")

    def total_transfer_time_min(self) -> tuple[int, bool]:
        """計算總轉乘時間（Property 5）

        回傳 (總轉乘時間, 是否使用預設轉乘時間)
        """
        if self.walking_time_min is None:
            return DEFAULT_BUFFER_TIME_MIN, True
        return self.walking_time_min + self.buffer_time_min, False
