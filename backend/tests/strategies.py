from datetime import datetime, timedelta, timezone

from hypothesis import strategies as st

from app.models.enums import TransportMode
from app.models.station import Station
from app.models.transfer import TransferStation
from app.models.timetable import LiveBoardEntry
from app.models.route import RouteSegment
from app.models.risk import RiskPredictionDTO
from app.models.alert import ServiceAlert

TAIWAN_LAT = st.floats(min_value=21.0, max_value=26.0, allow_nan=False, allow_infinity=False)
TAIWAN_LON = st.floats(min_value=119.0, max_value=122.0, allow_nan=False, allow_infinity=False)
SAFE_TEXT = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))


@st.composite
def st_valid_station(draw):
    return Station(
        station_id=draw(SAFE_TEXT),
        original_id=draw(SAFE_TEXT),
        name_zh=draw(SAFE_TEXT),
        name_en=None,
        transport_mode=draw(st.sampled_from(TransportMode)),
        latitude=draw(TAIWAN_LAT),
        longitude=draw(TAIWAN_LON),
    )


@st.composite
def st_transfer_station(draw):
    return TransferStation(
        transfer_id=draw(SAFE_TEXT),
        from_station=draw(st_valid_station()),
        to_station=draw(st_valid_station()),
        from_platform=draw(SAFE_TEXT),
        to_platform=draw(SAFE_TEXT),
        walking_distance_m=draw(st.integers(min_value=1, max_value=5000)),
        walking_time_min=draw(st.integers(min_value=1, max_value=30)),
        buffer_time_min=draw(st.integers(min_value=1, max_value=15)),
    )


@st.composite
def st_route_segment(draw):
    departure = draw(
        st.datetimes(
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2030, 1, 1),
            timezones=st.just(timezone.utc),
        )
    )
    duration = draw(st.integers(min_value=1, max_value=180))
    return RouteSegment(
        segment_id=draw(SAFE_TEXT),
        transport_mode=draw(st.sampled_from(TransportMode)),
        trip_id=draw(SAFE_TEXT),
        from_station=draw(st_valid_station()),
        to_station=draw(st_valid_station()),
        departure_time=departure,
        arrival_time=departure + timedelta(minutes=duration),
        duration_minutes=duration,
    )


@st.composite
def st_liveboard_entry(draw):
    scheduled = draw(
        st.datetimes(
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2030, 1, 1),
            timezones=st.just(timezone.utc),
        )
    )
    delay = draw(st.integers(min_value=-15, max_value=60))
    return LiveBoardEntry(
        trip_id=draw(SAFE_TEXT),
        station_id=draw(SAFE_TEXT),
        transport_mode=draw(st.sampled_from(TransportMode)),
        estimated_arrival=scheduled + timedelta(minutes=delay),
        scheduled_arrival=scheduled,
        destination=draw(SAFE_TEXT),
    )


@st.composite
def st_risk_prediction(draw):
    return RiskPredictionDTO(
        transfer_id=draw(SAFE_TEXT),
        risk_level=draw(st.sampled_from(["準點", "輕微延誤", "嚴重延誤"])),
        predicted_delay_minutes=draw(st.floats(min_value=0, max_value=60, allow_nan=False)),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        data_sufficient=draw(st.booleans()),
    )


@st.composite
def st_service_alert(draw):
    start = draw(
        st.datetimes(
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2030, 1, 1),
            timezones=st.just(timezone.utc),
        )
    )
    return ServiceAlert(
        alert_id=draw(SAFE_TEXT),
        transport_mode=draw(st.sampled_from(TransportMode)),
        title=draw(SAFE_TEXT),
        description=draw(SAFE_TEXT),
        severity=draw(st.sampled_from(["停駛", "延誤", "路線異動"])),
        affected_stations=draw(st.lists(SAFE_TEXT, max_size=5)),
        affected_routes=draw(st.lists(SAFE_TEXT, max_size=5)),
        start_time=start,
        status=draw(st.sampled_from(["進行中", "已恢復", "已結束"])),
    )
