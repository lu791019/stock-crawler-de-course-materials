# 第 14 章：把資料搬進雲端倉儲 — MySQL → BigQuery（OLTP → OLAP）

> 這一章教「為什麼 MySQL 不夠」。你會把股價同步進雲端資料倉儲 BigQuery，並在上面做真正的分析（算移動平均、每日漲跌統計）。

> ⚠️ 這一章需要 GCP（Google Cloud）帳號與憑證，屬於進階內容。沒有 GCP 帳號的話，先讀懂「資料怎麼流」和觀念，實作等有帳號再做。

---

## 做完這一章，你會做到

1. 說得出 OLTP（交易型）和 OLAP（分析型）資料庫的差別。
2. 看懂怎麼把 MySQL 的資料同步進 BigQuery。
3. 看懂怎麼在 BigQuery 上用 SQL 做分析（去重、移動平均、每日彙總）。
4. 理解 ELT 這個流程。

---

## 先搞懂：OLTP vs OLAP

| | OLTP（例：MySQL）| OLAP（例：BigQuery）|
|---|---|---|
| 用途 | 即時、頻繁的小筆讀寫 | 大範圍的分析查詢 |
| 典型操作 | 寫入今天的股價、查一支股票 | 掃描三年、上千支股票算相關性 |
| 比喻 | 收銀機 | 財報分析室 |

前面你把股價寫進 MySQL——那是**營運資料庫（OLTP）**，擅長「一筆一筆即時寫入」。但當你要「一次掃三年、上千支股票做統計」，讓這種分析查詢**直接打在 MySQL 上**，會拖慢正在寫入的爬蟲，兩邊互相影響。

**解法：把資料另外同步一份到資料倉儲（OLAP）**，分析都在倉儲做，MySQL 專心負責寫入。BigQuery 就是 Google Cloud 上的資料倉儲，擅長「掃大量歷史資料」。

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `crawler/bigquery.py` | 工具模組 | 封裝 BigQuery 連線、建表、上傳、建 View |
| `crawler/stock_sync_mysql_to_bigquery.py` | 同步 | 把 MySQL 資料搬到 BigQuery |
| `crawler/stock_bigquery_data_transform.py` | 轉換 | 在 BigQuery 上建分析用的 View / Table |

---

## 資料怎麼流（先看全貌）

```
爬蟲 → MySQL（OLTP，營運寫入）
            │  stock_sync_mysql_to_bigquery.py  ← 把原始資料搬過去
            ▼
      BigQuery（OLAP，分析倉儲）：原始表 TaiwanStockPrice
            │  stock_bigquery_data_transform.py  ← 在倉儲裡整理成分析表
            ▼
      分析用的 View / Table（去重、移動平均、每日彙總）→ 給報表 / BI 查
```

這就是資料工程常說的 **ELT**：先把資料 **L**oad（載入）進倉儲，再在倉儲裡 **T**ransform（轉換）。跟傳統「先轉換再載入」的 ETL 相反——雲端倉儲夠強，所以偏好先搬進去、再用它的算力轉換。

---

## 一行一行讀懂關鍵片段

### ① 上傳到 BigQuery（`bigquery.py`）

```python
def upload_data_to_bigquery(table_name, df, dataset_id=DATASET_ID, mode="replace"):
    client = get_bigquery_client()
    table_id = f"{PROJECT_ID}.{dataset_id}.{table_name}"
    # replace = 整張覆蓋；append = 附加
    write_disp = WriteDisposition.WRITE_TRUNCATE if mode == "replace" else WriteDisposition.WRITE_APPEND
    job_config = LoadJobConfig(write_disposition=write_disp, autodetect=True)
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()   # 等這個批次載入 job 跑完
```

重點：

- `table_id` 是 BigQuery 的三段式命名：`專案.資料集.表`。
- `WRITE_TRUNCATE`（覆蓋）vs `WRITE_APPEND`（附加）：對應你在第 5 章學過的 `if_exists`，概念一樣。
- `load_table_from_dataframe`：用「批次載入 job」把 DataFrame 匯進 BigQuery。專案註解特別提到一個實務重點——**這種批次 load job 是免費的**（只算儲存費），而另一種 streaming insert（逐筆即時寫入）會依寫入量計費。所以「每日整批股價」這種場景用批次 load 最划算。
- `job.result()`：因為 load 是**非同步**的，這行是「等它做完」（是不是想到第 1 章的 `.delay()` + 之後 `.get()`？概念相通）。

