# 需求文件

## 簡介

跨運具轉乘資訊整合查詢平台旨在解決目前各運輸系統（捷運、高鐵、臺鐵、航空、渡輪）轉乘資訊分散於不同平台的問題。本平台提供一站式跨運具路線查詢服務，整合各運輸機關即時到離站資訊，自動規劃最佳轉乘路線，並透過歷史延誤資料預測轉乘風險，主動提醒旅客注意高風險路段。

## 術語表

- **Platform（平台）**：跨運具轉乘資訊整合查詢平台之系統整體
- **TDX_API**：交通部運輸資料流通服務平台所提供之公開 API 介面
- **Transfer_Station（轉乘站）**：兩種以上運輸工具可相互轉乘之車站或場站
- **Route_Planner（路線規劃器）**：負責計算跨運具最佳轉乘路線之模組
- **Buffer_Time（緩衝時間）**：旅客於轉乘站步行及等候所需之最低時間
- **Risk_Predictor（風險預測器）**：基於歷史延誤資料預測轉乘準點風險之模組
- **LiveBoard（即時到離站看板）**：各運輸機關提供之即時列車/班次到離站動態資訊
- **Transport_Mode（運具類型）**：包含捷運、高鐵、臺鐵、航空、渡輪等運輸方式
- **User（使用者）**：使用本平台查詢轉乘路線之旅客
- **Data_Adapter（資料轉接器）**：將不同運輸機關之資料格式統一轉換為平台內部格式之元件
- **Cache（快取）**：暫存已取得之 API 資料以減少重複請求並提升回應速度之機制
- **Connection_Risk（轉乘風險）**：特定轉乘組合因時間不足或班次延誤而無法順利銜接之風險等級

## 需求

### 需求 1：跨運具路線查詢

**使用者故事：** 身為一位旅客，我想要輸入起點站與終點站後查詢跨運具轉乘路線，以便一次取得完整的跨運具行程規劃。

#### 驗收條件

1. WHEN User 輸入起點站與終點站，THE Route_Planner SHALL 回傳 1 至 5 條路線，每條路線包含起點站至終點站之所有乘車段、Transfer_Station、各段 Transport_Mode，且至少一條路線包含兩種以上 Transport_Mode 之轉乘
2. WHEN User 輸入起點站與終點站，THE Route_Planner SHALL 於 5 秒內回傳查詢結果
3. THE Route_Planner SHALL 支援以下 Transport_Mode 之任意兩種以上組合進行路線規劃：捷運、高鐵、臺鐵、航空、渡輪
4. WHEN 查詢結果包含多條可行路線，THE Route_Planner SHALL 依總行程時間（含各段乘車時間、Transfer_Station 之 Buffer_Time 及候車時間）由短至長排序呈現
5. THE Route_Planner SHALL 於每條路線中標示各段所使用之 Transport_Mode 與對應車次/班次編號
6. IF 起點站與終點站之間無任何可行跨運具路線，THEN THE Route_Planner SHALL 回傳明確提示訊息告知無可用路線
7. IF User 輸入之起點站或終點站名稱不存在於系統站點資料中，THEN THE Route_Planner SHALL 回傳驗證錯誤訊息指出無法識別之站名

### 需求 2：轉乘站資訊整合

**使用者故事：** 身為一位旅客，我想要查看轉乘站的詳細資訊，以便了解轉乘步行距離與所需時間。

#### 驗收條件

1. THE Platform SHALL 儲存並提供所有 Transfer_Station 之站間步行距離（單位：公尺）與步行時間（單位：分鐘）資料
2. WHEN User 選擇特定轉乘路線，THE Platform SHALL 於 3 秒內顯示各 Transfer_Station 之步行距離（公尺）與預估步行時間（分鐘）
3. THE Platform SHALL 將 Buffer_Time 納入路線規劃之轉乘時間計算中，其中總轉乘時間 = 站間步行時間 + Buffer_Time
4. IF Transfer_Station 之步行時間資料缺失，THEN THE Platform SHALL 使用預設 Buffer_Time（10 分鐘）作為總轉乘時間進行計算，並於該轉乘段標示「使用預設轉乘時間」提示
5. THE Platform SHALL 為每個 Transfer_Station 提供以下資料欄位：起點運具月台/出口名稱、終點運具月台/入口名稱、步行距離（公尺，範圍 1 至 5000）、步行時間（分鐘，範圍 1 至 30）

