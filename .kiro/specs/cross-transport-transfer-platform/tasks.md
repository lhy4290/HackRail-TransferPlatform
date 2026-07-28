# 實作計畫：跨運具轉乘資訊整合查詢平台

## 概述

本實作計畫將跨運具轉乘資訊整合查詢平台之設計拆解為可執行的編碼任務。採用分層建構策略：先建立資料層與核心介面，再實作整合層與應用邏輯，最後完成前端表現層與整合測試。後端使用 Python FastAPI，前端使用 React + TypeScript，地圖使用 Leaflet.js。

## 任務

- [ ] 1. 建立專案結構與核心資料模型
  - [ ] 1.1 初始化後端專案結構與依賴套件
    - 建立 Python 專案目錄結構（`backend/`）含 `app/`, `app/models/`, `app/adapters/`, `app/services/`, `app/api/`, `app/cache/`, `tests/`
    - 建立 `pyproject.toml` 或 `requirements.txt`，安裝 FastAPI, uvicorn, pydantic, httpx, aiosqlite, hypothesis, pytest, pytest-asyncio
    - 建立 FastAPI 主應用程式進入點 `app/main.py`
    - _需求: 4.1, 9.2_

  - [ ] 1.2 定義核心資料模型與列舉型別
    - 實作 `app/models/enums.py`：TransportMode, ConnectionRiskLevel, CachePolicy, ErrorType 列舉
    - 實作 `app/models/station.py`：Station Pydantic 模型
    - 實作 `app/models/transfer.py`：TransferStation Pydantic 模型（含欄位驗證 walking_distance_m 1-5000, walking_time_min 1-30）
    - 實作 `app/models/timetable.py`：TimetableEntry, LiveBoardEntry 模型
    - 實作 `app/models/route.py`：RouteSegment, RoutePlanDTO 模型
    - 實作 `app/models/risk.py`：RiskPredictionDTO 模型
    - 實作 `app/models/alert.py`：ServiceAlert 模型
    - 實作 `app/models/errors.py`：PlatformError 資料類別
    - _需求: 2.5, 10.1, 10.3_

  - [ ]* 1.3 撰寫資料模型屬性測試
    - **Property 6: 轉乘站資料欄位驗證** — 驗證 TransferStation 之 walking_distance_m (1-5000) 與 walking_time_min (1-30) 欄位約束
    - **Property 19: JSON 序列化往返特性** — 驗證所有核心模型經 JSON 序列化再反序列化後欄位相等
    - **驗證: 需求 2.5, 10.3**

  - [ ] 1.4 建立資料庫 Schema 與初始化腳本
    - 實作 `app/db/schema.sql`：包含 stations, transfer_stations, network_edges, delay_history, api_call_logs, service_alerts_cache 資料表
    - 實作 `app/db/database.py`：SQLite 連線管理與 Schema 初始化函式
    - 建立索引以優化查詢效能
    - _需求: 2.1, 6.2, 9.5_

