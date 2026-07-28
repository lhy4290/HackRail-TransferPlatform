import { useEffect, useState } from "react";
import { getAllStations } from "../services/api";
import { TRANSPORT_MODE_LABELS, type StationSuggestion, type TransportMode } from "../types";

interface Props {
  label: string;
  onChange: (stationId: string | null) => void;
  errorMessage?: string;
}

type LoadState = "loading" | "error" | "ready";

export function StationModeSelect({ label, onChange, errorMessage }: Props) {
  const [stations, setStations] = useState<StationSuggestion[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [mode, setMode] = useState<TransportMode | "">("");
  const [stationId, setStationId] = useState("");

  useEffect(() => {
    let cancelled = false;
    getAllStations()
      .then((result) => {
        if (cancelled) return;
        setStations(result);
        setLoadState("ready");
      })
      .catch(() => {
        if (!cancelled) setLoadState("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const availableModes = Array.from(new Set(stations.map((s) => s.transport_mode)));
  const stationsForMode = stations
    .filter((s) => s.transport_mode === mode)
    .sort((a, b) => a.name_zh.localeCompare(b.name_zh, "zh-Hant"));

  function handleModeChange(nextMode: TransportMode | "") {
    setMode(nextMode);
    setStationId("");
    onChange(null);
  }

  function handleStationChange(nextStationId: string) {
    setStationId(nextStationId);
    onChange(nextStationId || null);
  }

  const modePlaceholder =
    loadState === "loading" ? "載入運具中..." : loadState === "error" ? "載入失敗" : "選擇運具";

  return (
    <div className="station-mode-select">
      <span className="field-label">{label}</span>
      <div className="mode-station-row">
        <select
          aria-label={`${label}運具`}
          value={mode}
          disabled={loadState !== "ready"}
          onChange={(e) => handleModeChange(e.target.value as TransportMode | "")}
        >
          <option value="">{modePlaceholder}</option>
          {availableModes.map((m) => (
            <option key={m} value={m}>
              {TRANSPORT_MODE_LABELS[m]}
            </option>
          ))}
        </select>
        <select
          aria-label={`${label}站名`}
          value={stationId}
          disabled={!mode}
          onChange={(e) => handleStationChange(e.target.value)}
        >
          <option value="">{mode ? "選擇站名" : "請先選擇運具"}</option>
          {stationsForMode.map((s) => (
            <option key={s.station_id} value={s.station_id}>
              {s.name_zh}
              {s.name_en ? ` (${s.name_en})` : ""}
            </option>
          ))}
        </select>
      </div>
      {loadState === "error" && (
        <p className="field-error">站點資料載入失敗，請確認後端服務是否已啟動</p>
      )}
      {loadState === "ready" && availableModes.length === 0 && (
        <p className="field-error">目前尚無可用站點資料</p>
      )}
      {errorMessage && <p className="field-error">{errorMessage}</p>}
    </div>
  );
}
