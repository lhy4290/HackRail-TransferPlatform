from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.adapters.tdx_client import TDXClient


@pytest.mark.asyncio
async def test_request_logs_successful_call():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)

    logged_calls = []

    async def log_fn(endpoint, response_time_ms, status_code, error_message):
        logged_calls.append((endpoint, response_time_ms, status_code, error_message))

    client = TDXClient("id", "secret", http_client=http_client, log_fn=log_fn)
    client._token = "token"
    client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)

    await client.request("/v2/ok")

    assert len(logged_calls) == 1
    endpoint, response_time_ms, status_code, error_message = logged_calls[0]
    assert endpoint == "/v2/ok"
    assert response_time_ms >= 0
    assert status_code == 200
    assert error_message is None

    await client.aclose()


@pytest.mark.asyncio
async def test_request_logs_each_retry_attempt_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)

    logged_calls = []

    async def log_fn(endpoint, response_time_ms, status_code, error_message):
        logged_calls.append((endpoint, response_time_ms, status_code, error_message))

    async def no_sleep(_seconds):
        return None

    client = TDXClient("id", "secret", http_client=http_client, sleep_fn=no_sleep, log_fn=log_fn)
    client._token = "token"
    client._token_expires = datetime.now(timezone.utc) + timedelta(hours=1)

    from app.models.errors import TDXAPIError

    with pytest.raises(TDXAPIError):
        await client.request("/v2/fail", max_retries=2, retry_interval=0)

    assert len(logged_calls) == 3
    assert all(call[2] == 500 for call in logged_calls)
    assert all(call[3] is not None for call in logged_calls)

    await client.aclose()
