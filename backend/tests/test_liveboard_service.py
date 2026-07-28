import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.cache.cache_manager import CacheManager
from app.models.enums import TransportMode
from app.models.errors import PlatformError, TDXAPIError, ErrorType
from app.models.timetable import LiveBoardEntry, TimetableEntry
from app.services.liveboard_service import LiveBoardService


class _FakeAdapter:
    def __init__(self, liveboard_entries=None, timetable_entries=None, fail_liveboard=False):
        self.liveboard_entries = liveboard_entries or []
        self.timetable_entries = timetable_entries or []
        self.fail_liveboard = fail_liveboard

    async def get_liveboard(self, station_id):
        if self.fail_liveboard:
            raise TDXAPIError(
                PlatformError(error_type=ErrorType.TIMEOUT, message="timeout", endpoint="/liveboard")
            )
        return self.liveboard_entries

    async def get_timetable(self, station_id, date):
        return self.timetable_entries


# Feature: cross-transport-transfer-platform, Property 7: 延誤狀態計算
@given(delay=st.integers(min_value=-30, max_value=60))
@settings(max_examples=100)
def test_liveboard_entry_delay_and_status(delay):
    scheduled = datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)
    entry = LiveBoardEntry(
        trip_id="T1",
        station_id="S1",
        transport_mode=TransportMode.TRA,
        estimated_arrival=scheduled + timedelta(minutes=delay),
        scheduled_arrival=scheduled,
        destination="終點",
    )
    assert entry.delay_minutes == delay
    if delay < 0:
        assert entry.status == "提前"
    elif delay == 0:
        assert entry.status == "準點"
    else:
        assert entry.status == "延誤"


# Feature: cross-transport-transfer-platform, Property 8: 銜接不足警示
@given(
    available_minutes=st.integers(min_value=0, max_value=60),
    buffer_time_min=st.integers(min_value=1, max_value=30),
)
@settings(max_examples=100)
def test_connection_time_sufficiency(available_minutes, buffer_time_min):
    sufficient = LiveBoardService.has_sufficient_connection_time(available_minutes, buffer_time_min)
    assert sufficient == (available_minutes >= buffer_time_min)


@pytest.mark.asyncio
async def test_get_liveboard_returns_realtime_data_and_caches():
    entries = [
        LiveBoardEntry(
            trip_id="T1",
            station_id="S1",
            transport_mode=TransportMode.TRA,
            destination="終點",
        )
    ]
    adapter = _FakeAdapter(liveboard_entries=entries)
    cache = CacheManager()
    service = LiveBoardService({TransportMode.TRA: adapter}, cache)

    result, is_realtime = await service.get_liveboard("S1", TransportMode.TRA)
    assert is_realtime is True
    assert result == entries

    # 第二次呼叫應從快取取得（不再呼叫 adapter）
    adapter.fail_liveboard = True
    result2, is_realtime2 = await service.get_liveboard("S1", TransportMode.TRA)
    assert is_realtime2 is True
    assert result2 == entries


@pytest.mark.asyncio
async def test_get_liveboard_falls_back_to_timetable_when_tdx_unavailable():
    timetable_entries = [
        TimetableEntry(
            trip_id="T2",
            station_id="S2",
            transport_mode=TransportMode.TRA,
            arrival_time=datetime(2026, 1, 5, 9, 0),
            destination="終點2",
            direction=0,
        )
    ]
    adapter = _FakeAdapter(fail_liveboard=True, timetable_entries=timetable_entries)
    cache = CacheManager()
    service = LiveBoardService({TransportMode.TRA: adapter}, cache)

    result, is_realtime = await service.get_liveboard("S2", TransportMode.TRA)
    assert is_realtime is False
    assert len(result) == 1
    assert result[0].trip_id == "T2"
    assert result[0].destination == "終點2"
