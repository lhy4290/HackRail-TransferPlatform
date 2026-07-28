import { describe, expect, it } from "vitest";
import type { RoutePlanDTO, RouteSegment, Station, TransferStation } from "../types";
import { buildRouteTimeline } from "./routeTimeline";

function station(id: string, mode: Station["transport_mode"] = "metro_kaohsiung"): Station {
  return {
    station_id: id,
    original_id: id,
    name_zh: id,
    transport_mode: mode,
    latitude: 22.6,
    longitude: 120.3,
  };
}

function segment(
  id: string,
  from: string,
  to: string,
  mode: Station["transport_mode"] = "metro_kaohsiung",
): RouteSegment {
  return {
    segment_id: id,
    transport_mode: mode,
    trip_id: `trip_${id}`,
    from_station: station(from, mode),
    to_station: station(to, mode),
    departure_time: "2026-01-01T08:00:00",
    arrival_time: "2026-01-01T08:10:00",
    duration_minutes: 10,
  };
}

function transfer(from: string, to: string): TransferStation {
  return {
    transfer_id: `t_${from}_${to}`,
    from_station: station(from),
    to_station: station(to, "thsr"),
    from_platform: "A",
    to_platform: "B",
    walking_distance_m: 200,
    walking_time_min: 5,
    buffer_time_min: 10,
  };
}

function route(segments: RouteSegment[], transfers: TransferStation[] = []): RoutePlanDTO {
  return {
    route_id: "r1",
    segments,
    transfers,
    total_time_minutes: segments.reduce((sum, s) => sum + s.duration_minutes, 0),
    transfer_count: transfers.length,
    transport_modes_used: [...new Set(segments.map((s) => s.transport_mode))],
  };
}

describe("buildRouteTimeline", () => {
  it("merges consecutive same-mode continuous segments into one leg", () => {
    const segments = [segment("1", "A", "B"), segment("2", "B", "C"), segment("3", "C", "D")];
    const timeline = buildRouteTimeline(route(segments));

    expect(timeline).toHaveLength(1);
    expect(timeline[0]).toEqual({ type: "leg", segments });
  });

  it("splits into separate legs with an inline transfer when mode changes", () => {
    const metroSeg = segment("1", "A", "B", "metro_kaohsiung");
    const thsrSeg = segment("2", "B", "C", "thsr");
    const t = transfer("B", "B");
    const timeline = buildRouteTimeline(route([metroSeg, thsrSeg], [t]));

    expect(timeline).toEqual([
      { type: "leg", segments: [metroSeg] },
      { type: "transfer", transfer: t },
      { type: "leg", segments: [thsrSeg] },
    ]);
  });

  it("splits legs without a transfer entry when no matching transfer exists", () => {
    const metroSeg = segment("1", "A", "B", "metro_kaohsiung");
    const thsrSeg = segment("2", "B", "C", "thsr");
    const timeline = buildRouteTimeline(route([metroSeg, thsrSeg], []));

    expect(timeline).toEqual([
      { type: "leg", segments: [metroSeg] },
      { type: "leg", segments: [thsrSeg] },
    ]);
  });

  it("returns a single leg for a single-segment route", () => {
    const seg = segment("1", "A", "B");
    const timeline = buildRouteTimeline(route([seg]));

    expect(timeline).toEqual([{ type: "leg", segments: [seg] }]);
  });

  it("returns an empty timeline for a route with no segments", () => {
    expect(buildRouteTimeline(route([]))).toEqual([]);
  });
});
