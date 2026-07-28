# 單一容器同時提供 API 與前端靜態檔案（同一網域，前端 /api 相對路徑呼叫無需額外設定）。
# 部署平台（如 Render）偵測到本檔案即會以 Docker 方式建置，無需另外設定 build/start command。

FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS backend
WORKDIR /app/backend
COPY backend/ ./
RUN pip install --no-cache-dir .
COPY --from=frontend-build /app/frontend/dist ./app/static

# 未設定 TDX_CLIENT_ID/TDX_CLIENT_SECRET 環境變數時，main.py 會自動改用
# app/demo_data/snapshot.json 之 Demo 快照啟動，無需任何憑證即可運作。
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
