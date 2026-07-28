"""擷取一份真實 TDX 資料快照，供無 TDX 憑證環境（如評審 Demo）使用。

用途：報名/提交作品時不隨程式碼附上真實 TDX 憑證（backend/.env），但仍希望評審
能在沒有任何憑證的情況下，直接執行 Demo 並查詢一組事先指定好的起點/終點站。

執行方式（需在 backend/.env 已設定真實 TDX_CLIENT_ID / TDX_CLIENT_SECRET 的機器上跑一次）：
    cd backend
    .\\.venv\\Scripts\\python.exe -m scripts.capture_demo_snapshot

輸出：backend/app/demo_data/snapshot.json，內含：
  - stations: 七種運具之真實站點資料（完整站點，確保路網連通性；渡輪/公車已依
    建構參數限定範圍，見下方 adapters 清單）
  - edges:    同運具站對站真實路網邊（供 TransportGraph 還原）
  - alerts:   擷取當下之真實營運通報（略過各運具已知失敗/佔位通報）
  - curated_station_ids: 供 Demo 前端下拉選單使用之精選站點清單
    （評審只能從這份清單挑選起點/終點，其餘完整站點資料僅用於維持路網連通性）

此腳本本身不會被提交作品執行；提交的程式碼只依賴其輸出的 snapshot.json，
執行時完全不需要任何 TDX 憑證（見 app.api.dependencies.build_demo_app_state）。
"""

import asyncio
import json
import logging
import sys
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.bus_adapter import BusAdapter
from app.adapters.ferry_adapter import FerryAdapter
from app.adapters.metro_adapter import MetroAdapter
from app.adapters.tdx_client import TDXClient
from app.adapters.thsr_adapter import THSRAdapter
from app.adapters.tra_adapter import TRAAdapter
from app.adapters.travel_bus_adapter import TravelBusAdapter
from app.config import load_tdx_credentials
from app.models.alert import ServiceAlert
from app.models.enums import TransportMode
from app.models.network import NetworkEdge
from app.models.station import Station
from app.services.data_ingestion import DEFAULT_REQUEST_INTERVAL_SECONDS, _fetch_with_rate_limit_retry
from app.services.transfer_seed import resolve_transfer_seeds
from app.services.transport_graph import TransportGraph

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "demo_data" / "snapshot.json"

# 精選 Demo 站點：(站名片段, 運具)。評審只能在這份清單內任意搭配起點/終點查詢。
# 涵蓋三個真實跨運具共構站（左營、台中/新烏日、桃園/高鐵桃園），可展示轉乘情境，
# 也各自保留數個同運具站點，可展示單一運具路線。
#   注意：TDX 各運具官方站名之正/簡體「臺/台」用字並不一致
#   （例如 THSR 用「台北」「台中」，TRA/Metro Taichung 用「臺北」「臺中」），
#   以下站名需與各運具實際回傳值相符，才能比對得到正確站點。
CURATED_STATION_NAMES: List[Tuple[str, TransportMode]] = [
    ("台北", TransportMode.THSR),
    ("板橋", TransportMode.THSR),
    ("桃園", TransportMode.THSR),
    ("新竹", TransportMode.THSR),
    ("台中", TransportMode.THSR),
    ("嘉義", TransportMode.THSR),
    ("台南", TransportMode.THSR),
    ("左營", TransportMode.THSR),
    ("臺北", TransportMode.TRA),
    ("新竹", TransportMode.TRA),
    ("臺中", TransportMode.TRA),
    ("新烏日", TransportMode.TRA),
    ("嘉義", TransportMode.TRA),
    ("臺南", TransportMode.TRA),
    ("新左營", TransportMode.TRA),
    ("高雄", TransportMode.TRA),
    ("台北車站", TransportMode.METRO_TAOYUAN),
    ("高鐵桃園", TransportMode.METRO_TAOYUAN),
    ("高鐵臺中", TransportMode.METRO_TAICHUNG),
    ("松竹", TransportMode.METRO_TAICHUNG),
    ("左營", TransportMode.METRO_KAOHSIUNG),
    ("高雄車站", TransportMode.METRO_KAOHSIUNG),
    # 「美麗島」為紅/橘線交會站，本資料集未含線間轉乘邊，與其餘精選站點不連通，故不列入
    ("鼓山", TransportMode.TRA),  # 與高雄鼓山輪渡站（渡輪）構成真實跨運具轉乘
    ("苗栗", TransportMode.THSR),  # 與高鐵苗栗站接駁公車構成真實跨運具轉乘
    # 台灣好行（TaiwanTrip）三條指標路線之終點站，與下方對應高鐵站構成真實跨運具轉乘：
    ("日月潭", TransportMode.BUS),  # 台灣好行日月潭線終點，接高鐵臺中站
    ("阿里山轉運站", TransportMode.BUS),  # 台灣好行阿里山線終點，接高鐵嘉義站
    ("小灣", TransportMode.BUS),  # 台灣好行墾丁快線終點（墾丁大灣沙灘），接高鐵左營站
]

