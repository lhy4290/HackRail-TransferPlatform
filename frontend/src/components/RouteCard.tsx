import { TRANSPORT_MODE_COLORS, TRANSPORT_MODE_LABELS, type RoutePlanDTO } from "../types";
import { formatTotalDuration } from "../utils/formatDuration";
import { buildRouteTimeline } from "../utils/routeTimeline";
import { RouteLegBlock } from "./RouteLegBlock";

interface Props {
  route: RoutePlanDTO;
  isSelected: boolean;
  onSelect: () => void;
  isAffectedByAlert?: boolean;
}

export function RouteCard({ route, isSelected, onSelect, isAffectedByAlert }: Props) {
  const hasSevereDelay = (route.risk_predictions ?? []).some((r) => r.risk_level === "嚴重延誤");
  const timeline = buildRouteTimeline(route);

  return (
    <article className={`route-card${isSelected ? " selected" : ""}`} onClick={onSelect}>
      <header>
        <span className="total-time">{formatTotalDuration(route.total_time_minutes)}</span>
        <span className="transfer-count">轉乘 {route.transfer_count} 次</span>
        {hasSevereDelay && <span className="severe-warning">嚴重延誤警示</span>}
        {isAffectedByAlert && <span className="alert-warning">受營運異常影響</span>}
      </header>

      <div className="mode-badges">
        {route.transport_modes_used.map((mode) => (
          <span key={mode} className="mode-badge" style={{ backgroundColor: TRANSPORT_MODE_COLORS[mode] }}>
            {TRANSPORT_MODE_LABELS[mode]}
          </span>
        ))}
      </div>

      <ol className="segments">
        {timeline.map((item) =>
          item.type === "leg" ? (
            <RouteLegBlock key={item.segments[0].segment_id} segments={item.segments} />
          ) : (
            <li key={item.transfer.transfer_id} className="transfer-info">
              <strong>
                {item.transfer.from_station.name_zh} → {item.transfer.to_station.name_zh}
              </strong>
              <span>
                步行 {item.transfer.walking_distance_m} 公尺 / {item.transfer.walking_time_min ?? 10} 分鐘
              </span>
              {item.transfer.walking_time_min === null && (
                <span className="default-time-hint">使用預設轉乘時間</span>
              )}
            </li>
          ),
        )}
      </ol>

      {(route.risk_predictions ?? []).length > 0 && (
        <div className="risk-predictions">
          {route.risk_predictions!.map((r) => (
            <span
              key={r.transfer_id}
              className={`risk-badge risk-${r.risk_level === "嚴重延誤" ? "severe" : r.risk_level === "輕微延誤" ? "minor" : "ontime"}`}
            >
              {r.risk_level}
              {!r.data_sufficient && r.message ? `（${r.message}）` : ""}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
