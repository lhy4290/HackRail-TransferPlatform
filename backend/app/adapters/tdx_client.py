import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

import httpx

from app.models.enums import ErrorType
from app.models.errors import PlatformError, TDXAPIError

logger = logging.getLogger(__name__)

LogFn = Callable[[str, int, int, Optional[str]], Awaitable[None]]


class TDXClient:
    """TDX API 統一存取客戶端，處理 OAuth 認證與錯誤重試"""

    BASE_URL = "https://tdx.transportdata.tw/api/basic"
    AUTH_URL = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        http_client: Optional[httpx.AsyncClient] = None,
        sleep_fn: Callable[[float], Any] = asyncio.sleep,
        log_fn: Optional[LogFn] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._http_client = http_client or httpx.AsyncClient()
        self._sleep = sleep_fn
        self._log_fn = log_fn
        self.error_log: list[PlatformError] = []

    async def _log_call(self, endpoint: str, response_time_ms: int, status_code: int, error_message: Optional[str]) -> None:
        """記錄單次 API 呼叫之回應時間與錯誤率統計（需求 9.5）"""
        if self._log_fn is not None:
            await self._log_fn(endpoint, response_time_ms, status_code, error_message)

    async def authenticate(self) -> str:
        """取得或刷新 OAuth access token"""
        now = datetime.now(timezone.utc)
        if self._token and self._token_expires and now < self._token_expires:
            return self._token

        response = await self._http_client.post(
            self.AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        expires_in = payload.get("expires_in", 1800)
        self._token_expires = now + timedelta(seconds=max(expires_in - 60, 0))
        return self._token

    async def request(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        max_retries: int = 2,
        retry_interval: float = 2.0,
        timeout: float = 10.0,
    ) -> Any:
        """
        發送 API 請求，含重試邏輯。
        - 逾時 10 秒觸發重試
        - 最多重試 2 次，間隔 2 秒
        - 失敗後記錄錯誤並拋出 TDXAPIError
        """
        url = f"{self.BASE_URL}{endpoint}"
        last_error_type = ErrorType.API_ERROR
        last_detail: Any = None
        attempt = 0

        while attempt <= max_retries:
            start = time.monotonic()
            try:
                token = await self.authenticate()
                response = await self._http_client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=timeout,
                )
                elapsed_ms = int((time.monotonic() - start) * 1000)
                if response.status_code >= 400:
                    last_error_type = ErrorType.API_ERROR
                    last_detail = response.status_code
                    await self._log_call(endpoint, elapsed_ms, response.status_code, f"HTTP {response.status_code}")
                else:
                    await self._log_call(endpoint, elapsed_ms, response.status_code, None)
                    return response.json()
            except httpx.TimeoutException:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                last_error_type = ErrorType.TIMEOUT
                last_detail = f"timeout after {timeout}s"
                await self._log_call(endpoint, elapsed_ms, 0, "timeout")
            except httpx.HTTPError as exc:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                last_error_type = ErrorType.API_ERROR
                last_detail = str(exc)
                await self._log_call(endpoint, elapsed_ms, 0, str(exc))

            if attempt < max_retries:
                await self._sleep(retry_interval)
            attempt += 1

        platform_error = PlatformError(
            error_type=last_error_type,
            message=f"TDX API 請求失敗（{endpoint}）：{last_detail}",
            details={"detail": last_detail, "attempts": attempt},
            endpoint=endpoint,
        )
        logger.error(
            "TDX API 呼叫失敗 endpoint=%s type=%s detail=%s", endpoint, last_error_type, last_detail
        )
        self.error_log.append(platform_error)
        raise TDXAPIError(platform_error)

    async def aclose(self) -> None:
        await self._http_client.aclose()
