import axios from "axios";
import type {
  LiveBoardResponse,
  RouteSearchResponse,
  ServiceAlert,
  StationSuggestion,
  TransferInfoResponse,
} from "../types";

const client = axios.create({ baseURL: "/api", timeout: 10_000 });

export interface RouteSearchParams {
  origin: string;
  destination: string;
  departure_time?: string;
}

export async function searchRoutes(params: RouteSearchParams): Promise<RouteSearchResponse> {
  const { data } = await client.post<RouteSearchResponse>("/routes/search", params);
  return data;
}

export async function suggestStations(query: string, limit = 10): Promise<StationSuggestion[]> {
  const { data } = await client.get<StationSuggestion[]>("/stations/suggest", {
    params: { q: query, limit },
  });
  return data;
}

export async function getAllStations(): Promise<StationSuggestion[]> {
  const { data } = await client.get<StationSuggestion[]>("/stations");
  return data;
}

export async function getLiveboard(stationId: string): Promise<LiveBoardResponse> {
  const { data } = await client.get<LiveBoardResponse>(`/liveboard/${encodeURIComponent(stationId)}`);
  return data;
}

export async function getTransferInfo(transferId: string): Promise<TransferInfoResponse> {
  const { data } = await client.get<TransferInfoResponse>(`/transfers/${encodeURIComponent(transferId)}`);
  return data;
}

export async function getAlerts(transportMode?: string): Promise<ServiceAlert[]> {
  const { data } = await client.get<ServiceAlert[]>("/alerts", {
    params: transportMode ? { transport_mode: transportMode } : {},
  });
  return data;
}

export { client as apiClient };
