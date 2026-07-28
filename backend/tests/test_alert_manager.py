import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.enums import TransportMode
from app.models.errors import ErrorType, PlatformError, TDXAPIError
from app.models.route import RouteSegment
from app.services.alert_manager import AlertManager
from tests.strategies import st_route_segment, st_service_alert

from app.cache.cache_manager import CacheManager
from app.models.route import RoutePlanDTO


def _route_from_segment(segment: RouteSegment) -> RoutePlanDTO:
    return RoutePlanDTO(
        route_id="r1",
        segments=[segment],
        total_time_minutes=segment.duration_minutes,
        transfer_count=0,
        transport_modes_used=[segment.transport_mode],
    )


# Feature: cross-transport-transfer-platform, Property 17: 進行中通報警示
@given(
    segment=st_route_segment(),
    status=st.sampled_from(["進行中", "已恢復", "已結束"]),
)
@settings(max_examples=100, deadline=None)
def test_active_alert_marks_route_affected(segment, status):
    route = _route_from_segment(segment)
    alert = None

    async def build_and_check():
        nonlocal alert
        from app.models.alert import ServiceAlert

        alert = ServiceAlert(
            alert_id="A1",
            transport_mode=segment.transport_mode,
            title="測試通報",
            severity="延誤",
            affected_stations=[segment.from_station.station_id],
            affected_routes=[],
            start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status=status,
        )
        result = AlertManager.check_route_impact(route, [alert])
        expected_affected = status == "進行中"
        assert result.affected == expected_affected

    asyncio.run(build_and_check())


# Feature: cross-transport-transfer-platform, Property 18: 通報依運具分類
@given(alerts=st.lists(st_service_alert(), min_size=0, max_size=20))
@settings(max_examples=100, deadline=None)
def test_alerts_grouped_by_same_transport_mode(alerts):
    groups = AlertManager.group_by_mode(alerts)
    for mode, group in groups.items():
        assert all(a.transport_mode == mode for a in group)
    # 分組後總數量應與原始清單相同
    assert sum(len(g) for g in groups.values()) == len(alerts)


class _FailingAdapter:
    async def get_alerts(self):
        raise TDXAPIError(PlatformError(error_type=ErrorType.TIMEOUT, message="timeout", endpoint="/alerts"))


class _WorkingAdapter:
    def __init__(self, alerts):
        self._alerts = alerts

    async def get_alerts(self):
        return self._alerts


@pytest.mark.asyncio
async def test_get_active_alerts_serves_cache_within_ttl_without_refetching():
    from app.models.alert import ServiceAlert

    cache = CacheManager()
    old_alert = ServiceAlert(
        alert_id="OLD",
        transport_mode=TransportMode.TRA,
        title="舊通報",
        severity="延誤",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="進行中",
    )
    working_adapter = _WorkingAdapter([old_alert])
    manager = AlertManager([working_adapter], cache)
    first = await manager.get_active_alerts()
    assert first == [old_alert]

    # 快取尚未過期（10 分鐘 TTL 內），即使改用會失敗的 adapter 仍應直接回傳快取資料
    manager.adapters = [_FailingAdapter()]
    second = await manager.get_active_alerts()
    assert second == [old_alert]


@pytest.mark.asyncio
async def test_get_active_alerts_returns_empty_when_cache_expired_and_fetch_fails():
    cache = CacheManager()
    manager = AlertManager([_FailingAdapter()], cache)
    result = await manager.get_active_alerts()
    assert result == []


@pytest.mark.asyncio
async def test_get_active_alerts_skips_failing_adapter_but_keeps_others():
    from app.models.alert import ServiceAlert

    working_alert = ServiceAlert(
        alert_id="OK",
        transport_mode=TransportMode.THSR,
        title="正常通報",
        severity="延誤",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="進行中",
    )
    cache = CacheManager()
    manager = AlertManager([_FailingAdapter(), _WorkingAdapter([working_alert])], cache)

    result = await manager.get_active_alerts()

    assert result == [working_alert]
