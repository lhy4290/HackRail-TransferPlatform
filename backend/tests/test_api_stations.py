import asyncio

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.api.dependencies import AppState
from app.cache.cache_manager import CacheManager
from app.db.database import Database
from app.main import app
from app.models.enums import TransportMode
from app.services.alert_manager import AlertManager
from app.services.liveboard_service import LiveBoardService
from app.services.risk_predictor import RiskPredictor
from app.services.route_planner import RoutePlanner
from app.services.transport_graph import TransportGraph
from tests.conftest import make_station


def _build_state_with_many_stations(num_matching: int, num_other: int, tmp_path) -> AppState:
    db = Database(tmp_path / "stations_test.db")
    asyncio.run(db.init_schema())
    cache = CacheManager()
    graph = TransportGraph()
    stations = {}

    for i in range(num_matching):
        s = make_station(f"MATCH_{i}", f"測試站{i}", TransportMode.TRA)
        stations[s.station_id] = s

    for i in range(num_other):
        s = make_station(f"OTHER_{i}", f"其他站{i}", TransportMode.TRA)
        stations[s.station_id] = s

    return AppState(
        db=db,
        cache=cache,
        graph=graph,
        planner=RoutePlanner(graph),
        risk_predictor=RiskPredictor(db),
        alert_manager=AlertManager(adapters=[], cache=cache),
        liveboard_service=LiveBoardService(adapters_by_mode={}, cache=cache),
        stations_by_id=stations,
    )


# Feature: cross-transport-transfer-platform, Property 14: 自動完成結果約束
@given(num_matching=st.integers(min_value=0, max_value=15))
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_autocomplete_result_constraints(num_matching, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("stations")
    state = _build_state_with_many_stations(num_matching, num_other=5, tmp_path=tmp_path)
    app.state.platform = state

    with TestClient(app) as c:
        app.state.platform = state
        resp = c.get("/api/stations/suggest", params={"q": "測試站"})
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) <= 10
        for r in results:
            assert "測試站" in r["name_zh"]


def test_autocomplete_requires_at_least_two_characters(client):
    resp = client.get("/api/stations/suggest", params={"q": "台"})
    assert resp.status_code == 422


def test_autocomplete_no_match_returns_empty_list(client):
    resp = client.get("/api/stations/suggest", params={"q": "ZZZZZ"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_stations_returns_all_stations_regardless_of_count(client, seeded_state):
    resp = client.get("/api/stations")

    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == len(seeded_state.stations_by_id)
    assert {r["station_id"] for r in results} == set(seeded_state.stations_by_id.keys())


def test_list_stations_filters_to_visible_station_ids_when_set(client, seeded_state):
    """Demo 模式限定評審可查詢之起點/終點：visible_station_ids 非 None 時僅回傳其中之站點"""
    seeded_state.visible_station_ids = frozenset({"ORIGIN", "MID"})

    resp = client.get("/api/stations")

    assert resp.status_code == 200
    results = resp.json()
    assert {r["station_id"] for r in results} == {"ORIGIN", "MID"}
