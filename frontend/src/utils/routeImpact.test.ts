import { describe, expect, it } from "vitest";
import type { RoutePlanDTO, ServiceAlert, Station } from "../types";
import { groupAlertsByMode, isRouteAffectedByAlerts } from "./routeImpact";

function station(id: string): Station {
  return {
    station_id: id,
    original_id: id,
    name_zh: id,
    transport_mode: "tra",
    latitude: 25,
    longitude: 121,
  };
}

function route(fromId: string, toId: string, tripId = "TRIP1"): RoutePlanDTO {
  return {
    route_id: "r1",
    segments: [
      {
        segment_id: "s1",
        transport_mode: "tra",
        trip_id: tripId,
        from_station: station(fromId),
        to_station: station(toId),
        departure_time: "2026-01-01T00:00:00Z",
        arrival_time: "2026-01-01T00:30:00Z",
        duration_minutes: 30,
      },
    ],
    transfers: [],
    total_time_minutes: 30,
    transfer_count: 0,
    transport_modes_used: ["tra"],
  };
}

function alert(status: string, affectedStations: string[] = []): ServiceAlert {
  return {
    alert_id: "a1",
    transport_mode: "tra",
    title: "測試通報",
    description: "",
    severity: "延誤",
    affected_stations: affectedStations,
    affected_routes: [],
    start_time: "2026-01-01T00:00:00Z",
    status,
    source: "TDX",
  };
}

describe("isRouteAffectedByAlerts", () => {
  it("marks route affected only when an active alert overlaps its stations", () => {
    const r = route("A", "B");
    expect(isRouteAffectedByAlerts(r, [alert("進行中", ["A"])])).toBe(true);
    expect(isRouteAffectedByAlerts(r, [alert("已恢復", ["A"])])).toBe(false);
    expect(isRouteAffectedByAlerts(r, [alert("進行中", ["Z"])])).toBe(false);
  });
});

describe("groupAlertsByMode", () => {
  it("groups alerts so every entry in a group shares the same transport_mode", () => {
    const alerts = [alert("進行中", ["A"]), alert("已結束", ["B"])];
    const groups = groupAlertsByMode(alerts);
    for (const [mode, group] of Object.entries(groups)) {
      expect(group.every((a) => a.transport_mode === mode)).toBe(true);
    }
  });
});
