export type TransportMode =
  | "metro_taoyuan"
  | "metro_taichung"
  | "metro_kaohsiung"
  | "tra"
  | "thsr"
  | "aviation"
  | "ferry"
  | "bus";

export const TRANSPORT_MODE_LABELS: Record<TransportMode, string> = {
  metro_taoyuan: "桃園捷運",
  metro_taichung: "臺中捷運",
  metro_kaohsiung: "高雄捷運",
  tra: "臺鐵",
  thsr: "高鐵",
  aviation: "航空",
  ferry: "渡輪",
  bus: "公車",
};

export const TRANSPORT_MODE_COLORS: Record<TransportMode, string> = {
  thsr: "#38bdf8",
  tra: "#818cf8",
  metro_taoyuan: "#c084fc",
  metro_taichung: "#fb923c",
  metro_kaohsiung: "#f472b6",
  aviation: "#2dd4bf",
  ferry: "#22d3ee",
  bus: "#a78bfa",
};

export interface Station {
  station_id: string;
  original_id: string;
  name_zh: string;
  name_en?: string | null;
  transport_mode: TransportMode;
  latitude: number;
  longitude: number;
  address?: string | null;
}

export interface TransferStation {
  transfer_id: string;
  from_station: Station;
  to_station: Station;
  from_platform: string;
  to_platform: string;
  walking_distance_m: number;
  walking_time_min: number | null;
  buffer_time_min: number;
}

export interface RouteSegment {
  segment_id: string;
  transport_mode: TransportMode;
  trip_id: string;
  from_station: Station;
  to_station: Station;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
}

export interface RiskPredictionDTO {
  transfer_id: string;
  risk_level: "準點" | "輕微延誤" | "嚴重延誤";
  predicted_delay_minutes: number;
  confidence: number;
  data_sufficient: boolean;
  message?: string | null;
}

export interface RoutePlanDTO {
  route_id: string;
  segments: RouteSegment[];
  transfers: TransferStation[];
  total_time_minutes: number;
  transfer_count: number;
  transport_modes_used: TransportMode[];
  risk_predictions?: RiskPredictionDTO[] | null;
}

export interface ServiceAlert {
  alert_id: string;
  transport_mode: TransportMode;
  title: string;
  description: string;
  severity: string;
  affected_stations: string[];
  affected_routes: string[];
  start_time: string;
  end_time?: string | null;
  status: string;
  source: string;
}

export interface RouteSearchResponse {
  routes: RoutePlanDTO[];
  alerts: ServiceAlert[];
  cached: boolean;
  data_possibly_outdated: boolean;
  message?: string;
}

export interface StationSuggestion {
  station_id: string;
  name_zh: string;
  name_en?: string | null;
  transport_mode: TransportMode;
}

export interface LiveBoardEntry {
  trip_id: string;
  station_id: string;
  transport_mode: TransportMode;
  estimated_arrival?: string | null;
  estimated_departure?: string | null;
  scheduled_arrival?: string | null;
  scheduled_departure?: string | null;
  delay_minutes: number;
  status: "提前" | "準點" | "延誤";
  destination: string;
}

export interface LiveBoardResponse {
  station_id: string;
  entries: LiveBoardEntry[];
  is_realtime: boolean;
}

export interface TransferInfoResponse {
  transfer: TransferStation;
  total_transfer_time_minutes: number;
  message?: string | null;
}
