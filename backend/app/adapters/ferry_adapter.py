from datetime import datetime
from typing import Dict, List, Tuple

from app.adapters.base_adapter import BaseTransportAdapter, FieldSpec
from app.adapters.tdx_client import TDXClient
from app.models.alert import ServiceAlert
from app.models.enums import TransportMode
from app.models.network import NetworkEdge
from app.models.station import Station
from app.models.timetable import LiveBoardEntry, TimetableEntry

# 短程渡輪多以固定班距（Frequencies）營運、無逐班時刻，GeneralSchedule 亦無法提供
# 站間行駛時間；此時退回以航線總距離（RouteDistance，公里）除以假設平均航速估算，
# 屬暫時性估算，非實際船班資料。
FERRY_ASSUMED_AVG_SPEED_KMH = 15

# 短程渡輪（如鼓山－旗津）純距離/航速估算會嚴重低估實際航程時間，因為靠泊、
# 上下船耗時不隨距離縮短而等比例減少；故以此作為估算下限（TDX Description
# 對此類短程航線多描述為「航程約 10 分鐘左右」）。
FERRY_MIN_CROSSING_MINUTES = 8


class FerryAdapter(BaseTransportAdapter):
    """渡輪轉接器（真實 TDX v3 Ship API，僅涵蓋市內短程航線 RouteType=Internal）

    與其他運具不同，TDX 渡輪類別實際掛在 /v3/Ship/...（非 /v2/），且站點稱為
    「港口 Port」而非 Station。RouteType 需指定為 Internal/OutlyingIslands/
    Bilateral/MiniThreeLinks/Other 其中之一；本轉接器僅處理 Internal（市內短程
    航線，如高雄鼓山－旗津渡輪），跨島/兩岸航線暫不在此平台範圍內。
    """

    transport_mode = TransportMode.FERRY

    ROUTE_TYPE = "Internal"
    ALERT_CITY = "Kaohsiung"

    PORT_SPECS = [
        FieldSpec("port_id", "PortID"),
        FieldSpec("name_zh", "PortName.Zh_tw"),
        FieldSpec("name_en", "PortName.En", required=False, default=None),
        FieldSpec("latitude", "PortPosition.PositionLat", cast=float),
        FieldSpec("longitude", "PortPosition.PositionLon", cast=float),
    ]

    def __init__(self, tdx_client: TDXClient):
        super().__init__(tdx_client)

    def _namespaced_id(self, raw_port_id: str) -> str:
        return f"FERRY_{raw_port_id}"

    async def get_stations(self) -> List[Station]:
        envelope = await self.tdx_client.request("/v3/Ship/Port")
        raw_list = envelope.get("Ports", []) if isinstance(envelope, dict) else envelope
        stations = []
        for raw in raw_list:
            fields = self._map_record(raw, self.PORT_SPECS)
            stations.append(
                Station(
                    station_id=self._namespaced_id(str(fields["port_id"])),
                    original_id=str(fields["port_id"]),
                    name_zh=fields["name_zh"],
                    name_en=fields.get("name_en"),
                    transport_mode=self.transport_mode,
                    latitude=fields["latitude"],
                    longitude=fields["longitude"],
                    address=raw.get("City"),
                )
            )
        return stations

    @staticmethod
    def _extract_schedule_minutes(schedule_raw: list) -> Dict[Tuple[str, int, str, str], int]:
        """由 GeneralSchedule 之 TimeTables 逐站 TravelTime（分鐘）萃取站間實際航行時間。

        僅部分航線（如觀光船班）有固定時刻表；採班距營運之短程渡輪
        （如鼓山－旗津）TimeTables 為空，需由呼叫端另以距離估算。
        """
        minutes_by_segment: Dict[Tuple[str, int, str, str], int] = {}
        for route in schedule_raw:
            route_id = route.get("RouteID", "")
            direction = int(route.get("Direction", 0))
            for timetable in route.get("TimeTables", []):
                stop_times = sorted(timetable.get("StopTimes", []), key=lambda s: s["StopSequence"])
                for prev, curr in zip(stop_times, stop_times[1:]):
                    minutes = prev.get("TravelTime")
                    if minutes:
                        minutes_by_segment[(route_id, direction, prev["PortID"], curr["PortID"])] = max(
                            1, round(minutes)
                        )
        return minutes_by_segment

    async def get_routes(self) -> List[NetworkEdge]:
        """取得同運具路網邊。

        真實 TDX 無統一之渡輪「站對站行駛時間」端點：以 StopOfRoute 取得航線
        逐站序列（已含雙向），優先以 GeneralSchedule 之固定時刻表換算實際航行
        時間；無固定時刻表（班距營運）之航線則退回以 Route 之 RouteDistance
        與假設平均航速估算。
        """
        stop_of_route = await self.tdx_client.request(
            f"/v3/Ship/StopOfRoute/RouteType/{self.ROUTE_TYPE}"
        )
        schedule_raw = await self.tdx_client.request(
            f"/v3/Ship/GeneralSchedule/RouteType/{self.ROUTE_TYPE}"
        )
        routes_raw = await self.tdx_client.request(f"/v3/Ship/Route/RouteType/{self.ROUTE_TYPE}")

        schedule_minutes = self._extract_schedule_minutes(schedule_raw)
        distance_by_route: Dict[str, float] = {
            r["RouteID"]: r.get("RouteDistance", 0) for r in routes_raw if r.get("RouteDistance")
        }

        edges = []
        for route in stop_of_route:
            route_id = route.get("RouteID", "")
            direction = int(route.get("Direction", 0))
            stops = sorted(route.get("Stops", []), key=lambda s: s["StopSequence"])
            segment_count = max(1, len(stops) - 1)
            distance_km = distance_by_route.get(route_id, 0)

            for prev, curr in zip(stops, stops[1:]):
                prev_port = str(prev["PortID"])
                curr_port = str(curr["PortID"])
                minutes = schedule_minutes.get((route_id, direction, prev_port, curr_port))
                if minutes is None:
                    per_segment_km = distance_km / segment_count if distance_km else 0
                    estimated = round(per_segment_km / FERRY_ASSUMED_AVG_SPEED_KMH * 60) if per_segment_km else 0
                    minutes = max(FERRY_MIN_CROSSING_MINUTES, estimated)

                edges.append(
                    NetworkEdge(
                        edge_id=f"FERRY_{prev_port}_{curr_port}_{route_id}_{direction}",
                        from_station_id=self._namespaced_id(prev_port),
                        to_station_id=self._namespaced_id(curr_port),
                        transport_mode=self.transport_mode,
                        route_name=route.get("RouteName", {}).get("Zh_tw", route_id),
                        base_travel_time_min=minutes,
                    )
                )
        return edges

    async def get_timetable(self, station_id: str, date: datetime) -> List[TimetableEntry]:
        """以 GeneralSchedule 固定時刻表回傳班表；班距營運（無固定時刻表）之航線回傳空清單。"""
        raw_port_id = station_id.split("_", 1)[-1]
        schedule_raw = await self.tdx_client.request(
            f"/v3/Ship/GeneralSchedule/RouteType/{self.ROUTE_TYPE}"
        )
        entries = []
        for route in schedule_raw:
            for timetable in route.get("TimeTables", []):
                stop_times = timetable.get("StopTimes", [])
                for stop_time in stop_times:
                    if str(stop_time.get("PortID")) != raw_port_id:
                        continue
                    departure = stop_time.get("DepartureTime") or stop_time.get("ArrivalTime")
                    if not departure:
                        continue
                    entries.append(
                        TimetableEntry(
                            trip_id=timetable.get("TripID", ""),
                            station_id=station_id,
                            transport_mode=self.transport_mode,
                            arrival_time=None,
                            departure_time=datetime.combine(date.date(), datetime.strptime(departure, "%H:%M").time()),
                            destination=route.get("RouteName", {}).get("Zh_tw", "未知"),
                            direction=int(route.get("Direction", 0)),
                        )
                    )
        return entries

    async def get_liveboard(self, station_id: str) -> List[LiveBoardEntry]:
        """TDX 渡輪類別無即時船位/到站資訊之公開端點，故一律回傳空清單，
        由 LiveBoardService 依既有機制退回班表資料。"""
        return []

    async def get_alerts(self) -> List[ServiceAlert]:
        """取得營運通報。

        端點與欄位命名尚未如 Metro/TRA/THSR 般於本平台完整驗證過（僅初步查證
        /v3/Ship/Alert/Domestic/City/{City} 可回應 200），故欄位解析採保守預設，
        格式不符時寧可回傳空清單，不猜測語意。
        """
        raw_list = await self.tdx_client.request(f"/v3/Ship/Alert/Domestic/City/{self.ALERT_CITY}")
        alerts = []
        for raw in raw_list if isinstance(raw_list, list) else []:
            alerts.append(
                ServiceAlert(
                    alert_id=f"FERRY_{raw.get('AlertID', raw.get('RouteID', ''))}",
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
