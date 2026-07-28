from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.station import Station
from app.models.transfer import TransferStation
from app.models.enums import TransportMode
from app.services.transfer_calculator import DEFAULT_TRANSFER_MESSAGE, compute_transfer_time

_STATION = Station(
    station_id="S1",
    original_id="S1",
    name_zh="測試站",
    transport_mode=TransportMode.TRA,
    latitude=25.0,
    longitude=121.5,
)


# Feature: cross-transport-transfer-platform, Property 5: 轉乘時間計算
@given(
    walking_time=st.one_of(st.none(), st.integers(min_value=1, max_value=30)),
    buffer_time=st.integers(min_value=1, max_value=15),
)
@settings(max_examples=100)
def test_compute_transfer_time(walking_time, buffer_time):
    transfer = TransferStation(
        transfer_id="T1",
        from_station=_STATION,
        to_station=_STATION,
        from_platform="A",
        to_platform="B",
        walking_distance_m=100,
        walking_time_min=walking_time,
        buffer_time_min=buffer_time,
    )
    total, message = compute_transfer_time(transfer)

    if walking_time is None:
        assert total == 10
        assert message == DEFAULT_TRANSFER_MESSAGE
    else:
        assert total == walking_time + buffer_time
        assert message is None
