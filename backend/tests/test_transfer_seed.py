from app.models.enums import TransportMode
from app.services.transfer_seed import ILLUSTRATIVE_TRANSFER_SEEDS, TransferSeedEntry, resolve_transfer_seeds
from tests.conftest import make_station


def test_resolve_transfer_seeds_matches_both_stations_by_name():
    stations_by_id = {
        "THSR_1": make_station("THSR_1", "左營", TransportMode.THSR),
        "TRA_1": make_station("TRA_1", "新左營", TransportMode.TRA),
    }
    seeds = [TransferSeedEntry("左營", TransportMode.THSR, "新左營", TransportMode.TRA, 200, 3)]

    resolved = resolve_transfer_seeds(stations_by_id, seeds)

    assert len(resolved) == 1
    assert resolved[0].from_station.station_id == "THSR_1"
    assert resolved[0].to_station.station_id == "TRA_1"
    assert resolved[0].walking_time_min == 3


def test_resolve_transfer_seeds_skips_when_one_side_missing():
    stations_by_id = {"THSR_1": make_station("THSR_1", "左營", TransportMode.THSR)}
    seeds = [TransferSeedEntry("左營", TransportMode.THSR, "新左營", TransportMode.TRA, 200, 3)]

    resolved = resolve_transfer_seeds(stations_by_id, seeds)

    assert resolved == []


def test_default_seeds_include_kaohsiung_ferry_and_miaoli_hsr_shuttle_transfers():
    stations_by_id = {
        "TRA_4380": make_station("TRA_4380", "鼓山", TransportMode.TRA),
        "FERRY_TW074": make_station("FERRY_TW074", "高雄鼓山輪渡站", TransportMode.FERRY),
        "THSR_1035": make_station("THSR_1035", "苗栗", TransportMode.THSR),
        "BUS_297592": make_station("BUS_297592", "高鐵苗栗站", TransportMode.BUS),
    }

    resolved = resolve_transfer_seeds(stations_by_id, ILLUSTRATIVE_TRANSFER_SEEDS)

    pairs = {(t.from_station.station_id, t.to_station.station_id) for t in resolved}
    assert ("TRA_4380", "FERRY_TW074") in pairs
    assert ("THSR_1035", "BUS_297592") in pairs


def test_default_seeds_include_taiwan_trip_bus_hsr_transfers():
    stations_by_id = {
        "THSR_CYI": make_station("THSR_CYI", "嘉義", TransportMode.THSR),
        "TBUS_272098": make_station("TBUS_272098", "高鐵嘉義站", TransportMode.BUS),
        "THSR_TXG": make_station("THSR_TXG", "台中", TransportMode.THSR),
        "TBUS_TXG1": make_station("TBUS_TXG1", "高鐵臺中站", TransportMode.BUS),
        "THSR_ZY": make_station("THSR_ZY", "左營", TransportMode.THSR),
        "TBUS_ZY1": make_station("TBUS_ZY1", "高鐵左營站", TransportMode.BUS),
        "THSR_HSC": make_station("THSR_HSC", "新竹", TransportMode.THSR),
        "TBUS_HSC1": make_station("TBUS_HSC1", "高鐵新竹站", TransportMode.BUS),
    }

    resolved = resolve_transfer_seeds(stations_by_id, ILLUSTRATIVE_TRANSFER_SEEDS)

    pairs = {(t.from_station.station_id, t.to_station.station_id) for t in resolved}
    assert ("THSR_CYI", "TBUS_272098") in pairs
    assert ("THSR_TXG", "TBUS_TXG1") in pairs
    assert ("THSR_ZY", "TBUS_ZY1") in pairs
    assert ("THSR_HSC", "TBUS_HSC1") in pairs
