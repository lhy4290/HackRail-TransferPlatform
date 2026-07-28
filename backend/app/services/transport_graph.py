from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

from app.models.enums import TransportMode
from app.models.network import NetworkEdge
from app.models.station import Station
from app.models.transfer import TransferStation


@dataclass(frozen=True)
class GraphNode:
    """圖節點：代表一個站點"""

    station_id: str
    transport_mode: TransportMode


@dataclass
class GraphEdge:
    """圖邊：代表一段行程或轉乘"""

    source: str
    target: str
    edge_type: str  # "route" 或 "transfer"
    transport_mode: TransportMode
    travel_time_fn: Callable[[datetime], int]
    trip_id: Optional[str] = None
    uses_default_transfer_time: bool = False
    transfer_ref: Optional[TransferStation] = None


class TransportGraph:
    """跨運具交通路網圖：站點為節點，同運具路段與跨運具轉乘為邊"""

    def __init__(self):
        self.stations: Dict[str, Station] = {}
        self.adjacency: Dict[str, List[GraphEdge]] = {}

    def add_station(self, station: Station) -> None:
        self.stations[station.station_id] = station
        self.adjacency.setdefault(station.station_id, [])

    def has_station(self, station_id: str) -> bool:
        return station_id in self.stations

    def neighbors(self, station_id: str) -> List[GraphEdge]:
        return self.adjacency.get(station_id, [])

    def add_route_edge(self, edge: NetworkEdge, trip_id: Optional[str] = None) -> None:
        """加入同運具路段邊（時變權重函式，原型階段回傳固定基礎行駛時間）"""

        def travel_time_fn(_departure_time: datetime, _minutes: int = edge.base_travel_time_min) -> int:
            return _minutes

        graph_edge = GraphEdge(
            source=edge.from_station_id,
            target=edge.to_station_id,
            edge_type="route",
            transport_mode=edge.transport_mode,
            travel_time_fn=travel_time_fn,
            trip_id=trip_id or edge.edge_id,
        )
        self.adjacency.setdefault(edge.from_station_id, []).append(graph_edge)

    def add_transfer_edge(self, transfer: TransferStation, bidirectional: bool = True) -> None:
        """加入跨運具步行轉乘邊，權重 = 步行時間 + Buffer_Time（或缺失時之預設值）"""
        total_time, uses_default = transfer.total_transfer_time_min()

        def travel_time_fn(_departure_time: datetime, _minutes: int = total_time) -> int:
            return _minutes

        forward = GraphEdge(
            source=transfer.from_station.station_id,
            target=transfer.to_station.station_id,
            edge_type="transfer",
            transport_mode=transfer.to_station.transport_mode,
            travel_time_fn=travel_time_fn,
            trip_id=transfer.transfer_id,
            uses_default_transfer_time=uses_default,
            transfer_ref=transfer,
        )
        self.adjacency.setdefault(transfer.from_station.station_id, []).append(forward)

        if bidirectional:
            backward = GraphEdge(
                source=transfer.to_station.station_id,
                target=transfer.from_station.station_id,
                edge_type="transfer",
                transport_mode=transfer.from_station.transport_mode,
                travel_time_fn=travel_time_fn,
                trip_id=transfer.transfer_id,
                uses_default_transfer_time=uses_default,
                transfer_ref=transfer,
            )
            self.adjacency.setdefault(transfer.to_station.station_id, []).append(backward)
