import asyncio
from datetime import datetime

from app.adapters.travel_bus_adapter import TravelBusAdapter
from app.models.enums import TransportMode
from tests.fakes import FakeTDXClient

STOP_OF_ROUTE_TAIWAN_TRIP = [
    {
        "RouteUID": "THB7329",
        "SubRouteUID": "THB732901",
        "TaiwanTripName": {"Zh_tw": "阿里山線-A線", "En": "Alishan Route A"},
        "Direction": 0,
        "Stops": [
            {"StopID": "272098", "StopName": {"Zh_tw": "高鐵嘉義站", "En": "THSR Chiayi"}, "StopPosition": {"PositionLat": 23.45, "PositionLon": 120.55}},
            {"StopID": "301935", "StopName": {"Zh_tw": "頂六國小", "En": "Dingliu Elementary"}, "StopPosition": {"PositionLat": 23.46, "PositionLon": 120.56}},
        ],
    },
    {
        "RouteUID": "THB6670",
        "SubRouteUID": "THB6670A1",
        "TaiwanTripName": {"Zh_tw": "日月潭線", "En": "Sun Moon Lake Route"},
        "Direction": 0,
        "Stops": [
            {"StopID": "272098", "StopName": {"Zh_tw": "高鐵嘉義站", "En": "THSR Chiayi"}, "StopPosition": {"PositionLat": 23.45, "PositionLon": 120.55}},
            {"StopID": "999001", "StopName": {"Zh_tw": "日月潭", "En": "Sun Moon Lake"}, "StopPosition": {"PositionLat": 23.86, "PositionLon": 120.91}},
        ],
    },
]


def test_get_stations_dedupes_stops_shared_across_subroutes():
    # 高鐵嘉義站在兩條不同子路線中都出現，應僅計入一次
    client = FakeTDXClient({"/v2/Tourism/Bus/StopOfRoute/TaiwanTrip": STOP_OF_ROUTE_TAIWAN_TRIP})
    adapter = TravelBusAdapter(client)

    stations = asyncio.run(adapter.get_stations())

    station_ids = {s.station_id for s in stations}
    assert station_ids == {"TBUS_272098", "TBUS_301935", "TBUS_999001"}
    assert all(s.transport_mode == TransportMode.BUS for s in stations)


def test_get_routes_uses_runtime_seconds_when_available():
    client = FakeTDXClient(
        {
            "/v2/Tourism/Bus/StopOfRoute/TaiwanTrip": STOP_OF_ROUTE_TAIWAN_TRIP,
            "/v2/Tourism/Bus/S2TravelTime/TaiwanTrip": [
                {
                    "SubRouteUID": "THB732901",
                    "TravelTimes": [
                        {"Sequence": 1, "FromStopID": "272098", "ToStopID": "301935", "Distance": 4, "RunTime": 1200},
                    ],
                }
            ],
        }
    )
    adapter = TravelBusAdapter(client)

    edges = asyncio.run(adapter.get_routes())

    assert len(edges) == 1
    assert edges[0].from_station_id == "TBUS_272098"
    assert edges[0].to_station_id == "TBUS_301935"
    assert edges[0].base_travel_time_min == 20
    assert edges[0].route_name == "阿里山線-A線"


def test_get_routes_falls_back_to_distance_estimate_when_runtime_zero():
    # 真實資料中約 13% 區間 RunTime 為 0（非固定班距路線常見資料缺口）
    client = FakeTDXClient(
        {
            "/v2/Tourism/Bus/StopOfRoute/TaiwanTrip": STOP_OF_ROUTE_TAIWAN_TRIP,
            "/v2/Tourism/Bus/S2TravelTime/TaiwanTrip": [
                {
                    "SubRouteUID": "THB6670A1",
                    "TravelTimes": [
                        {"Sequence": 1, "FromStopID": "272098", "ToStopID": "999001", "Distance": 60, "RunTime": 0},
                    ],
                }
            ],
        }
    )
    adapter = TravelBusAdapter(client)

    edges = asyncio.run(adapter.get_routes())

    assert len(edges) == 1
    assert edges[0].base_travel_time_min >= 3
    assert edges[0].base_travel_time_min == 120  # 60km / 30km/h * 60 = 120min


def test_get_stations_merges_different_stop_ids_sharing_the_same_name():
    # 真實資料中，同一實體地點（如「高鐵嘉義站」）在不同子路線常登記為不同 StopID，
    # 若逐 StopID 建站會把同一站點拆成多個互不相連的節點，導致轉乘站比對到錯誤節點。
    stop_of_route = [
        {
            "SubRouteUID": "A1",
            "TaiwanTripName": {"Zh_tw": "路線甲"},
            "Stops": [
                {"StopID": "272098", "StopName": {"Zh_tw": "高鐵嘉義站"}, "StopPosition": {"PositionLat": 23.45, "PositionLon": 120.55}},
                {"StopID": "301935", "StopName": {"Zh_tw": "頂六國小"}, "StopPosition": {"PositionLat": 23.46, "PositionLon": 120.56}},
            ],
        },
        {
            "SubRouteUID": "B1",
            "TaiwanTripName": {"Zh_tw": "路線乙"},
            "Stops": [
                # 不同 StopID，但站名與上方完全相同 -> 應合併為同一站點
                {"StopID": "17184", "StopName": {"Zh_tw": "高鐵嘉義站"}, "StopPosition": {"PositionLat": 23.45, "PositionLon": 120.55}},
                {"StopID": "999999", "StopName": {"Zh_tw": "某景點"}, "StopPosition": {"PositionLat": 23.5, "PositionLon": 120.6}},
            ],
        },
    ]
    client = FakeTDXClient(
        {
            "/v2/Tourism/Bus/StopOfRoute/TaiwanTrip": stop_of_route,
            "/v2/Tourism/Bus/S2TravelTime/TaiwanTrip": [
                {"SubRouteUID": "A1", "TravelTimes": [{"FromStopID": "272098", "ToStopID": "301935", "Distance": 4, "RunTime": 300}]},
                {"SubRouteUID": "B1", "TravelTimes": [{"FromStopID": "17184", "ToStopID": "999999", "Distance": 4, "RunTime": 300}]},
            ],
        }
    )
    adapter = TravelBusAdapter(client)

    stations = asyncio.run(adapter.get_stations())
    station_names = [s.name_zh for s in stations]
    assert station_names.count("高鐵嘉義站") == 1

    canonical_id = next(s.station_id for s in stations if s.name_zh == "高鐵嘉義站")
    edges = asyncio.run(adapter.get_routes())
    from_ids = {e.from_station_id for e in edges}
    # 兩條子路線的「高鐵嘉義站」（StopID 272098 與 17184）皆應解析為同一 canonical 站點 ID
    assert from_ids == {canonical_id}


