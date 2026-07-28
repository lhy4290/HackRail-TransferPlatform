import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.models.alert import ServiceAlert
from app.models.network import NetworkEdge
from app.models.station import Station

DEMO_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "demo_data" / "snapshot.json"


@dataclass
class DemoSnapshot:
    """事先擷取之真實 TDX 資料快照（見 scripts/capture_demo_snapshot.py）。

    供無 TDX 憑證環境（如評審 Demo）建立 AppState 用，載入過程不呼叫任何即時 API。
    """

    stations: List[Station]
    edges: List[NetworkEdge]
    alerts: List[ServiceAlert]
    curated_station_ids: List[str]


def load_demo_snapshot(path: Path = DEMO_SNAPSHOT_PATH) -> DemoSnapshot:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return DemoSnapshot(
        stations=[Station.model_validate(s) for s in raw["stations"]],
        edges=[NetworkEdge.model_validate(e) for e in raw["edges"]],
        alerts=[ServiceAlert.model_validate(a) for a in raw["alerts"]],
        curated_station_ids=list(raw["curated_station_ids"]),
    )


class StaticAlertSource:
    """AlertManager 用之靜態通報來源，回傳快照擷取當下之營運通報，不呼叫任何 API。"""

    transport_mode = "demo"

    def __init__(self, alerts: List[ServiceAlert]):
        self._alerts = alerts

    async def get_alerts(self) -> List[ServiceAlert]:
        return self._alerts