- [ ] 2. 實作整合層：TDX 客戶端與快取管理
  - [ ] 2.1 實作 TDX API 客戶端
    - 實作 `app/adapters/tdx_client.py`：TDXClient 類別
    - 實作 OAuth 認證流程（取得/刷新 access token）
    - 實作 HTTP 請求方法，含 10 秒逾時、最多 2 次重試（間隔 2 秒）邏輯
    - 失敗時記錄錯誤（含錯誤類型、時間、端點資訊）
    - _需求: 4.3, 4.7_

  - [ ]* 2.2 撰寫 TDX 客戶端重試行為屬性測試
    - **Property 10: API 重試行為** — 驗證重試次數不超過 2 次、間隔為 2 秒、失敗時錯誤訊息包含正確資訊
    - **驗證: 需求 4.3**

  - [ ] 2.3 實作快取管理器
    - 實作 `app/cache/cache_manager.py`：CacheManager 類別
    - 實作記憶體快取後端（原型用）
    - 支援三種快取策略：STATIC (24 小時 TTL)、REALTIME (30 秒 TTL)、ALERT (10 分鐘 TTL)
    - 實作 get/set/invalidate 方法與 TTL 過期檢查
    - _需求: 4.4, 4.5, 4.6_

  - [ ] 2.4 實作資料轉接器基底類別與各運具轉接器
    - 實作 `app/adapters/base_adapter.py`：BaseTransportAdapter 抽象基底類別
    - 實作 `app/adapters/metro_adapter.py`：MetroAdapter（桃園/臺中/高雄捷運，以 system_id 區分）
    - 實作 `app/adapters/tra_adapter.py`：TRAAdapter（臺鐵）
    - 實作 `app/adapters/thsr_adapter.py`：THSRAdapter（高鐵）
    - 各轉接器負責將 TDX 原始 JSON 欄位名稱對應轉換為平台統一內部格式
    - _需求: 4.1, 4.2, 4.7, 10.1_

  - [ ]* 2.5 撰寫資料轉接器屬性測試與單元測試
    - **Property 9: TDX 資料格式統一化** — 驗證不同 Transport_Mode 之 TDX 回傳經轉換後符合統一 schema
    - **Property 20: 無效 JSON 錯誤報告** — 驗證無效 JSON 輸入（欄位缺失/型別錯誤/語法無效）回傳正確錯誤訊息
    - **Property 21: 非必要欄位預設值填補** — 驗證非必要欄位缺失時以預設值填入且記錄警告
    - **驗證: 需求 4.1, 10.1, 10.4, 10.5**

- [ ] 3. 檢查點 — 確認整合層測試通過
  - 確認所有測試通過，若有問題請詢問使用者。

- [ ] 4. 實作應用邏輯層：路線規劃引擎
  - [ ] 4.1 建構交通路網圖模型
    - 實作 `app/services/transport_graph.py`：GraphNode, GraphEdge, TransportGraph 類別
    - 實作從資料庫載入站點與路網邊建構圖結構之方法
    - 實作加入轉乘邊（跨運具步行轉乘）之方法
    - _需求: 1.3, 2.1, 2.3_

  - [ ] 4.2 實作路線規劃器核心演算法
    - 實作 `app/services/route_planner.py`：RoutePlanner 類別
    - 實作 Time-Dependent Dijkstra 演算法，支援時變邊權重
    - 轉乘成本計算：步行時間 + buffer_time + 候車時間
    - 回傳 1 至 5 條路線，依總行程時間排序
    - 確保至少一條路線包含兩種以上 Transport_Mode
    - 處理無可行路線情境（回傳明確提示）
    - _需求: 1.1, 1.2, 1.3, 1.4, 1.6_

  - [ ]* 4.3 撰寫路線規劃器屬性測試
    - **Property 1: 路線結構與多運具約束** — 驗證回傳路線數 1-5 條，segments 涵蓋起點至終點，至少一條含兩種以上 Transport_Mode
    - **Property 2: 路線排序不變式** — 驗證路線結果依 total_time_minutes 升序排列
    - **Property 3: 路段資訊完整性** — 驗證每個 RouteSegment 之 transport_mode 有效且 trip_id 非空
    - **Property 4: 無效站名驗證** — 驗證不存在站名輸入回傳驗證錯誤
    - **驗證: 需求 1.1, 1.4, 1.5, 1.7**

  - [ ] 4.4 實作轉乘時間計算邏輯
    - 實作 `app/services/transfer_calculator.py`：轉乘時間計算函式
    - 總轉乘時間 = walking_time_min + buffer_time_min
    - 若 walking_time_min 缺失，使用預設 10 分鐘並標示「使用預設轉乘時間」
    - _需求: 2.3, 2.4_

  - [ ]* 4.5 撰寫轉乘時間計算屬性測試
    - **Property 5: 轉乘時間計算** — 驗證有值時為 walking_time_min + buffer_time_min，缺失時使用預設 10 分鐘且標示提示
    - **驗證: 需求 2.3, 2.4**

  - [ ] 4.6 實作即時到離站服務
    - 實作 `app/services/liveboard_service.py`：LiveBoardService 類別
    - 從各運具轉接器取得即時資料，快取 30 秒
    - 計算延誤分鐘數與狀態（提前/準點/延誤）
    - TDX API 不可用時改用班表資料並顯示提示
    - _需求: 3.1, 3.2, 3.4_

  - [ ]* 4.7 撰寫延誤狀態計算屬性測試
    - **Property 7: 延誤狀態計算** — 驗證 delay_minutes 正確計算且 status 正確對應（提前/準點/延誤）
    - **Property 8: 銜接不足警示** — 驗證可用銜接時間 < buffer_time_min 時標示警示
    - **驗證: 需求 3.2, 3.5**

