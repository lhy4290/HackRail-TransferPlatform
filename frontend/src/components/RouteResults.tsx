import type { RoutePlanDTO, ServiceAlert } from "../types";
import { isRouteAffectedByAlerts } from "../utils/routeImpact";
import { RouteCard } from "./RouteCard";

interface Props {
  routes: RoutePlanDTO[];
  alerts: ServiceAlert[];
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
  message?: string;
}

export function RouteResults({ routes, alerts, selectedRouteId, onSelectRoute, message }: Props) {
  if (routes.length === 0) {
    return <p className="no-routes">{message ?? "無可用路線"}</p>;
  }

  const sorted = [...routes].sort((a, b) => a.total_time_minutes - b.total_time_minutes);

  return (
    <div className="route-results">
      {sorted.map((route) => (
        <RouteCard
          key={route.route_id}
          route={route}
          isSelected={route.route_id === selectedRouteId}
          onSelect={() => onSelectRoute(route.route_id)}
          isAffectedByAlert={isRouteAffectedByAlerts(route, alerts)}
        />
      ))}
    </div>
  );
}
