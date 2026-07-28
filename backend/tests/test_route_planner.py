import asyncio
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.enums import TransportMode
from app.models.errors import ValidationError
from app.models.network import NetworkEdge
from app.models.station import Station
from app.models.transfer import TransferStation
from app.services.route_planner import NoRouteFoundError, RoutePlanner
from app.services.transport_graph import TransportGraph

DEPARTURE = datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)  # 週一 08:00


def _station(station_id: str, mode: TransportMode) -> Station:
    return Station(
        station_id=station_id,
        original_id=station_id,
        name_zh=station_id,
        transport_mode=mode,
        latitude=25.0,
        longitude=121.5,
    )


def _build_two_path_graph(direct_time: int, leg1_time: int, transfer_time: int, leg2_time: int) -> TransportGraph:
    """建立測試路網：
    - 單運具直達路徑：origin -TRA-> destination
    - 跨運具轉乘路徑：origin -TRA-> mid -轉乘-> mid2 -THSR-> destination
    """
    graph = TransportGraph()
    origin = _station("ORIGIN", TransportMode.TRA)
    mid = _station("MID", TransportMode.TRA)
    mid2 = _station("MID2", TransportMode.THSR)
    destination = _station("DEST", TransportMode.THSR)
    for s in (origin, mid, mid2, destination):
        graph.add_station(s)

    graph.add_route_edge(
        NetworkEdge(
            edge_id="direct",
            from_station_id="ORIGIN",
            to_station_id="DEST",
            transport_mode=TransportMode.TRA,
            base_travel_time_min=direct_time,
        ),
        trip_id="TRIP_DIRECT",
    )
    graph.add_route_edge(
        NetworkEdge(
            edge_id="leg1",
            from_station_id="ORIGIN",
            to_station_id="MID",
            transport_mode=TransportMode.TRA,
            base_travel_time_min=leg1_time,
        ),
        trip_id="TRIP_LEG1",
    )
    graph.add_route_edge(
        NetworkEdge(
            edge_id="leg2",
            from_station_id="MID2",
            to_station_id="DEST",
            transport_mode=TransportMode.THSR,
            base_travel_time_min=leg2_time,
        ),
        trip_id="TRIP_LEG2",
    )
    graph.add_transfer_edge(
        TransferStation(
            transfer_id="MID_TO_MID2",
            from_station=mid,
            to_station=mid2,
            from_platform="A",
            to_platform="B",
            walking_distance_m=200,
            walking_time_min=max(transfer_time - 10, 1),
            buffer_time_min=10,
        ),
        bidirectional=False,
    )
    return graph


# Feature: cross-transport-transfer-platform, Property 1: 路線結構與多運具約束
# Feature: cross-transport-transfer-platform, Property 2: 路線排序不變式
# Feature: cross-transport-transfer-platform, Property 3: 路段資訊完整性
@given(
    direct_time=st.integers(min_value=5, max_value=120),
    leg1_time=st.integers(min_value=5, max_value=60),
    transfer_time=st.integers(min_value=11, max_value=30),
    leg2_time=st.integers(min_value=5, max_value=60),
)
@settings(max_examples=100, deadline=None)
def test_route_planner_structure_sorting_and_multimodal(direct_time, leg1_time, transfer_time, leg2_time):
    async def run():
        graph = _build_two_path_graph(direct_time, leg1_time, transfer_time, leg2_time)
        planner = RoutePlanner(graph)
        routes = await planner.plan_routes("ORIGIN", "DEST", DEPARTURE, max_results=5)

        # Property 1: 回傳路線數量介於 1 至 5 條之間
        assert 1 <= len(routes) <= 5
        # Property 1: 每條路線 segments 完整涵蓋起點至終點
        for route in routes:
            assert route.segments[0].from_station.station_id == "ORIGIN"
            assert route.segments[-1].to_station.station_id == "DEST"
        # Property 1: 至少一條路線包含兩種以上 Transport_Mode
        assert any(len(set(r.transport_modes_used)) >= 2 for r in routes)
        # Property 2: 路線結果依總行程時間升序排列
        for i in range(len(routes) - 1):
            assert routes[i].total_time_minutes <= routes[i + 1].total_time_minutes
        # Property 3: 每個 RouteSegment 之 transport_mode 有效且 trip_id 非空
        for route in routes:
            for seg in route.segments:
                assert isinstance(seg.transport_mode, TransportMode)
                assert len(seg.trip_id) > 0

    asyncio.run(run())


# Feature: cross-transport-transfer-platform, Property 4: 無效站名驗證
@given(bad_name=st.text(alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=10))
@settings(max_examples=100, deadline=None)
def test_invalid_station_name_raises_validation_error(bad_name):
    graph = _build_two_path_graph(30, 10, 15, 10)
    valid_ids = set(graph.stations.keys())
    if bad_name in valid_ids:
        bad_name = bad_name + "_UNKNOWN_SUFFIX"

    async def run():
        planner = RoutePlanner(graph)
        with pytest.raises(ValidationError) as exc_info:
            await planner.plan_routes(bad_name, "DEST", DEPARTURE)
        assert bad_name in exc_info.value.platform_error.message

    asyncio.run(run())


@pytest.mark.asyncio
async def test_same_origin_destination_raises_validation_error():
    graph = _build_two_path_graph(30, 10, 15, 10)
    planner = RoutePlanner(graph)
    with pytest.raises(ValidationError):
        await planner.plan_routes("ORIGIN", "ORIGIN", DEPARTURE)


@pytest.mark.asyncio
async def test_no_route_found_raises_error():
    graph = TransportGraph()
    graph.add_station(_station("A", TransportMode.TRA))
    graph.add_station(_station("B", TransportMode.TRA))
    planner = RoutePlanner(graph)
    with pytest.raises(NoRouteFoundError):
        await planner.plan_routes("A", "B", DEPARTURE)
