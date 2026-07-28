import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, List, Optional

from app.adapters.tdx_client import TDXClient
from app.models.alert import ServiceAlert
from app.models.enums import ErrorType, TransportMode
from app.models.errors import DataParseError, PlatformError
from app.models.network import NetworkEdge
from app.models.station import Station
from app.models.timetable import LiveBoardEntry, TimetableEntry

logger = logging.getLogger(__name__)


@dataclass
class FieldSpec:
    """描述一個內部欄位如何從原始 TDX JSON 取得

    source_path 支援以 "." 分隔的巢狀路徑，例如 "StationName.Zh_tw"
    """

    internal_name: str
    source_path: str
    required: bool = True
    default: Any = None
    cast: Optional[Callable[[Any], Any]] = None


class BaseTransportAdapter(ABC):
    """所有運具轉接器之抽象基底類別

    共用的欄位轉換邏輯（_map_record）讓新增運具轉接器時，只需定義該運具專屬的
    FieldSpec 清單與 API 端點，無須修改既有其他運具轉接器之轉換邏輯（需求 4.7）。
    """

    transport_mode: TransportMode

    def __init__(self, tdx_client: TDXClient):
        self.tdx_client = tdx_client
        self.parse_warnings: list[str] = []

    @abstractmethod
    async def get_stations(self) -> List[Station]:
        """取得該運具所有站點資料"""
        ...

    @abstractmethod
    async def get_routes(self) -> List[NetworkEdge]:
        """取得該運具所有路線/路網結構"""
        ...

    @abstractmethod
    async def get_timetable(self, station_id: str, date: datetime) -> List[TimetableEntry]:
        """取得特定站點之班表"""
        ...

    @abstractmethod
    async def get_liveboard(self, station_id: str) -> List[LiveBoardEntry]:
        """取得特定站點之即時到離站資訊"""
        ...

    @abstractmethod
    async def get_alerts(self) -> List[ServiceAlert]:
        """取得營運通報"""
        ...

    # ---- 共用欄位轉換工具 ----

    @staticmethod
    def _get_nested(raw: dict, path: str) -> Any:
        value: Any = raw
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    def _map_record(self, raw: dict, specs: List[FieldSpec]) -> dict:
        """依 FieldSpec 清單將原始 TDX JSON 轉換為內部欄位字典。

        - 必要欄位缺失 -> 拋出 DataParseError（記錄原始 JSON 與欄位名稱，對應需求 10.4 / Property 20）
        - 非必要欄位缺失或為 null -> 填入預設值並記錄警告（對應需求 10.5 / Property 21）
        - 欄位型別轉換失敗（cast）-> 拋出 DataParseError
        """
        result: dict[str, Any] = {}
        missing_required: list[str] = []

        for spec in specs:
            value = self._get_nested(raw, spec.source_path)
            if value is None:
                if spec.required:
                    missing_required.append(spec.internal_name)
                    continue
                value = spec.default
                self.parse_warnings.append(
                    f"欄位 {spec.internal_name} 缺失或為 null，已填入預設值 {spec.default!r}"
                )
            elif spec.cast is not None:
                try:
                    value = spec.cast(value)
                except (TypeError, ValueError) as exc:
                    error = PlatformError(
                        error_type=ErrorType.PARSE_ERROR,
                        message=f"欄位 {spec.internal_name} 型別錯誤：{exc}",
                        details={"field": spec.internal_name},
                    )
                    logger.error("%s | raw=%s", error.message, raw)
                    raise DataParseError(error, raw_payload=json.dumps(raw, ensure_ascii=False)) from exc
            result[spec.internal_name] = value

        if missing_required:
            error = PlatformError(
                error_type=ErrorType.PARSE_ERROR,
                message=f"必要欄位缺失：{', '.join(missing_required)}",
                details={"missing_fields": missing_required},
            )
            logger.error("%s | raw=%s", error.message, raw)
            raise DataParseError(error, raw_payload=json.dumps(raw, ensure_ascii=False))

        return result

    def parse_json(self, raw_json: str) -> Any:
        """解析原始 JSON 字串；語法無效時拋出 DataParseError（需求 10.4）"""
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError as exc:
            error = PlatformError(
                error_type=ErrorType.PARSE_ERROR,
                message=f"JSON 語法無效：{exc}",
                details={"error": str(exc)},
            )
            logger.error("%s | raw=%s", error.message, raw_json)
            raise DataParseError(error, raw_payload=raw_json) from exc