def test_get_routes_dedupes_repeated_subroute_records():
    # 真實資料中同一 SubRouteUID 常重複出現多次（推測為不同服務日版本）
    duplicated_record = {
        "SubRouteUID": "THB732901",
        "TravelTimes": [
            {"Sequence": 1, "FromStopID": "272098", "ToStopID": "301935", "Distance": 4, "RunTime": 300},
        ],
    }
    client = FakeTDXClient(
        {
            "/v2/Tourism/Bus/StopOfRoute/TaiwanTrip": STOP_OF_ROUTE_TAIWAN_TRIP,
            "/v2/Tourism/Bus/S2TravelTime/TaiwanTrip": [duplicated_record, dict(duplicated_record)],
        }
    )
    adapter = TravelBusAdapter(client)

    edges = asyncio.run(adapter.get_routes())

    assert len(edges) == 1


def test_get_alerts_maps_news_records():
    client = FakeTDXClient(
        {
            "/v2/Tourism/Bus/News/TaiwanTrip": [
                {
                    "NewsID": "New0001914",
                    "NewsCategory": "3",
                    "Title": "阿里山線因道路搶修，部分路段改道",
                    "Description": "詳細內容",
                    "StartTime": "2026-07-24T00:00:00+08:00",
                    "EndTime": "2026-07-29T00:00:00+08:00",
                }
            ]
        }
    )
    adapter = TravelBusAdapter(client)

    alerts = asyncio.run(adapter.get_alerts())

    assert len(alerts) == 1
    assert alerts[0].alert_id == "TBUS_New0001914"
    assert alerts[0].transport_mode == TransportMode.BUS
    assert alerts[0].title == "阿里山線因道路搶修，部分路段改道"


def test_get_alerts_dedupes_repeated_news_ids():
    # 真實資料中同一 NewsID 常重複出現多筆（推測為公告牽涉多條路線各自登記一筆）
    duplicated_news = {
        "NewsID": "New0001914",
        "NewsCategory": "3",
        "Title": "阿里山線因道路搶修，部分路段改道",
        "Description": "詳細內容",
        "StartTime": "2026-07-24T00:00:00+08:00",
    }
    client = FakeTDXClient(
        {"/v2/Tourism/Bus/News/TaiwanTrip": [duplicated_news, dict(duplicated_news), dict(duplicated_news)]}
    )
    adapter = TravelBusAdapter(client)

    alerts = asyncio.run(adapter.get_alerts())

    assert len(alerts) == 1


def test_get_timetable_filters_by_service_day_and_stop():
    client = FakeTDXClient(
        {
            "/v2/Tourism/Bus/StopOfRoute/TaiwanTrip": STOP_OF_ROUTE_TAIWAN_TRIP,
            "/v2/Tourism/Bus/Schedule/TaiwanTrip": [
                {
                    "TaiwanTripName": {"Zh_tw": "阿里山線-A線"},
                    "Direction": 0,
                    "Timetables": [
                        {
                            "TripID": "1",
                            "ServiceDay": {
                                "Sunday": 0, "Monday": 1, "Tuesday": 1, "Wednesday": 1,
                                "Thursday": 1, "Friday": 1, "Saturday": 0,
                            },
                            "StopTimes": [
                                {"StopID": "272098", "ArrivalTime": "08:40", "DepartureTime": "08:40"},
                                {"StopID": "301935", "ArrivalTime": "-:-", "DepartureTime": "-:-"},
                            ],
                        }
                    ],
                }
            ]
        }
    )
    adapter = TravelBusAdapter(client)

    # 2026-07-27 是星期一
    entries = asyncio.run(adapter.get_timetable("TBUS_272098", datetime(2026, 7, 27)))

    assert len(entries) == 1
    assert entries[0].destination == "阿里山線-A線"
    assert entries[0].departure_time == datetime(2026, 7, 27, 8, 40)

    # 站牌僅有佔位時刻 "-:-" 者應被略過
    entries_no_time = asyncio.run(adapter.get_timetable("TBUS_301935", datetime(2026, 7, 27)))
    assert entries_no_time == []

    # 2026-07-26 是星期日，該班次 ServiceDay.Sunday 為 0，應無結果
    entries_sunday = asyncio.run(adapter.get_timetable("TBUS_272098", datetime(2026, 7, 26)))
    assert entries_sunday == []
