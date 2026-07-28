import { useState } from "react";
import { TRANSPORT_MODE_LABELS } from "../types";
import type { ServiceAlert, TransportMode } from "../types";
import { groupAlertsByMode, isAlertActive } from "../utils/routeImpact";

interface Props {
  alerts: ServiceAlert[];
  relevantModes: TransportMode[];
  isUnavailable?: boolean;
}

export function AlertBanner({ alerts, relevantModes, isUnavailable }: Props) {
  const [detailAlert, setDetailAlert] = useState<ServiceAlert | null>(null);

  if (isUnavailable) {
    return <p className="alert-unavailable">營運通報資訊暫不可用</p>;
  }

  const relevantSet = new Set(relevantModes);
  const groups = groupAlertsByMode(alerts.filter((a) => relevantSet.has(a.transport_mode)));

  if (Object.keys(groups).length === 0) {
    return null;
  }

  return (
    <div className="alert-banner">
      {Object.entries(groups).map(([mode, modeAlerts]) => (
        <div key={mode} className="alert-group">
          <h4>{TRANSPORT_MODE_LABELS[mode as keyof typeof TRANSPORT_MODE_LABELS] ?? mode}</h4>
          <ul>
            {modeAlerts.map((alert) => (
              <li key={alert.alert_id} className={isAlertActive(alert) ? "active" : "resolved"}>
                <button type="button" className="alert-title-link" onClick={() => setDetailAlert(alert)}>
                  {alert.title}
                </button>
                <span className="alert-status"> ({alert.status})</span>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {detailAlert && (
        <div className="alert-detail-overlay" role="presentation" onClick={() => setDetailAlert(null)}>
          <div
            className="alert-detail-panel"
            role="dialog"
            aria-label="通報詳情"
            onClick={(e) => e.stopPropagation()}
          >
            <button type="button" className="close-button" onClick={() => setDetailAlert(null)} aria-label="關閉">
              ×
            </button>
            <h3>{detailAlert.title}</h3>
            <p className="alert-detail-meta">
              {TRANSPORT_MODE_LABELS[detailAlert.transport_mode]} · {detailAlert.status}
            </p>
            {detailAlert.description && <p className="alert-detail-description">{detailAlert.description}</p>}
          </div>
        </div>
      )}
    </div>
  );
}
