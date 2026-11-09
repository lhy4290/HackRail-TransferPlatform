from app.adapters.thsr_adapter import THSRAdapter
from app.adapters.tra_adapter import TRAAdapter
from app.models.enums import ErrorType, TransportMode
from app.models.errors import PlatformError, TDXAPIError
from app.services.data_ingestion import ingest_network
from app.services.transport_graph import TransportGraph
from tests.fakes import FakeTDXClient


def _thsr_adapter():
    fake = FakeTDXClient(
        {
            "/v2/Rail/THSR/Station": [
                {
                    "StationID": "1",
                    "StationName": {"Zh_tw": "台北", "En": "Taipei"},
                    "StationPosition": {"PositionLat": 25.0, "PositionLon": 121.5},
                }
            ],
        }
    )
    return THSRAdapter(fake)


def _failing_tra_adapter():
    class _RaisingTDXClient(FakeTDXClient):
        async def request(self, endpoint, params=None, **kwargs):
            raise RuntimeError("TDX 逾時")

    return TRAAdapter(_RaisingTDXClient())


async def test_ingest_network_populates_graph_and_stations():
    graph = TransportGraph()
    stations_by_id = {}

    await ingest_network([_thsr_adapter()], graph, stations_by_id)

    assert "THSR_1" in stations_by_id
    assert stations_by_id["THSR_1"].transport_mode == TransportMode.THSR
    assert graph.has_station("THSR_1")


async def test_ingest_network_skips_failing_adapter_without_raising():
    graph = TransportGraph()
    stations_by_id = {}

    await ingest_network([_failing_tra_adapter(), _thsr_adapter()], graph, stations_by_id)

    assert "THSR_1" in stations_by_id
    assert not any(sid.startswith("TRA_") for sid in stations_by_id)


def _rate_limited_error() -> TDXAPIError:
    return TDXAPIError(
        PlatformError(error_type=ErrorType.API_ERROR, message="429", details={"detail": 429})
    )


async def test_ingest_network_retries_after_rate_limit_then_succeeds():
    class _FlakyAdapter:
        transport_mode = TransportMode.THSR

        def __init__(self):
            self.station_calls = 0

        async def get_stations(self):
            self.station_calls += 1
            if self.station_calls < 3:
                raise _rate_limited_error()
            return await _thsr_adapter().get_stations()

        async def get_routes(self):
            return []

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    graph = TransportGraph()
    stations_by_id = {}

    await ingest_network([_FlakyAdapter()], graph, stations_by_id, sleep_fn=fake_sleep)

    assert "THSR_1" in stations_by_id
    assert sleeps == [5.0, 10.0]


async def test_ingest_network_reports_incomplete_modes():
    graph = TransportGraph()
    stations_by_id = {}

    incomplete = await ingest_network([_failing_tra_adapter(), _thsr_adapter()], graph, stations_by_id)

    assert incomplete == {TransportMode.TRA}


def test_backfill_from_snapshot_fills_only_missing_modes_without_duplicates():
    """滾動部署時 TDX 限流導致某運具路段缺漏，應以快照補齊，且不重複加入已載入的路段。"""
    from app.models.network import NetworkEdge
    from app.models.station import Station
    from app.services.data_ingestion import backfill_from_snapshot

    def station(sid, mode):
        return Station(station_id=sid, original_id=sid, name_zh=sid, transport_mode=mode, latitude=25.0, longitude=121.5)

    def edge(src, dst, mode):
        return NetworkEdge(edge_id=f"{src}_{dst}", from_station_id=src, to_station_id=dst, transport_mode=mode, base_travel_time_min=10)

    graph = TransportGraph()
    stations_by_id = {}
    # 即時擷取：高鐵只拿到 A 站與 A→B 路段；台鐵完整
    for s in (station("THSR_A", TransportMode.THSR), station("TRA_X", TransportMode.TRA)):
        graph.add_station(s)
        stations_by_id[s.station_id] = s
    graph.add_route_edge(edge("THSR_A", "THSR_B", TransportMode.THSR))

    snapshot_stations = [
        station("THSR_A", TransportMode.THSR),
        station("THSR_B", TransportMode.THSR),
        station("TRA_Y", TransportMode.TRA),
    ]
    snapshot_edges = [
        edge("THSR_A", "THSR_B", TransportMode.THSR),  # 已存在，不可重複
        edge("THSR_B", "THSR_C", TransportMode.THSR),
        edge("TRA_X", "TRA_Y", TransportMode.TRA),  # 台鐵不在缺漏清單，不可補
    ]

    added = backfill_from_snapshot({TransportMode.THSR}, graph, stations_by_id, snapshot_stations, snapshot_edges)

    assert added == 1
    assert "THSR_B" in stations_by_id
    assert "TRA_Y" not in stations_by_id
    assert [e.target for e in graph.neighbors("THSR_A")] == ["THSR_B"]
    assert [e.target for e in graph.neighbors("THSR_B")] == ["THSR_C"]
    assert graph.neighbors("TRA_X") == []