### 需求 3：即時到離站資訊整合

**使用者故事：** 身為一位旅客，我想要查看即時的列車到離站動態，以便確認轉乘銜接是否充裕。

#### 驗收條件

1. THE Platform SHALL 每 60 秒更新一次各 Transport_Mode 之 LiveBoard 資料
2. WHEN User 查詢路線後，THE Platform SHALL 於 3 秒內顯示各轉乘段之即時預估到站時間，並標示與班表時刻之差異（提前、準點、或延誤分鐘數）
3. WHILE User 瀏覽路線結果頁面，THE Platform SHALL 每 60 秒更新一次 LiveBoard 資訊並重新計算轉乘時間估算
4. IF TDX_API 於 10 秒內未回傳 LiveBoard 資料或回傳錯誤碼，THEN THE Platform SHALL 顯示「即時資訊暫不可用」提示並改用班表時刻資料
5. IF LiveBoard 即時資料更新後顯示轉乘段之銜接時間不足 Buffer_Time，THEN THE Platform SHALL 於該轉乘段標示警示並提示 User 銜接可能不足

### 需求 4：TDX API 資料整合

**使用者故事：** 身為系統開發者，我想要透過統一的資料層存取各運輸機關資料，以便維護資料一致性與擴充性。

#### 驗收條件

1. THE Data_Adapter SHALL 將 TDX_API 回傳之各 Transport_Mode（捷運、高鐵、臺鐵、航空、渡輪）資料中不同機關欄位名稱（如 StationID、STATION_NAME 等）對應轉換為平台統一之內部格式，使相同語意欄位對應至相同內部欄位名稱
2. THE Data_Adapter SHALL 從 TDX_API 擷取、解析並轉換靜態資料（站點、路網、班表）與即時資料（LiveBoard、營運通報）為平台內部格式
3. IF TDX_API 回傳錯誤碼或逾時未回應（超過 10 秒），THEN THE Data_Adapter SHALL 重試最多 2 次（每次間隔 2 秒），若仍失敗則記錄錯誤並回傳包含錯誤類型（逾時或錯誤碼）、發生時間及所呼叫之 API 端點資訊之錯誤訊息
4. THE Cache SHALL 將靜態資料（站點資訊、路網）快取至少 24 小時以減少 API 呼叫次數
5. THE Cache SHALL 將即時資料（LiveBoard）快取不超過 30 秒以確保資料時效性
6. WHEN Cache 中之靜態資料已超過 24 小時，THE Data_Adapter SHALL 自動向 TDX_API 重新擷取該資料並更新 Cache
7. IF 新增一種 Transport_Mode 之 Data_Adapter，THEN THE Data_Adapter SHALL 無須修改既有其他 Transport_Mode 之轉換邏輯即可完成整合

### 需求 5：路線視覺化呈現

**使用者故事：** 身為一位旅客，我想要在地圖上看到轉乘路線，以便直覺地理解行程走向與轉乘位置。

#### 驗收條件

