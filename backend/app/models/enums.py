from enum import Enum


class TransportMode(str, Enum):
    """運具類型"""

    METRO_TAOYUAN = "metro_taoyuan"
    METRO_TAICHUNG = "metro_taichung"
    METRO_KAOHSIUNG = "metro_kaohsiung"
    TRA = "tra"
    THSR = "thsr"
    AVIATION = "aviation"
    FERRY = "ferry"
    BUS = "bus"


class ConnectionRiskLevel(str, Enum):
    """轉乘風險等級"""

    ON_TIME = "準點"
    MINOR_DELAY = "輕微延誤"
    SEVERE_DELAY = "嚴重延誤"


class CachePolicy(str, Enum):
    """快取策略"""

    STATIC = "static"
    REALTIME = "realtime"
    ALERT = "alert"


class ErrorType(str, Enum):
    """錯誤類型"""

    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    SERVICE_UNAVAILABLE = "service_unavailable"


def classify_risk(delay_minutes: float) -> ConnectionRiskLevel:
    """依預測延誤分鐘數分類風險等級（Property 11）"""
    if delay_minutes <= 5:
        return ConnectionRiskLevel.ON_TIME
    if delay_minutes <= 15:
        return ConnectionRiskLevel.MINOR_DELAY
    return ConnectionRiskLevel.SEVERE_DELAY
