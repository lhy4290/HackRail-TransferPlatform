import asyncio
import logging
from typing import Awaitable, Callable, Dict, List, Optional, TypeVar

from app.adapters.base_adapter import BaseTransportAdapter
from app.models.enums import ErrorType
from app.models.errors import TDXAPIError
from app.models.station import Station
from app.services.transport_graph import TransportGraph

logger = logging.getLogger(__name__)

# TDX 對短時間內密集呼叫會回應 429；啟動時一次擷取 5 個運具 x 2 個端點，
# 呼叫間需錯開間隔，避免觸發流量限制。
DEFAULT_REQUEST_INTERVAL_SECONDS = 2.0

# 429 為短期流量限制，非請求本身錯誤，故在 TDXClient 既有之逾時/一般錯誤重試之外，
# 針對批次擷取場景額外以遞增間隔重試（不影響 TDXClient 本身之重試契約）。
RATE_LIMIT_BACKOFF_SECONDS = (5.0, 10.0, 20.0)

SleepFn = Callable[[float], Awaitable[None]]
T = TypeVar("T")


def _is_rate_limited(exc: TDXAPIError) -> bool:
    details = exc.platform_error.details or {}
    return exc.platform_error.error_type == ErrorType.API_ERROR and details.get("detail") == 429


async def _fetch_with_rate_limit_retry(fetch: Callable[[], Awaitable[T]], sleep_fn: SleepFn) -> T:
    last_exc: Optional[TDXAPIError] = None
    for backoff in (0.0, *RATE_LIMIT_BACKOFF_SECONDS):
        if backoff:
            logger.warning("TDX 回應 429，%.0f 秒後重試", backoff)
            await sleep_fn(backoff)
        try:
            return await fetch()
        except TDXAPIError as exc:
            if not _is_rate_limited(exc):
                raise
            last_exc = exc
    raise last_exc


async def ingest_network(
    adapters: List[BaseTransportAdapter],
    graph: TransportGraph,
    stations_by_id: Dict[str, Station],
    request_interval_seconds: float = 0.0,
    sleep_fn: SleepFn = asyncio.sleep,
) -> None:
    """向每個運具轉接器擷取站點與路網邊，寫入圖與站點索引。

    單一運具擷取失敗（TDX 逾時/錯誤/資料解析失敗）不應阻擋其他運具，
    故個別 catch 並記錄錯誤後繼續處理下一個 adapter；429 流量限制另以遞增間隔重試。
    """
    for adapter in adapters:
        try:
            stations = await _fetch_with_rate_limit_retry(adapter.get_stations, sleep_fn)
        except Exception:
            logger.exception("擷取 %s 站點資料失敗，略過該運具", adapter.transport_mode)
            continue

        for station in stations:
            graph.add_station(station)
            stations_by_id[station.station_id] = station

        if request_interval_seconds:
            await sleep_fn(request_interval_seconds)

        try:
            edges = await _fetch_with_rate_limit_retry(adapter.get_routes, sleep_fn)
        except Exception:
            logger.exception("擷取 %s 路網資料失敗，僅載入站點", adapter.transport_mode)
            continue

        for edge in edges:
            graph.add_route_edge(edge)

        if request_interval_seconds:
            await sleep_fn(request_interval_seconds)