- [ ] 5. 實作應用邏輯層：風險預測與營運通報
  - [ ] 5.1 實作風險預測器
    - 實作 `app/services/risk_predictor.py`：RiskPredictor 類別
    - 實作風險等級分類邏輯：0-5 分鐘→準點、6-15 分鐘→輕微延誤、>15 分鐘→嚴重延誤
    - 特徵向量：transfer_station_id, transport_mode_pair, time_period (尖峰/離峰), day_of_week, historical_avg_delay
    - 尖峰時段判定：週一至五 07:00-09:00 及 17:00-19:00
    - 歷史資料不足（<30 天）時標示 data_sufficient=false 及「資料不足，風險僅供參考」
    - 無歷史資料時停用預測功能並顯示「風險預測功能尚未啟用」
    - _需求: 6.1, 6.2, 6.4, 6.5, 6.6_

  - [ ]* 5.2 撰寫風險預測器屬性測試
    - **Property 11: 風險等級分類** — 驗證延誤分鐘數正確對應三種風險等級
    - **Property 13: 歷史資料不足警示** — 驗證資料天數 <30 天時 data_sufficient=false 且 message 正確
    - **驗證: 需求 6.1, 6.6**

  - [ ] 5.3 實作嚴重延誤替代路線建議
    - 擴充 RoutePlanner，當路線中有「嚴重延誤」轉乘節點時提供替代路線
    - 替代路線之所有轉乘節點之 Connection_Risk 均非「嚴重延誤」
    - _需求: 6.3_

  - [ ]* 5.4 撰寫替代路線屬性測試
    - **Property 12: 嚴重延誤替代路線** — 驗證存在嚴重延誤時至少提供一條無嚴重延誤之替代路線
    - **驗證: 需求 6.3**

  - [ ] 5.5 實作營運通報管理器
    - 實作 `app/services/alert_manager.py`：AlertManager 類別
    - 整合各運具轉接器之營運通報資料
    - 通報依 Transport_Mode 分類
    - 檢查路線是否受營運異常影響
    - 營運異常導致銜接不足時建議替代路線
    - 通報資料取得失敗時保留最近成功資料（≤10 分鐘）
    - _需求: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 5.6 撰寫營運通報屬性測試
    - **Property 17: 進行中通報警示** — 驗證 status 為「進行中」之通報影響路線標示警示
    - **Property 18: 通報依運具分類** — 驗證分類後各群組內通報之 transport_mode 相同
    - **驗證: 需求 8.2, 8.4**

- [ ] 6. 檢查點 — 確認應用邏輯層測試通過
  - 確認所有測試通過，若有問題請詢問使用者。

