from datetime import datetime
from typing import List

from app.adapters.base_adapter import BaseTransportAdapter, FieldSpec
from app.adapters.tdx_client import TDXClient
from app.models.alert import ServiceAlert
from app.models.enums import TransportMode
from app.models.network import NetworkEdge
from app.models.station import Station
from app.models.timetable import LiveBoardEntry, TimetableEntry


TRA_ASSUMED_AVG_SPEED_KMH = 60  # 站間行駛時間之暫時性估算值，非實際車次資料


class TRAAdapter(BaseTransportAdapter):
    """臺鐵轉接器

    站點欄位格式與 TDX 其他軌道運具一致：StationID、StationName.Zh_tw/En、
    StationPosition.PositionLon/PositionLat（已對照真實 TDX v2 Rail API 驗證）。
    """

    transport_mode = TransportMode.TRA

    STATION_SPECS = [
        FieldSpec("station_id", "StationID"),
        FieldSpec("name_zh", "StationName.Zh_tw"),
        FieldSpec("name_en", "StationName.En", required=False, default=None),
        FieldSpec("latitude", "StationPosition.PositionLat", cast=float),
        FieldSpec("longitude", "StationPosition.PositionLon", cast=float),
    ]

    LIVEBOARD_SPECS = [
        FieldSpec("trip_id", "TRAIN_NO"),
        FieldSpec("station_id", "STATION_ID"),
        FieldSpec("estimated_arrival", "DELAY_TIME", required=False, default=None, cast=datetime.fromisoformat),
        FieldSpec("scheduled_arrival", "SCHEDULE_TIME", required=False, default=None, cast=datetime.fromisoformat),
        FieldSpec("destination", "END_STATION_NAME", required=False, default="未知"),
    ]

    def __init__(self, tdx_client: TDXClient):
        super().__init__(tdx_client)

    def _namespaced_id(self, raw_station_id: str) -> str:
        return f"TRA_{raw_station_id}"

    async def get_stations(self) -> List[Station]:
        raw_list = await self.tdx_client.request("/v2/Rail/TRA/Station")
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
        """取得同運具路網邊。

        真實 TDX 並無臺鐵「站對站行駛時間」端點，改用 StationOfLine（各線別依序
        排列之站點與累計里程 TraveledDistance）推導路網拓樸，並以假設之平均營運
        速度換算預估行駛時間。此為暫時性估算（非實際車次時刻），待 HackRail 競賽
        釋出臺鐵正式資料（如瓶頸路段容量等）後應予替換。
        """
        raw_list = await self.tdx_client.request("/v2/Rail/TRA/StationOfLine")
        edges = []
        for line in raw_list:
            line_id = line.get("LineID", "")
            stations = sorted(line.get("Stations", []), key=lambda s: s["Sequence"])
            for prev, curr in zip(stations, stations[1:]):
                distance_km = abs(curr.get("TraveledDistance", 0) - prev.get("TraveledDistance", 0))
                duration_min = max(1, round(distance_km / TRA_ASSUMED_AVG_SPEED_KMH * 60))
                prev_id = self._namespaced_id(str(prev["StationID"]))
                curr_id = self._namespaced_id(str(curr["StationID"]))
                # 真實列車雙向皆行駛，StationOfLine 僅提供單向序列，故雙向各建一條邊
                edges.append(
                    NetworkEdge(
                        edge_id=f"TRA_{prev['StationID']}_{curr['StationID']}_{line_id}",
                        from_station_id=prev_id,
                        to_station_id=curr_id,
                        transport_mode=self.transport_mode,
                        route_name=line_id,
                        base_travel_time_min=duration_min,
                    )
                )
                edges.append(
                    NetworkEdge(
                        edge_id=f"TRA_{curr['StationID']}_{prev['StationID']}_{line_id}",
                        from_station_id=curr_id,
                        to_station_id=prev_id,
                        transport_mode=self.transport_mode,
                        route_name=line_id,
                        base_travel_time_min=duration_min,
                    )
                )
        return edges

    async def get_timetable(self, station_id: str, date: datetime) -> List[TimetableEntry]:
        raw_station_id = station_id.split("_", 1)[-1]
        raw_list = await self.tdx_client.request(
            "/v2/Rail/TRA/DailyTimetable",
            params={"stationID": raw_station_id, "date": date.date().isoformat()},
        )
        entries = []
        for raw in raw_list:
            entries.append(
                TimetableEntry(
                    trip_id=raw["TRAIN_NO"],
                    station_id=station_id,
                    transport_mode=self.transport_mode,
                    arrival_time=datetime.fromisoformat(raw["ARRIVAL_TIME"]) if raw.get("ARRIVAL_TIME") else None,
                    departure_time=datetime.fromisoformat(raw["DEPARTURE_TIME"]) if raw.get("DEPARTURE_TIME") else None,
                    destination=raw.get("END_STATION_NAME", "未知"),
                    direction=int(raw.get("DIRECTION", 0)),
                )
            )
        return entries

    async def get_liveboard(self, station_id: str) -> List[LiveBoardEntry]:
        raw_station_id = station_id.split("_", 1)[-1]
        raw_list = await self.tdx_client.request(
            "/v2/Rail/TRA/LiveBoard", params={"stationID": raw_station_id}
        )
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
        raw_list = await self.tdx_client.request("/v2/Rail/TRA/AlertInfo")
        alerts = []
        for raw in raw_list:
            alerts.append(
                ServiceAlert(
                    alert_id=f"TRA_{raw['ALERT_ID']}",
                    transport_mode=self.transport_mode,
                    title=raw.get("TITLE", ""),
                    description=raw.get("DESCRIPTION", ""),
                    severity=raw.get("SEVERITY", "延誤"),
                    affected_stations=[self._namespaced_id(sid) for sid in raw.get("AFFECTED_STATION_IDS", [])],
                    affected_routes=raw.get("AFFECTED_ROUTES", []),
                    start_time=datetime.fromisoformat(raw["START_TIME"]),
                    end_time=datetime.fromisoformat(raw["END_TIME"]) if raw.get("END_TIME") else None,
                    status=raw.get("STATUS", "進行中"),
                )
            )
        return alerts