# 渡輪／高鐵接駁公車資料集本身已透過 Adapter 建構參數限定範圍（渡輪僅市內短程
# 航線，公車僅行經高鐵苗栗站之路線），故不逐一列名，先將這兩種運具擷取到的
# 「所有」站點都視為候選，再透過 _prune_to_reachable_component() 篩掉與其餘
# 精選站點不互通者（例如離島渡輪、與淡水線無關之航線，彼此互不相連）。
# 台灣好行（TravelBusAdapter，TBUS_ 前綴）站點數量龐大（全國近 90 條路線），
# 不比照全量納入，改以上方 CURATED_STATION_NAMES 明確指定代表性景點終點站，
# 避免精選清單過度膨脹；故以站點 ID 前綴而非 TransportMode 判斷是否全量納入。
AUTO_INCLUDE_ID_PREFIXES = ["FERRY_", "BUS_"]


def _prune_to_reachable_component(
    curated_ids: List[str], stations: List[Station], edges: List[NetworkEdge], core_station_id: str
) -> List[str]:
    """僅保留與 core_station_id 雙向皆可達之精選站點。

    精選清單須滿足「任意兩站皆能查得到路線」（評審可任意搭配起訖），但
    AUTO_INCLUDE_ALL_MODES 納入之渡輪/公車候選站點中，有不少屬於彼此無關、
    互不相連的獨立子網路（如離島渡輪航線、與 Cijin 渡輪無關之淡水航線），
    若未經連通性篩選，會讓評審選到查無路線的組合。
    """
    graph = TransportGraph()
    stations_by_id: Dict[str, Station] = {}
    for station in stations:
        graph.add_station(station)
        stations_by_id[station.station_id] = station
    for edge in edges:
        graph.add_route_edge(edge)
    for transfer in resolve_transfer_seeds(stations_by_id):
        graph.add_transfer_edge(transfer)

    def bfs(start: str, forward: bool) -> set:
        seen = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if forward:
                next_ids = [e.target for e in graph.neighbors(current)]
            else:
                next_ids = [sid for sid in graph.stations if any(e.target == current for e in graph.neighbors(sid))]
            for next_id in next_ids:
                if next_id not in seen:
                    seen.add(next_id)
                    queue.append(next_id)
        return seen

    mutually_reachable = bfs(core_station_id, forward=True) & bfs(core_station_id, forward=False)
    pruned = [sid for sid in curated_ids if sid in mutually_reachable]

    for sid in curated_ids:
        if sid not in mutually_reachable:
            station = stations_by_id.get(sid)
            logger.warning(
                "精選站點與核心站點不互通，已排除：%s / %s",
                sid,
                station.name_zh if station else "?",
            )
    return pruned


