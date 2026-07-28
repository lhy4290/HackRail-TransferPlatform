import asyncio
import logging
from typing import Callable, List

from app.models.enums import CachePolicy
from app.services.alert_manager import ALERTS_CACHE_KEY, AlertManager
from app.cache.cache_manager import CacheManager

logger = logging.getLogger(__name__)

# 營運通報須於 2 分鐘內反映至查詢結果（需求 8.1），故排程週期設為 2 分鐘
DEFAULT_ALERT_REFRESH_INTERVAL_SECONDS = 120
# 靜態資料 TTL 為 24 小時，每小時檢查一次是否需要重新擷取（需求 4.6, 9.4）
DEFAULT_STATIC_CHECK_INTERVAL_SECONDS = 3600

STATIC_DATA_CACHE_KEY = "network_graph_loaded_at"
STATIC_DATA_MAX_AGE_SECONDS = 86400


class SyncScheduler:
    """後端定期資料同步排程

    - 每 ALERT_REFRESH_INTERVAL_SECONDS 秒重新整理營運通報快取，確保新通報於 2 分鐘內反映
    - 每 STATIC_CHECK_INTERVAL_SECONDS 秒檢查靜態資料是否已超過 24 小時，過期則觸發重新擷取
    """

    def __init__(
        self,
        alert_manager: AlertManager,
        cache: CacheManager,
        alert_interval_seconds: int = DEFAULT_ALERT_REFRESH_INTERVAL_SECONDS,
        static_check_interval_seconds: int = DEFAULT_STATIC_CHECK_INTERVAL_SECONDS,
        sleep_fn: Callable = asyncio.sleep,
    ):
        self.alert_manager = alert_manager
        self.cache = cache
        self.alert_interval_seconds = alert_interval_seconds
        self.static_check_interval_seconds = static_check_interval_seconds
        self.sleep_fn = sleep_fn
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def refresh_alerts_once(self) -> None:
        """立即重新整理營運通報快取（需求 8.1）"""
        await self.cache.invalidate(ALERTS_CACHE_KEY)
        await self.alert_manager.get_active_alerts()

    async def check_static_data_once(self) -> bool:
        """檢查靜態資料是否已超過 24 小時；過期則重新標記擷取時間（需求 4.6）

        回傳 True 表示資料已過期並已觸發重新擷取。
        """
        is_stale = await self.cache.is_stale(STATIC_DATA_CACHE_KEY, max_age_seconds=STATIC_DATA_MAX_AGE_SECONDS)
        if is_stale:
            logger.info("靜態資料已超過 24 小時，觸發重新擷取")
            await self.cache.set(STATIC_DATA_CACHE_KEY, True, CachePolicy.STATIC)
        return is_stale

    async def _alerts_loop(self) -> None:
        while self._running:
            try:
                await self.refresh_alerts_once()
            except Exception:
                logger.exception("營運通報定期更新失敗")
            await self.sleep_fn(self.alert_interval_seconds)

    async def _static_data_loop(self) -> None:
        while self._running:
            try:
                await self.check_static_data_once()
            except Exception:
                logger.exception("靜態資料過期檢查失敗")
            await self.sleep_fn(self.static_check_interval_seconds)

    def start(self) -> None:
        self._running = True
        self._tasks = [
            asyncio.create_task(self._alerts_loop()),
            asyncio.create_task(self._static_data_loop()),
        ]

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = []
