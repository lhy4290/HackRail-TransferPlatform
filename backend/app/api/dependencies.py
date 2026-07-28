from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional

from app.adapters.bus_adapter import BusAdapter
from app.adapters.ferry_adapter import FerryAdapter
from app.adapters.metro_adapter import MetroAdapter
from app.adapters.tdx_client import TDXClient
from app.adapters.thsr_adapter import THSRAdapter
from app.adapters.tra_adapter import TRAAdapter
from app.adapters.travel_bus_adapter import TravelBusAdapter
from app.cache.cache_manager import CacheManager
from app.db.database import Database
from app.models.station import Station
from app.models.transfer import TransferStation
from app.services.alert_manager import AlertManager
from app.services.data_ingestion import DEFAULT_REQUEST_INTERVAL_SECONDS, ingest_network
from app.services.demo_snapshot import DEMO_SNAPSHOT_PATH, StaticAlertSource, load_demo_snapshot
from app.services.liveboard_service import LiveBoardService
from app.services.risk_predictor import RiskPredictor
from app.services.route_planner import RoutePlanner
from app.services.transfer_seed import resolve_transfer_seeds
from app.services.transport_graph import TransportGraph


@dataclass
class AppState:
    """整個平台於單一 FastAPI process 內共用之服務實例集合"""

    db: Database
    cache: CacheManager
    graph: TransportGraph
    planner: RoutePlanner
    risk_predictor: RiskPredictor
    alert_manager: AlertManager
    liveboard_service: LiveBoardService
    stations_by_id: Dict[str, Station] = field(default_factory=dict)
    transfers_by_id: Dict[str, TransferStation] = field(default_factory=dict)
    # 非 None 時，/api/stations 僅回傳此清單內之站點（Demo 模式限定評審可查詢之起點/終點）
    visible_station_ids: Optional[FrozenSet[str]] = None


def build_empty_app_state(db_path: str = ":memory:") -> AppState:
    """建立不含任何站點資料之預設 AppState（無 TDX 憑證時之安全預設值）"""
    db = Database(db_path)
    cache = CacheManager()
    graph = TransportGraph()
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
    )


async def build_app_state_from_tdx(client_id: str, client_secret: str) -> AppState:
    """以真實 TDX 憑證建立 AppState：擷取各運具站點/路網資料並組出示意跨運具轉乘站。

    轉乘站資料為示意值（見 app.services.transfer_seed），TDX 本身不提供跨運具
    步行距離/時間資料。
    """
    db = Database()
    cache = CacheManager()
    graph = TransportGraph()
    planner = RoutePlanner(graph)
    risk_predictor = RiskPredictor(db)

    tdx_client = TDXClient(client_id, client_secret, log_fn=db.log_api_call)
    adapters = [
        MetroAdapter("TYMC", tdx_client),
        MetroAdapter("KRTC", tdx_client),
        MetroAdapter("TMRT", tdx_client),
        TRAAdapter(tdx_client),
        THSRAdapter(tdx_client),
        FerryAdapter(tdx_client),
        # 高鐵站接駁公車：目前僅示範苗栗站（真實已驗證行經「高鐵苗栗站」站牌之路線），
        # 要新增其他高鐵站接駁，於此清單追加對應之 (city, 站牌關鍵字) 即可。
        BusAdapter("MiaoliCounty", "高鐵苗栗站", tdx_client),
        # 台灣好行：與上方 BusAdapter 共用 TransportMode.BUS。兩者站點 ID 前綴不同
        # （BUS_ / TBUS_）不會互相覆蓋，但 liveboard_service 之 adapters_by_mode 為
        # 單一 mode -> 單一 adapter 對應，此處排序在後故 BUS 一律解析為本轉接器；
        # 對 Miaoli 站點無影響，因其 get_timetable() 本就固定回傳空清單。
        TravelBusAdapter(tdx_client),
    ]

    stations_by_id: Dict[str, Station] = {}
    await ingest_network(
        adapters, graph, stations_by_id, request_interval_seconds=DEFAULT_REQUEST_INTERVAL_SECONDS
    )

    transfers = resolve_transfer_seeds(stations_by_id)
    transfers_by_id: Dict[str, TransferStation] = {}
    for transfer in transfers:
        graph.add_transfer_edge(transfer)
        transfers_by_id[transfer.transfer_id] = transfer

    alert_manager = AlertManager(adapters=adapters, cache=cache)
    liveboard_service = LiveBoardService(
        adapters_by_mode={adapter.transport_mode: adapter for adapter in adapters}, cache=cache
    )

    return AppState(
        db=db,
        cache=cache,
        graph=graph,
        planner=planner,
        risk_predictor=risk_predictor,
        alert_manager=alert_manager,
        liveboard_service=liveboard_service,
        stations_by_id=stations_by_id,
        transfers_by_id=transfers_by_id,
    )


def build_demo_app_state(snapshot_path: Path = DEMO_SNAPSHOT_PATH) -> AppState:
    """以事先擷取之真實資料快照建立 AppState，不呼叫任何即時 TDX API。

    供無 TDX 憑證環境使用（例如提交作品供評審 Demo 時，不隨程式碼附上真實憑證）。
    快照涵蓋完整站點/路網資料以確保路網連通性，但 /api/stations 僅會回傳
    snapshot 內指定的精選站點清單（visible_station_ids），故評審只能在這批
    預先指定好的起點/終點之間查詢，不會意外觸發未預期之錯誤情境。
    """
    db = Database()
    cache = CacheManager()
    graph = TransportGraph()
    planner = RoutePlanner(graph)
    risk_predictor = RiskPredictor(db)

    snapshot = load_demo_snapshot(snapshot_path)

    stations_by_id: Dict[str, Station] = {}
    for station in snapshot.stations:
        graph.add_station(station)
        stations_by_id[station.station_id] = station

    for edge in snapshot.edges:
        graph.add_route_edge(edge)

    transfers = resolve_transfer_seeds(stations_by_id)
    transfers_by_id: Dict[str, TransferStation] = {}
    for transfer in transfers:
        graph.add_transfer_edge(transfer)
        transfers_by_id[transfer.transfer_id] = transfer

    alert_manager = AlertManager(adapters=[StaticAlertSource(snapshot.alerts)], cache=cache)
    liveboard_service = LiveBoardService(adapters_by_mode={}, cache=cache)

    return AppState(
        db=db,
        cache=cache,
        graph=graph,
        planner=planner,
        risk_predictor=risk_predictor,
        alert_manager=alert_manager,
        liveboard_service=liveboard_service,
        stations_by_id=stations_by_id,
        transfers_by_id=transfers_by_id,
        visible_station_ids=frozenset(snapshot.curated_station_ids) or None,
    )
