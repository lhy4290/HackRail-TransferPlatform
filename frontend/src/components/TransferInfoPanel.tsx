import { useEffect, useState } from "react";
import { getLiveboard } from "../services/api";
import type { LiveBoardEntry, TransferStation } from "../types";

interface Props {
  transfer: TransferStation;
  onClose: () => void;
}

export function TransferInfoPanel({ transfer, onClose }: Props) {
  const [entries, setEntries] = useState<LiveBoardEntry[]>([]);
  const [isRealtime, setIsRealtime] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setLoaded(false);
    getLiveboard(transfer.to_station.station_id)
      .then((res) => {
        setEntries(res.entries.slice(0, 3));
        setIsRealtime(res.is_realtime);
        setLoaded(true);
      })
      .catch(() => {
        setEntries([]);
        setIsRealtime(false);
        setLoaded(true);
      });
  }, [transfer.to_station.station_id]);

  return (
    <div className="transfer-info-panel" role="dialog" aria-label="轉乘站資訊">
      <button type="button" className="close-button" onClick={onClose} aria-label="關閉">
        ×
      </button>
      <h3>
        {transfer.from_station.name_zh} → {transfer.to_station.name_zh}
      </h3>
      <p>步行時間：{transfer.walking_time_min ?? 10} 分鐘</p>
      {loaded && !isRealtime && <p className="realtime-unavailable">即時班次資訊暫不可用，以下為班表時刻</p>}
      {loaded && entries.length === 0 && <p>暫無班次資訊</p>}
      <ul>
        {entries.map((e) => (
          <li key={e.trip_id}>
            {e.trip_id} → {e.destination}（{e.status}
            {e.delay_minutes !== 0 ? ` ${Math.abs(e.delay_minutes)} 分鐘` : ""}）
          </li>
        ))}
      </ul>
    </div>
  );
}
