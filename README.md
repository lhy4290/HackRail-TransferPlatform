# HackRail 轉乘通 — Cross-Transport Transfer Platform

A cross-transport transfer information platform built for the HackRail hackathon, unifying Taiwan's fragmented rail systems — Metro (Taoyuan/Taichung/Kaohsiung), TRA, and THSR — into a single trip-planning experience. Enter an origin and destination, and the platform integrates real-time arrival/departure data across operators, automatically plans the best multi-modal transfer route, and predicts transfer risk from historical delay data so travelers know which connections to worry about.

## Features

- **Cross-transport route search** — Time-Dependent Dijkstra plus a custom Yen's k-shortest-paths implementation returns 1–5 routes within 5 seconds, sorted by total trip time, guaranteeing at least one route spans 2+ transport modes.
- **Transfer station details** — walking distance and time between connecting platforms, with buffer time factored into total transfer time (defaults applied with a visible notice when data is missing).
- **Live arrival/departure board** — polls each operator's live board every 60s, showing early/on-time/delayed status versus scheduled times, and flags connections where the buffer time is at risk.
- **Transfer risk prediction** — classifies each connection as On-Time / Minor Delay / Severe Delay based on station, transport-mode combination, and peak/off-peak timing, and surfaces a low-risk alternative route when a connection is flagged severe.
- **Route map visualization** — Leaflet.js map with distinct colors per transport mode and transfer station markers, responsive across devices.
- **Service alert integration** — surfaces TDX operational alerts on affected routes and proactively suggests alternatives when an alert threatens a connection.

## Architecture

Four-layer design: **Data → Integration → Application Logic → Presentation**


Adding a new transport mode only requires a new adapter subclass + `FieldSpec` — no changes to existing adapter logic.

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- (Optional) TDX API credentials — [register here](https://tdx.transportdata.tw/) — only needed for live data; see **Demo Mode** below to run without any credentials.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Optional: enable live TDX data
# create backend/.env with:
#   TDX_CLIENT_ID=your_client_id
#   TDX_CLIENT_SECRET=your_client_secret

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
