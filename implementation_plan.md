# Implementation Plan：14–17 章雙寫改版（爬蟲同時寫 MySQL＋BigQuery）

> 2026-08-04 規劃定稿。實作在新 session 進行（本規劃 session context 已低）。
> 執行前先讀本檔＋task.md；手冊為唯一事實來源，全部改動照課程規矩：實測後才寫進教材、禁用詞掃描、教材規範（直述、環境數值不進內文）。

## 目標（Dex 決策，2026-08-03/04 討論定案）

把 14–17 章的資料路線從「爬蟲寫 MySQL → 批次同步到 BigQuery」改為：

**爬蟲每次抓取，同時寫兩份**——MySQL（14/15 章＝VM 容器 → 16 章起＝Cloud SQL）＋ BigQuery raw 層。Airflow 排程時走同一條雙寫路。

範圍認知：**14 章微調、15–17 章大改**。

## 已定案的六個決策

| # | 決策 | 內容 |
|---|------|------|
| D1 | 雙寫方式 | **不用旗標**。一支程式寫兩邊；14 章就開始跑（不細講），15 章才詳細介紹。本機（1–13 章）相容：沒設 `GCP_PROJECT_ID` 就**明確印一行**「BQ 未設定，略過雲端寫入」繼續跑（明確降級，不是靜默 fallback） |
| D2 | 憑證 | VM **建機時就給 `--scopes=cloud-platform`**（14 章 F 段建 VM 指令加參數），容器用 VM 附掛身分寫 BQ、不放金鑰進容器。**金鑰教學保留**、場景化：「程式在 GCP 外面（本機爬蟲/backfill）才需要金鑰」——14 章一次對照講清楚兩種憑證 |
| D3 | 同步程式 | `stock_sync_mysql_to_bigquery.py` 退出教學主線（不講）。實際定位為 backfill 工具，repo 保留 |
| D4 | 17 章 DAG | 每日排程照跑，內容變為：**觸發爬蟲（雙寫當日新資料）＋ transform task（重算 stage/app）**。消失的只有「把 MySQL 整批複製到 BQ」的搬運 task（資料寫入當下已在 BQ） |
| D5 | BQ 亮點教學 | 15 章補「資料倉儲非它不可」的功能教學（見下方清單），主線四個＋補充若干 |
| D6 | Spanner | **開 90 天免費試用 instance 動手教**＋與 Cloud SQL 比較、要看得出亮點；另加 Cloud SQL vs BigQuery 兩層對照（15 章概念級、16 章營運級）與 GCP 資料庫選型光譜表 |

## 程式改動（實作前先讀實際程式碼，schema-aware）

1. **worker 儲存路徑雙寫**：現有 MySQL 寫入（upsert）之後，加 BigQuery append（batch load，沿用 `crawler/bigquery.py` 的 `upload_data_to_bigquery`，mode="append"，dataset=raw）。
   - 沒設 `GCP_PROJECT_ID` → 印「BQ 未設定，略過雲端寫入」，MySQL 照寫
   - BQ 寫入失敗（網路/權限）→ 印明確錯誤，不擋 MySQL（爬蟲主職不因分析副本失敗而死）
   - 落點：先讀 `crawler/worker.py`／存檔函式所在檔，確認實際結構再動
2. **`crawler/bigquery.py`**：`BQ_DATASET` 機制已在（預設 stock）。雙寫落 raw——決定：worker 內寫死 raw 或沿用環境變數（傾向 worker 明確傳 `dataset_id="raw"`，不依賴 env）
3. **compose 檔**：worker 的 environment 加 `GCP_PROJECT_ID`（雲端 override 給值；本機 compose 不給 → 自動略過 BQ）。`docker-compose-all.yml` 與 `docker-compose-local.yml`、`gcp-worker-override.yml` 一致性檢查
4. **容器內憑證**：VM 容器經 metadata server 用 VM 身分——**需實測容器內是否直通**（Docker 容器可存取 metadata server，預期可；實測確認）
5. **17 章 DAG**：`stock_crawler_etl_bigquery_dag` 改造——移除 sync task、加 transform task 維護 stage/app（Step 3/4 的 SQL 包成函式）；producer DAG 不動

## BQ 亮點教學清單（D5，15 章）