1. WHEN User 選擇一條查詢結果路線，THE Platform SHALL 於 3 秒內在地圖上以視覺可區辨之不同顏色標示各 Transport_Mode 路段，且每種 Transport_Mode 使用固定之專屬顏色，並自動調整地圖縮放範圍以完整顯示整條路線
2. WHEN User 選擇一條查詢結果路線，THE Platform SHALL 於地圖上標示該路線所有 Transfer_Station 之位置圖標
3. WHEN User 點選地圖上之 Transfer_Station 圖標，THE Platform SHALL 於 1 秒內顯示該站之步行時間（分鐘）及未來 3 班次之即時到離站時間與目的地資訊
4. THE Platform SHALL 支援最小寬度 320 像素之行動裝置與桌面瀏覽器之響應式地圖顯示，地圖區域至少佔可視區域高度之 50%
5. IF 路段之地理座標資料無法取得，THEN THE Platform SHALL 以文字清單方式呈現該路段資訊，並顯示提示訊息說明地圖無法顯示該路段
6. IF LiveBoard 資料暫時無法取得，THEN THE Platform SHALL 於 Transfer_Station 資訊面板中顯示「即時班次資訊暫不可用」並改以班表時刻替代

### 需求 6：轉乘風險預測（加值模組）

**使用者故事：** 身為一位旅客，我想要了解特定轉乘組合的準點風險，以便在時間緊迫時選擇更安全的替代路線。

#### 驗收條件

1. WHEN User 查詢路線結果後，THE Risk_Predictor SHALL 於 3 秒內對每個轉乘節點計算 Connection_Risk 等級：「準點」（預測延誤 0–5 分鐘）、「輕微延誤」（預測延誤 6–15 分鐘）、「嚴重延誤」（預測延誤超過 15 分鐘）
2. THE Risk_Predictor SHALL 使用以下特徵進行預測：Transfer_Station、Transport_Mode 組合、時段（尖峰：週一至週五 07:00–09:00 及 17:00–19:00；離峰：其餘時段）、星期幾、歷史平均延誤分鐘數
3. IF Connection_Risk 等級為「嚴重延誤」，THEN THE Platform SHALL 於路線結果頁面中該轉乘節點旁顯示警示標示，並提供至少一條 Connection_Risk 等級非「嚴重延誤」之替代路線
4. THE Risk_Predictor SHALL 以三類別加權平均（weighted F1-score）達到 0.7 以上之預測準確度，評估資料集須包含至少 30 天之歷史延誤紀錄且涵蓋所有已上線之 Transport_Mode
5. IF 歷史延誤資料尚未取得，THEN THE Risk_Predictor SHALL 停用預測功能並於介面上標示「風險預測功能尚未啟用」
6. IF 特定 Transfer_Station 之歷史延誤資料不足 30 天，THEN THE Risk_Predictor SHALL 對該轉乘節點標示「資料不足，風險僅供參考」並以現有資料進行預測

### 需求 7：查詢介面

**使用者故事：** 身為一位旅客，我想要透過簡潔的介面輸入查詢條件，以便快速取得轉乘路線結果。

#### 驗收條件

1. THE Platform SHALL 提供起點站與終點站之搜尋欄位，並支援站名模糊搜尋與自動完成功能
2. WHEN User 輸入部分站名（至少 2 個字元），THE Platform SHALL 於 500 毫秒內顯示最多 10 筆符合之站名建議清單
3. THE Platform SHALL 提供出發時間選擇功能，預設為當前時間，可選範圍為當前時間起 30 天內
4. WHEN User 送出查詢，THE Platform SHALL 顯示載入指示器直到結果回傳或達到 10 秒逾時上限
5. IF 查詢條件不完整（缺少起點或終點），THEN THE Platform SHALL 於對應欄位旁顯示驗證提示訊息，指明該欄位為必填
6. IF User 輸入之站名無任何符合結果，THEN THE Platform SHALL 於建議清單區域顯示「查無符合站名」提示
7. IF User 選擇之起點站與終點站相同，THEN THE Platform SHALL 顯示驗證提示訊息，指明起點與終點不得相同，並阻止送出查詢
8. IF 查詢結果於 10 秒內未回傳，THEN THE Platform SHALL 隱藏載入指示器並顯示逾時提示訊息，允許 User 重新送出查詢

### 需求 8：營運異常通報

**使用者故事：** 身為一位旅客，我想要即時接收營運異常資訊，以便提前調整行程避免受困。

