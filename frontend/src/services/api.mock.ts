/**
 * 靜態 Mock API — 不依賴任何後端或 .env 設定。
 * 使用內嵌 demo 資料回應所有 API 呼叫，用於靜態打包版本。
 */
import type {
  LiveBoardResponse,
  RouteSearchResponse,
  ServiceAlert,
  StationSuggestion,
  TransferInfoResponse,
} from "../types";

export interface RouteSearchParams {
  origin: string;
  destination: string;
  departure_time?: string;
}

// ─── Demo Stations（精選站點） ──────────────────────────────────────
const DEMO_STATIONS: StationSuggestion[] = [
  { station_id: "THSR_1000", name_zh: "南港", name_en: "Nangang", transport_mode: "thsr" },
  { station_id: "THSR_1010", name_zh: "台北", name_en: "Taipei", transport_mode: "thsr" },
  { station_id: "THSR_1020", name_zh: "板橋", name_en: "Banqiao", transport_mode: "thsr" },
  { station_id: "THSR_1030", name_zh: "桃園", name_en: "Taoyuan", transport_mode: "thsr" },
  { station_id: "THSR_1040", name_zh: "新竹", name_en: "Hsinchu", transport_mode: "thsr" },
  { station_id: "THSR_1050", name_zh: "苗栗", name_en: "Miaoli", transport_mode: "thsr" },
  { station_id: "THSR_1060", name_zh: "台中", name_en: "Taichung", transport_mode: "thsr" },
  { station_id: "THSR_1070", name_zh: "彰化", name_en: "Changhua", transport_mode: "thsr" },
  { station_id: "TRA_1000", name_zh: "台北", name_en: "Taipei", transport_mode: "tra" },
  { station_id: "TRA_1210", name_zh: "桃園", name_en: "Taoyuan", transport_mode: "tra" },
  { station_id: "TRA_3300", name_zh: "新竹", name_en: "Hsinchu", transport_mode: "tra" },
  { station_id: "TRA_3340", name_zh: "竹南", name_en: "Zhunan", transport_mode: "tra" },
  { station_id: "TRA_4080", name_zh: "台中", name_en: "Taichung", transport_mode: "tra" },
  { station_id: "TYMC_A1", name_zh: "台北車站", name_en: "Taipei Main Station", transport_mode: "metro_taoyuan" },
  { station_id: "TYMC_A18", name_zh: "桃園高鐵站", name_en: "Taoyuan HSR Station", transport_mode: "metro_taoyuan" },
  { station_id: "TMRT_G17", name_zh: "高鐵台中站", name_en: "HSR Taichung Station", transport_mode: "metro_taichung" },
  { station_id: "KRTC_R11", name_zh: "高雄車站", name_en: "Kaohsiung Main Station", transport_mode: "metro_kaohsiung" },
  { station_id: "KRTC_R16", name_zh: "左營", name_en: "Zuoying", transport_mode: "metro_kaohsiung" },
];

// ─── Demo Alerts ──────────────────────────────────────────────────
const DEMO_ALERTS: ServiceAlert[] = [
  {
    alert_id: "DEMO_001",
    transport_mode: "thsr",
    title: "[Demo] 高鐵正常營運中",
    description: "目前各列車準點運行。",
    severity: "info",
    affected_stations: [],
    affected_routes: [],
    start_time: new Date().toISOString(),
    end_time: null,
    status: "持續中",
    source: "Demo",
  },
];

// ─── Helper: 產生 demo 時間 ─────────────────────────────────────────
function futureTime(minutesFromNow: number): string {
  return new Date(Date.now() + minutesFromNow * 60_000).toISOString();
}

// ─── Mock API implementations ────────────────────────────────────────

