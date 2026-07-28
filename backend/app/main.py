import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import alerts, health, liveboard, metrics, routes, stations, transfers
from app.api.dependencies import build_app_state_from_tdx, build_demo_app_state, build_empty_app_state
from app.api.error_handler import register_error_handlers
from app.config import load_tdx_credentials
from app.models.enums import CachePolicy
from app.services.demo_snapshot import DEMO_SNAPSHOT_PATH
from app.services.sync_scheduler import SyncScheduler

logger = logging.getLogger(__name__)


def _build_fallback_state():
    """無真實 TDX 憑證，或憑證擷取失敗時之退回狀態：優先使用 Demo 快照（若存在），
    否則以空狀態啟動（見 build_empty_app_state 文件）。"""
    if DEMO_SNAPSHOT_PATH.exists():
        logger.info("使用 Demo 快照啟動（%s）", DEMO_SNAPSHOT_PATH)
        return build_demo_app_state()
    return build_empty_app_state()


@asynccontextmanager
async def lifespan(app: FastAPI):
    credentials = load_tdx_credentials()
    if credentials is not None:
        try:
            state = await build_app_state_from_tdx(credentials.client_id, credentials.client_secret)
        except Exception:
            logger.exception("TDX 資料匯入失敗，改以 Demo 快照或空狀態啟動")
            state = _build_fallback_state()
    else:
        state = _build_fallback_state()

    await state.db.init_schema()
    await state.cache.set("network_graph_loaded_at", True, CachePolicy.STATIC)
    app.state.platform = state

    scheduler = SyncScheduler(alert_manager=state.alert_manager, cache=state.cache)
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    await scheduler.stop()


app = FastAPI(title="跨運具轉乘查詢平台 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(routes.router)
app.include_router(stations.router)
app.include_router(liveboard.router)
app.include_router(transfers.router)
app.include_router(alerts.router)
app.include_router(health.router)
app.include_router(metrics.router)

# 前端打包後的靜態檔案（由部署流程之 Dockerfile 於 build 階段複製進來，見 repo 根目錄
# Dockerfile）。本機開發時通常不存在此目錄（改用 `npm run dev` 的 Vite dev server），
# 故僅於實際存在時掛載，避免本機開發環境因找不到目錄而啟動失敗。所有 API 路徑皆以
# 明確的 /api/... 前綴宣告（見各 app/api/*.py），故掛載於根目錄不會與 API 路由衝突。
_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="frontend")