#### 驗收條件

1. WHEN TDX_API 發佈營運通報（列車停駛、延誤超過 5 分鐘、路線異動），THE Platform SHALL 於 2 分鐘內將該通報呈現於包含受影響站點或路段之路線查詢結果中
2. WHILE TDX_API 之營運通報狀態未標示為「已恢復」或「已結束」，THE Platform SHALL 於受影響路線（經過該通報所列站點或路段之路線）旁標示警示圖標
3. WHEN 營運異常導致已查詢路線中任一轉乘節點之預估銜接時間不足 Buffer_Time，THE Platform SHALL 於 30 秒內主動建議 User 至少 1 條不經過受影響路段之替代路線
4. THE Platform SHALL 將營運通報資訊依 Transport_Mode 分類呈現
5. IF 營運異常影響已查詢路線之轉乘可行性且無可用替代路線，THEN THE Platform SHALL 顯示提示訊息告知 User 目前無替代路線可供建議
6. IF TDX_API 營運通報資料無法取得或格式異常，THEN THE Platform SHALL 顯示「營運通報資訊暫不可用」提示並保留最近一次成功取得之通報資料持續顯示，快取保留時間不超過 10 分鐘

### 需求 9：系統效能與可用性

**使用者故事：** 身為系統維運人員，我想要確保平台具備足夠的效能與可用性，以便服務穩定運作。

#### 驗收條件

1. WHILE 同時有 100 位 User 進行路線查詢，THE Platform SHALL 維持每次查詢回應時間於 5 秒以內（第 95 百分位數）
2. THE Platform SHALL 維持每月 99% 以上之服務可用率，其中「可用」定義為健康檢查端點於 10 秒內回應成功
3. IF Platform 與 TDX_API 之連線中斷，THEN THE Platform SHALL 使用 Cache 中之靜態資料（站點資訊、路網、班表）持續提供路線規劃查詢服務，並於查詢結果中標示「即時資訊暫不可用，結果依據快取資料」
4. IF Platform 與 TDX_API 之連線中斷超過 24 小時，THEN THE Platform SHALL 於查詢介面顯示「資料可能已過期」警示
5. THE Platform SHALL 記錄所有對外 API 呼叫（TDX_API）之回應時間與錯誤率，並透過監控端點提供最近 7 日之統計數據供查閱

### 需求 10：資料格式轉換與解析

**使用者故事：** 身為系統開發者，我想要正確解析各種 TDX API 回傳之 JSON 資料格式，以便確保資料轉換無遺漏。

#### 驗收條件

1. THE Data_Adapter SHALL 解析 TDX_API 回傳之 JSON 格式資料為平台內部資料結構，支援以下資料類別：靜態資料（站點資訊、路網結構、班表時刻）與即時資料（LiveBoard 到離站動態、營運通報），涵蓋桃園捷運、臺中捷運、高雄捷運、臺鐵、高鐵等五種 Transport_Mode 之回傳格式
2. THE Data_Adapter SHALL 將平台內部資料結構格式化為 JSON 格式以供前端使用，且單筆資料結構之格式化處理時間不超過 200 毫秒
3. THE Data_Adapter SHALL 確保任何有效之平台內部資料結構（所有必要欄位皆非 null 且型別正確），經格式化為 JSON 再解析回內部資料結構後，所有欄位值與原始物件逐欄位相等（往返特性）
4. IF TDX_API 回傳之 JSON 資料出現以下任一情況：必要欄位缺失、欄位型別與預期不符、或 JSON 語法無效，THEN THE Data_Adapter SHALL 回傳包含錯誤類型與欄位名稱之錯誤訊息，並記錄該筆異常原始 JSON 內容
5. IF TDX_API 回傳之 JSON 資料中僅部分非必要欄位缺失或為 null，THEN THE Data_Adapter SHALL 以預設值填入該欄位並完成解析，同時記錄警告訊息標明所填補之欄位名稱
