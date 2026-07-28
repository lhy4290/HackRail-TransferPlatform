from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.db.database import Database
from app.models.enums import ConnectionRiskLevel, TransportMode, classify_risk
from app.services.risk_predictor import MIN_HISTORY_DAYS, RiskPredictor

STATION_ID = "TRA_1000"
MODE = TransportMode.TRA


async def _seed_history(db: Database, num_days: int, delay_minutes: int) -> None:
    base_day = datetime(2026, 1, 1)
    async with db.connect() as conn:
        for i in range(num_days):
            day = base_day + timedelta(days=i)
            await conn.execute(
                """
                INSERT INTO delay_history
                    (station_id, transport_mode, trip_id, scheduled_time, actual_time,
                     delay_minutes, day_of_week, is_peak_hour)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    STATION_ID,
                    MODE.value,
                    "TRIP1",
                    day.isoformat(),
                    (day + timedelta(minutes=delay_minutes)).isoformat(),
                    delay_minutes,
                    day.weekday(),
                    0,
                ),
            )
        await conn.commit()


# Feature: cross-transport-transfer-platform, Property 11: 風險等級分類
@given(delay=st.integers(min_value=0, max_value=120))
@settings(max_examples=100)
def test_risk_level_classification(delay: int):
    level = classify_risk(delay)
    if delay <= 5:
        assert level == ConnectionRiskLevel.ON_TIME
    elif delay <= 15:
        assert level == ConnectionRiskLevel.MINOR_DELAY
    else:
        assert level == ConnectionRiskLevel.SEVERE_DELAY


# Feature: cross-transport-transfer-platform, Property 13: 歷史資料不足警示
@given(num_days=st.integers(min_value=1, max_value=29))
@settings(max_examples=20, deadline=None)
def test_insufficient_history_flags_data_sufficient_false(num_days, tmp_path_factory):
    import asyncio

    async def run():
        tmp_path = tmp_path_factory.mktemp("risk_db")
        db = Database(tmp_path / "test.db")
        await db.init_schema()
        await _seed_history(db, num_days=num_days, delay_minutes=3)

        predictor = RiskPredictor(db)
        prediction = await predictor.predict_risk(
            "T1", STATION_ID, MODE, datetime(2026, 1, 5, 10, 0)  # 離峰時段
        )
        assert prediction.data_sufficient is False
        assert prediction.message == "資料不足，風險僅供參考"

    asyncio.run(run())


@pytest.mark.asyncio
async def test_sufficient_history_marks_data_sufficient_true(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.init_schema()
    await _seed_history(db, num_days=MIN_HISTORY_DAYS, delay_minutes=20)

    predictor = RiskPredictor(db)
    prediction = await predictor.predict_risk("T1", STATION_ID, MODE, datetime(2026, 1, 5, 10, 0))
    assert prediction.data_sufficient is True
    assert prediction.message is None
    assert prediction.risk_level == ConnectionRiskLevel.SEVERE_DELAY.value


@pytest.mark.asyncio
async def test_no_history_disables_prediction(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.init_schema()

    predictor = RiskPredictor(db)
    prediction = await predictor.predict_risk("T1", "UNKNOWN_STATION", MODE, datetime(2026, 1, 5, 10, 0))
    assert prediction.data_sufficient is False
    assert prediction.message == "風險預測功能尚未啟用"

    available, message = await predictor.check_availability("UNKNOWN_STATION", MODE)
    assert available is False
    assert message == "風險預測功能尚未啟用"
