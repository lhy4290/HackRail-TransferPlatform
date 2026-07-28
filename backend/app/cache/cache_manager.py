import time
from typing import Any, Callable, Optional, Protocol

from app.models.enums import CachePolicy

_TTL_MAP: dict[CachePolicy, int] = {
    CachePolicy.STATIC: 86400,  # 24 hours
    CachePolicy.REALTIME: 30,  # 30 seconds
    CachePolicy.ALERT: 600,  # 10 minutes
}


class CacheBackend(Protocol):
    def get(self, key: str) -> Optional[tuple[Any, float]]: ...

    def set(self, key: str, value: Any, stored_at: float) -> None: ...

    def delete(self, key: str) -> None: ...


class InMemoryCacheBackend:
    """記憶體快取後端（原型用）"""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[tuple[Any, float]]:
        return self._store.get(key)

    def set(self, key: str, value: Any, stored_at: float) -> None:
        self._store[key] = (value, stored_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class CacheManager:
    """快取管理器，支援不同 TTL 策略"""

    def __init__(self, backend: Optional[CacheBackend] = None, clock: Callable[[], float] = time.monotonic):
        self.backend = backend or InMemoryCacheBackend()
        self._clock = clock
        self._ttl_map = _TTL_MAP

    def ttl_seconds(self, policy: CachePolicy) -> int:
        return self._ttl_map[policy]

    async def get(self, key: str, policy: CachePolicy) -> Optional[Any]:
        """取得快取資料，若過期或不存在回傳 None"""
        entry = self.backend.get(key)
        if entry is None:
            return None
        value, stored_at = entry
        age = self._clock() - stored_at
        if age > self._ttl_map[policy]:
            self.backend.delete(key)
            return None
        return value

    async def set(self, key: str, value: Any, policy: CachePolicy) -> None:
        """設定快取資料"""
        self.backend.set(key, value, self._clock())

    async def invalidate(self, key: str) -> None:
        """手動失效特定快取"""
        self.backend.delete(key)

    async def is_stale(self, key: str, max_age_seconds: float) -> bool:
        """檢查快取資料是否已超過指定秒數（例如 24 小時過期警示判斷）"""
        entry = self.backend.get(key)
        if entry is None:
            return True
        _, stored_at = entry
        return (self._clock() - stored_at) > max_age_seconds
