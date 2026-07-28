import logging
from dataclasses import dataclass
from typing import Dict, List

from app.adapters.base_adapter import BaseTransportAdapter
from app.cache.cache_manager import CacheManager
from app.models.alert import ServiceAlert
from app.models.enums import CachePolicy, TransportMode
from app.models.errors import TDXAPIError
from app.models.route import RoutePlanDTO
from app.services.route_planner import RoutePlanner

logger = logging.getLogger(__name__)

ALERTS_CACHE_KEY = "alerts:all"


@dataclass
class RouteImpactResult:
    """路線受營運異常影響之檢查結果"""

    affected: bool
    alerts: List[ServiceAlert]


class AlertManager:
    """營運異常通報管理，整合 TDX 營運通報資料（需求 8.1-8.6）"""

    def __init__(self, adapters: List[BaseTransportAdapter], cache: CacheManager):
        self.adapters = adapters
        self.cache = cache

    async def get_active_alerts(self) -> List[ServiceAlert]:
        """取得所有進行中的營運通報。

        通報快取採 ALERT 策略（TTL 10 分鐘），只要快取未過期即直接回傳，
        天然滿足「保留最近一次成功取得之通報資料，快取保留時間不超過 10 分鐘」
        （需求 8.6）；快取過期後才會重新呼叫 TDX，若當下呼叫失敗則回傳空清單，
        由呼叫端顯示「營運通報資訊暫不可用」。
        """
        cached = await self.cache.get(ALERTS_CACHE_KEY, CachePolicy.ALERT)
        if cached is not None:
            return cached

        all_alerts: List[ServiceAlert] = []
        for adapter in self.adapters:
            try:
                all_alerts.extend(await adapter.get_alerts())
            except TDXAPIError:
                logger.warning("擷取 %s 營運通報失敗，略過該運具", getattr(adapter, "transport_mode", adapter))

        await self.cache.set(ALERTS_CACHE_KEY, all_alerts, CachePolicy.ALERT)
        return all_alerts

    @staticmethod
    def group_by_mode(alerts: List[ServiceAlert]) -> Dict[TransportMode, List[ServiceAlert]]:
        """通報依 Transport_Mode 分類（Property 18）"""
        groups: Dict[TransportMode, List[ServiceAlert]] = {}
        for alert in alerts:
            groups.setdefault(alert.transport_mode, []).append(alert)
        return groups

    @staticmethod
    def check_route_impact(route: RoutePlanDTO, alerts: List[ServiceAlert]) -> RouteImpactResult:
        """檢查特定路線是否受進行中之營運異常影響（Property 17）"""
        affected_station_ids = {
            station.station_id for seg in route.segments for station in (seg.from_station, seg.to_station)
        }
        route_trip_ids = {seg.trip_id for seg in route.segments}

        matched = [
            alert
            for alert in alerts
            if alert.is_active
            and (
                affected_station_ids & set(alert.affected_stations)
                or route_trip_ids & set(alert.affected_routes)
            )
        ]
        return RouteImpactResult(affected=bool(matched), alerts=matched)

    async def suggest_alternatives(
        self,
        planner: RoutePlanner,
        origin: str,
        destination: str,
        departure_time,
        alerts: List[ServiceAlert],
        max_results: int = 5,
    ) -> List[RoutePlanDTO]:
        """建議不經過受影響路段之替代路線"""
        candidates = await planner.plan_routes(origin, destination, departure_time, max_results=max_results)
        return [r for r in candidates if not self.check_route_impact(r, alerts).affected]