- [ ] 7. 實作 REST API 端點
  - [ ] 7.1 實作路線查詢 API 端點
    - 實作 `app/api/routes.py`：POST `/api/routes/search` 端點
    - 請求驗證：起點/終點不得為空、不得相同、站名須存在系統中
    - 回應含路線清單、風險標註、營運通報
    - 回應時間 5 秒上限，逾時回傳逾時提示
    - 標示是否使用快取資料
    - _需求: 1.1, 1.2, 1.6, 1.7, 7.5, 7.7, 7.8_

  - [ ]* 7.2 撰寫路線查詢 API 驗證屬性測試
    - **Property 15: 查詢欄位驗證** — 驗證缺少起點或終點時回傳驗證錯誤
    - **Property 16: 起終點相同驗證** — 驗證起終點相同時回傳驗證錯誤並阻止查詢
    - **驗證: 需求 7.5, 7.7**

  - [ ] 7.3 實作站名自動完成 API 端點
    - 實作 `app/api/stations.py`：GET `/api/stations/suggest` 端點
    - 至少 2 字元觸發搜尋，回傳最多 10 筆結果
    - 支援模糊搜尋（站名包含輸入字串）
    - 回應時間 < 500 毫秒
    - 無匹配結果時回傳空列表
    - _需求: 7.1, 7.2, 7.6_

  - [ ]* 7.4 撰寫站名自動完成屬性測試
    - **Property 14: 自動完成結果約束** — 驗證 ≥2 字元輸入回傳 ≤10 筆結果且站名包含輸入字串
    - **驗證: 需求 7.2**

  - [ ] 7.5 實作即時到離站與轉乘站資訊 API 端點
    - 實作 `app/api/liveboard.py`：GET `/api/liveboard/{station_id}` 端點
    - 實作 `app/api/transfers.py`：GET `/api/transfers/{transfer_id}` 端點
    - 轉乘站資訊含步行距離、步行時間、起終點月台名稱
    - _需求: 2.2, 2.5, 3.2_

  - [ ] 7.6 實作營運通報與系統監控 API 端點
    - 實作 `app/api/alerts.py`：GET `/api/alerts` 端點，支援依 transport_mode 篩選
    - 實作 `app/api/health.py`：GET `/api/health` 健康檢查端點（10 秒內回應）
    - 實作 `app/api/metrics.py`：GET `/api/metrics` 監控端點（最近 7 日統計）
    - _需求: 8.4, 9.2, 9.5_

  - [ ] 7.7 實作全域錯誤處理與降級策略
    - 實作 `app/api/error_handler.py`：全域例外處理器
    - TDX API 不可用時使用快取資料並標示「即時資訊暫不可用」
    - 連線中斷超過 24 小時標示「資料可能已過期」
    - 統一錯誤回應格式（PlatformError）
    - _需求: 3.4, 9.3, 9.4_

- [ ] 8. 檢查點 — 確認後端 API 端點測試通過
  - 確認所有測試通過，若有問題請詢問使用者。

- [ ] 9. 實作前端：查詢介面與路線結果
  - [ ] 9.1 初始化前端專案結構
    - 建立 React + TypeScript 專案（`frontend/`），使用 Vite 建置工具
    - 安裝依賴：react, react-dom, typescript, leaflet, react-leaflet, axios
    - 建立目錄結構：`src/components/`, `src/services/`, `src/types/`, `src/hooks/`
    - 定義 TypeScript 型別對應後端 DTO（Station, RoutePlanDTO, RiskPredictionDTO, ServiceAlert）
    - _需求: 5.4, 7.1_

  - [ ] 9.2 實作查詢表單元件
    - 實作起點/終點站搜尋欄位元件，含自動完成功能
    - 至少 2 字元觸發自動完成，500 毫秒內顯示建議
    - 無匹配時顯示「查無符合站名」
    - 實作出發時間選擇功能（預設當前時間，可選 30 天內）
    - 實作表單驗證：起點/終點必填、不得相同
    - 送出查詢時顯示載入指示器，10 秒逾時顯示逾時提示
    - _需求: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [ ] 9.3 實作路線結果列表元件
    - 顯示 1-5 條路線，每條含所有乘車段、轉乘站、各段 Transport_Mode 與車次編號
    - 依總行程時間排序呈現
    - 顯示各轉乘站步行距離與步行時間
    - 顯示即時到離站時間及與班表差異（提前/準點/延誤 N 分鐘）
    - 顯示風險等級標示（準點/輕微延誤/嚴重延誤），嚴重延誤顯示警示
    - 無可行路線時顯示「無可用路線」
    - _需求: 1.1, 1.4, 1.5, 1.6, 2.2, 3.2, 6.1, 6.3_

  - [ ] 9.4 實作營運通報顯示元件
    - 受影響路線旁標示警示圖標
    - 通報依 Transport_Mode 分類呈現
    - 進行中通報持續顯示直到狀態變為「已恢復」或「已結束」
    - 即時資訊不可用時顯示對應提示
    - _需求: 8.1, 8.2, 8.4, 8.5, 8.6_

