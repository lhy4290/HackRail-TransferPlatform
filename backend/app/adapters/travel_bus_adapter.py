from datetime import datetime
from typing import Dict, List

from app.adapters.base_adapter import BaseTransportAdapter, FieldSpec
from app.adapters.tdx_client import TDXClient
from app.models.alert import ServiceAlert
from app.models.enums import TransportMode
from app.models.network import NetworkEdge
from app.models.station import Station
from app.models.timetable import LiveBoardEntry, TimetableEntry

# 台灣好行（TaiwanTrip）站對站行駛時間（S2TravelTime）約 13% 區間 RunTime 為 0
# （非固定班距路線常見資料缺口），此時退回以 Distance（公里）與假設平均車速估算。
# 山區/景點道路車速普遍低於市區公車，採較保守之估算車速。
TRAVEL_BUS_ASSUMED_AVG_SPEED_KMH = 30
TRAVEL_BUS_MIN_SEGMENT_MINUTES = 3


class TravelBusAdapter(BaseTransportAdapter):
    """台灣好行轉接器（真實 TDX v2 Tourism/Bus TaiwanTrip API）。

    與 BusAdapter（高鐵接駁公車，依城市+站牌關鍵字逐路線查詢）不同，台灣好行
    在 TDX 上是獨立分類，端點不以城市分頁，一次呼叫即可取得全國約 90 條台灣好行
    路線之站點與路網（真實路徑係由 TDX 原始 Swagger JSON 逐一驗證取得，非猜測），
    故本轉接器不需 BusAdapter 那種逐路線間隔呼叫的流量限制處理。

    真實資料中，多筆 SubRouteUID 記錄內容完全相同（推測為不同服務日版本），
    以 SubRouteUID 去重後再處理。
    """

    transport_mode = TransportMode.BUS

    STOP_SPECS = [
        FieldSpec("stop_id", "StopID"),
        FieldSpec("name_zh", "StopName.Zh_tw"),
        FieldSpec("name_en", "StopName.En", required=False, default=None),
        FieldSpec("latitude", "StopPosition.PositionLat", cast=float),
        FieldSpec("longitude", "StopPosition.PositionLon", cast=float),
    ]

    def __init__(self, tdx_client: TDXClient):
        super().__init__(tdx_client)
        self._stop_of_route_cache: list | None = None
        self._canonical_cache: tuple[Dict[str, Station], Dict[str, str]] | None = None

    def _namespaced_id(self, raw_stop_id: str) -> str:
        # 與 BusAdapter 之 BUS_ 前綴區隔，避免不同 TDX 資料集之 StopID 恰好相同時互相覆蓋。
        return f"TBUS_{raw_stop_id}"

    async def _fetch_stop_of_route(self) -> list:
        """取得全國台灣好行路線逐站序列，快取於實例內供 get_stations()/get_routes() 共用。"""
        if self._stop_of_route_cache is None:
            self._stop_of_route_cache = await self.tdx_client.request(
                "/v2/Tourism/Bus/StopOfRoute/TaiwanTrip"
            )
        return self._stop_of_route_cache

    async def _build_canonical_map(self) -> tuple[Dict[str, Station], Dict[str, str]]:
        """依站名（而非 StopID）合併同一站點，回傳 (站名 -> Station, 原始 StopID -> 站名)。

        真實資料中，同一實體地點（例如「高鐵嘉義站」「日月潭」）在不同子路線裡常各自
        登記為不同的 StopID（例如高鐵嘉義站在阿里山線與其他路線分屬不同 StopID），
        若逐 StopID 建站會把同一地點拆成多個互不相連的節點，導致轉乘站怎麼比對都
        比對到「不在該路線上」的那一份，路網因而斷裂。改以站名作為合併鍵，讓所有
        子路線之邊最終都收斂到同一個站點節點。風險：若不同縣市恰好有同名但不同地
        點之站牌（例如泛用之「遊客中心」），會被誤併為同一節點；本平台僅將此邏輯
        用於精選之知名景點終點站（見 capture_demo_snapshot.py），尚未發現誤併案例。
        """
        if self._canonical_cache is not None:
            return self._canonical_cache

        sub_routes = await self._fetch_stop_of_route()
        stations_by_name: Dict[str, Station] = {}
        raw_stop_id_to_name: Dict[str, str] = {}
        for sub_route in sub_routes:
            for raw in sub_route.get("Stops", []):
                fields = self._map_record(raw, self.STOP_SPECS)
                name = fields["name_zh"]
                raw_id = str(fields["stop_id"])
                raw_stop_id_to_name[raw_id] = name
                if name in stations_by_name:
                    continue
                stations_by_name[name] = Station(
                    station_id=self._namespaced_id(raw_id),
                    original_id=raw_id,
                    name_zh=name,
                    name_en=fields.get("name_en"),
                    transport_mode=self.transport_mode,
                    latitude=fields["latitude"],
                    longitude=fields["longitude"],
                )

        self._canonical_cache = (stations_by_name, raw_stop_id_to_name)
        return self._canonical_cache

    async def get_stations(self) -> List[Station]:
        stations_by_name, _ = await self._build_canonical_map()
        return list(stations_by_name.values())

    async def get_routes(self) -> List[NetworkEdge]:
        """取得同運具路網邊。

        真實 TDX 台灣好行 S2TravelTime 端點（/v2/Tourism/Bus/S2TravelTime/TaiwanTrip）
        一次回傳全國所有子路線之逐站 RunTime（秒）；RunTime 為 0 時（約 13% 區間）
        退回以 Distance（公里）與假設平均車速估算。
        """
        sub_routes = await self._fetch_stop_of_route()
        trip_names: Dict[str, str] = {
            sub_route.get("SubRouteUID"): sub_route.get("TaiwanTripName", {}).get(
                "Zh_tw", sub_route.get("SubRouteUID", "")
            )
            for sub_route in sub_routes
        }
        stations_by_name, raw_stop_id_to_name = await self._build_canonical_map()

        travel_times = await self.tdx_client.request("/v2/Tourism/Bus/S2TravelTime/TaiwanTrip")

        edges = []
        seen_sub_routes: set = set()
        for record in travel_times:
            sub_route_uid = record.get("SubRouteUID")
            if sub_route_uid in seen_sub_routes:
                continue
            seen_sub_routes.add(sub_route_uid)

            route_name = trip_names.get(sub_route_uid, sub_route_uid or "")
            for segment in record.get("TravelTimes", []):
                from_id = segment.get("FromStopID")
                to_id = segment.get("ToStopID")
                if from_id is None or to_id is None:
                    continue
                from_name = raw_stop_id_to_name.get(str(from_id))
                to_name = raw_stop_id_to_name.get(str(to_id))
                if from_name is None or to_name is None:
                    continue
                from_station_id = stations_by_name[from_name].station_id
                to_station_id = stations_by_name[to_name].station_id

                run_time_seconds = segment.get("RunTime") or 0
                if run_time_seconds > 0:
                    minutes = max(1, round(run_time_seconds / 60))
                else:
                    distance_km = segment.get("Distance") or 0
                    estimated = (
                        round(distance_km / TRAVEL_BUS_ASSUMED_AVG_SPEED_KMH * 60) if distance_km else 0
                    )
                    minutes = max(TRAVEL_BUS_MIN_SEGMENT_MINUTES, estimated)

                edges.append(
                    NetworkEdge(
                        edge_id=f"TBUS_{from_id}_{to_id}_{sub_route_uid}",
                        from_station_id=from_station_id,
                        to_station_id=to_station_id,
                        transport_mode=self.transport_mode,
                        route_name=route_name,
                        base_travel_time_min=minutes,
                    )
                )
        return edges

    async def get_timetable(self, station_id: str, date: datetime) -> List[TimetableEntry]:
        """以 Schedule/TaiwanTrip 固定時刻表回傳班表，依 ServiceDay 篩選查詢日期之星期。

        真實資料中同一站名可能對應多個原始 StopID（見 _build_canonical_map 說明），
        故比對時需接受該站名底下任一原始 StopID，而非僅比對 station_id 內嵌之單一 StopID。
        """
        _, raw_stop_id_to_name = await self._build_canonical_map()
        target_name = raw_stop_id_to_name.get(station_id.split("_", 1)[-1])
        matching_raw_ids = {
            raw_id for raw_id, name in raw_stop_id_to_name.items() if name == target_name
        }
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        target_weekday = weekday_names[date.weekday()]

        schedule_raw = await self.tdx_client.request("/v2/Tourism/Bus/Schedule/TaiwanTrip")
        entries = []
        for record in schedule_raw:
            destination = record.get("TaiwanTripName", {}).get("Zh_tw", "未知")
            direction = int(record.get("Direction", 0))
            for timetable in record.get("Timetables", []):
                service_day = timetable.get("ServiceDay", {})
                if not service_day.get(target_weekday, 0):
                    continue
                for stop_time in timetable.get("StopTimes", []):
                    if str(stop_time.get("StopID")) not in matching_raw_ids:
                        continue
                    departure = stop_time.get("DepartureTime") or stop_time.get("ArrivalTime")
                    if not departure or departure == "-:-":
                        continue
                    entries.append(
                        TimetableEntry(
                            trip_id=timetable.get("TripID", ""),
                            station_id=station_id,
                            transport_mode=self.transport_mode,
                            arrival_time=None,
                            departure_time=datetime.combine(date.date(), datetime.strptime(departure, "%H:%M").time()),
                            destination=destination,
                            direction=direction,
                        )
                    )
        return entries

    async def get_liveboard(self, station_id: str) -> List[LiveBoardEntry]:
        """即時到站預估端點（RealTimeByFrequency/RealTimeNearStop）尚未於本平台驗證，
        暫回傳空清單，由 LiveBoardService 依既有機制退回班表資料。"""
        return []

    async def get_alerts(self) -> List[ServiceAlert]:
        """取得營運通報（/v2/Tourism/Bus/News/TaiwanTrip，已於本平台驗證可回應 200）。

        真實資料中，同一 NewsID 常重複出現多筆（推測為公告牽涉多條路線，各自登記一筆），
        與 get_routes() 之 SubRouteUID 重複問題同性質，以 NewsID 去重後再處理。
        """
        raw_list = await self.tdx_client.request("/v2/Tourism/Bus/News/TaiwanTrip")
        alerts = []
        seen_news_ids: set = set()
        for raw in raw_list if isinstance(raw_list, list) else []:
            news_id = raw.get("NewsID", "")
            if news_id in seen_news_ids:
                continue
            seen_news_ids.add(news_id)
            alerts.append(
                ServiceAlert(
                    alert_id=f"TBUS_{news_id}",
                    transport_mode=self.transport_mode,
                    title=raw.get("Title", raw.get("Description", "")),
                    description=raw.get("Description", ""),
                    severity=raw.get("NewsCategory", "未知"),
                    affected_stations=[],
                    affected_routes=[],
                    start_time=datetime.fromisoformat(raw["StartTime"]) if raw.get("StartTime") else datetime.now(),
                    end_time=datetime.fromisoformat(raw["EndTime"]) if raw.get("EndTime") else None,
                )
            )
        return alerts
