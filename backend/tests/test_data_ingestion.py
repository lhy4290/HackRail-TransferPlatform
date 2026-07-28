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
