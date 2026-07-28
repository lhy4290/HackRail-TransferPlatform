import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RouteSegment, Station } from "../types";
import { RouteLegBlock } from "./RouteLegBlock";

function station(id: string, name: string): Station {
  return {
    station_id: id,
    original_id: id,
    name_zh: name,
    transport_mode: "metro_kaohsiung",
    latitude: 22.6,
    longitude: 120.3,
  };
}

function segment(id: string, fromName: string, toName: string): RouteSegment {
  return {
    segment_id: id,
    transport_mode: "metro_kaohsiung",
    trip_id: `trip_${id}`,
    from_station: station(`S_${fromName}`, fromName),
    to_station: station(`S_${toName}`, toName),
    departure_time: "2026-01-01T08:00:00",
    arrival_time: "2026-01-01T08:10:00",
    duration_minutes: 5,
  };
}

describe("RouteLegBlock", () => {
  it("shows only the first and last station names when collapsed, with direction and total time", () => {
    const segments = [segment("1", "A", "B"), segment("2", "B", "C"), segment("3", "C", "D")];
    render(<RouteLegBlock segments={segments} />);

    expect(screen.getByText("往 D 方向")).toBeInTheDocument();
    expect(screen.getByText(/A.*→.*D/)).toBeInTheDocument();
    expect(screen.getByText("15分鐘")).toBeInTheDocument();
    expect(screen.queryByText("B")).not.toBeInTheDocument();
    expect(screen.queryByText("C")).not.toBeInTheDocument();
    expect(screen.queryByText(/trip_2/)).not.toBeInTheDocument();
  });

  it("reveals intermediate stops when the summary is clicked", () => {
    const segments = [segment("1", "A", "B"), segment("2", "B", "C")];
    render(<RouteLegBlock segments={segments} />);

    fireEvent.click(screen.getByRole("button"));

    expect(screen.getByText("trip_1")).toBeInTheDocument();
    expect(screen.getByText("trip_2")).toBeInTheDocument();
  });

  it("does not show an expand toggle for a single-segment leg", () => {
    render(<RouteLegBlock segments={[segment("1", "A", "B")]} />);

    expect(screen.queryByText("▼")).not.toBeInTheDocument();
  });
});