主線四個：
1. **公開資料集震撼查詢**：查 `bigquery-public-data`（數十億筆秒回）——「MySQL 做不到」開場
2. **掃描量預估（dry run）**：執行前右上角顯示會掃多少——計費模式具象化＋省錢
3. **Time Travel**：`FOR SYSTEM_TIME AS OF` 現場誤刪救回
4. **BQML**：`CREATE MODEL` 一句 SQL 對股價跑線性回歸——倉儲內建 ML

補充：Materialized View（對照手動 CTAS）、Scheduled Queries（對照 Airflow）、INFORMATION_SCHEMA 查成本。全部要在 BQ 實跑、輸出進教材。

## Spanner 節（D6，位置：16 章教完 Cloud SQL 後）

- 開 90 天免費試用 instance（不扣款）；**動手前先讀官方限制文件**（free trial 的功能/區域/PU 限制），列 checklist 再動
- 動手內容候選（以試用版實測可行為準）：建 instance → GoogleSQL 建表插查 → **不停機調整運算單元**（對照 Cloud SQL 改機型要重啟）→ schema 變更不鎖表 → interleaved table
- 對照表：Cloud SQL vs Spanner（擴展方式/一致性/維護時段/連線模型/價格量級/適用場景）
- 收工：試用 instance 刪除（90 天後會開始計費，教材要寫清楚）

## 各章改動計畫

### 14 章（微調）
- F 段建 VM 指令加 `--scopes=cloud-platform`＋一段「VM 身分」說明；**新增「兩種憑證對照」小節**（金鑰=GCP 外、VM 身分=GCP 內；D2）
- H 段：compose up 後雙寫已發生——加一句「BQ 那份 15 章才講，先知道有寫」；H-4 驗證加第 8 步（BQ raw 有資料，一條 bq query）
- 17 章 T-1 的 scopes 段落簡化（建機就給了，只剩「舊 VM 補改」場景）
- H-1b（uv）已完成不動

### 15 章（大改）
- 敘事重排：雙寫詳解（worker 程式碼逐段讀）→ OLTP vs OLAP＋**Cloud SQL vs BQ 概念對照**（同一筆資料的兩個命運）→ BQ 亮點四連發 → 三層（raw 已由爬蟲餵，Step 3/4 stage/app 照現版）→ Looker（現版 Step 5 保留）
- 移除：同步程式主線段（D3）、金鑰主線教學（改引用 14 章對照；本機補充保留金鑰用法）
- backfill 一句話帶過（「開雙寫前的歷史資料用 repo 內工具搬，不在課程範圍」）

### 16 章（大改）
- 搬家敘事不變（MySQL→Cloud SQL），但雙寫讓「三個值」變「兩個值＋雙寫照舊」——Part E override 重寫
- 新增 **Cloud SQL vs BQ 營運級對照**（連線/授權/停機模式差異）
- 新增 **Spanner 動手節**＋**GCP 資料庫選型光譜表**（Cloud SQL/Spanner/BQ/Firestore/Bigtable）
- B-4 部署時注入等既有內容保留

### 17 章（大改）
- DAG 改造（D4）：每日線＝producer 觸發雙寫＋transform 維護層；資料線圖重畫
- T-1 scopes 段改寫（對應 14 章建機即給）
- Composer 段照舊

## 實測要求（每項都要在 GCP 真跑）

1. 本機（無 GCP_PROJECT_ID）跑 worker：MySQL 寫入正常＋明確略過訊息
2. VM 容器雙寫：MySQL＋raw 同時落地；scopes 憑證直通確認
3. BQ 亮點四個 demo 全實跑、輸出截取
4. Spanner 試用 instance 全流程（含刪除）
5. 17 章 DAG 端到端：排程觸發 → 雙寫 → transform → app 更新
6. 全章禁用詞掃描、圖片引用檢查

## 風險與注意

- **量最大是 15/16 章敘事重寫**——分次 commit（每章一個 section 一 commit）
- 舊截圖（ch15/01-03、13-14 等）數字/畫面與新流程不完全一致——截圖是範例可先留，重拍列後續
- 投影片（EP12/17/18/20）全部落後——**本輪不動**，完成手冊後另開投影片批次
- Spanner 免費試用條款可能已變——動手前必查官方文件
- 手冊18（機密管理）已刪除於前次改版，引用連動要掃
- context 管理：實作 session 從本檔＋task.md 開工，不需重讀本次討論歷史

## 不做的事

- 不做旗標系統（D1）
- 不教 streaming insert（維持 batch load，免費）
- 不把金鑰塞進容器（D2）
- 同步程式不刪除、不教學（D3）
- 投影片本輪不動
