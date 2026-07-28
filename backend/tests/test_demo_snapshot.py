import asyncio
import json

from app.api.dependencies import build_demo_app_state
from app.services.demo_snapshot import StaticAlertSource, load_demo_snapshot
from tests.conftest import make_station


def _write_snapshot(tmp_path, stations, edges, alerts, curated_station_ids):
    path = tmp_path / "snapshot.json"
    path.write_text(
        json.dumps(
            {
                "stations": [s.model_dump(mode="json") for s in stations],
                "edges": [e.model_dump(mode="json") for e in edges],
                "alerts": [a.model_dump(mode="json") for a in alerts],
                "curated_station_ids": curated_station_ids,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_load_demo_snapshot_round_trips_stations_edges_alerts(tmp_path):
    from app.models.alert import ServiceAlert
    from app.models.enums import TransportMode
    from app.models.network import NetworkEdge

    origin = make_station("A", "起點站", TransportMode.TRA)
    dest = make_station("B", "終點站", TransportMode.TRA)
    edge = NetworkEdge(
        edge_id="e1", from_station_id="A", to_station_id="B", transport_mode=TransportMode.TRA, base_travel_time_min=10
    )
    alert = ServiceAlert(
        alert_id="al1",
        transport_mode=TransportMode.TRA,
        title="測試通報",
        severity="延誤",
        start_time="2026-01-01T00:00:00",
    )

    path = _write_snapshot(tmp_path, [origin, dest], [edge], [alert], ["A", "B"])

    snapshot = load_demo_snapshot(path)

    assert [s.station_id for s in snapshot.stations] == ["A", "B"]
    assert [e.edge_id for e in snapshot.edges] == ["e1"]
    assert [a.alert_id for a in snapshot.alerts] == ["al1"]
    assert snapshot.curated_station_ids == ["A", "B"]


def test_static_alert_source_returns_frozen_alert_list():
    from app.models.alert import ServiceAlert
    from app.models.enums import TransportMode

    alert = ServiceAlert(
        alert_id="al1",
        transport_mode=TransportMode.TRA,
        title="測試通報",
        severity="延誤",
        start_time="2026-01-01T00:00:00",
    )
    source = StaticAlertSource([alert])

    result = asyncio.run(source.get_alerts())

    assert result == [alert]


def test_build_demo_app_state_wires_graph_and_visible_station_ids(tmp_path):
    from app.models.enums import TransportMode
    from app.models.network import NetworkEdge

    origin = make_station("ORIGIN", "台北車站", TransportMode.TRA)
    dest = make_station("DEST", "左營", TransportMode.THSR)
    edge = NetworkEdge(
        edge_id="e1",
        from_station_id="ORIGIN",
        to_station_id="DEST",
        transport_mode=TransportMode.TRA,
        base_travel_time_min=15,
    )

    path = _write_snapshot(tmp_path, [origin, dest], [edge], [], ["ORIGIN", "DEST"])

    state = build_demo_app_state(path)

    assert set(state.stations_by_id.keys()) == {"ORIGIN", "DEST"}
    assert state.visible_station_ids == frozenset({"ORIGIN", "DEST"})
    assert state.graph.has_station("ORIGIN")
    assert any(e.target == "DEST" for e in state.graph.neighbors("ORIGIN"))


def test_build_demo_app_state_never_calls_live_tdx(tmp_path, monkeypatch):
    """Demo 模式核心保證：不應存在任何對外之即時 TDX 呼叫路徑"""
    import httpx

    def _fail(*args, **kwargs):
        raise AssertionError("Demo 模式不應呼叫任何外部網路請求")

    monkeypatch.setattr(httpx.AsyncClient, "request", _fail)
    monkeypatch.setattr(httpx.AsyncClient, "get", _fail)
    monkeypatch.setattr(httpx.AsyncClient, "post", _fail)

    path = _write_snapshot(tmp_path, [], [], [], [])
    state = build_demo_app_state(path)

    assert state.stations_by_id == {}
    assert state.visible_station_ids is None
