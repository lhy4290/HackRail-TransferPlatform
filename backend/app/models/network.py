from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import TransportMode


class NetworkEdge(BaseModel):
    """路網邊：代表同運具內兩站之間可直接搭乘的路段"""

    edge_id: str
    from_station_id: str
    to_station_id: str
    transport_mode: TransportMode
    route_name: Optional[str] = None
    base_travel_time_min: int = Field(..., ge=0)
