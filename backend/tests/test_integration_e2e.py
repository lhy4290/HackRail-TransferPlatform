import asyncio
import time
from datetime import datetime, timezone

import httpx
import pytest

from app.main import app
from app.models.alert import ServiceAlert
from app.models.enums import ErrorType, TransportMode
from app.models.errors import PlatformError, TDXAPIError


class _FailingLiveboardAdapter:
    """模擬 TDX API 逾時/失敗之轉接器，用於驗證降級行為"""

    async def get_liveboard(self, station_id):
        raise TDXAPIError(PlatformError(error_type=ErrorType.TIMEOUT, message="逾時", endpoint="/liveboard"))

    async def get_timetable(self, station_id, date):
        return []


@pytest.mark.asyncio
async def test_end_to_end_route_search_returns_full_route_with_risk_and_alerts(seeded_state):
    active_alert = ServiceAlert(
        alert_id="A1",
        transport_mode=TransportMode.TRA,
        title="路線異動",
        severity="路線異動",
        affected_stations=["ORIGIN"],
        affected_routes=[],
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="進行中",
    )

    class _AlertOnlyAdapter:
        async def get_alerts(self):
            return [active_alert]

    seeded_state.alert_manager.adapters = [_AlertOnlyAdapter()]
    app.state.platform = seeded_state

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/routes/search",
            json={"origin": "ORIGIN", "destination": "DEST", "departure_time": "2026-01-05T08:00:00"},
        )

    assert resp.status_code == 200
    body = resp.json()
    # 端對端：從 API 請求到回傳完整路線（含段落、轉乘、風險標註與通報）
    assert 1 <= len(body["routes"]) <= 5
    for route in body["routes"]:
        assert route["segments"][0]["from_station"]["station_id"] == "ORIGIN"
        assert route["segments"][-1]["to_station"]["station_id"] == "DEST"
    assert any(a["alert_id"] == "A1" for a in body["alerts"])


@pytest.mark.asyncio
async def test_tdx_timeout_degrades_liveboard_to_unavailable(seeded_state):
    seeded_state.liveboard_service.adapters_by_mode[TransportMode.TRA] = _FailingLiveboardAdapter()
    app.state.platform = seeded_state

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/liveboard/ORIGIN")

    assert resp.status_code == 200
    body = resp.json()
    # TDX 逾時後應改用班表資料並標示非即時
    assert body["is_realtime"] is False


@pytest.mark.asyncio
async def test_service_alert_impacts_route_query_results(seeded_state):
    active_alert = ServiceAlert(
        alert_id="A2",
        transport_mode=TransportMode.TRA,
        title="列車延誤",
        severity="延誤",
        affected_stations=["MID"],
        affected_routes=[],
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="進行中",
    )

    class _AlertOnlyAdapter:
        async def get_alerts(self):
            return [active_alert]

    seeded_state.alert_manager.adapters = [_AlertOnlyAdapter()]
    app.state.platform = seeded_state

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/routes/search",
            json={"origin": "ORIGIN", "destination": "DEST", "departure_time": "2026-01-05T08:00:00"},
        )

    body = resp.json()
    assert any(a["alert_id"] == "A2" for a in body["alerts"])
    # 通報涵蓋 MID 站，該路線確實經過 MID -> 前端可據此標示警示圖標
    stations_in_routes = {
        s["station_id"]
        for route in body["routes"]
        for seg in route["segments"]
        for s in (seg["from_station"], seg["to_station"])
    }
    assert "MID" in stations_in_routes


@pytest.mark.asyncio
async def test_concurrent_route_search_p95_under_5_seconds(seeded_state):
    """100 並發查詢 P95 回應時間 < 5 秒（需求 9.1）

    此為程式碼內建之輕量煙霧測試；正式負載測試以 Locust 對已部署服務執行（見 design.md）。
    """
    app.state.platform = seeded_state
    transport = httpx.ASGITransport(app=app)

    async def one_request(client: httpx.AsyncClient) -> float:
        start = time.monotonic()
        resp = await client.post(
            "/api/routes/search",
            json={"origin": "ORIGIN", "destination": "DEST", "departure_time": "2026-01-05T08:00:00"},
        )
        assert resp.status_code == 200
        return time.monotonic() - start

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        durations = await asyncio.gather(*[one_request(client) for _ in range(100)])

    durations_sorted = sorted(durations)
    p95_index = int(len(durations_sorted) * 0.95)
    p95_duration = durations_sorted[min(p95_index, len(durations_sorted) - 1)]
    assert p95_duration < 5.0