### ② 用日期做分區（partition）

```python
table.time_partitioning = bigquery.TimePartitioning(
    type_=bigquery.TimePartitioningType.DAY,
    field="date",
)
```

**分區**是資料倉儲省錢又加速的關鍵。它把大表依 `date` 切成一天一塊，之後你查「只看某個月」時，BigQuery 只掃那幾塊、不用掃整張表——BigQuery 依掃描量計費，掃得少就便宜又快。

### ③ 在 BigQuery 上做分析（`stock_bigquery_data_transform.py`）

這是 OLAP 真正發威的地方——用 SQL 的**視窗函數（window function）**算技術指標。看這段建「趨勢分析 View」的 SQL：

```sql
SELECT
  stock_id, trade_date, close,
  -- 昨天的收盤價
  LAG(close) OVER (PARTITION BY stock_id ORDER BY trade_date) AS prev_close,
  -- 5 日移動平均（含今天往前 4 天）
  AVG(close) OVER (
    PARTITION BY stock_id ORDER BY trade_date
    ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
  ) AS ma5,
  -- 20 日移動平均
  AVG(close) OVER (
    PARTITION BY stock_id ORDER BY trade_date
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
  ) AS ma20
FROM vw_stock_price_daily
```

白話：

- `PARTITION BY stock_id ORDER BY trade_date`：對「每一支股票、按日期排序」分別計算。
- `LAG(close)`：抓「上一列（昨天）」的收盤價，用來算漲跌。
- `AVG(close) OVER (... ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)`：算「今天往前含 4 天」共 5 天的平均，也就是股市常說的 **5 日均線（MA5）**；20 天就是 MA20。

這種「一整支股票的時間序列分析」正是 OLAP 的強項，也是為什麼要把資料搬進 BigQuery——在 MySQL 上對整個歷史做這種計算會很吃力。

---

## 一步一步跟著做（需 GCP）

> 沒有 GCP 帳號可以跳過實作，只讀觀念。

### Step 1：準備 GCP 環境

