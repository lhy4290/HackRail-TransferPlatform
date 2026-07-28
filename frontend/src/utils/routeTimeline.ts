import type { RoutePlanDTO, RouteSegment, TransferStation } from "../types";

export interface RouteLeg {
  type: "leg";
  segments: RouteSegment[];
}

export interface RouteTransferStep {
  type: "transfer";
  transfer: TransferStation;
}

export type RouteTimelineItem = RouteLeg | RouteTransferStep;

function findTransfer(
  transfers: TransferStation[],
  fromStationId: string,
  toStationId: string,
): TransferStation | undefined {
  return transfers.find(
    (t) =>
      (t.from_station.station_id === fromStationId && t.to_station.station_id === toStationId) ||
      (t.to_station.station_id === fromStationId && t.from_station.station_id === toStationId),
  );
}

/**
 * 將路線的逐段 segments 依「同運具且站點連續」合併為可摺疊的區塊（leg），
 * 並在區塊之間插入實際發生的轉乘站資訊，還原成使用者實際體驗的時間軸。
 */
export function buildRouteTimeline(route: RoutePlanDTO): RouteTimelineItem[] {
  if (route.segments.length === 0) return [];

  const timeline: RouteTimelineItem[] = [];
  let currentLeg: RouteSegment[] = [route.segments[0]];

  for (let i = 1; i < route.segments.length; i++) {
    const prev = route.segments[i - 1];
    const curr = route.segments[i];
    const continuous =
      prev.transport_mode === curr.transport_mode &&
      prev.to_station.station_id === curr.from_station.station_id;

    if (continuous) {
      currentLeg.push(curr);
      continue;
    }

    timeline.push({ type: "leg", segments: currentLeg });
    const transfer = findTransfer(route.transfers, prev.to_station.station_id, curr.from_station.station_id);
    if (transfer) {
      timeline.push({ type: "transfer", transfer });
    }
    currentLeg = [curr];
  }

  timeline.push({ type: "leg", segments: currentLeg });
  return timeline;
}
