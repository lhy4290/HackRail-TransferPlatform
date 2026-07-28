import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.adapters.tdx_client import TDXClient
from app.models.enums import ErrorType
from app.models.errors import TDXAPIError


class CountingSleep:
    def __init__(self):
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _make_failing_client(fail_kind: str) -> tuple[TDXClient, dict]:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if fail_kind == "timeout":
            raise httpx.TimeoutException("simulated timeout", request=request)
        return httpx.Response(500, json={"error": "boom"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = TDXClient("id", "secret", http_client=http_client)
    client._token = "fake-token"
    client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    return client, call_count


# Feature: cross-transport-transfer-platform, Property 10: API 重試行為
@given(fail_kind=st.sampled_from(["timeout", "api_error"]))
@settings(max_examples=100, deadline=None)
def test_retry_behavior_limits_and_error_detail(fail_kind: str):
    async def run() -> None:
        client, call_count = _make_failing_client(fail_kind)
        sleep_counter = CountingSleep()
        client._sleep = sleep_counter

        with pytest.raises(TDXAPIError) as exc_info:
            await client.request("/v2/test/endpoint", max_retries=2, retry_interval=2.0, timeout=10.0)

        # 初始請求 1 次 + 最多重試 2 次 = 總共 3 次呼叫
        assert call_count["n"] == 3
        # 重試間隔固定為 2 秒，且僅重試 2 次
        assert sleep_counter.calls == [2.0, 2.0]

        error = exc_info.value.platform_error
        assert error.endpoint == "/v2/test/endpoint"
        assert error.timestamp is not None
        assert error.error_type in (ErrorType.TIMEOUT, ErrorType.API_ERROR)
        if fail_kind == "timeout":
            assert error.error_type == ErrorType.TIMEOUT
        else:
            assert error.error_type == ErrorType.API_ERROR

        await client.aclose()

    asyncio.run(run())


@pytest.mark.asyncio
async def test_request_succeeds_without_retry_on_first_try():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = TDXClient("id", "secret", http_client=http_client)
    client._token = "fake-token"
    client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)

    sleep_counter = CountingSleep()
    client._sleep = sleep_counter

    result = await client.request("/v2/ok")
    assert result == {"ok": True}
    assert sleep_counter.calls == []
    await client.aclose()
