# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

The full stack described by the Kiro spec is implemented: `backend/` (Python/FastAPI) and `frontend/` (React/TypeScript/Vite). All 14 top-level tasks in `tasks.md` are done and checked off. The spec docs at `.kiro/specs/cross-transport-transfer-platform/` remain the source of truth for *why* the code is shaped the way it is — consult them before changing behavior, not just the code.

**Known simplifications** (intentional, not bugs to "fix"):
- `RiskPredictor` (`app/services/risk_predictor.py`) uses a documented heuristic (peak/off-peak historical average delay) instead of a trained scikit-learn/XGBoost model, since no historical delay dataset exists to train one. The interface matches what design.md specifies, so a real model can be swapped in later without touching callers.
- TRA/THSR `get_alerts()` (`app/adapters/tra_adapter.py` / `thsr_adapter.py`) still call an unconfirmed `/AlertInfo` endpoint that currently 404s live; only Metro alerts (`/v2/Rail/Metro/Alert/{system}`) are confirmed working against real TDX.

### Live TDX vs. Demo mode

Real TDX credentials work: `app/api/dependencies.build_app_state_from_tdx()` wires the 5 real adapters (`MetroAdapter("TYMC"/"KRTC"/"TMRT")`, `TRAAdapter`, `THSRAdapter`) against live endpoints and is used automatically by `main.py`'s lifespan whenever `backend/.env` has `TDX_CLIENT_ID`/`TDX_CLIENT_SECRET` set. Station schema is identical across all three operators in reality (`StationID`, `StationName.Zh_tw/En`, `StationPosition.PositionLon/PositionLat`); the differing per-adapter `FieldSpec` conventions described below exist to exercise the Adapter Pattern, not because real TDX payloads differ. Note the "臺/台" character variant is genuinely inconsistent across operators in real data (THSR uses "台北"/"台中"; TRA and Metro Taichung use "臺北"/"臺中") — station-name matching (e.g. `transfer_seed.py`) must use the exact variant each operator actually returns.

Because the competition submission won't ship real TDX credentials, there's a third boot path — **Demo mode** — for judges to run locally with zero credentials and zero live API calls:
- `scripts/capture_demo_snapshot.py` is a one-off, manually-run script (needs real credentials in `backend/.env`) that captures a full real snapshot (all stations/edges from all 5 adapters, for correct route-planning connectivity, plus any live alerts) into `app/demo_data/snapshot.json`, along with a curated whitelist of ~20 station IDs (`CURATED_STATION_NAMES` in that script) picked to showcase all 3 real cross-modal transfer hubs (左營/新左營/左營-KRTC, 台中/新烏日/高鐵臺中站, 桃園/高鐵桃園站). Re-run it to refresh the snapshot before a demo.
- `app/api/dependencies.build_demo_app_state()` loads that snapshot with no network calls at all, and is used automatically by `main.py`'s lifespan whenever `TDX_CLIENT_ID`/`TDX_CLIENT_SECRET` are absent (the case when the repo is submitted without `.env`) — this is `AppState.visible_station_ids`, which `GET /api/stations` filters by so the frontend dropdown only ever offers the curated whitelist, while the underlying graph keeps full connectivity so any combination among them resolves a real route.
- Kaohsiung MRT's Red/Orange interchange (美麗島, R10/O5) isn't in the curated whitelist: the graph has no same-mode line-interchange edges for stations sharing one physical building under two different line codes, so it's unreachable from the rest of the curated set — a genuine gap, not specific to demo mode.

## Commands

### Backend (`backend/`, Python 3.11+, venv at `backend/.venv`)

```powershell
# from backend/
.\.venv\Scripts\python.exe -m pytest tests/ -q          # run all tests
.\.venv\Scripts\python.exe -m pytest tests/test_route_planner.py -q   # single file
.\.venv\Scripts\python.exe -m pytest tests/test_route_planner.py::test_invalid_station_name_raises_validation_error -q  # single test
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000   # run dev server
```
Dependencies are declared in `pyproject.toml` (runtime deps + `[project.optional-dependencies].dev` for pytest/pytest-asyncio/hypothesis); install with `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`. `pytest-asyncio` runs in `asyncio_mode = "auto"` (see `pyproject.toml`), so async test functions don't need an explicit marker.

### Frontend (`frontend/`, Vite + React + TS)

```bash
npm install        # from frontend/
npm run dev        # dev server; /api proxied to http://localhost:8000 (see vite.config.ts)
npm run test       # vitest run (all tests)
npx vitest run src/components/SearchForm.test.tsx   # single file
npm run build      # tsc -b && vite build — treat tsc errors as build failures
```

## Architecture

Four-layer design per `design.md`, implemented as:

```
frontend/src/               React SPA (Vite)
  components/                SearchForm, RouteResults, RouteCard, AlertBanner, MapView, TransferInfoPanel
  hooks/                      useLiveRouteUpdates (60s polling)
  services/api.ts             typed axios client, mirrors backend DTOs in types/index.ts

backend/app/
  models/                     Pydantic DTOs + enums (Station, TransferStation, RoutePlanDTO, RiskPredictionDTO, ServiceAlert, PlatformError, ...)
  adapters/                   TDXClient (OAuth + retry) + BaseTransportAdapter + MetroAdapter/TRAAdapter/THSRAdapter
  cache/cache_manager.py      CachePolicy-keyed TTL cache (STATIC/REALTIME/ALERT)
  services/                   TransportGraph, RoutePlanner, RiskPredictor, AlertManager, LiveBoardService, transfer_calculator, SyncScheduler
  api/                        FastAPI routers (routes, stations, liveboard, transfers, alerts, health, metrics) + dependencies.AppState + error_handler.py
  db/                         schema.sql + Database (aiosqlite)
  main.py                     wires AppState + SyncScheduler into FastAPI's lifespan
```

Key implementation details worth knowing before changing this code:

- **`AppState`** (`app/api/dependencies.py`) is the single object holding every service instance for a request; routers read it via `request.app.state.platform`. Tests build their own seeded `AppState` (see `tests/conftest.py::seeded_state`) and assign it to `app.state.platform` *after* entering the `TestClient` context manager, because entering the context re-runs `lifespan` and would otherwise overwrite it with an empty state.
- **Adapter Pattern**: `BaseTransportAdapter._map_record()` (in `app/adapters/base_adapter.py`) is the one place that turns a raw TDX JSON dict into internal fields, driven by a per-adapter `FieldSpec` list. In real TDX data all three operators actually share the same station schema (see "Live TDX vs. Demo mode" above) — the per-adapter `FieldSpec` split still matters for `get_routes()`/`get_alerts()`, whose real endpoints and payload shapes genuinely differ per operator (`S2STravelTime` vs. `StationOfLine`-derived edges; Metro's `Alert` envelope vs. TRA/THSR's still-unconfirmed `AlertInfo`). Adding a new transport mode means adding a new adapter subclass with its own `FieldSpec`s, never editing `base_adapter.py` or existing adapters.
- **Route planning** (`app/services/route_planner.py`) is Time-Dependent Dijkstra plus a from-scratch Yen's k-shortest-paths implementation (`_k_shortest_paths`). `plan_routes()` guarantees 1–5 routes sorted ascending by `total_time_minutes`, with at least one route using 2+ transport modes (backfilled via `_best_multi_modal_path` if the top-K search didn't surface one). `ensure_non_severe_alternative()` is a separate step (called from the `/api/routes/search` handler) that takes an injected `risk_fn` callable so `RoutePlanner` never depends on `RiskPredictor` directly.
- **Cache TTLs are the enforcement mechanism**, not a side detail: e.g. `AlertManager.get_active_alerts()` relies on `CacheManager`'s `ALERT` policy (10 min TTL) to satisfy "keep showing last known alerts for up to 10 minutes on TDX failure" — there's no separate stale-read code path, so don't add one.
- **TDX client retry contract** (`app/adapters/tdx_client.py`) is exact and property-tested: 10s timeout, max 2 retries, 2s between retries, and every attempt (success or failure) is reported through an optional `log_fn` hook for `api_call_logs` — `SyncScheduler` and adapters wire this up when a real `Database` is available.
- **JSON round-trip is a hard invariant** (Property 19): any valid Pydantic model must satisfy `Model.model_validate_json(m.model_dump_json()) == m`. Keep this in mind before adding custom validators/serializers.
- Response-time budgets from `requirements.md` are enforced in code, not just documented: e.g. `/api/routes/search` wraps `plan_routes()` in `asyncio.wait_for(..., timeout=5.0)` (`app/api/routes.py`), autocomplete's 500ms/≤10-results budget is enforced by `Query(..., min_length=2)` + slicing in `app/api/stations.py`.

## Testing strategy

Dual-track per `design.md`: pytest for unit/integration tests, **Hypothesis** for the 21 numbered correctness properties. Every property test is tagged with a comment `# Feature: cross-transport-transfer-platform, Property {N}: {property_text}` and runs `@settings(max_examples=100)` (a few graph-search-heavy tests use fewer examples with `deadline=None` — see `tests/test_risk_predictor.py`). `tests/strategies.py` and `tests/fakes.py` hold shared Hypothesis strategies and fake TDX clients/adapters reused across test files.

Frontend tests use Vitest + `@testing-library/react`; `src/setupTests.ts` wires in `@testing-library/jest-dom`.

When adding a feature that maps to a numbered Property in `design.md`, write the Hypothesis test first (or alongside) rather than only example-based asserts — that's the existing convention throughout `backend/tests/`.

`tests/test_integration_e2e.py` covers true end-to-end flows (API request → full route + risk + alerts, TDX-timeout degradation, alert-impacted route search, and a 100-concurrent-request P95 smoke test using `httpx.ASGITransport`). A real production load test would use Locust against a deployed instance, per `design.md` — the in-repo test is a fast correctness smoke test, not a substitute.
