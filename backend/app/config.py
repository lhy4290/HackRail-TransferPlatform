import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class TDXCredentials:
    client_id: str
    client_secret: str


def load_tdx_credentials() -> Optional[TDXCredentials]:
    """讀取 TDX_CLIENT_ID / TDX_CLIENT_SECRET 環境變數（或 backend/.env）。

    未設定時回傳 None，呼叫端應 fallback 至 build_empty_app_state()（無憑證之安全預設值）。
    """
    client_id = os.environ.get("TDX_CLIENT_ID")
    client_secret = os.environ.get("TDX_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    return TDXCredentials(client_id=client_id, client_secret=client_secret)
