from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models.enums import TransportMode
from app.models.station import Station


def test_search_routes_happy_path(client):
    resp = client.post(
        "/api/routes/search",
        json={"origin": "ORIGIN", "destination": "DEST", "departure_time": "2026-01-05T08:00:00"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert 1 <= len(body["routes"]) <= 5
    assert any(len(set(r["transport_modes_used"])) >= 2 for r in body["routes"])


def test_search_routes_no_route_found_returns_message(client):
    resp = client.post("/api/routes/search", json={"origin": "ORIGIN", "destination": "ORIGIN_UNREACHABLE"})
    # 未知站名視為驗證錯誤而非「無路線」
    assert resp.status_code == 422


# Feature: cross-transport-transfer-platform, Property 15: 查詢欄位驗證
@given(missing_field=st.sampled_from(["origin", "destination"]))
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_missing_field_returns_validation_error(client, missing_field):
    payload = {"origin": "ORIGIN", "destination": "DEST"}
    payload[missing_field] = ""
    resp = client.post("/api/routes/search", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert "必填" in body["message"]


# Feature: cross-transport-transfer-platform, Property 16: 起終點相同驗證
def test_same_origin_destination_blocks_query(client):
    resp = client.post("/api/routes/search", json={"origin": "ORIGIN", "destination": "ORIGIN"})
    assert resp.status_code == 422
    body = resp.json()
    assert "相同" in body["message"]


def test_unknown_station_name_returns_validation_error(client):
    resp = client.post("/api/routes/search", json={"origin": "NOT_A_STATION", "destination": "DEST"})
    assert resp.status_code == 422
    body = resp.json()
    assert "NOT_A_STATION" in body["message"]


def test_no_route_between_tra_thsr_stations_reports_data_unavailable(client, seeded_state):
    # 臺鐵/高鐵目前僅有站點、無路網邊，故與其他站點必然查無路線；
    # 此情境應提示「資料尚未開放」而非讓使用者誤以為單純沒有可行路線
    isolated = Station(
        station_id="ISOLATED_TRA",
        original_id="ISOLATED_TRA",
        name_zh="孤立臺鐵站",
        transport_mode=TransportMode.TRA,
        latitude=25.0,
        longitude=121.5,
    )
    seeded_state.graph.add_station(isolated)
    seeded_state.stations_by_id["ISOLATED_TRA"] = isolated

    resp = client.post("/api/routes/search", json={"origin": "ORIGIN", "destination": "ISOLATED_TRA"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["routes"] == []
    assert "尚未開放" in body["message"]


def test_no_route_between_other_modes_reports_generic_message(client, seeded_state):
    # 非臺鐵/高鐵之查無路線情境（例如兩個互不相連的捷運系統）維持原本的通用訊息；
    # 兩端都須為非臺鐵/高鐵站點，才能排除「起訖點本身即屬資料缺口運具」的情況
    isolated_a = Station(
        station_id="ISOLATED_METRO_A",
        original_id="ISOLATED_METRO_A",
        name_zh="孤立捷運站A",
        transport_mode=TransportMode.METRO_KAOHSIUNG,
        latitude=22.6,
        longitude=120.3,
    )
    isolated_b = Station(
        station_id="ISOLATED_METRO_B",
        original_id="ISOLATED_METRO_B",
        name_zh="孤立捷運站B",
        transport_mode=TransportMode.METRO_TAICHUNG,
        latitude=24.1,
        longitude=120.6,
    )
    seeded_state.graph.add_station(isolated_a)
    seeded_state.graph.add_station(isolated_b)
    seeded_state.stations_by_id["ISOLATED_METRO_A"] = isolated_a
    seeded_state.stations_by_id["ISOLATED_METRO_B"] = isolated_b

    resp = client.post(
        "/api/routes/search", json={"origin": "ISOLATED_METRO_A", "destination": "ISOLATED_METRO_B"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["routes"] == []
    assert body["message"] == "無可用路線"
