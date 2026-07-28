import { useState } from "react";
import { TRANSPORT_MODE_COLORS, TRANSPORT_MODE_LABELS, type RouteSegment } from "../types";
import { formatSegmentMinutes, formatTotalDuration } from "../utils/formatDuration";

interface Props {
  segments: RouteSegment[];
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });
}

export function RouteLegBlock({ segments }: Props) {
  const [expanded, setExpanded] = useState(false);
  const first = segments[0];
  const last = segments[segments.length - 1];
  const totalMinutes = segments.reduce((sum, s) => sum + s.duration_minutes, 0);
  const hasIntermediateStops = segments.length > 1;

  return (
    <li className="route-leg">
      <button
        type="button"
        className="route-leg-summary"
        onClick={() => hasIntermediateStops && setExpanded((e) => !e)}
        aria-expanded={hasIntermediateStops ? expanded : undefined}
      >
        <span className="mode-tag" style={{ color: TRANSPORT_MODE_COLORS[first.transport_mode] }}>
          {TRANSPORT_MODE_LABELS[first.transport_mode]}
        </span>
        <span className="leg-direction">往 {last.to_station.name_zh} 方向</span>
        <span className="leg-stations">
          {first.from_station.name_zh} {formatTime(first.departure_time)} → {last.to_station.name_zh}{" "}
          {formatTime(last.arrival_time)}
        </span>
        <span className="duration">{formatTotalDuration(totalMinutes)}</span>
        {hasIntermediateStops && (
          <span className="expand-icon" aria-hidden="true">
            {expanded ? "▲" : "▼"}
          </span>
        )}
      </button>

      {hasIntermediateStops && expanded && (
        <ol className="leg-detail">
          {segments.map((seg) => (
            <li key={seg.segment_id}>
              <span className="trip-id">{seg.trip_id}</span>
              <span>
                {seg.from_station.name_zh} {formatTime(seg.departure_time)} → {seg.to_station.name_zh}{" "}
                {formatTime(seg.arrival_time)}
              </span>
              <span className="duration">{formatSegmentMinutes(seg.duration_minutes)}</span>
            </li>
          ))}
        </ol>
      )}
    </li>
  );
}
