from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.dependencies import AppState
from app.models.transfer import TransferStation
from app.services.transfer_calculator import compute_transfer_time

router = APIRouter()


class TransferInfoDTO(BaseModel):
    transfer: TransferStation
    total_transfer_time_minutes: int
    message: Optional[str] = None


@router.get("/api/transfers/{transfer_id}", response_model=TransferInfoDTO)
async def get_transfer_info(transfer_id: str, request: Request) -> TransferInfoDTO:
    """取得轉乘站步行距離與時間（需求 2.2, 2.5）"""
    state: AppState = request.app.state.platform
    transfer = state.transfers_by_id.get(transfer_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail=f"找不到轉乘站資訊：{transfer_id}")

    total_minutes, message = compute_transfer_time(transfer)
    return TransferInfoDTO(transfer=transfer, total_transfer_time_minutes=total_minutes, message=message)