1. 建立 GCP 專案，開啟 BigQuery API。
2. 建立服務帳戶（Service Account），下載 JSON 金鑰。
3. 設定憑證環境變數，並在 `config.py` 取消 `GCP_PROJECT_ID` 的註解、填你的專案 ID：

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your-key.json"
```

### Step 2：把 MySQL 同步進 BigQuery

```bash
uv run crawler/stock_sync_mysql_to_bigquery.py
```

這支會：建立 BigQuery dataset（如果沒有）→ 從 MySQL `SELECT * FROM TaiwanStockPrice` 讀成 DataFrame → 建好帶分區的 BQ 表 → 覆蓋上傳。

### Step 3：在 BigQuery 上建分析 View / Table

```bash
uv run crawler/stock_bigquery_data_transform.py
```

這支會建立去重的每日股價 View、含 MA5/MA20 的趨勢分析 View、每日市場彙總 View。

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | GCP Console 的 BigQuery 出現 `stock` 資料集與 `TaiwanStockPrice` 表 | 同步成功 |
| 2 | 出現 `vw_stock_trend_analysis` 等 View | 轉換成功 |
| 3 | 查詢時只掃到相關分區 | 分區生效、省錢 |

---

## 想再深入一點

- **load job vs streaming insert（費用差很大）。** 批次 load job（本專案用的）免費、只算儲存；streaming insert 逐筆即時寫入要依量計費。每日整批股價這種場景，批次 load 又便宜又適合。這是實務上很重要的成本觀念。
- **分區（partition）為什麼能省錢？** BigQuery 依「掃描的資料量」收費。把表依日期分區後，查「某個月」只掃那個月的分區，不用掃整張三年的表。所以查得少 = 便宜 + 快。
- **View vs Table 差在哪？** View 是「一段存起來的查詢」，每次查它才即時算；Table 是把結果實體存下來。專案兩者都建：View 保持即時、Table 加速重複查詢。
- **這裡的「去重」跟第 6 章不一樣。** 第 6 章是在寫入時用主鍵 upsert 去重；這裡是在查詢時用 `ROW_NUMBER() ... WHERE rn = 1` 只留每組第一筆。兩種都是去重，但一個發生在「寫入端」、一個發生在「分析端」，適用情境不同。

---

## 想一想（確認你懂了）

**Q1：用一句話說出 OLTP 和 OLAP 的差別，各舉一個場景。**

OLTP 擅長「即時、頻繁的小筆讀寫」（例如爬蟲每天寫入股價、查單一支股票），MySQL 是代表；OLAP 擅長「大範圍的分析查詢」（例如掃三年全市場算移動平均），BigQuery 是代表。一個像收銀機，一個像分析室。

**Q2：為什麼不直接讓分析查詢打在 MySQL 上？會有什麼副作用？**

因為大範圍分析查詢很吃資源，直接打在 MySQL 上會拖慢它正在做的即時寫入（爬蟲），兩邊互相影響。把分析移到 BigQuery，MySQL 就能專心負責營運寫入，各司其職。

**Q3：ELT 和傳統 ETL 差在哪個字母的順序？為什麼雲端倉儲時代偏好 ELT？**

差在 T（Transform）和 L（Load）的順序。傳統 ETL 是「先轉換、再載入」；ELT 是「先載入進倉儲、再用倉儲的算力轉換」。因為雲端倉儲（如 BigQuery）算力很強，先把原始資料整批搬進去、再用 SQL 轉換，比在外面慢慢轉再載入更有效率也更彈性。

---

## 換你試試看

> 以下需要 GCP 環境；沒有的話，改成「讀懂 SQL 並用自己的話解釋它在算什麼」。

**練習 1：讀懂 MA5 的 SQL**

看趨勢分析 View 裡算 `ma5` 的那段 `AVG(close) OVER (... ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)`，用自己的話解釋「為什麼是往前 4 天加今天，剛好 5 天」。這讓你搞懂視窗函數的「範圍」是怎麼界定的。

**練習 2：自己加一個 MA10**

模仿 MA5、MA20 的寫法，加一個 10 日均線 `ma10`（提示：`ROWS BETWEEN 9 PRECEDING AND CURRENT ROW`）。這讓你確認你真的看懂了移動平均的寫法，而不只是複製貼上。

**練習 3：想一個「分區」能省錢的查詢**

假設你只想看 2024 年 6 月的資料。寫出一段會「只掃到那個月分區」的 `WHERE` 條件（提示：對分區欄位 `date` 加範圍過濾）。想一想：如果不加這個條件、直接 `SELECT *`，BigQuery 會掃多少資料、花多少錢？

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| 憑證錯誤 / 權限不足 | `GOOGLE_APPLICATION_CREDENTIALS` 沒設對，或服務帳戶少權限 | 確認金鑰路徑；給服務帳戶 BigQuery 權限 |
| 查詢很貴 | 用了 `SELECT *` 全表掃描 | 加分區過濾、只選需要的欄位 |
| schema 型別對不上 | MySQL 與 BigQuery 型別對應問題 | 用 `bigquery.py` 裡定義好的 schema，或注意日期/數值精度 |

---

## 這一章你學到了

- OLTP 負責即時寫入、OLAP 負責大規模分析，兩者分工。
- 資料倉儲（BigQuery）讓分析不拖累營運資料庫。
- 用批次 load + 分區省錢，用視窗函數在倉儲裡算技術指標。
- ELT：先搬進倉儲，再用倉儲算力轉換。

## 課程總結

到這裡，整套課程走完了：**抓取（Celery + 分流 + 失敗處理）→ 落地（MySQL + 冪等）→ 視覺化（Metabase）→ 排程（APScheduler → Airflow）→ 一鍵整合，最後把資料送進雲端倉儲 BigQuery。**「爬蟲 → 佇列 → 落地 → 編排 → 倉儲」這條路，就是資料工程的基本功。接下來的雲端段課程，會把這整套系統搬上 GCP。
