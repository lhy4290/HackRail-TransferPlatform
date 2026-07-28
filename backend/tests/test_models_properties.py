from hypothesis import given, settings

from app.models.station import Station
from app.models.transfer import TransferStation
from app.models.route import RouteSegment
from app.models.risk import RiskPredictionDTO
from app.models.alert import ServiceAlert
from tests.strategies import (
    st_valid_station,
    st_transfer_station,
    st_route_segment,
    st_risk_prediction,
    st_service_alert,
)


# Feature: cross-transport-transfer-platform, Property 6: 轉乘站資料欄位驗證
@given(transfer=st_transfer_station())
@settings(max_examples=100)
def test_transfer_station_field_bounds(transfer: TransferStation):
    assert len(transfer.from_platform) > 0
    assert len(transfer.to_platform) > 0
    assert 1 <= transfer.walking_distance_m <= 5000
    assert transfer.walking_time_min is None or 1 <= transfer.walking_time_min <= 30


# Feature: cross-transport-transfer-platform, Property 19: JSON 序列化往返特性
@given(station=st_valid_station())
@settings(max_examples=100)
def test_station_json_round_trip(station: Station):
    json_str = station.model_dump_json()
    restored = Station.model_validate_json(json_str)
    assert restored == station


@given(transfer=st_transfer_station())
@settings(max_examples=100)
def test_transfer_station_json_round_trip(transfer: TransferStation):
    json_str = transfer.model_dump_json()
    restored = TransferStation.model_validate_json(json_str)
    assert restored == transfer


@given(segment=st_route_segment())
@settings(max_examples=100)
def test_route_segment_json_round_trip(segment: RouteSegment):
    json_str = segment.model_dump_json()
    restored = RouteSegment.model_validate_json(json_str)
    assert restored == segment


@given(risk=st_risk_prediction())
@settings(max_examples=100)
def test_risk_prediction_json_round_trip(risk: RiskPredictionDTO):
    json_str = risk.model_dump_json()
    restored = RiskPredictionDTO.model_validate_json(json_str)
    assert restored == risk


@given(alert=st_service_alert())
@settings(max_examples=100)
def test_service_alert_json_round_trip(alert: ServiceAlert):
    json_str = alert.model_dump_json()
    restored = ServiceAlert.model_validate_json(json_str)
    assert restored == alert
