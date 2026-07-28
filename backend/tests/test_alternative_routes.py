import asyncio
from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.enums import ConnectionRiskLevel, TransportMode
from app.models.network import NetworkEdge
from app.models.risk import RiskPredictionDTO
from app.models.route import RoutePlanDTO
from app.models.station import Station
from app.services.route_planner import RoutePlanner
from app.services.transport_graph import TransportGraph

DEPARTURE = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)


def _station(station_id: str, mode: TransportMode = TransportMode.TRA) -> Station:
    return Station(
        station_id=station_id,
        original_id=station_id,
        name_zh=station_id,
        transport_mode=mode,
        latitude=25.0,
        longitude=121.5,
    )


def _build_graph(bad_times: list, good_time: int) -> TransportGraph:
    """建立一個含多條「嚴重延誤」路線與一條較慢但安全之替代路線的測試路網"""
    graph = TransportGraph()
    graph.add_station(_station("ORIGIN"))
    graph.add_station(_station("DEST"))
    for i, t in enumerate(bad_times):
        graph.add_route_edge(
            NetworkEdge(
                edge_id=f"bad{i}",
                from_station_id="ORIGIN",
                to_station_id="DEST",
                transport_mode=TransportMode.TRA,
                base_travel_time_min=t,
            ),
            trip_id=f"BAD{i}",
        )
    graph.add_route_edge(
        NetworkEdge(
            edge_id="good",
            from_station_id="ORIGIN",
            to_station_id="DEST",
            transport_mode=TransportMode.TRA,
            base_travel_time_min=good_time,
        ),
        trip_id="GOOD",
    )
    return graph


async def _risk_fn(route: RoutePlanDTO) -> list[RiskPredictionDTO]:
    severe = any(seg.trip_id.startswith("BAD") for seg in route.segments)
    level = ConnectionRiskLevel.SEVERE_DELAY.value if severe else ConnectionRiskLevel.ON_TIME.value
    return [
        RiskPredictionDTO(
            transfer_id="synthetic",
            risk_level=level,
            predicted_delay_minutes=20.0 if severe else 0.0,
            confidence=1.0,
        )
    ]


# Feature: cross-transport-transfer-platform, Property 12: 嚴重延誤替代路線
@given(
    bad_times=st.lists(st.integers(min_value=5, max_value=15), min_size=3, max_size=3, unique=True),
    good_time=st.integers(min_value=25, max_value=40),
)
@settings(max_examples=100, deadline=None)
def test_severe_delay_alternative_route_provided(bad_times, good_time):
    async def run():
        graph = _build_graph(bad_times, good_time)
        planner = RoutePlanner(graph)
        # 僅取前 3 條（全數為 BAD，最快的三條），刻意不含 GOOD
        routes = await planner.plan_routes("ORIGIN", "DEST", DEPARTURE, max_results=3)
        assert len(routes) == 3
        assert all(r.segments[0].trip_id.startswith("BAD") for r in routes)

        result = await planner.ensure_non_severe_alternative(
            routes, "ORIGIN", "DEST", DEPARTURE, _risk_fn, max_extra_search=10
        )

        has_severe = any(
            any(p.risk_level == ConnectionRiskLevel.SEVERE_DELAY.value for p in (r.risk_predictions or []))
            for r in result
        )
        has_safe_alternative = any(
            all(p.risk_level != ConnectionRiskLevel.SEVERE_DELAY.value for p in (r.risk_predictions or []))
            for r in result
        )
        assert has_severe
        assert has_safe_alternative

    asyncio.run(run())
