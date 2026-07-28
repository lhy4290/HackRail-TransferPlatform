import itertools
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Awaitable, Callable, List, Optional, Set, Tuple

from app.models.enums import ConnectionRiskLevel, ErrorType, TransportMode
from app.models.errors import PlatformError, ValidationError
from app.models.risk import RiskPredictionDTO
from app.models.route import RoutePlanDTO, RouteSegment
from app.services.transport_graph import GraphEdge, TransportGraph

RiskFn = Callable[[RoutePlanDTO], Awaitable[List[RiskPredictionDTO]]]


@dataclass
class _PathStep:
    edge: GraphEdge
    departure_time: datetime
    arrival_time: datetime


class NoRouteFoundError(Exception):
    """起點與終點之間無任何可行跨運具路線（需求 1.6）"""

    def __init__(self, origin: str, destination: str):
        self.origin = origin
        self.destination = destination
        super().__init__(f"無可用路線：{origin} -> {destination}")


def _edge_key(step: _PathStep) -> Tuple[str, str, Optional[str]]:
    return (step.edge.source, step.edge.target, step.edge.trip_id)


def _path_key(path: List[_PathStep]) -> Tuple:
    return tuple(_edge_key(s) for s in path)


class RoutePlanner:
    """路線規劃核心引擎：Time-Dependent Dijkstra + Yen's K-最短路徑演算法"""

    def __init__(self, graph: TransportGraph):
        self.graph = graph

    def validate_stations(self, origin: str, destination: str) -> None:
        unknown = [s for s in (origin, destination) if not self.graph.has_station(s)]
        if unknown:
            raise ValidationError(
                PlatformError(
                    error_type=ErrorType.VALIDATION_ERROR,
                    message=f"無法識別站名：{', '.join(unknown)}",
                    details={"unknown_stations": unknown},
                )
            )
        if origin == destination:
            raise ValidationError(
                PlatformError(
                    error_type=ErrorType.VALIDATION_ERROR,
                    message="起點與終點不得相同",
                )
            )

    async def plan_routes(
        self,
        origin: str,
        destination: str,
        departure_time: datetime,
        max_results: int = 5,
        max_transfers: int = 4,
    ) -> List[RoutePlanDTO]:
        """
        規劃跨運具路線。
        1. 以 Time-Dependent Dijkstra 為基礎，透過 Yen's 演算法找出前 K 條最短路線
        2. 若最短路線集合中無任何一條包含兩種以上運具，額外搜尋最佳多運具路線並納入
        3. 依總行程時間排序後回傳
        """
        self.validate_stations(origin, destination)

        paths = self._k_shortest_paths(origin, destination, departure_time, max_results)
        if not paths:
            raise NoRouteFoundError(origin, destination)

        if not any(len(self._transport_modes_used(p)) >= 2 for p in paths):
            multi_modal_path = self._best_multi_modal_path(origin, destination, departure_time)
            if multi_modal_path is not None:
                if len(paths) >= max_results:
                    paths[-1] = multi_modal_path
                else:
                    paths.append(multi_modal_path)

        route_plans = [self._build_route_plan(p, departure_time, idx) for idx, p in enumerate(paths)]
        route_plans.sort(key=lambda r: r.total_time_minutes)
        return route_plans[:max_results]

    async def ensure_non_severe_alternative(
        self,
        routes: List[RoutePlanDTO],
        origin: str,
        destination: str,
        departure_time: datetime,
        risk_fn: RiskFn,
        max_extra_search: int = 15,
    ) -> List[RoutePlanDTO]:
        """為路線集合標註風險，並確保「嚴重延誤」路線存在時至少有一條替代路線
        之所有轉乘節點風險皆非「嚴重延誤」（需求 6.3 / Property 12）。

        risk_fn 由呼叫端注入（通常為 RiskPredictor.predict_route_risks），
        使 RoutePlanner 無須直接依賴 RiskPredictor 實作。
        """

        def is_severe(route: RoutePlanDTO) -> bool:
            return any(
                p.risk_level == ConnectionRiskLevel.SEVERE_DELAY.value for p in (route.risk_predictions or [])
            )

        annotated: List[RoutePlanDTO] = []
        for route in routes:
            risks = await risk_fn(route)
            annotated.append(route.model_copy(update={"risk_predictions": risks}))

        has_severe = any(is_severe(r) for r in annotated)
        has_safe_alternative = any(not is_severe(r) for r in annotated)

        if has_severe and not has_safe_alternative:
            existing_signatures = {tuple(seg.trip_id for seg in r.segments) for r in annotated}
            candidates = self._k_shortest_paths(origin, destination, departure_time, k=max_extra_search)
            for offset, path in enumerate(candidates):
                candidate_route = self._build_route_plan(path, departure_time, index=len(annotated) + offset)
                signature = tuple(seg.trip_id for seg in candidate_route.segments)
                if signature in existing_signatures:
                    continue
                risks = await risk_fn(candidate_route)
                candidate_route = candidate_route.model_copy(update={"risk_predictions": risks})
                if not is_severe(candidate_route):
                    annotated.append(candidate_route)
                    break

        annotated.sort(key=lambda r: r.total_time_minutes)
        return annotated

    # ---- Time-Dependent Dijkstra ----

    def _shortest_path(
        self,
        origin: str,
        destination: str,
        departure_time: datetime,
        excluded_edges: Set[Tuple[str, str, Optional[str]]],
        excluded_nodes: Set[str],
    ) -> Optional[List[_PathStep]]:
        import heapq

        counter = itertools.count()
        pq: list = [(departure_time, next(counter), origin, [])]
        best_arrival: dict = {origin: departure_time}

        while pq:
            arrival_time, _, station_id, path = heapq.heappop(pq)
            if arrival_time > best_arrival.get(station_id, arrival_time):
                continue
            if station_id == destination and path:
                return path
            for edge in self.graph.neighbors(station_id):
                if edge.target in excluded_nodes:
                    continue
                key = (edge.source, edge.target, edge.trip_id)
                if key in excluded_edges:
                    continue
                duration = edge.travel_time_fn(arrival_time)
                next_arrival = arrival_time + timedelta(minutes=duration)
                if next_arrival < best_arrival.get(edge.target, next_arrival + timedelta(minutes=1)):
                    best_arrival[edge.target] = next_arrival
                    step = _PathStep(edge=edge, departure_time=arrival_time, arrival_time=next_arrival)
                    heapq.heappush(pq, (next_arrival, next(counter), edge.target, path + [step]))
        return None

    # ---- Yen's K-shortest loopless paths ----

    def _k_shortest_paths(
        self, origin: str, destination: str, departure_time: datetime, k: int
    ) -> List[List[_PathStep]]:
        first = self._shortest_path(origin, destination, departure_time, set(), set())
        if first is None:
            return []

        a_paths: List[List[_PathStep]] = [first]
        b_candidates: List[List[_PathStep]] = []
        seen_keys = {_path_key(first)}

        while len(a_paths) < k:
            prev_path = a_paths[-1]
            for i in range(len(prev_path)):
                spur_node = origin if i == 0 else prev_path[i - 1].edge.target
                root_path = prev_path[:i]
                root_key = _path_key(root_path)
                spur_departure = departure_time if i == 0 else root_path[-1].arrival_time

                excluded_edges = {
                    _edge_key(path[i])
                    for path in a_paths + b_candidates
                    if len(path) > i and _path_key(path[:i]) == root_key
                }
                excluded_nodes = {step.edge.source for step in root_path}
                excluded_nodes.discard(spur_node)

                spur_path = self._shortest_path(spur_node, destination, spur_departure, excluded_edges, excluded_nodes)
                if spur_path is not None:
                    total_path = root_path + spur_path
                    key = _path_key(total_path)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        b_candidates.append(total_path)

            if not b_candidates:
                break
            b_candidates.sort(key=lambda p: p[-1].arrival_time)
            a_paths.append(b_candidates.pop(0))

        return a_paths[:k]

    def _best_multi_modal_path(
        self, origin: str, destination: str, departure_time: datetime
    ) -> Optional[List[_PathStep]]:
        candidates = self._k_shortest_paths(origin, destination, departure_time, k=20)
        multi_modal = [p for p in candidates if len(self._transport_modes_used(p)) >= 2]
        if not multi_modal:
            return None
        multi_modal.sort(key=lambda p: p[-1].arrival_time)
        return multi_modal[0]

    @staticmethod
    def _transport_modes_used(path: List[_PathStep]) -> Set[TransportMode]:
        return {step.edge.transport_mode for step in path if step.edge.edge_type == "route"}

    def _build_route_plan(self, path: List[_PathStep], departure_time: datetime, index: int) -> RoutePlanDTO:
        segments: List[RouteSegment] = []
        transfers = []
        modes_used: List[TransportMode] = []

        for step in path:
            edge = step.edge
            if edge.edge_type == "route":
                from_station = self.graph.stations[edge.source]
                to_station = self.graph.stations[edge.target]
                segments.append(
                    RouteSegment(
                        segment_id=f"seg_{len(segments)}",
                        transport_mode=edge.transport_mode,
                        trip_id=edge.trip_id or f"{edge.source}-{edge.target}",
                        from_station=from_station,
                        to_station=to_station,
                        departure_time=step.departure_time,
                        arrival_time=step.arrival_time,
                        duration_minutes=int((step.arrival_time - step.departure_time).total_seconds() // 60),
                    )
                )
                if edge.transport_mode not in modes_used:
                    modes_used.append(edge.transport_mode)
            elif edge.edge_type == "transfer" and edge.transfer_ref is not None:
                transfers.append(edge.transfer_ref)

        total_minutes = int((path[-1].arrival_time - departure_time).total_seconds() // 60) if path else 0
        return RoutePlanDTO(
            route_id=f"route_{index}",
            segments=segments,
            transfers=transfers,
            total_time_minutes=total_minutes,
            transfer_count=len(transfers),
            transport_modes_used=modes_used,
        )
