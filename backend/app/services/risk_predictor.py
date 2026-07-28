from dataclasses import dataclass
from datetime import datetime, time
from typing import List, Optional

from app.db.database import Database
from app.models.enums import ConnectionRiskLevel, TransportMode, classify_risk
from app.models.risk import DATA_INSUFFICIENT_MESSAGE, RiskPredictionDTO
from app.models.route import RoutePlanDTO

MIN_HISTORY_DAYS = 30
DISABLED_MESSAGE = "風險預測功能尚未啟用"

# 尖峰時段：週一至五 07:00-09:00 及 17:00-19:00
PEAK_WINDOWS = ((time(7, 0), time(9, 0)), (time(17, 0), time(19, 0)))


def is_peak_hour(dt: datetime) -> bool:
    """判斷是否為尖峰時段"""
    if dt.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    current_time = dt.time()
    return any(start <= current_time <= end for start, end in PEAK_WINDOWS)


@dataclass
class _HistoryStats:
    distinct_days: int
    avg_delay_minutes: float
    avg_delay_peak: Optional[float]
    avg_delay_offpeak: Optional[float]


class RiskPredictor:
    """轉乘風險預測模組

    原型階段以歷史平均延誤分鐘數（依尖峰/離峰分層）作為預測依據；
    正式環境可替換為 scikit-learn / XGBoost 訓練之分類模型，介面維持不變。
    """

    def __init__(self, db: Database):
        self.db = db

    async def _history_stats(self, station_id: str, transport_mode: TransportMode) -> _HistoryStats:
        async with self.db.connect() as conn:
            cursor = await conn.execute(
                """
                SELECT delay_minutes, is_peak_hour, DATE(scheduled_time) as day
                FROM delay_history
                WHERE station_id = ? AND transport_mode = ?
                """,
                (station_id, transport_mode.value),
            )
            rows = await cursor.fetchall()

        if not rows:
            return _HistoryStats(distinct_days=0, avg_delay_minutes=0.0, avg_delay_peak=None, avg_delay_offpeak=None)

        distinct_days = len({row[2] for row in rows})
        delays = [row[0] for row in rows]
        peak_delays = [row[0] for row in rows if row[1]]
        offpeak_delays = [row[0] for row in rows if not row[1]]

        return _HistoryStats(
            distinct_days=distinct_days,
            avg_delay_minutes=sum(delays) / len(delays),
            avg_delay_peak=(sum(peak_delays) / len(peak_delays)) if peak_delays else None,
            avg_delay_offpeak=(sum(offpeak_delays) / len(offpeak_delays)) if offpeak_delays else None,
        )

    async def check_availability(self, station_id: str, transport_mode: TransportMode) -> tuple[bool, str]:
        """檢查特定站點是否有足夠歷史資料（≥30天）"""
        stats = await self._history_stats(station_id, transport_mode)
        if stats.distinct_days == 0:
            return False, DISABLED_MESSAGE
        if stats.distinct_days < MIN_HISTORY_DAYS:
            return False, DATA_INSUFFICIENT_MESSAGE
        return True, ""

    async def predict_risk(
        self,
        transfer_id: str,
        station_id: str,
        transport_mode: TransportMode,
        departure_time: datetime,
    ) -> RiskPredictionDTO:
        """預測單一轉乘節點之風險等級"""
        stats = await self._history_stats(station_id, transport_mode)

        if stats.distinct_days == 0:
            return RiskPredictionDTO(
                transfer_id=transfer_id,
                risk_level=ConnectionRiskLevel.ON_TIME.value,
                predicted_delay_minutes=0.0,
                confidence=0.0,
                data_sufficient=False,
                message=DISABLED_MESSAGE,
            )

        peak = is_peak_hour(departure_time)
        if peak and stats.avg_delay_peak is not None:
            predicted_delay = stats.avg_delay_peak
        elif not peak and stats.avg_delay_offpeak is not None:
            predicted_delay = stats.avg_delay_offpeak
        else:
            predicted_delay = stats.avg_delay_minutes

        risk_level = classify_risk(predicted_delay)
        data_sufficient = stats.distinct_days >= MIN_HISTORY_DAYS
        message = None if data_sufficient else DATA_INSUFFICIENT_MESSAGE
        confidence = min(1.0, stats.distinct_days / MIN_HISTORY_DAYS)

        return RiskPredictionDTO(
            transfer_id=transfer_id,
            risk_level=risk_level.value,
            predicted_delay_minutes=predicted_delay,
            confidence=confidence,
            data_sufficient=data_sufficient,
            message=message,
        )

    async def predict_route_risks(self, route: RoutePlanDTO, departure_time: datetime) -> List[RiskPredictionDTO]:
        """批次預測整條路線所有轉乘節點之風險"""
        predictions = []
        for transfer in route.transfers:
            prediction = await self.predict_risk(
                transfer.transfer_id,
                transfer.to_station.station_id,
                transfer.to_station.transport_mode,
                departure_time,
            )
            predictions.append(prediction)
        return predictions