def _resolve_curated_ids(stations: List[Station]) -> List[str]:
    resolved: List[str] = []
    for name, mode in CURATED_STATION_NAMES:
        candidates = [s for s in stations if s.transport_mode == mode and name in s.name_zh]
        exact = next((s for s in candidates if s.name_zh == name), None)
        chosen = exact or (candidates[0] if candidates else None)
        if chosen is None:
            logger.warning("找不到精選站點：%s (%s)，已略過", name, mode.value)
            continue
        if chosen.station_id not in resolved:
            resolved.append(chosen.station_id)
        logger.info("精選站點已對應：%s (%s) -> %s / %s", name, mode.value, chosen.station_id, chosen.name_zh)

    for station in stations:
        if (
            any(station.station_id.startswith(prefix) for prefix in AUTO_INCLUDE_ID_PREFIXES)
            and station.station_id not in resolved
        ):
            resolved.append(station.station_id)
            logger.info("自動納入精選站點（%s）：%s / %s", station.transport_mode.value, station.station_id, station.name_zh)

    return resolved


async def main() -> None:
    credentials = load_tdx_credentials()
    if credentials is None:
        raise SystemExit("找不到 TDX_CLIENT_ID / TDX_CLIENT_SECRET，請確認 backend/.env 已設定真實憑證")

    tdx_client = TDXClient(credentials.client_id, credentials.client_secret)
    adapters = [
        MetroAdapter("TYMC", tdx_client),
        MetroAdapter("KRTC", tdx_client),
        MetroAdapter("TMRT", tdx_client),
        TRAAdapter(tdx_client),
        THSRAdapter(tdx_client),
        FerryAdapter(tdx_client),
        BusAdapter("MiaoliCounty", "高鐵苗栗站", tdx_client),
        TravelBusAdapter(tdx_client),
    ]

    all_stations: List[Station] = []
    all_edges: List[NetworkEdge] = []
    all_alerts: List[ServiceAlert] = []

    for adapter in adapters:
        logger.info("=== 擷取 %s ===", adapter.transport_mode.value)

        try:
            stations = await _fetch_with_rate_limit_retry(adapter.get_stations, asyncio.sleep)
            all_stations.extend(stations)
            logger.info("站點數：%d", len(stations))
        except Exception:
            logger.warning("擷取 %s 站點資料失敗，快照略過該運具，不影響其他運具", adapter.transport_mode.value)
            continue
        await asyncio.sleep(DEFAULT_REQUEST_INTERVAL_SECONDS)

        try:
            edges = await _fetch_with_rate_limit_retry(adapter.get_routes, asyncio.sleep)
            all_edges.extend(edges)
            logger.info("路網邊數：%d", len(edges))
        except Exception:
            logger.warning("擷取 %s 路網資料失敗，快照僅保留該運具站點", adapter.transport_mode.value)
        await asyncio.sleep(DEFAULT_REQUEST_INTERVAL_SECONDS)

        try:
            alerts = await _fetch_with_rate_limit_retry(adapter.get_alerts, asyncio.sleep)
            all_alerts.extend(alerts)
            logger.info("營運通報數：%d", len(alerts))
        except Exception:
            logger.warning("擷取 %s 營運通報失敗，快照略過該運具通報", adapter.transport_mode.value)
        await asyncio.sleep(DEFAULT_REQUEST_INTERVAL_SECONDS)

    curated_ids = _resolve_curated_ids(all_stations)
    if curated_ids:
        curated_ids = _prune_to_reachable_component(curated_ids, all_stations, all_edges, curated_ids[0])

    snapshot = {
        "stations": [s.model_dump(mode="json") for s in all_stations],
        "edges": [e.model_dump(mode="json") for e in all_edges],
        "alerts": [a.model_dump(mode="json") for a in all_alerts],
        "curated_station_ids": curated_ids,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "快照已寫入 %s（站點 %d、路網邊 %d、通報 %d、精選站點 %d）",
        OUTPUT_PATH,
        len(all_stations),
        len(all_edges),
        len(all_alerts),
        len(curated_ids),
    )


if __name__ == "__main__":
    asyncio.run(main())