- [ ] 10. 實作前端：地圖視覺化
  - [ ] 10.1 實作 Leaflet 地圖路線視覺化元件
    - 整合 Leaflet.js 地圖元件
    - 各 Transport_Mode 使用固定專屬顏色標示路段
    - 自動調整地圖縮放範圍完整顯示整條路線
    - 標示所有轉乘站位置圖標
    - 響應式設計：支援最小寬度 320px，地圖佔可視區域高度 50% 以上
    - _需求: 5.1, 5.2, 5.4_

  - [ ] 10.2 實作轉乘站資訊面板
    - 點選轉乘站圖標後 1 秒內顯示資訊面板
    - 面板內容：步行時間（分鐘）、未來 3 班次即時到離站時間與目的地
    - LiveBoard 不可用時顯示「即時班次資訊暫不可用」並以班表替代
    - 座標資料無法取得之路段以文字清單呈現並顯示提示
    - _需求: 5.3, 5.5, 5.6_

- [ ] 11. 實作即時資料輪詢與動態更新
  - [ ] 11.1 實作前端即時資料輪詢機制
    - 每 60 秒向後端輪詢 LiveBoard 資料
    - 更新路線結果頁面之即時到離站資訊
    - 重新計算轉乘時間估算
    - 銜接時間不足 Buffer_Time 時顯示警示
    - 營運異常導致銜接不足時主動建議替代路線（30 秒內）
    - _需求: 3.1, 3.3, 3.5, 8.3_

  - [ ] 11.2 實作後端定期資料同步排程
    - 靜態資料超過 24 小時自動重新擷取
    - API 呼叫紀錄（回應時間、錯誤率）寫入 api_call_logs
    - 營運通報 2 分鐘內反映至查詢結果
    - _需求: 4.6, 8.1, 9.5_

- [ ] 12. 檢查點 — 確認前後端整合測試通過
  - 確認所有測試通過，若有問題請詢問使用者。

- [ ] 13. 端對端整合與最終驗證
  - [ ] 13.1 前後端整合串接
    - 確認所有 API 端點與前端元件正確串接
    - 設定 CORS 允許前端存取
    - 確認錯誤狀態正確傳遞與顯示
    - 確認快取降級策略正確運作
    - _需求: 9.3, 9.4_

  - [ ]* 13.2 撰寫後端整合測試
    - 測試端對端路線查詢流程（API 請求 → 路線結果）
    - 測試 TDX API 逾時時的降級行為
    - 測試營運通報影響路線查詢結果
    - 測試 100 並發查詢 P95 < 5 秒（負載測試）
    - _需求: 9.1, 9.3_

- [ ] 14. 最終檢查點 — 確認所有測試通過
  - 確認所有測試通過，若有問題請詢問使用者。

## 備註

- 標記 `*` 之任務為選用任務，可於快速 MVP 時跳過
- 每項任務均參照具體需求以確保可追溯性
- 檢查點確保漸進式驗證
- 屬性測試（Property-Based Tests）使用 Hypothesis 框架驗證通用正確性屬性
- 單元測試驗證特定範例與邊界條件
- 後端使用 Python FastAPI + SQLite（原型階段）
- 前端使用 React + TypeScript + Leaflet.js
- 所有屬性測試最低迭代次數為 100 次

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.4"] },
    { "id": 2, "tasks": ["1.3", "2.1", "2.3"] },
    { "id": 3, "tasks": ["2.2", "2.4"] },
    { "id": 4, "tasks": ["2.5", "4.1"] },
    { "id": 5, "tasks": ["4.2", "4.4", "4.6"] },
    { "id": 6, "tasks": ["4.3", "4.5", "4.7", "5.1"] },
    { "id": 7, "tasks": ["5.2", "5.3", "5.5"] },
    { "id": 8, "tasks": ["5.4", "5.6", "7.1", "7.3"] },
    { "id": 9, "tasks": ["7.2", "7.4", "7.5", "7.6", "7.7"] },
    { "id": 10, "tasks": ["9.1"] },
    { "id": 11, "tasks": ["9.2", "9.3", "9.4"] },
    { "id": 12, "tasks": ["10.1", "10.2"] },
    { "id": 13, "tasks": ["11.1", "11.2"] },
    { "id": 14, "tasks": ["13.1"] },
    { "id": 15, "tasks": ["13.2"] }
  ]
}
```
