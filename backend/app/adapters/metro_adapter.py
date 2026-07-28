from datetime import datetime
from typing import List

from app.adapters.base_adapter import BaseTransportAdapter, FieldSpec
from app.adapters.tdx_client import TDXClient
from app.models.alert import ServiceAlert
from app.models.enums import TransportMode
from app.models.network import NetworkEdge
from app.models.station import Station
from app.models.timetable import LiveBoardEntry, TimetableEntry

_SYSTEM_TO_MODE = {
    "TYMC": TransportMode.METRO_TAOYUAN,
    "KRTC": TransportMode.METRO_KAOHSIUNG,
    "TMRT": TransportMode.METRO_TAICHUNG,
}

NORMAL_OPERATION_TITLE = "正常營運"


class MetroAdapter(BaseTransportAdapter):
    """捷運轉接器（桃園/臺中/高雄共用，透過 system_id 區分）

    原始 TDX 捷運資料格式：StationID、StationName.Zh_tw/En（雙語物件）、
    StationPosition.PositionLon/PositionLat。
    """

    STATION_SPECS = [
        FieldSpec("station_id", "StationID"),
        FieldSpec("name_zh", "StationName.Zh_tw"),
        FieldSpec("name_en", "StationName.En", required=False, default=None),
        FieldSpec("latitude", "StationPosition.PositionLat", cast=float),
        FieldSpec("longitude", "StationPosition.PositionLon", cast=float),
    ]

    LIVEBOARD_SPECS = [
        FieldSpec("trip_id", "TripID"),
        FieldSpec("station_id", "StationID"),
        FieldSpec("estimated_arrival", "EstimatedTime", required=False, default=None, cast=datetime.fromisoformat),
        FieldSpec("scheduled_arrival", "ScheduledTime", required=False, default=None, cast=datetime.fromisoformat),
        FieldSpec("destination", "DestinationStationName.Zh_tw", required=False, default="未知"),
    ]

    def __init__(self, system_id: str, tdx_client: TDXClient):
        super().__init__(tdx_client)
        self.system_id = system_id
        self.transport_mode = _SYSTEM_TO_MODE[system_id]

    def _namespaced_id(self, raw_station_id: str) -> str:
        return f"{self.system_id}_{raw_station_id}"

    async def get_stations(self) -> List[Station]:
        raw_list = await self.tdx_client.request(f"/v2/Rail/Metro/Station/{self.system_id}")
        stations = []
        for raw in raw_list:
            fields = self._map_record(raw, self.STATION_SPECS)
            stations.append(
                Station(
                    station_id=self._namespaced_id(str(fields["station_id"])),
                    original_id=str(fields["station_id"]),
                    name_zh=fields["name_zh"],
                    name_en=fields.get("name_en"),
                    transport_mode=self.transport_mode,
                    latitude=fields["latitude"],
                    longitude=fields["longitude"],
                )
            )
        return stations

    async def get_routes(self) -> List[NetworkEdge]:
        """取得站對站行駛時間，組成同運具路網邊。

        真實 TDX 端點為 /v2/Rail/Metro/S2STravelTime/{system}，
        回傳格式為「每條路線一筆記錄，內含 TravelTimes 逐站區間陣列」，
        RunTime 單位為秒，需換算為分鐘。
        """
        raw_list = await self.tdx_client.request(f"/v2/Rail/Metro/S2STravelTime/{self.system_id}")
        edges = []
        for line in raw_list:
            line_name = line.get("LineID") or line.get("LineNo")
            for segment in line.get("TravelTimes", []):
                run_time_seconds = int(segment["RunTime"])
                edges.append(
                    NetworkEdge(
                        edge_id=f"{self.system_id}_{segment['FromStationID']}_{segment['ToStationID']}_{line_name}",
                        from_station_id=self._namespaced_id(segment["FromStationID"]),
                        to_station_id=self._namespaced_id(segment["ToStationID"]),
                        transport_mode=self.transport_mode,
                        route_name=line_name,
                        base_travel_time_min=max(1, round(run_time_seconds / 60)),
                    )
                )
        return edges

    async def get_timetable(self, station_id: str, date: datetime) -> List[TimetableEntry]:
        raw_station_id = station_id.split("_", 1)[-1]
        raw_list = await self.tdx_client.request(
            f"/v2/Rail/Metro/S2STravelTime/{self.system_id}",
            params={"$filter": f"StationID eq '{raw_station_id}'", "date": date.date().isoformat()},
        )
        entries = []
        for raw in raw_list:
            entries.append(
                TimetableEntry(
                    trip_id=raw["TripID"],
                    station_id=station_id,
                    transport_mode=self.transport_mode,
                    arrival_time=datetime.fromisoformat(raw["ArrivalTime"]) if raw.get("ArrivalTime") else None,
                    departure_time=datetime.fromisoformat(raw["DepartureTime"]) if raw.get("DepartureTime") else None,
                    destination=raw.get("DestinationStationName", {}).get("Zh_tw", "未知"),
                    direction=int(raw.get("Direction", 0)),
                )
            )
        return entries

    async def get_liveboard(self, station_id: str) -> List[LiveBoardEntry]:
        raw_station_id = station_id.split("_", 1)[-1]
        raw_list = await self.tdx_client.request(f"/v2/Rail/Metro/LiveBoard/{self.system_id}/{raw_station_id}")
        entries = []
        for raw in raw_list:
            fields = self._map_record(raw, self.LIVEBOARD_SPECS)
            entries.append(
                LiveBoardEntry(
                    trip_id=str(fields["trip_id"]),
                    station_id=station_id,
                    transport_mode=self.transport_mode,
                    estimated_arrival=fields.get("estimated_arrival"),
                    scheduled_arrival=fields.get("scheduled_arrival"),
                    destination=fields.get("destination", "未知"),
                )
            )
        return entries

    async def get_alerts(self) -> List[ServiceAlert]:
        """取得營運通報。

        真實 TDX 端點回傳格式為 {"Alerts": [...], "UpdateTime": ..., ...} 之包裝物件，
        並非陣列本身；每筆通報之 Scope（受影響站點/路線/車次）巢狀結構與 Status
        對照表目前僅觀察到「正常營運」單一案例，尚無實際延誤/停駛案例可驗證確切欄位語意，
        故 affected_stations/affected_routes 採保守解析，格式不符時回傳空清單
        （避免誤判路線受影響，優先安全退化而非猜測）。
        """
        envelope = await self.tdx_client.request(f"/v2/Rail/Metro/Alert/{self.system_id}")
        raw_list = envelope.get("Alerts", []) if isinstance(envelope, dict) else envelope

        alerts = []
        for raw in raw_list:
            if raw.get("Title") == NORMAL_OPERATION_TITLE:
                # TDX 於無異常時仍會回傳一筆「正常營運」佔位通報，非真正的營運異常，故略過
                continue
            scope = raw.get("Scope") or {}
            affected_stations = [
                self._namespaced_id(str(s)) for s in scope.get("Stations", []) if isinstance(s, (str, int))
            ]
            affected_routes = [str(r) for r in scope.get("Lines", []) if isinstance(r, (str, int))]
            alerts.append(
                ServiceAlert(
                    alert_id=f"{self.system_id}_{raw['AlertID']}",
                    transport_mode=self.transport_mode,
                    title=raw.get("Title", ""),
                    description=raw.get("Description", ""),
                    severity=raw.get("Title", "未知"),
                    affected_stations=affected_stations,
                    affected_routes=affected_routes,
                    start_time=datetime.fromisoformat(raw["PublishTime"]),
                    end_time=None,
                )
            )
        return alerts
