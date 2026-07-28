import asyncio

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.adapters.metro_adapter import MetroAdapter
from app.adapters.thsr_adapter import THSRAdapter
from app.adapters.tra_adapter import TRAAdapter
from app.models.errors import DataParseError
from app.models.station import Station
from tests.fakes import FakeTDXClient

TAIWAN_LAT = st.floats(min_value=21.0, max_value=26.0, allow_nan=False, allow_infinity=False)
TAIWAN_LON = st.floats(min_value=119.0, max_value=122.0, allow_nan=False, allow_infinity=False)
SAFE_TEXT = st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N")))


@st.composite
def st_rail_raw_station(draw):
    """三種軌道運具（捷運/臺鐵/高鐵）之真實 TDX 站點格式一致，皆為此巢狀雙語結構。"""
    return {
        "StationID": draw(SAFE_TEXT),
        "StationName": {"Zh_tw": draw(SAFE_TEXT), "En": draw(SAFE_TEXT)},
        "StationPosition": {"PositionLon": draw(TAIWAN_LON), "PositionLat": draw(TAIWAN_LAT)},
    }


def _build_metro_adapter(raw_station):
    client = FakeTDXClient({"/v2/Rail/Metro/Station/TYMC": [raw_station]})
    return MetroAdapter("TYMC", client)


def _build_tra_adapter(raw_station):
    client = FakeTDXClient({"/v2/Rail/TRA/Station": [raw_station]})
    return TRAAdapter(client)


def _build_thsr_adapter(raw_station):
    client = FakeTDXClient({"/v2/Rail/THSR/Station": [raw_station]})
    return THSRAdapter(client)


ADAPTER_BUILDERS = [
    (_build_metro_adapter, st_rail_raw_station()),
    (_build_tra_adapter, st_rail_raw_station()),
    (_build_thsr_adapter, st_rail_raw_station()),
]


# Feature: cross-transport-transfer-platform, Property 9: TDX 資料格式統一化
@given(choice=st.sampled_from(range(len(ADAPTER_BUILDERS))), data=st.data())
@settings(max_examples=100, deadline=None)
def test_adapters_produce_unified_station_schema(choice, data):
    builder, strategy = ADAPTER_BUILDERS[choice]
    raw_station = data.draw(strategy)
    adapter = builder(raw_station)

    async def run():
        stations = await adapter.get_stations()
        assert len(stations) == 1
        station = stations[0]
        assert isinstance(station, Station)
        # 所有轉接器產出的 Station 物件欄位名稱一致（同一 Pydantic schema）
        assert set(station.model_dump().keys()) == {
            "station_id",
            "original_id",
            "name_zh",
            "name_en",
            "transport_mode",
            "latitude",
            "longitude",
            "address",
        }
        assert station.transport_mode == adapter.transport_mode
        assert len(station.station_id) > 0
        assert len(station.name_zh) > 0
        assert 21.0 <= station.latitude <= 26.0
        assert 119.0 <= station.longitude <= 122.0

    asyncio.run(run())


# Feature: cross-transport-transfer-platform, Property 20: 無效 JSON 錯誤報告
@given(choice=st.sampled_from(range(len(ADAPTER_BUILDERS))), data=st.data())
@settings(max_examples=100, deadline=None)
def test_adapters_report_missing_required_field(choice, data):
    builder, strategy = ADAPTER_BUILDERS[choice]
    raw_station = dict(data.draw(strategy))
    del raw_station["StationName"]
    adapter = builder(raw_station)

    async def run():
        with pytest.raises(DataParseError) as exc_info:
            await adapter.get_stations()
        error = exc_info.value.platform_error
        assert "name_zh" in error.details["missing_fields"]
        assert exc_info.value.raw_payload != ""

    asyncio.run(run())


def test_parse_json_invalid_syntax_raises_parse_error():
    adapter = _build_tra_adapter({})
    with pytest.raises(DataParseError):
        adapter.parse_json("{not valid json")


# Feature: cross-transport-transfer-platform, Property 21: 非必要欄位預設值填補
@given(choice=st.sampled_from(range(len(ADAPTER_BUILDERS))), data=st.data())
@settings(max_examples=100, deadline=None)
def test_adapters_fill_default_for_missing_optional_field(choice, data):
    builder, strategy = ADAPTER_BUILDERS[choice]
    raw_station = dict(data.draw(strategy))
    # 三種運具之英文站名皆巢狀在 StationName.En，移除該子欄位而非整個物件
    raw_station["StationName"] = {"Zh_tw": raw_station["StationName"]["Zh_tw"]}
    adapter = builder(raw_station)

    async def run():
        stations = await adapter.get_stations()
        assert len(stations) == 1
        assert stations[0].name_en is None
        assert any("name_en" in w for w in adapter.parse_warnings)

    asyncio.run(run())


