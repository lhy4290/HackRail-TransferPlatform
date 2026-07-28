import asyncio
import logging
from datetime import datetime
from typing import Dict, List

from app.adapters.base_adapter import BaseTransportAdapter, FieldSpec
from app.adapters.tdx_client import TDXClient
from app.models.alert import ServiceAlert
from app.models.enums import TransportMode
from app.models.errors import TDXAPIError
from app.models.network import NetworkEdge
from app.models.station import Station
from app.models.timetable import LiveBoardEntry, TimetableEntry

logger = logging.getLogger(__name__)

# get_routes() 對每條匹配路線各別呼叫一次 S2STravelTime（同一縣市內密集連續呼叫
# 同一端點），與其他轉接器單次呼叫即取得全網資料不同，故路線間需錯開間隔避免
# 觸發 TDX 429 流量限制。
PER_ROUTE_REQUEST_INTERVAL_SECONDS = 2.0


class BusAdapter(BaseTransportAdapter):
    """公路客運轉接器（真實 TDX v2 Bus City API），範圍限定於高鐵站接駁公車。

    全國公車路網規模極大（單一縣市即數百條路線），不適合比照鐵路/渡輪整批匯入；
    故本轉接器以建構子參數（city, hsr_stop_filter）限定只匯入「行經指定高鐵接駁
    站牌」之路線與站牌，作為高鐵站與周邊城鎮接駁之示範，而非全國公車路網。
    要新增其他高鐵站（如高鐵彰化站、高鐵台南站），只需以不同參數再建立一個實例，
    無需修改本類別。
    """

    transport_mode = TransportMode.BUS

    STOP_SPECS = [
        FieldSpec("stop_id", "StopID"),
        FieldSpec("name_zh", "StopName.Zh_tw"),
        FieldSpec("name_en", "StopName.En", required=False, default=None),
        FieldSpec("latitude", "StopPosition.PositionLat", cast=float),
        FieldSpec("longitude", "StopPosition.PositionLon", cast=float),
    ]

    def __init__(self, city: str, hsr_stop_filter: str, tdx_client: TDXClient):
        super().__init__(tdx_client)
        self.city = city
        self.hsr_stop_filter = hsr_stop_filter
        self._matched_routes_cache: list | None = None

    def _namespaced_id(self, raw_stop_id: str) -> str:
        return f"BUS_{raw_stop_id}"

    async def _matched_routes(self) -> list:
        """取得該城市內，行經指定高鐵接駁站牌之路線（含逐站站序）。

        get_stations()/get_routes() 皆需要此資料，快取於實例內以避免同一次
        資料匯入重複呼叫 /v2/Bus/StopOfRoute/City/{City}（該端點資料量較大，
        重複呼叫易觸發 TDX 429 流量限制）。
        """
        if self._matched_routes_cache is None:
            all_routes = await self.tdx_client.request(f"/v2/Bus/StopOfRoute/City/{self.city}")
            self._matched_routes_cache = [
                route
                for route in all_routes
                if any(self.hsr_stop_filter in s.get("StopName", {}).get("Zh_tw", "") for s in route.get("Stops", []))
            ]
        return self._matched_routes_cache

    async def get_stations(self) -> List[Station]:
        routes = await self._matched_routes()
        stations: Dict[str, Station] = {}
        for route in routes:
            for raw in route.get("Stops", []):
                fields = self._map_record(raw, self.STOP_SPECS)
                station_id = self._namespaced_id(str(fields["stop_id"]))
                if station_id in stations:
                    continue
                stations[station_id] = Station(
                    station_id=station_id,
                    original_id=str(fields["stop_id"]),
                    name_zh=fields["name_zh"],
                    name_en=fields.get("name_en"),
                    transport_mode=self.transport_mode,
                    latitude=fields["latitude"],
                    longitude=fields["longitude"],
                )
        return list(stations.values())

    async def get_routes(self) -> List[NetworkEdge]:
        """取得同運具路網邊。

        真實 TDX 端點為 /v2/Bus/S2STravelTime/City/{City}/{RouteID}，格式與 Metro
        之 S2STravelTime 相同（依時段分桶之逐站區間 RunTime，秒），僅取第一個時段
        區間作為代表性估算（尖離峰行駛時間本有差異，暫不逐時段區分）。
        """
        routes = await self._matched_routes()
        route_ids = {route.get("RouteID") for route in routes if route.get("RouteID")}

        route_names: Dict[str, str] = {
            route.get("RouteID"): route.get("RouteName", {}).get("Zh_tw", route.get("RouteID", ""))
            for route in routes
        }

        edges = []
        for index, route_id in enumerate(route_ids):
            if index > 0:
                await asyncio.sleep(PER_ROUTE_REQUEST_INTERVAL_SECONDS)
            try:
                travel_data = await self.tdx_client.request(
                    f"/v2/Bus/S2STravelTime/City/{self.city}/{route_id}"
                )
            except TDXAPIError:
                logger.warning("擷取公車路線 %s 站對站行駛時間失敗，略過該路線", route_id)
                continue

            for sub_route in travel_data:
                time_windows = sub_route.get("TravelTimes", [])
                if not time_windows:
                    continue
                for segment in time_windows[0].get("S2STimes", []):
                    run_time_seconds = segment.get("RunTime")
                    if run_time_seconds is None:
                        continue
                    from_id = str(segment["FromStopID"])
                    to_id = str(segment["ToStopID"])
                    edges.append(
                        NetworkEdge(
                            edge_id=f"BUS_{from_id}_{to_id}_{route_id}",
                            from_station_id=self._namespaced_id(from_id),
                            to_station_id=self._namespaced_id(to_id),
                            transport_mode=self.transport_mode,
                            route_name=route_names.get(route_id, route_id),
                            base_travel_time_min=max(1, round(run_time_seconds / 60)),
                        )
                    )
        return edges

    async def get_timetable(self, station_id: str, date: datetime) -> List[TimetableEntry]:
        """公路客運無統一之固定時刻表端點（多為即時預估到站時間），暫回傳空清單。"""
        return []

    async def get_liveboard(self, station_id: str) -> List[LiveBoardEntry]:
        """即時到站預估端點尚未於本平台驗證，暫回傳空清單，
        由 LiveBoardService 依既有機制退回班表資料（目前亦為空）。"""
        return []

    async def get_alerts(self) -> List[ServiceAlert]:
        """取得營運通報。

        端點與欄位命名尚未於本平台完整驗證過，故欄位解析採保守預設，
        格式不符時寧可回傳空清單，不猜測語意。
        """
        raw_list = await self.tdx_client.request(f"/v2/Bus/Alert/City/{self.city}")
        alerts = []
        for raw in raw_list if isinstance(raw_list, list) else []:
            alerts.append(
                ServiceAlert(
                    alert_id=f"BUS_{raw.get('AlertID', raw.get('RouteID', ''))}",
                    transport_mode=self.transport_mode,
                    title=raw.get("Title", raw.get("Description", "")),
                    description=raw.get("Description", ""),
                    severity=raw.get("Title", "未知"),
                    affected_stations=[],
                    affected_routes=[str(raw.get("RouteID"))] if raw.get("RouteID") else [],
                    start_time=datetime.fromisoformat(raw["PublishTime"]) if raw.get("PublishTime") else datetime.now(),
                    end_time=None,
                )
            )
        return alerts
