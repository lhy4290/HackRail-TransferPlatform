from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.models.enums import ErrorType


@dataclass
class PlatformError:
    """統一錯誤格式"""

    error_type: ErrorType
    message: str
    details: Optional[dict] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    endpoint: Optional[str] = None


class TDXAPIError(Exception):
    """TDX API 呼叫失敗（逾時或錯誤碼），攜帶 PlatformError 詳細資訊"""

    def __init__(self, platform_error: PlatformError):
        self.platform_error = platform_error
        super().__init__(platform_error.message)


class DataParseError(Exception):
    """TDX 回傳 JSON 解析失敗（必要欄位缺失/型別錯誤/JSON 語法無效）"""

    def __init__(self, platform_error: PlatformError, raw_payload: str = ""):
        self.platform_error = platform_error
        self.raw_payload = raw_payload
        super().__init__(platform_error.message)


class ValidationError(Exception):
    """使用者輸入驗證錯誤"""

    def __init__(self, platform_error: PlatformError):
        self.platform_error = platform_error
        super().__init__(platform_error.message)
