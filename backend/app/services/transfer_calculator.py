from typing import Optional, Tuple

from app.models.transfer import TransferStation

DEFAULT_TRANSFER_MESSAGE = "使用預設轉乘時間"


def compute_transfer_time(transfer: TransferStation) -> Tuple[int, Optional[str]]:
    """計算總轉乘時間（Property 5）

    總轉乘時間 = walking_time_min + buffer_time_min；若 walking_time_min 缺失，
    使用預設值 10 分鐘並回傳提示訊息「使用預設轉乘時間」。

    回傳 (總轉乘時間分鐘, 提示訊息或 None)
    """
    total_minutes, uses_default = transfer.total_transfer_time_min()
    message = DEFAULT_TRANSFER_MESSAGE if uses_default else None
    return total_minutes, message