def test_metro_get_routes_flattens_s2s_travel_time_lines():
    client = FakeTDXClient(
        {
            "/v2/Rail/Metro/S2STravelTime/KRTC": [
                {
                    "LineID": "O",
                    "TravelTimes": [
                        {"FromStationID": "O1", "ToStationID": "O2", "RunTime": 120, "StopTime": 30},
                        {"FromStationID": "O2", "ToStationID": "O3", "RunTime": 90, "StopTime": 30},
                    ],
                }
            ]
        }
    )
    adapter = MetroAdapter("KRTC", client)

    edges = asyncio.run(adapter.get_routes())

    assert len(edges) == 2
    assert edges[0].from_station_id == "KRTC_O1"
    assert edges[0].to_station_id == "KRTC_O2"
    assert edges[0].base_travel_time_min == 2
    assert edges[1].base_travel_time_min == 2  # round(90/60) == 2


def test_tra_get_routes_derives_bidirectional_edges_from_station_of_line():
    client = FakeTDXClient(
        {
            "/v2/Rail/TRA/StationOfLine": [
                {
                    "LineID": "EL",
                    "Stations": [
                        {"Sequence": 0, "StationID": "0920", "StationName": "八堵", "TraveledDistance": 0},
                        {"Sequence": 1, "StationID": "7390", "StationName": "暖暖", "TraveledDistance": 1.6},
                        {"Sequence": 2, "StationID": "7380", "StationName": "四腳亭", "TraveledDistance": 3.9},
                    ],
                }
            ]
        }
    )
    adapter = TRAAdapter(client)

    edges = asyncio.run(adapter.get_routes())

    assert len(edges) == 4  # 2 段 x 雙向
    forward = next(e for e in edges if e.from_station_id == "TRA_0920" and e.to_station_id == "TRA_7390")
    backward = next(e for e in edges if e.from_station_id == "TRA_7390" and e.to_station_id == "TRA_0920")
    assert forward.base_travel_time_min == backward.base_travel_time_min
    assert forward.base_travel_time_min >= 1


def test_thsr_get_routes_derives_bidirectional_edges_from_station_of_line():
    client = FakeTDXClient(
        {
            "/v2/Rail/THSR/StationOfLine": [
                {
                    "LineID": "THSR",
                    "Stations": [
                        {"Sequence": 1, "StationID": "0990", "CumulativeDistance": 0},
                        {"Sequence": 2, "StationID": "1000", "CumulativeDistance": 9.2},
                    ],
                }
            ]
        }
    )
    adapter = THSRAdapter(client)

    edges = asyncio.run(adapter.get_routes())

    assert len(edges) == 2
    assert {e.from_station_id for e in edges} == {"THSR_0990", "THSR_1000"}
    assert all(e.base_travel_time_min >= 1 for e in edges)


def test_metro_get_alerts_unwraps_real_alert_envelope():
    # 真實 TDX /v2/Rail/Metro/Alert/{system} 回傳格式為包裝物件，Alerts 為內層陣列
    client = FakeTDXClient(
        {
            "/v2/Rail/Metro/Alert/KRTC": {
                "UpdateTime": "2026-07-26T20:34:34+08:00",
                "AuthorityCode": "KRTC",
                "Alerts": [
                    {
                        "AlertID": "1",
                        "Title": "測試通報",
                        "Description": "測試說明",
                        "Status": 1,
                        "Scope": {"Stations": ["R16"], "Lines": ["R"]},
                        "PublishTime": "2026-01-01T00:00:00+08:00",
                    }
                ],
            }
        }
    )
    adapter = MetroAdapter("KRTC", client)

    alerts = asyncio.run(adapter.get_alerts())

    assert len(alerts) == 1
    assert alerts[0].alert_id == "KRTC_1"
    assert alerts[0].affected_stations == ["KRTC_R16"]
    assert alerts[0].affected_routes == ["R"]


def test_metro_get_alerts_filters_out_normal_operation_placeholder():
    # TDX 無異常時仍會回傳一筆「正常營運」佔位通報，非真正的營運異常，應予過濾
    client = FakeTDXClient(
        {
            "/v2/Rail/Metro/Alert/KRTC": {
                "Alerts": [
                    {
                        "AlertID": "mrt_000",
                        "Title": "正常營運",
                        "Description": "正常營運",
                        "Status": 1,
                        "Scope": {"Stations": [], "Lines": []},
                        "PublishTime": "2026-07-26T20:34:34+08:00",
                    },
                    {
                        "AlertID": "2",
                        "Title": "列車延誤",
                        "Description": "號誌故障",
                        "Status": 2,
                        "Scope": {"Stations": ["R16"], "Lines": ["R"]},
                        "PublishTime": "2026-01-01T00:00:00+08:00",
                    },
                ],
            }
        }
    )
    adapter = MetroAdapter("KRTC", client)

    alerts = asyncio.run(adapter.get_alerts())

    assert len(alerts) == 1
    assert alerts[0].title == "列車延誤"
