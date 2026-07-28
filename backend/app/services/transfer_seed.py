from dataclasses import dataclass
from typing import Dict, List, Optional

from app.models.enums import TransportMode
from app.models.station import Station
from app.models.transfer import TransferStation


@dataclass(frozen=True)
class TransferSeedEntry:
    """示意用跨運具轉乘站資料。

    TDX 各運具 API 只提供同運具站點資料，並不包含跨運具步行距離/時間，
    故以站名比對的方式，將已知的共構轉乘站手動整理成種子資料。
    name_a/name_b 分開設定，因同一共構站在不同運具官方站名常不同
    （例如高鐵「左營」與臺鐵「新左營」為同一共構站，但站名不同）。
    walking_distance_m / walking_time_min 為示意值，正式使用前應人工實地調查後更正。
    """

    name_a: str
    mode_a: TransportMode
    name_b: str
    mode_b: TransportMode
    walking_distance_m: int
    walking_time_min: Optional[int] = None
    buffer_time_min: int = 10


# 台灣已知的跨運具共構轉乘站（示意資料，非 TDX 提供，需人工調查後更新為實際量測值）
ILLUSTRATIVE_TRANSFER_SEEDS: List[TransferSeedEntry] = [
    # 左營共構站：高鐵/高雄捷運官方站名為「左營」，與其共構的臺鐵站名為「新左營」（非舊左營站）
    TransferSeedEntry("左營", TransportMode.THSR, "新左營", TransportMode.TRA, 200, 3),
    TransferSeedEntry("左營", TransportMode.THSR, "左營", TransportMode.METRO_KAOHSIUNG, 300, 5),
    # 台中高鐵共構站：高鐵官方站名為「台中」，與其共構的臺鐵站名為「新烏日」
    TransferSeedEntry("台中", TransportMode.THSR, "新烏日", TransportMode.TRA, 250, 4),
    # 台中捷運官方站名為「高鐵臺中站」（臺為正體字，非「台」），故比對用字需一致
    TransferSeedEntry("台中", TransportMode.THSR, "高鐵臺中", TransportMode.METRO_TAICHUNG, 150, 3),
    # 桃園高鐵共構站：高鐵官方站名為「桃園」，機場捷運官方站名為「高鐵桃園」
    TransferSeedEntry("桃園", TransportMode.THSR, "高鐵桃園", TransportMode.METRO_TAOYUAN, 100, 2),
    # 高雄鼓山：臺鐵「鼓山」站與鼓山輪渡站（往旗津渡輪）步行可達，為真實跨運具轉乘點
    TransferSeedEntry("鼓山", TransportMode.TRA, "高雄鼓山輪渡站", TransportMode.FERRY, 350, 5),
    # 高鐵苗栗站接駁：巴士站牌「高鐵苗栗站」即設於高鐵苗栗站站體外，屬同一建築之接駁站
    TransferSeedEntry("苗栗", TransportMode.THSR, "高鐵苗栗站", TransportMode.BUS, 80, 2),
    # 台灣好行（TaiwanTrip）路線之高鐵站牌，均設於各站站體外，屬同一建築之接駁站
    TransferSeedEntry("嘉義", TransportMode.THSR, "高鐵嘉義站", TransportMode.BUS, 80, 2),
    TransferSeedEntry("台中", TransportMode.THSR, "高鐵臺中站", TransportMode.BUS, 80, 2),
    TransferSeedEntry("左營", TransportMode.THSR, "高鐵左營站", TransportMode.BUS, 80, 2),
    TransferSeedEntry("新竹", TransportMode.THSR, "高鐵新竹站", TransportMode.BUS, 80, 2),
]


def _find_station(stations_by_id: Dict[str, Station], name_fragment: str, mode: TransportMode) -> Optional[Station]:
    for station in stations_by_id.values():
        if station.transport_mode == mode and name_fragment in station.name_zh:
            return station
    return None


def resolve_transfer_seeds(
    stations_by_id: Dict[str, Station],
    seeds: List[TransferSeedEntry] = ILLUSTRATIVE_TRANSFER_SEEDS,
) -> List[TransferStation]:
    """依站名比對已匯入之站點，組出示意轉乘站資料；任一端找不到對應站點則略過該筆"""
    resolved: List[TransferStation] = []
    for seed in seeds:
        from_station = _find_station(stations_by_id, seed.name_a, seed.mode_a)
        to_station = _find_station(stations_by_id, seed.name_b, seed.mode_b)
        if from_station is None or to_station is None:
            continue
        resolved.append(
            TransferStation(
                transfer_id=f"seed_{from_station.station_id}_{to_station.station_id}",
                from_station=from_station,
                to_station=to_station,
                from_platform=seed.mode_a.value,
                to_platform=seed.mode_b.value,
                walking_distance_m=seed.walking_distance_m,
                walking_time_min=seed.walking_time_min,
                buffer_time_min=seed.buffer_time_min,
            )
        )
    return resolved
