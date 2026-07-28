-- 站點資料表
CREATE TABLE IF NOT EXISTS stations (
    station_id TEXT PRIMARY KEY,
    original_id TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    name_en TEXT,
    transport_mode TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 轉乘站資料表
CREATE TABLE IF NOT EXISTS transfer_stations (
    transfer_id TEXT PRIMARY KEY,
    from_station_id TEXT NOT NULL REFERENCES stations(station_id),
    to_station_id TEXT NOT NULL REFERENCES stations(station_id),
    from_platform TEXT NOT NULL,
    to_platform TEXT NOT NULL,
    walking_distance_m INTEGER NOT NULL CHECK (walking_distance_m BETWEEN 1 AND 5000),
    walking_time_min INTEGER CHECK (walking_time_min BETWEEN 1 AND 30),
    buffer_time_min INTEGER DEFAULT 10,
    UNIQUE(from_station_id, to_station_id)
);

-- 路網邊（圖的邊）
CREATE TABLE IF NOT EXISTS network_edges (
    edge_id TEXT PRIMARY KEY,
    from_station_id TEXT NOT NULL REFERENCES stations(station_id),
    to_station_id TEXT NOT NULL REFERENCES stations(station_id),
    transport_mode TEXT NOT NULL,
    route_name TEXT,
    base_travel_time_min INTEGER NOT NULL
);

-- 歷史延誤紀錄
CREATE TABLE IF NOT EXISTS delay_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL REFERENCES stations(station_id),
    transport_mode TEXT NOT NULL,
    trip_id TEXT,
    scheduled_time TIMESTAMP NOT NULL,
    actual_time TIMESTAMP,
    delay_minutes INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    is_peak_hour BOOLEAN NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API 呼叫監控紀錄
CREATE TABLE IF NOT EXISTS api_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL,
    response_time_ms INTEGER NOT NULL,
    status_code INTEGER NOT NULL,
    error_message TEXT,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 營運通報快取
CREATE TABLE IF NOT EXISTS service_alerts_cache (
    alert_id TEXT PRIMARY KEY,
    transport_mode TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    severity TEXT NOT NULL,
    affected_stations TEXT NOT NULL,  -- JSON array
    affected_routes TEXT NOT NULL,    -- JSON array
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status TEXT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 建立索引
CREATE INDEX IF NOT EXISTS idx_stations_transport_mode ON stations(transport_mode);
CREATE INDEX IF NOT EXISTS idx_stations_name_zh ON stations(name_zh);
CREATE INDEX IF NOT EXISTS idx_delay_history_station ON delay_history(station_id, transport_mode);
CREATE INDEX IF NOT EXISTS idx_delay_history_time ON delay_history(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_network_edges_from ON network_edges(from_station_id);
CREATE INDEX IF NOT EXISTS idx_api_logs_time ON api_call_logs(called_at);
