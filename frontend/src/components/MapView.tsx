import L from "leaflet";
import "leaflet/dist/leaflet.css";
import icon from "leaflet/dist/images/marker-icon.png";
import iconShadow from "leaflet/dist/images/marker-shadow.png";
import { useEffect, useState } from "react";
import { MapContainer, Marker, Polyline, TileLayer, useMap } from "react-leaflet";
import { TRANSPORT_MODE_COLORS, type RoutePlanDTO, type Station, type TransferStation } from "../types";
import { TransferInfoPanel } from "./TransferInfoPanel";

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

function hasValidCoords(station: Station): boolean {
  return (
    Number.isFinite(station.latitude) &&
    Number.isFinite(station.longitude) &&
    !(station.latitude === 0 && station.longitude === 0)
  );
}

function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length > 0) {
      map.fitBounds(positions, { padding: [30, 30] });
    }
  }, [positions, map]);
  return null;
}

interface Props {
  route: RoutePlanDTO | null;
}

export function MapView({ route }: Props) {
  const [selectedTransfer, setSelectedTransfer] = useState<TransferStation | null>(null);

  useEffect(() => {
    setSelectedTransfer(null);
  }, [route?.route_id]);

  if (!route) return null;

  const validSegments = route.segments.filter(
    (seg) => hasValidCoords(seg.from_station) && hasValidCoords(seg.to_station),
  );
  const invalidSegments = route.segments.filter((seg) => !validSegments.includes(seg));

  const positions: [number, number][] = validSegments.flatMap((seg) => [
    [seg.from_station.latitude, seg.from_station.longitude],
    [seg.to_station.latitude, seg.to_station.longitude],
  ]);

  if (positions.length === 0) {
    return <TextRouteList route={route} message="地圖無法顯示此路線（座標資料無法取得），以文字清單呈現：" />;
  }

  return (
    <div className="map-view-container">
      <MapContainer center={positions[0]} zoom={12} className="map-container">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <FitBounds positions={positions} />
        {validSegments.map((seg) => (
          <Polyline
            key={seg.segment_id}
            positions={[
              [seg.from_station.latitude, seg.from_station.longitude],
              [seg.to_station.latitude, seg.to_station.longitude],
            ]}
            pathOptions={{ color: TRANSPORT_MODE_COLORS[seg.transport_mode], weight: 5 }}
          />
        ))}
        {route.transfers.map((transfer) => (
          <Marker
            key={transfer.transfer_id}
            position={[transfer.to_station.latitude, transfer.to_station.longitude]}
            eventHandlers={{ click: () => setSelectedTransfer(transfer) }}
          />
        ))}
      </MapContainer>

      {invalidSegments.length > 0 && (
        <TextRouteList
          route={{ ...route, segments: invalidSegments }}
          message="以下路段座標資料無法取得，以文字清單呈現："
        />
      )}

      {selectedTransfer && <TransferInfoPanel transfer={selectedTransfer} onClose={() => setSelectedTransfer(null)} />}
    </div>
  );
}

function TextRouteList({ route, message }: { route: RoutePlanDTO; message: string }) {
  return (
    <div className="text-route-list">
      <p>{message}</p>
      <ol>
        {route.segments.map((seg) => (
          <li key={seg.segment_id}>
            {seg.from_station.name_zh} → {seg.to_station.name_zh}（{seg.trip_id}）
          </li>
        ))}
      </ol>
    </div>
  );
}
