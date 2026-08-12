# 補充 L：雲地混合 — 地端資料橋接上雲（金鑰、sync 與身分邊界）

> 你在本機（自己的電腦）跑著 MySQL 與爬蟲，卻要把資料送進雲端的 BigQuery——這個「一半在地、一半在雲」的形態，業界叫**雲地混合（hybrid cloud）**。這一篇把課程裡跨過這條界線的工具（金鑰檔、`stock_sync_mysql_to_bigquery.py`）放回它們所屬的架構脈絡，並示範正確的操作流程。

---

## 做完這一篇，你會做到

1. 說得出雲地混合是什麼、課程的哪個階段就是這個形態。
2. 說得出為什麼本機程式要金鑰檔、VM 上的程式不用——身分邊界的概念。
3. 在本機正確執行 MySQL → BigQuery 的同步（回填），資料落在 raw 層。
4. 分辨「批次橋接」與「雙寫」兩種資料上雲方式的差異與取捨。

---

## 先搞懂：一條看不見的邊界

```
地端（你的電腦 / 機房）                雲端（GCP）
┌────────────────────┐              ┌────────────────┐
│ MySQL 容器（OLTP）   │──批次推送──→ │ BigQuery（OLAP） │
│ 爬蟲、Compose        │   sync 腳本  │ 資料倉儲         │
└────────────────────┘              └────────────────┘
          ↑ 跨過這條線，就需要「身分」
```

雲地混合的本質難題不是搬資料，是**兩邊的信任體系不同**：

| | 雲內的程式（VM 上的 worker） | 地端的程式（你電腦上的 sync） |
|---|---|---|
| GCP 怎麼認得它 | metadata server 發的**機器身分**（VM 附掛的服務帳戶） | 不認得——對 GCP 是陌生人 |
| 需要帶什麼 | 什麼都不用 | **金鑰檔**（`GOOGLE_APPLICATION_CREDENTIALS` 指向它） |
| 手冊出處 | 手冊 15 Step 1 的兩道閘門 | 手冊 15〈補充：在本機雙寫（金鑰用法）〉 |

兩者其實是同一套 ADC（Application Default Credentials）機制的兩條路：程式呼叫 `google.auth.default()` 時依序找「環境變數指的金鑰 → gcloud 的本機憑證 → metadata server」，全部落空就丟 `DefaultCredentialsError`——本機看到這個錯誤，第一反應就是查金鑰環境變數。

## 課程的演進，就是一次「混合 → 全雲」的遷移

| | 舊版課程（sync 時代） | 現行課程（雙寫時代） |
|---|---|---|
| OLTP 在哪 | 地端 MySQL | 雲端 Cloud SQL（手冊 16 搬家） |
| 資料怎麼上雲 | **批次橋接**：sync 定期整批推送 | **雙寫**：寫入當下兩邊同時落地 |
| 新鮮度 | 有時差（上次 sync 到現在的資料不在雲上） | 即時 |
| 需要金鑰嗎 | 要（程式在地端） | 不用（worker 在雲內） |
| sync 腳本的角色 | 主角 | **回填工具**——只在「開始雙寫前的歷史資料」要補進 BigQuery 時跑一次 |

很多企業今天仍停在左欄（地端 ERP／資料庫每晚批次進雲端倉儲），所以左欄不是「錯的舊做法」，是**真實世界的常見形態**；課程走到右欄，正好讓你把兩種形態都經歷一遍。

---

## 一步一步：在本機正確執行 sync（回填）

前提：手冊 14 的金鑰已下載到 `~/gcp-keys/`、手冊 15 補充段已給金鑰的服務帳戶 BigQuery 角色。

```bash
# ① 亮出身分——export 只活在當下這個終端機，重開就要重來
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/gcp-keys/{你的金鑰檔名}.json"
export GCP_PROJECT_ID="{你的專案ID}"

# ② 驗證憑證與專案（先驗再跑，錯在這裡就不會錯在後面）
ls -l "$GOOGLE_APPLICATION_CREDENTIALS"
uv run python -c "import google.auth; print(google.auth.default()[1])"   # 印出專案 ID = 通

# ③ 啟動本機 MySQL（資料來源）
docker compose -f docker-compose-local.yml up -d mysql

# ④ 跑同步——落點是 raw 層（現行預設；仍建議明講，意圖寫在指令上）
BQ_DATASET=raw uv run crawler/stock_sync_mysql_to_bigquery.py

# ⑤ 對帳（別只看程式跑完沒報錯）
bq query --nouse_legacy_sql "SELECT COUNT(*) FROM raw.TaiwanStockPrice"
```

## 讀懂 sync 在做什麼（以及它的兩個個性）

1. **全量重灌，不是增量**：每張表先 `drop_table_if_exists` 再重建重傳——跑幾次結果都一樣（冪等），但資料量大時每次都是整包重來。這是回填工具的合理設計，不是每日排程的合理設計——每日更新用雙寫，不用 sync。
2. **落點由 `BQ_DATASET` 決定，預設 `raw`**：歷史註記——舊版預設是 `stock`（單一 dataset 時代的命名），曾讓裸跑的人把資料靜默寫進三層之外的 `stock` dataset。預設值已改為對齊現行三層架構；看到專案裡有來路不明的 `stock` dataset，就是有人用舊版裸跑過。

## 常見錯誤

| 症狀 | 原因 | 處理 |
|------|------|------|
| `DefaultCredentialsError`（traceback 停在 `google.auth.default`） | 本機沒有身分：金鑰環境變數沒設，或**重開終端機後 export 失效** | 重跑步驟①②；要一勞永逸可寫進 `~/.bashrc` |
| 資料進了 `stock` dataset | 用舊版程式裸跑 sync（舊預設值） | `git pull` 更新；已寫錯的照「刪掉重灌」處理：`bq rm -r -f -d stock` 後用正確落點重跑——副本走錯房間，拆掉重蓋比搬家快（源頭 MySQL 都在，BQ 副本永遠可重生） |
| 想「修好」而去改 `bigquery.py`／`config.py` 把專案 ID、dataset 寫死 | 舊筆記的做法 | 不要——值全部用 export 給，程式碼保持乾淨；寫死的下場是 `git pull` 衝突＋換環境就壞 |
| 跑完沒報錯但 BigQuery 沒資料 | 對錯專案（`GCP_PROJECT_ID` 指到別的專案，資料寫去那邊了） | `echo $GCP_PROJECT_ID` 核對；到 BQ Console 切到該專案查 |

## 這一篇你學到了

- 雲地混合＝資料與程式跨在雲界線兩側；跨線的程式必須自帶身分（金鑰），線內的程式用機器身分。
- 「本機要金鑰、VM 不用」不是機器的差別，是**站在界線哪一邊**的差別。
- 批次橋接（sync）與雙寫是兩代做法：前者有時差、適合回填；後者即時、是現行主線。
- 副本資料走錯位置，刪掉重灌優於搬移——源頭還在，副本永遠可重生。
