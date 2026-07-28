import type { RoutePlanDTO, ServiceAlert } from "../types";

const RESOLVED_STATUSES = new Set(["已恢復", "已結束"]);

export function isAlertActive(alert: ServiceAlert): boolean {
  return !RESOLVED_STATUSES.has(alert.status);
}

export function isRouteAffectedByAlerts(route: RoutePlanDTO, alerts: ServiceAlert[]): boolean {
  const stationIds = new Set(route.segments.flatMap((seg) => [seg.from_station.station_id, seg.to_station.station_id]));
  const tripIds = new Set(route.segments.map((seg) => seg.trip_id));

  return alerts.some((alert) => {
    if (!isAlertActive(alert)) return false;
    const stationHit = alert.affected_stations.some((id) => stationIds.has(id));
    const routeHit = alert.affected_routes.some((id) => tripIds.has(id));
    return stationHit || routeHit;
  });
}

export function groupAlertsByMode(alerts: ServiceAlert[]): Record<string, ServiceAlert[]> {
  const groups: Record<string, ServiceAlert[]> = {};
  for (const alert of alerts) {
    groups[alert.transport_mode] = groups[alert.transport_mode] ?? [];
    groups[alert.transport_mode].push(alert);
  }
  return groups;
}
