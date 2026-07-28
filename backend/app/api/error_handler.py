import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import AppState
from app.models.enums import TransportMode
from app.models.errors import DataParseError, TDXAPIError, ValidationError
from app.services.route_planner import NoRouteFoundError

logger = logging.getLogger(__name__)

# 目前僅捷運（TYMC/KRTC/TMRT）已串接真實路網資料；臺鐵/高鐵僅有站點資料、無路網邊，
# 故查無路線時應提示「資料尚未開放」而非讓使用者誤以為單純沒有可行路線。
_ROUTE_DATA_UNAVAILABLE_MODES = {TransportMode.TRA, TransportMode.THSR}


async def tdx_api_error_handler(request: Request, exc: TDXAPIError) -> JSONResponse:
    """TDX API 不可用時之降級回應（需求 3.4, 9.3）"""
    logger.error("TDX API error: %s", exc.platform_error)
    return JSONResponse(
        status_code=503,
        content={
            "error_type": exc.platform_error.error_type.value,
            "message": "即時資訊暫不可用，結果依據快取資料",
            "endpoint": exc.platform_error.endpoint,
        },
    )


async def data_parse_error_handler(request: Request, exc: DataParseError) -> JSONResponse:
    """TDX 回傳資料解析失敗（需求 10.4）"""
    logger.error("Data parse error: %s | raw=%s", exc.platform_error, exc.raw_payload)
    return JSONResponse(
        status_code=422,
        content={
            "error_type": exc.platform_error.error_type.value,
            "message": "資料格式異常，部分資訊無法顯示",
            "details": exc.platform_error.details,
        },
    )


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """使用者輸入驗證錯誤（需求 1.7, 7.5, 7.7）"""
    return JSONResponse(
        status_code=422,
        content={
            "error_type": exc.platform_error.error_type.value,
            "message": exc.platform_error.message,
            "details": exc.platform_error.details,
        },
    )


async def no_route_found_handler(request: Request, exc: NoRouteFoundError) -> JSONResponse:
    """無可行路線（需求 1.6）"""
    state: AppState = request.app.state.platform
    origin_station = state.stations_by_id.get(exc.origin)
    destination_station = state.stations_by_id.get(exc.destination)
    involves_unavailable_data = any(
        station is not None and station.transport_mode in _ROUTE_DATA_UNAVAILABLE_MODES
        for station in (origin_station, destination_station)
    )
    message = (
        "此運具路網資料尚未開放，暫無法查詢路線" if involves_unavailable_data else "無可用路線"
    )
    return JSONResponse(
        status_code=200,
        content={"routes": [], "alerts": [], "cached": False, "message": message},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(TDXAPIError, tdx_api_error_handler)
    app.add_exception_handler(DataParseError, data_parse_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(NoRouteFoundError, no_route_found_handler)
