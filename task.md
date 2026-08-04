# Task List：14–17 章雙寫改版

> 搭配 implementation_plan.md。順序執行；每個 Phase 結束 commit 一次＋更新本檔勾選。
> 反饋循環：每段程式改動都要跑起來驗證；教材段落寫完做重現性通讀＋禁用詞掃描。

## Phase 0：前置盤點（新 session 開工第一件事）
- [x] 讀 implementation_plan.md 全文
- [x] 讀 `crawler/worker.py` 與存檔路徑實際程式碼（schema-aware，確認函式與欄位）
- [x] 讀 `crawler/bigquery.py` 現況（BQ_DATASET 機制已在）
- [x] `gcloud config get-value account` 確認是 dexdeclass06
- [x] 查 Spanner 90 天免費試用官方文件，列限制 checklist（區域/PU/功能）

## Phase 1：雙寫程式碼＋本機驗證
- [x] worker 存檔路徑加 BQ append（dataset 明確傳 "raw"；無 GCP_PROJECT_ID 印「BQ 未設定，略過雲端寫入」；BQ 失敗不擋 MySQL）
- [x] compose 三檔 environment 一致性（本機不給 GCP_PROJECT_ID、雲端 override 給）
- [x] 本機（Lima）跑 worker：MySQL 正常寫入＋略過訊息出現
- [x] commit

## Phase 2：VM 雙寫實測
- [x] VM 重建或 set-service-account 補 `cloud-platform` scopes（新建法：`--scopes=cloud-platform`）
- [x] VM 容器內 metadata server 憑證直通確認
- [x] producer 發任務 → worker 雙寫 → MySQL＋`raw.TaiwanStockPrice` 同時新增（bq query 前後筆數）
- [x] commit

## Phase 3：手冊14 微調
- [x] F 段建 VM 加 `--scopes=cloud-platform`＋ VM 身分說明
- [x] 新增「兩種憑證對照」小節（金鑰=GCP 外／VM 身分=GCP 內）
- [x] H 段補雙寫預告一句＋ H-4 加第 8 步 BQ 驗證
- [x] 禁用詞掃描；commit＋push

## Phase 4：手冊15 大改
- [x] 敘事重排：雙寫詳解（讀 worker 程式碼）→ OLTP/OLAP＋Cloud SQL vs BQ 概念對照表 → 三層（Step 3/4 沿用）
- [x] BQ 亮點主線四個實跑＋寫入：公開資料集震撼查詢／dry run 掃描量／Time Travel 救回／BQML 線性回歸
- [x] BQ 亮點補充：Materialized View、Scheduled Queries、INFORMATION_SCHEMA
- [x] 移除同步程式主線段；金鑰改引用 14 章對照；本機補充改雙寫版
- [x] Step 5 Looker 段沿用、檢查表/練習/排錯/團體節連動
- [x] 重現性通讀＋禁用詞掃描；commit＋push

## Phase 5：手冊16 大改
- [x] Part E override 重寫（雙寫下的搬家＝改 MYSQL_HOST，BQ 那份不受影響——搬家敘事的新賣點）
- [x] Cloud SQL vs BQ 營運級對照表
- [x] Spanner 動手節：試用 instance 建立→GoogleSQL 操作→不停機調 PU→對照表→刪除；全程實測
- [x] GCP 資料庫選型光譜表（SQL/Spanner/BQ/Firestore/Bigtable）
- [x] 連動：團體節/檢查表/收工段；禁用詞掃描；commit＋push

## Phase 6：手冊17 大改
- [ ] DAG 改造：移除 sync task、加 transform task（stage/app SQL 包函式）；程式實測
- [ ] 每日線敘事＋資料線圖重畫（雙寫版）
- [ ] T-1 scopes 段改寫（建機即給，舊 VM 補改當排錯）
- [ ] 端到端：排程觸發→雙寫→transform→app 更新（七步驟級驗證）
- [ ] 禁用詞掃描；commit＋push

## Phase 7：收尾
- [ ] 全庫交叉引用掃描（四章互指＋補充章）
- [ ] Lima pull；GCP 資源全停（VM/SQL/Spanner 試用刪除確認）
- [ ] HANDOFF 更新；投影片落差記待辦（EP12/17/18/20 另開批次）
