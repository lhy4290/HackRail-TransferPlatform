import pytest

from app.cache.cache_manager import CacheManager
from app.models.enums import CachePolicy


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.asyncio
async def test_cache_hit_before_ttl_expires():
    clock = FakeClock()
    cache = CacheManager(clock=clock)
    await cache.set("station:list", ["A", "B"], CachePolicy.STATIC)

    clock.now += 100  # well within 24h TTL
    assert await cache.get("station:list", CachePolicy.STATIC) == ["A", "B"]


@pytest.mark.asyncio
async def test_cache_miss_after_ttl_expires():
    clock = FakeClock()
    cache = CacheManager(clock=clock)
    await cache.set("liveboard:123", {"delay": 0}, CachePolicy.REALTIME)

    clock.now += 31  # REALTIME TTL is 30 seconds
    assert await cache.get("liveboard:123", CachePolicy.REALTIME) is None


@pytest.mark.asyncio
async def test_cache_miss_for_unknown_key():
    cache = CacheManager()
    assert await cache.get("missing", CachePolicy.ALERT) is None


@pytest.mark.asyncio
async def test_invalidate_removes_entry():
    cache = CacheManager()
    await cache.set("k", 1, CachePolicy.STATIC)
    await cache.invalidate("k")
    assert await cache.get("k", CachePolicy.STATIC) is None


@pytest.mark.asyncio
async def test_is_stale_reflects_age():
    clock = FakeClock()
    cache = CacheManager(clock=clock)
    await cache.set("stations", [], CachePolicy.STATIC)

    assert await cache.is_stale("stations", max_age_seconds=86400) is False
    clock.now += 86401
    assert await cache.is_stale("stations", max_age_seconds=86400) is True
