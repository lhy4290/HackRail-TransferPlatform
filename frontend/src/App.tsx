import { useEffect, useRef, useState } from "react";
import "./App.css";
import { AlertBanner } from "./components/AlertBanner";
import { MapView } from "./components/MapView";
import { RouteResults } from "./components/RouteResults";
import { SearchForm } from "./components/SearchForm";
import { useLiveRouteUpdates } from "./hooks/useLiveRouteUpdates";
import { searchRoutes, type RouteSearchParams } from "./services/api";
import type { RouteSearchResponse } from "./types";
import { isRouteAffectedByAlerts } from "./utils/routeImpact";

function App() {
  const [result, setResult] = useState<RouteSearchResponse | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [lastParams, setLastParams] = useState<RouteSearchParams | null>(null);
  const suggestedForRouteId = useRef<string | null>(null);

  function handleResults(response: RouteSearchResponse, params: RouteSearchParams) {
    setResult(response);
    setSelectedRouteId(response.routes[0]?.route_id ?? null);
    setLastParams(params);
    suggestedForRouteId.current = null;
  }

  const selectedRoute = result?.routes.find((r) => r.route_id === selectedRouteId) ?? null;
  const { warnings } = useLiveRouteUpdates(selectedRoute);

  // 營運異常導致銜接不足時，主動建議替代路線（需求 3.5, 8.3）
  useEffect(() => {
    if (!result || !selectedRoute || !lastParams) return;
    if (suggestedForRouteId.current === selectedRoute.route_id) return;

    const hasInsufficientConnection = warnings.some((w) => w.insufficient);
    const affectedByAlert = isRouteAffectedByAlerts(selectedRoute, result.alerts);

    if (hasInsufficientConnection && affectedByAlert) {
      suggestedForRouteId.current = selectedRoute.route_id;
      searchRoutes(lastParams).then((fresh) => {
        setResult(fresh);
        setSelectedRouteId(fresh.routes[0]?.route_id ?? null);
      });
    }
  }, [warnings, result, selectedRoute, lastParams]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>跨運具轉乘資訊整合查詢平台</h1>
        <span className="tagline">
          <span className="live-dot" aria-hidden="true" />
          即時路網 · 高鐵 · 台鐵 · 捷運
        </span>
      </header>
      <SearchForm onResults={handleResults} />

      {result && result.data_possibly_outdated && <p className="stale-warning">資料可能已過期</p>}

      {result && (
        <>
          <AlertBanner alerts={result.alerts} relevantModes={selectedRoute?.transport_modes_used ?? []} />
          <MapView route={selectedRoute} />
          <RouteResults
            routes={result.routes}
            alerts={result.alerts}
            selectedRouteId={selectedRouteId}
            onSelectRoute={setSelectedRouteId}
            message={result.message}
          />
        </>
      )}
    </div>
  );
}

export default App;
