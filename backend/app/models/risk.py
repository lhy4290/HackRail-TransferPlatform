from typing import Optional

from pydantic import BaseModel, Field

DATA_INSUFFICIENT_MESSAGE = "資料不足，風險僅供參考"


class RiskPredictionDTO(BaseModel):
    """風險預測結果"""

    transfer_id: str
    risk_level: str = Field(..., description="準點/輕微延誤/嚴重延誤")
    predicted_delay_minutes: float
    confidence: float = Field(..., ge=0.0, le=1.0)
    data_sufficient: bool = Field(True, description="歷史資料是否充足（≥30天）")
    message: Optional[str] = None
