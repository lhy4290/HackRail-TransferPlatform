import asyncio

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import AppState
from app.cache.cache_manager import CacheManager
from app.db.database import Database
from app.main import app
from app.models.enums import TransportMode
from app.models.network import NetworkEdge
from app.models.station import Station
from app.models.transfer import TransferStation
from app.services.alert_manager import AlertManager
from app.services.liveboard_service import LiveBoardService
from app.services.risk_predictor import RiskPredictor
from app.services.route_planner import RoutePlanner
from app.services.transport_graph import TransportGraph


@pytest.fixture(autouse=True)
def _no_real_tdx_credentials(monkeypatch):
    """測試不應讀到開發者本機的真實 .env TDX 憑證，避免意外打到真實 TDX API。"""
    monkeypatch.delenv("TDX_CLIENT_ID", raising=False)
    monkeypatch.delenv("TDX_CLIENT_SECRET", raising=False)


def make_station(station_id, name_zh, mode=TransportMode.TRA, name_en=None, lat=25.0, lon=121.5):
    return Station(
        station_id=station_id,
        original_id=station_id,
        name_zh=name_zh,
        name_en=name_en,
        transport_mode=mode,
        latitude=lat,
        longitude=lon,
    )


@pytest.fixture
def seeded_state(tmp_path):
    db = Database(tmp_path / "test.db")
    asyncio.run(db.init_schema())
    cache = CacheManager()
    graph = TransportGraph()

    origin = make_station("ORIGIN", "台北車站", TransportMode.TRA, name_en="Taipei Station")
    mid = make_station("MID", "板橋", TransportMode.TRA, name_en="Banqiao")
    mid2 = make_station("MID2", "左營", TransportMode.THSR, name_en="Zuoying")
    dest = make_station("DEST", "高雄車站", TransportMode.THSR, name_en="Kaohsiung Station")

    for s in (origin, mid, mid2, dest):
        graph.add_station(s)

    graph.add_route_edge(
        NetworkEdge(
            edge_id="e1",
            from_station_id="ORIGIN",
            to_station_id="MID",
            transport_mode=TransportMode.TRA,
            base_travel_time_min=20,
        ),
        trip_id="TRIP1",
    )
    graph.add_route_edge(
        NetworkEdge(
            edge_id="e2",
            from_station_id="MID2",
            to_station_id="DEST",
            transport_mode=TransportMode.THSR,
            base_travel_time_min=90,
        ),
        trip_id="TRIP2",
    )

    transfer = TransferStation(
        transfer_id="T1",
        from_station=mid,
        to_station=mid2,
        from_platform="A",
        to_platform="B",
        walking_distance_m=300,
        walking_time_min=5,
        buffer_time_min=10,
    )
    graph.add_transfer_edge(transfer, bidirectional=False)

    planner = RoutePlanner(graph)
    risk_predictor = RiskPredictor(db)
    alert_manager = AlertManager(adapters=[], cache=cache)
    liveboard_service = LiveBoardService(adapters_by_mode={}, cache=cache)

    return AppState(
        db=db,
        cache=cache,
        graph=graph,
        planner=planner,
        risk_predictor=risk_predictor,
        alert_manager=alert_manager,
        liveboard_service=liveboard_service,
        stations_by_id={s.station_id: s for s in (origin, mid, mid2, dest)},
        transfers_by_id={"T1": transfer},
    )


@pytest.fixture
def client(seeded_state):
    with TestClient(app) as c:
        app.state.platform = seeded_state
        yield c
