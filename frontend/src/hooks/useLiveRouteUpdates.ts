import { useEffect, useState } from "react";
import { getLiveboard } from "../services/api";
import type { LiveBoardEntry, RoutePlanDTO } from "../types";

const POLL_INTERVAL_MS = 60_000;

export interface ConnectionWarning {
  transferId: string;
  insufficient: boolean;
}

/**
 * 每 60 秒輪詢路線各轉乘站之即時到離站資料，重新計算銜接時間是否仍充足。
 */
export function useLiveRouteUpdates(route: RoutePlanDTO | null) {
  const [liveboardByStation, setLiveboardByStation] = useState<Record<string, LiveBoardEntry[]>>({});
  const [warnings, setWarnings] = useState<ConnectionWarning[]>([]);

  useEffect(() => {
    if (!route) {
      setLiveboardByStation({});
      setWarnings([]);
      return;
    }

    let cancelled = false;

    async function poll() {
      const stationIds = Array.from(
        new Set(route!.transfers.flatMap((t) => [t.from_station.station_id, t.to_station.station_id])),
      );

      const results = await Promise.all(
        stationIds.map(async (id) => {
          try {
            const res = await getLiveboard(id);
            return [id, res.entries] as const;
          } catch {
            return [id, [] as LiveBoardEntry[]] as const;
          }
        }),
      );
      if (cancelled) return;

      const byStation: Record<string, LiveBoardEntry[]> = Object.fromEntries(results);
      setLiveboardByStation(byStation);

      const nextWarnings: ConnectionWarning[] = route!.transfers.map((t) => {
        const arrivals = byStation[t.from_station.station_id] ?? [];
        const departures = byStation[t.to_station.station_id] ?? [];
        const arrival = arrivals[0]?.estimated_arrival ?? arrivals[0]?.scheduled_arrival;
        const nextDeparture = departures[0]?.estimated_departure ?? departures[0]?.scheduled_departure;

        if (!arrival || !nextDeparture) {
          return { transferId: t.transfer_id, insufficient: false };
        }

        const availableMinutes = (new Date(nextDeparture).getTime() - new Date(arrival).getTime()) / 60_000;
        const requiredMinutes = (t.walking_time_min ?? 10) + t.buffer_time_min;
        return { transferId: t.transfer_id, insufficient: availableMinutes < requiredMinutes };
      });
      setWarnings(nextWarnings);
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [route]);

  return { liveboardByStation, warnings };
}
