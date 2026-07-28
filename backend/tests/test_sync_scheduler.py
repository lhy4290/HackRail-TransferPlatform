import pytest

from app.cache.cache_manager import CacheManager
from app.models.enums import CachePolicy
from app.services.alert_manager import AlertManager
from app.services.sync_scheduler import STATIC_DATA_CACHE_KEY, SyncScheduler


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _CountingAdapter:
    def __init__(self):
        self.call_count = 0

    async def get_alerts(self):
        self.call_count += 1
        return []


@pytest.mark.asyncio
async def test_refresh_alerts_once_invalidates_and_refetches():
    cache = CacheManager()
    adapter = _CountingAdapter()
    manager = AlertManager([adapter], cache)

    await manager.get_active_alerts()
    assert adapter.call_count == 1

    # 快取仍在 10 分鐘 TTL 內，正常情況下不會重新呼叫
    await manager.get_active_alerts()
    assert adapter.call_count == 1

    scheduler = SyncScheduler(alert_manager=manager, cache=cache)
    await scheduler.refresh_alerts_once()
    assert adapter.call_count == 2


@pytest.mark.asyncio
async def test_check_static_data_once_detects_staleness_over_24h():
    clock = FakeClock()
    cache = CacheManager(clock=clock)
    await cache.set(STATIC_DATA_CACHE_KEY, True, CachePolicy.STATIC)

    manager = AlertManager([], cache)
    scheduler = SyncScheduler(alert_manager=manager, cache=cache)

    # 尚未超過 24 小時
    assert await scheduler.check_static_data_once() is False

    clock.now += 86401
    assert await scheduler.check_static_data_once() is True

    # 重新擷取後應重設過期時間，緊接著檢查應恢復為未過期
    assert await scheduler.check_static_data_once() is False


@pytest.mark.asyncio
async def test_start_and_stop_runs_loops_without_error():
    cache = CacheManager()
    manager = AlertManager([_CountingAdapter()], cache)

    calls = []

    async def fast_sleep(seconds):
        calls.append(seconds)
        if len(calls) > 3:
            raise RuntimeError("stop")

    scheduler = SyncScheduler(
        alert_manager=manager,
        cache=cache,
        alert_interval_seconds=0.01,
        static_check_interval_seconds=0.01,
        sleep_fn=fast_sleep,
    )
    scheduler.start()
    await scheduler.stop()
    # 停止後不應留下任何未完成任務
    assert scheduler._tasks == []