export async function searchRoutes(_params: RouteSearchParams): Promise<RouteSearchResponse> {
  // 回傳一個模擬路線：台北 → 桃園（高鐵）
  return {
    routes: [
      {
        route_id: "demo-route-1",
        segments: [
          {
            segment_id: "seg-1",
            transport_mode: "thsr",
            trip_id: "THSR-0613",
            from_station: {
              station_id: "THSR_1010",
              original_id: "1010",
              name_zh: "台北",
              name_en: "Taipei",
              transport_mode: "thsr",
              latitude: 25.0478,
              longitude: 121.5171,
            },
            to_station: {
              station_id: "THSR_1030",
              original_id: "1030",
              name_zh: "桃園",
              name_en: "Taoyuan",
              transport_mode: "thsr",
              latitude: 25.0132,
              longitude: 121.2144,
            },
            departure_time: futureTime(15),
            arrival_time: futureTime(35),
            duration_minutes: 20,
          },
        ],
        transfers: [],
        total_time_minutes: 20,
        transfer_count: 0,
        transport_modes_used: ["thsr"],
        risk_predictions: [],
      },
      {
        route_id: "demo-route-2",
        segments: [
          {
            segment_id: "seg-2a",
            transport_mode: "tra",
            trip_id: "TRA-1234",
            from_station: {
              station_id: "TRA_1000",
              original_id: "1000",
              name_zh: "台北",
              name_en: "Taipei",
              transport_mode: "tra",
              latitude: 25.0478,
              longitude: 121.5171,
            },
            to_station: {
              station_id: "TRA_1210",
              original_id: "1210",
              name_zh: "桃園",
              name_en: "Taoyuan",
              transport_mode: "tra",
              latitude: 25.0033,
              longitude: 121.3092,
            },
            departure_time: futureTime(10),
            arrival_time: futureTime(50),
            duration_minutes: 40,
          },
        ],
        transfers: [],
        total_time_minutes: 40,
        transfer_count: 0,
        transport_modes_used: ["tra"],
        risk_predictions: [],
      },
    ],
    alerts: DEMO_ALERTS,
    cached: false,
    data_possibly_outdated: false,
    message: "[靜態 Demo 模式] 此為離線展示資料，非即時查詢結果。",
  };
}

export async function suggestStations(query: string, limit = 10): Promise<StationSuggestion[]> {
  const q = query.toLowerCase();
  return DEMO_STATIONS.filter(
    (s) => s.name_zh.includes(query) || (s.name_en?.toLowerCase().includes(q) ?? false),
  ).slice(0, limit);
}

export async function getAllStations(): Promise<StationSuggestion[]> {
  return DEMO_STATIONS;
}

export async function getLiveboard(stationId: string): Promise<LiveBoardResponse> {
  return {
    station_id: stationId,
    entries: [
      {
        trip_id: "DEMO-T001",
        station_id: stationId,
        transport_mode: "thsr",
        estimated_arrival: futureTime(5),
        estimated_departure: futureTime(7),
        scheduled_arrival: futureTime(5),
        scheduled_departure: futureTime(7),
        delay_minutes: 0,
        status: "準點",
        destination: "左營",
      },
      {
        trip_id: "DEMO-T002",
        station_id: stationId,
        transport_mode: "thsr",
        estimated_arrival: futureTime(20),
        estimated_departure: futureTime(22),
        scheduled_arrival: futureTime(20),
        scheduled_departure: futureTime(22),
        delay_minutes: 0,
        status: "準點",
        destination: "南港",
      },
    ],
    is_realtime: false,
  };
}

export async function getTransferInfo(transferId: string): Promise<TransferInfoResponse> {
  return {
    transfer: {
      transfer_id: transferId,
      from_station: {
        station_id: "THSR_1010",
        original_id: "1010",
        name_zh: "台北",
        name_en: "Taipei",
        transport_mode: "thsr",
        latitude: 25.0478,
        longitude: 121.5171,
      },
      to_station: {
        station_id: "TRA_1000",
        original_id: "1000",
        name_zh: "台北",
        name_en: "Taipei",
        transport_mode: "tra",
        latitude: 25.0478,
        longitude: 121.5171,
      },
      from_platform: "1",
      to_platform: "3",
      walking_distance_m: 200,
      walking_time_min: 3,
      buffer_time_min: 5,
    },
    total_transfer_time_minutes: 8,
    message: "[Demo] 模擬轉乘資訊",
  };
}

export async function getAlerts(_transportMode?: string): Promise<ServiceAlert[]> {
  return DEMO_ALERTS;
}

// Dummy client export for compatibility
export const apiClient = {
  defaults: { baseURL: "/static-demo" },
};
