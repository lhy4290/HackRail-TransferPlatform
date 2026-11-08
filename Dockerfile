# 單一容器同時提供 API 與前端靜態檔案（同一網域，前端 /api 相對路徑呼叫無需額外設定）。
# 部署於 AWS ECS Fargate（見 infra/），本機測試：docker build -t hackrail . && docker run -p 8000:8000 hackrail

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

# 以非 root 使用者執行；SQLite 會寫到 /app/backend/data，所以把目錄交給這個使用者
RUN useradd --create-home --uid 10001 app && chown -R app:app /app/backend
USER app

# 未設定 TDX_CLIENT_ID/TDX_CLIENT_SECRET 環境變數時，main.py 會自動改用
# app/demo_data/snapshot.json 之 Demo 快照啟動，無需任何憑證即可運作。
EXPOSE 8000
# exec 讓 uvicorn 成為 PID 1，ECS 停 Task 時送的 SIGTERM 才會傳到 uvicorn，能正常關閉
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
