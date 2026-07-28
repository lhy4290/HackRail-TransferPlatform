import asyncio

from app.adapters.bus_adapter import BusAdapter
from app.adapters.ferry_adapter import FerryAdapter
from app.models.enums import TransportMode
from tests.fakes import FakeTDXClient


def test_ferry_get_stations_unwraps_port_envelope():
    # 真實 TDX /v3/Ship/Port 回傳格式為包裝物件，Ports 為內層陣列
    client = FakeTDXClient(
        {
            "/v3/Ship/Port": {
                "Ports": [
                    {
                        "PortID": "TW074",
                        "PortName": {"Zh_tw": "高雄鼓山輪渡站", "En": "Gushan Ferry Station"},
                        "PortPosition": {"PositionLat": 22.62, "PositionLon": 120.27},
                        "City": "高雄市",
                    }
                ],
                "UpdateTime": "2026-01-01T00:00:00+08:00",
            }
        }
    )
    adapter = FerryAdapter(client)

    stations = asyncio.run(adapter.get_stations())

    assert len(stations) == 1
    assert stations[0].station_id == "FERRY_TW074"
    assert stations[0].name_zh == "高雄鼓山輪渡站"
    assert stations[0].transport_mode == TransportMode.FERRY


def test_ferry_get_routes_uses_general_schedule_travel_time_when_available():
    client = FakeTDXClient(
        {
            "/v3/Ship/StopOfRoute/RouteType/Internal": [
                {
                    "RouteID": "HalohaR101",
                    "RouteName": {"Zh_tw": "大稻埕碼頭-淡水客船碼頭"},
                    "Direction": 0,
                    "Stops": [
                        {"StopSequence": 1, "PortID": "TW019"},
                        {"StopSequence": 2, "PortID": "TW054"},
                    ],
                }
            ],
            "/v3/Ship/GeneralSchedule/RouteType/Internal": [
                {
                    "RouteID": "HalohaR101",
                    "Direction": 0,
                    "TimeTables": [
                        {
                            "TripID": "HalohaR01",
                            "StopTimes": [
                                {"StopSequence": 1, "PortID": "TW019", "DepartureTime": "10:00", "TravelTime": 80},
                                {"StopSequence": 2, "PortID": "TW054", "ArrivalTime": "11:20", "TravelTime": 0},
                            ],
                        }
                    ],
                }
            ],
            "/v3/Ship/Route/RouteType/Internal": [
                {"RouteID": "HalohaR101", "RouteDistance": 9}
            ],
        }
    )
    adapter = FerryAdapter(client)

    edges = asyncio.run(adapter.get_routes())

    assert len(edges) == 1
    assert edges[0].from_station_id == "FERRY_TW019"
    assert edges[0].to_station_id == "FERRY_TW054"
    assert edges[0].base_travel_time_min == 80


def test_ferry_get_routes_falls_back_to_distance_estimate_when_no_fixed_schedule():
    # 班距營運（如鼓山－旗津）之航線 GeneralSchedule 僅有 Frequencies，無 TimeTables
    client = FakeTDXClient(
        {
            "/v3/Ship/StopOfRoute/RouteType/Internal": [
                {
                    "RouteID": "KHH001",
                    "RouteName": {"Zh_tw": "鼓山－旗津"},
                    "Direction": 0,
                    "Stops": [
                        {"StopSequence": 1, "PortID": "TW074"},
                        {"StopSequence": 2, "PortID": "TW073"},
                    ],
                }
            ],
            "/v3/Ship/GeneralSchedule/RouteType/Internal": [
                {"RouteID": "KHH001", "Direction": 0, "TimeTables": [], "Frequencies": [{"MinHeadwayMins": 6}]}
            ],
            "/v3/Ship/Route/RouteType/Internal": [{"RouteID": "KHH001", "RouteDistance": 1.5}],
        }
    )
    adapter = FerryAdapter(client)

    edges = asyncio.run(adapter.get_routes())

    assert len(edges) == 1
    assert edges[0].from_station_id == "FERRY_TW074"
    assert edges[0].to_station_id == "FERRY_TW073"
    assert edges[0].base_travel_time_min >= 1


HSR_SHUTTLE_STOP_OF_ROUTE = [
    {
        "RouteID": "0737",
        "RouteName": {"Zh_tw": "101"},
        "Direction": 0,
        "Stops": [
            {"StopID": "297592", "StopName": {"Zh_tw": "高鐵苗栗站", "En": "THSR Miaoli"}, "StopPosition": {"PositionLat": 24.6, "PositionLon": 120.8}},
            {"StopID": "297582", "StopName": {"Zh_tw": "竹南科學園區", "En": "Jhunan"}, "StopPosition": {"PositionLat": 24.7, "PositionLon": 120.9}},
        ],
    },
    {
        "RouteID": "0999",
        "RouteName": {"Zh_tw": "999"},
        "Direction": 0,
        "Stops": [
            {"StopID": "111111", "StopName": {"Zh_tw": "與高鐵站無關"}, "StopPosition": {"PositionLat": 24.1, "PositionLon": 120.1}},
        ],
    },
]


def test_bus_get_stations_only_includes_stops_from_matched_hsr_shuttle_routes():
    client = FakeTDXClient({"/v2/Bus/StopOfRoute/City/MiaoliCounty": HSR_SHUTTLE_STOP_OF_ROUTE})
    adapter = BusAdapter("MiaoliCounty", "高鐵苗栗站", client)

    stations = asyncio.run(adapter.get_stations())

    station_names = {s.name_zh for s in stations}
    assert station_names == {"高鐵苗栗站", "竹南科學園區"}
    assert all(s.transport_mode == TransportMode.BUS for s in stations)


def test_bus_get_routes_builds_edges_from_first_time_window():
    client = FakeTDXClient(
        {
            "/v2/Bus/StopOfRoute/City/MiaoliCounty": HSR_SHUTTLE_STOP_OF_ROUTE,
            "/v2/Bus/S2STravelTime/City/MiaoliCounty/0737": [
                {
                    "RouteID": "0737",
                    "SubRouteID": "0737C1",
                    "Direction": 0,
                    "TravelTimes": [
                        {
                            "StartHour": 7,
                            "EndHour": 8,
                            "S2STimes": [
                                {"FromStopID": "297592", "ToStopID": "297582", "RunTime": 300},
                            ],
                        }
                    ],
                }
            ],
        }
    )
    adapter = BusAdapter("MiaoliCounty", "高鐵苗栗站", client)

    edges = asyncio.run(adapter.get_routes())

    assert len(edges) == 1
    assert edges[0].from_station_id == "BUS_297592"
    assert edges[0].to_station_id == "BUS_297582"
    assert edges[0].base_travel_time_min == 5
    assert edges[0].transport_mode == TransportMode.BUS
