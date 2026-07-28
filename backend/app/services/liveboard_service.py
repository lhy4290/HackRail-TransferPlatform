from datetime import datetime
from typing import Dict, List, Tuple

from app.adapters.base_adapter import BaseTransportAdapter
from app.cache.cache_manager import CacheManager
from app.models.enums import CachePolicy, TransportMode
from app.models.errors import TDXAPIError
from app.models.timetable import LiveBoardEntry


class LiveBoardService:
    """即時到離站服務：整合各運具轉接器即時資料，快取 30 秒，
    TDX 不可用時改用班表資料（需求 3.1, 3.2, 3.4）"""

    def __init__(self, adapters_by_mode: Dict[TransportMode, BaseTransportAdapter], cache: CacheManager):
        self.adapters_by_mode = adapters_by_mode
        self.cache = cache

    @staticmethod
    def _cache_key(station_id: str) -> str:
        return f"liveboard:{station_id}"

    async def get_liveboard(
        self, station_id: str, transport_mode: TransportMode
    ) -> Tuple[List[LiveBoardEntry], bool]:
        """回傳 (LiveBoardEntry 清單, is_realtime)

        is_realtime 為 False 時表示 TDX 即時資料不可用，改以班表時刻資料替代。
        """
        cache_key = self._cache_key(station_id)
        cached = await self.cache.get(cache_key, CachePolicy.REALTIME)
        if cached is not None:
            return cached, True

        adapter = self.adapters_by_mode[transport_mode]
        try:
            entries = await adapter.get_liveboard(station_id)
            await self.cache.set(cache_key, entries, CachePolicy.REALTIME)
            return entries, True
        except TDXAPIError:
            fallback_entries = await self._fallback_to_timetable(adapter, station_id, transport_mode)
            return fallback_entries, False

    async def _fallback_to_timetable(
        self, adapter: BaseTransportAdapter, station_id: str, transport_mode: TransportMode
    ) -> List[LiveBoardEntry]:
        timetable_entries = await adapter.get_timetable(station_id, datetime.now())
        return [
            LiveBoardEntry(
                trip_id=t.trip_id,
                station_id=t.station_id,
                transport_mode=transport_mode,
                estimated_arrival=t.arrival_time,
                scheduled_arrival=t.arrival_time,
                destination=t.destination,
            )
            for t in timetable_entries
        ]

    @staticmethod
    def has_sufficient_connection_time(available_minutes: int, buffer_time_min: int) -> bool:
        """Property 8：可用銜接時間（下一班次到站時間 - 前段到達時間）是否足夠

        回傳 True 表示銜接時間充足；False 表示應標示警示。
        """
        return available_minutes >= buffer_time_min
