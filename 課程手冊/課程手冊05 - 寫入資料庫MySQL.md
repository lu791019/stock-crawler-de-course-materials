# 第 5 章：把資料存下來 — 寫入 MySQL

> 前面資料都只是印在畫面上，程式一關就沒了。這一章你會第一次把爬回來的股價「存下來」——拿掉 `_print`，改用會寫進 MySQL 的 `crawler_finmind`。

---

## 做完這一章，你會做到

1. 看懂怎麼用 SQLAlchemy 把一個 DataFrame 寫進 MySQL。
2. 讓爬蟲任務做完後，資料真的進到 MySQL、還另存一份 CSV。
3. 用三種方式驗證資料入庫：phpMyAdmin、docker exec 下 SQL、Python 查詢。
4. 發現一個問題：重跑就會產生重複資料（這是下一章要解決的）。

---

## 先搞懂：從「看過就忘」到「存起來」

前面的 print 版，資料印在畫面上，程式一結束就消失。真正的資料工程一定要**落地（持久化）**——把資料寫進資料庫，之後才能查詢、分析、視覺化。

這一章用的是 `crawler_finmind`（沒有 `_print`）。它比第 2 章那版多做兩件事：**寫進 MySQL** 和 **另存一份 CSV**。而前半段（呼叫 API、解析 JSON）跟第 2 章一模一樣——再一次，只換落地方式，前面不動。

---

## 先看大局：為什麼「資料儲存」是資料工程的核心

動手寫 MySQL 之前，先把視野拉高——你正在做的事，在資料工程的世界裡有名字、有座標。

### 為何「資料儲存」重要？

- **基礎角色**：資料工程的目標是讓資料能被收集、轉換、分析並產生價值，而「儲存」是整個流程的核心樞紐
- **可靠性**：沒有合適的資料儲存，資料可能遺失、錯誤或無法被有效存取
- **效能與成本**：不同的儲存技術會直接影響查詢速度、擴展能力與成本控管
- **下游應用**：BI 報表、機器學習模型、即時數據系統等都依賴資料儲存的設計品質
- **AI 世代**：AI 需要龐大的資料基礎，沒有合適的儲存架構，資料無法被有效整合、清理與提供給模型

### 關聯式資料庫（RDBMS）vs NoSQL

| | RDBMS 關聯式資料庫 | NoSQL 資料庫 |
|---|---|---|
| 特點 | 遵循固定的 Schema，使用 SQL 語言 | 類型多元：Key-Value、Document、Columnar、Graph |
| 適合 | 結構化資料、交易系統、需要複雜查詢或關聯的場景 | 非結構化或半結構化資料、大規模分散式系統 |
| 優點 | 資料一致性強（ACID）、成熟穩定 | 彈性高、容易水平擴展、支援海量資料 |
| 缺點 | 擴展性較差，水平擴展成本高 | 一致性通常採 CAP 理論的「最終一致性」，交易支持較弱 |
| 代表 | MySQL、PostgreSQL、SQLite | MongoDB（Document）、Redis（Key-Value）、Cassandra（Columnar）、Neo4j（Graph）|

股價資料欄位固定（date、open、close…）、要精準查詢 → RDBMS 是自然選擇，本課程用 MySQL。

### OLTP vs OLAP

| | OLTP 線上交易處理 | OLAP 線上分析處理 |
|---|---|---|
| 特點 | 針對大量、小型、即時的交易操作（新增、修改、刪除）| 針對大量歷史資料做聚合、分析、查詢 |
| 重點 | 速度快、一致性高 | 支援複雜查詢與大規模運算，偏重讀取性能 |
| 常見系統 | 電商訂單系統、銀行交易系統 | 商業智慧報表、數據倉庫、趨勢分析 |
| 常見工具 | MySQL、PostgreSQL、SQL Server | BigQuery、Snowflake、Redshift |

這一章做的是 OLTP——爬蟲一筆一筆把資料寫進 MySQL；到第 14 章會把資料搬進 BigQuery 做 OLAP 分析，兩邊你都會摸到。

### 資料的三種型態、熱與冷

- **結構化**：表格型態（交易、會員資料）→ 存關聯式資料庫
- **半結構化**：JSON、XML、Log → 我們從 FinMind API 拿回的原始回應就是 JSON，轉成 DataFrame 後才變結構化
- **非結構化**：影像、語音、影片 → 需要物件儲存（如 GCS、S3）

儲存技術必須能對應不同型態，否則資料難以被分析與利用。另一個維度是**熱資料 vs 冷資料（Storage Tiering）**：

- **熱資料**：常用、需快速存取 → 放高效能儲存（OLTP、快取系統）
- **冷資料**：不常用但需保留 → 放低成本的 Data Lake 或歸檔系統

平衡「效能」與「成本」，是資料工程的核心考量。

### Data Warehouse、Data Lake、Lakehouse（先認識名字就好）

- **Data Warehouse（數據倉庫）**：適合結構化資料與分析（OLAP）
- **Data Lake（數據湖）**：能儲存原始格式的海量資料，支援多種型態
- **Lakehouse**：融合 Warehouse 與 Lake 優點，既能存原始資料、又能做分析——現代資料平台的趨勢（Databricks、BigQuery、Snowflake）

還有一組常見對比：**批次處理（Batch）**定期匯入大批資料，適合報表、歷史分析；**即時處理（Streaming）**毫秒/秒級反應，適合風控、推薦系統。我們的爬蟲 pipeline 屬於批次；現代資料儲存必須能同時支援兩種工作負載。

### 星型 Schema：分析世界的資料模型（預告）

這一章的 `TaiwanStockPrice` 是一張「什麼都放」的單表——OLTP 世界這樣就夠用。但到了 OLAP 分析的世界，主流的建模方式是**星型 Schema（Star Schema）**：

- **事實表（Fact Table）**：放「發生的事」——每天每檔股票的價量，一筆一事件，量大
- **維度表（Dimension Table）**：放「描述性資訊」——股票基本資料（名稱、產業別）、日期屬性（星期幾、是否月底）
- 事實表在中間、維度表圍在四周，畫出來像一顆星星，因此得名。分析時用 JOIN 把維度接上事實，就能回答「半導體類股每月平均成交量」這種跨維度的問題

進階還有雪花 Schema（維度再正規化）、SCD（維度緩慢變化的處理）。現在先認識名字，第 14 章 BigQuery 與之後的維度建模補強會再回來。

### 更大的世界：大數據與現代資料棧（先認識名字就好）

當資料量超過單機能處理（TB～PB 級），會進入「大數據」生態：

- **分散式運算**：Hadoop 是早期代表，**Spark** 是現在的主流（記憶體內運算，快很多）——概念上就是把「多 worker 分工」放大到跨機器叢集，你在 Celery 學到的分散式思維完全通用
- **資料轉換層**：**dbt** 用 SQL + YAML 管理倉儲內的轉換（ELT 的 T），可測試、可版控，業界主流
- **資料品質**：Great Expectations、Soda 這類工具在 pipeline 中攔截爛資料，避免污染下游
- **即時同步（CDC）**：Debezium + Kafka 監聽資料庫變更、即時同步到別的系統，不用整批重跑

這些都是畢業後的補強地圖（完整版見學期專題機制總覽的 Roadmap）。本課先把 **MySQL → BigQuery** 這條主線走穩——它是一切進階的地基。

### 為什麼選 MySQL？（+ phpMyAdmin 是什麼）

**MySQL** 是一套開源的關聯式資料庫管理系統（RDBMS）：

- 使用 SQL（Structured Query Language）來管理資料
- 開源且免費：社群版可自由使用，也有商業授權版本
- 跨平台：支援 Windows、Linux、macOS
- 成熟穩定：廣泛應用在 Web 應用、企業系統，社群活躍
- 相容性高：有大量周邊工具與生態系支援（如 phpMyAdmin、各種 ORM 框架）

**phpMyAdmin** 是一個基於 PHP 開發的開源工具，提供 Web 介面來管理 MySQL / MariaDB 資料庫。它的目標是讓不熟悉命令列的使用者也能方便操作資料庫——透過網頁就能完成幾乎所有 SQL 指令的功能。等一下 Step 2 你就會用到它。

### SQL 指令的四大家族（DDL / DML / DQL / DCL）

SQL 指令看起來很多，其實按「管什麼」分成四家，之後看到任何指令都能對號入座：

| 家族 | 全名 | 管什麼 | 常見指令 | 本課在哪遇到 |
|------|------|--------|---------|-------------|
| **DDL** | Data Definition Language（資料定義）| 表的**結構**：建、改、刪表 | `CREATE`、`ALTER`、`DROP`、`TRUNCATE` | `to_sql` 幫你自動 CREATE TABLE；補充D 建索引、分區 |
| **DML** | Data Manipulation Language（資料操作）| 表裡的**資料**：增、改、刪 | `INSERT`、`UPDATE`、`DELETE` | `to_sql` append 就是一串 INSERT；第 6 章 upsert |
| **DQL** | Data Query Language（資料查詢）| **查**資料 | `SELECT`（配 `WHERE`、`JOIN`、`GROUP BY`）| 三種驗證入庫、`read_sql`、之後 Metabase 的每張圖 |
| **DCL** | Data Control Language（資料控制）| **誰能做什麼**：權限 | `GRANT`、`REVOKE` | 補充D 的受限帳號（app 只給 SELECT/INSERT）|

兩個備註：

- 跟 **CRUD** 的關係：CRUD 是「動作」視角（Create/Read/Update/Delete），四大家族是「指令分類」視角——CRUD 的 C、U、D 都屬於 DML，R 屬於 DQL。兩套講的是同一件事的不同切面。
- 有人會把 `COMMIT` / `ROLLBACK` 獨立成第五家 **TCL**（交易控制）——補充D 的交易一節玩的就是它們。

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `crawler/tasks_crawler_finmind.py` | 任務定義 | `crawler_finmind` + `upload_data_to_mysql` |
| `crawler/producer_crawler_finmind.py` | 生產者 | 派送 5 支股票的正式版任務 |
| `crawler/config.py` | 設定 | 提供 MySQL 連線資訊 |
| `example/mock_stock_price_data.sql` | 練習素材 | 模擬台股歷史股價，可在 phpMyAdmin 執行、填充資料練查詢（練習 4 用）|
| `example/vw_stock_price_daily.sql` | 預告 | 日線 View，第 8 章 Metabase 做圖表時會用到 |
| `example/ecommerce.sql` | 補充D 教材 | 三張表含外鍵的電商範例（users/products/orders）|

> `example/backup/` 裡是原課程（hahow）留下的通用練習檔（employees、students、ecommerce 等），本課程不使用，留作參考。

`config.py` 裡的 MySQL 設定（第 1 章看過）：

```python
MYSQL_HOST     = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT     = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_ACCOUNT  = os.environ.get("MYSQL_ACCOUNT", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "1234")
```

> MySQL 容器的設定來自 `docker-compose-local.yml`：資料庫 `mydb`、root 密碼 `1234`、port `3306`。

---

## 一行一行讀懂「寫入 MySQL」的函式

```python
from sqlalchemy import create_engine
from crawler.config import MYSQL_ACCOUNT, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT

def upload_data_to_mysql(df: pd.DataFrame):
    # ① 組出連線字串：mysql+pymysql://帳號:密碼@主機:埠/資料庫
    address = f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/mydb"

    # ② 建立一個可重用的連線引擎
    engine = create_engine(address)

    # ③ 把整個 DataFrame 附加到 TaiwanStockPrice 表；表不存在會自動建立
    try:
        df.to_sql("TaiwanStockPrice", con=engine, if_exists="append", index=False)
    except Exception:
        df.to_sql("TaiwanStockPrice", con=engine, if_exists="append", index=False)
```

一段一段看：

- **① 連線字串**：格式是 `mysql+pymysql://帳號:密碼@主機:埠/資料庫`。`mysql+pymysql` 是「用 pymysql 這個驅動連 MySQL」的意思；最後的 `mydb` 是資料庫名稱。
- **② `create_engine`**：建立一個引擎物件，代表「怎麼連到這個資料庫」。它可以重複使用。
- **③ `df.to_sql(...)`**：這是 pandas 的神奇一行——把整個 DataFrame 直接寫進資料表。三個參數要懂：
  - `"TaiwanStockPrice"`：要寫入的資料表名稱。
  - `if_exists="append"`：如果表已存在，就**把資料附加上去**（表不存在會自動建立）。**注意這個字：append 是「一直往後加」**，這就是為什麼重跑會產生重複，本章結尾會回來講。
  - `index=False`：不要把 DataFrame 的列索引也寫進去。
- **那個 `try/except` 為什麼在？** 想像一下第 1 章的情境：如果你**同時開了好幾個 worker、而且是第一次寫入、表還不存在**，可能會有兩個 worker 同時想建表而撞在一起。第一次失敗後重試一次通常就成功（因為表已被另一個 worker 建好了）。這是併發帶來的小狀況，作者用最簡單的重試化解。

### 補充：資料表到底是誰建的？（兩種方式）

**方式 A：讓程式自動建（這個專案用的）。** `to_sql` 在表不存在時，會看 DataFrame 的欄位名稱和型別自動建表。方便，但型別是「推斷」出來的。

**方式 B：自己用 SQL 手動建。** 到 phpMyAdmin → 選 `mydb` → **SQL** 頁籤，貼上：

```sql
CREATE TABLE IF NOT EXISTS TaiwanStockPrice (
    date VARCHAR(10),
    stock_id VARCHAR(10),
    Trading_Volume BIGINT,
    Trading_money BIGINT,
    open FLOAT,
    max FLOAT,
    min FLOAT,
    close FLOAT,
    spread FLOAT,
    Trading_turnover BIGINT
);
```

手動建的價值是**看懂表結構**：每個欄位叫什麼、什麼型別。就算你手動建過，`if_exists="append"` 也會直接往裡面塞資料，兩種方式不衝突。

> 這裡埋一個伏筆：注意這張表**沒有主鍵**——資料庫根本不知道哪兩筆算「同一筆」。這正是重複資料的根源，第 6 章會回來解決。

---

## 一行一行讀懂 `crawler_finmind` 任務

```python
@app.task()
def crawler_finmind(stock_id):
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": "2024-01-01",
        "end_date": "2025-06-17",
    }
    resp = requests.get(url, params=parameter)
    data = resp.json()
    if resp.status_code == 200:
        df = pd.DataFrame(data["data"])
        print(df)
        upload_data_to_mysql(df)                                    # ← 比第 2 章多這行：寫進 MySQL
        df.to_csv(f"output/TaiwanStockPrice_{stock_id}.csv",        # ← 也多這行：另存 CSV
                  index=False, encoding="utf-8-sig")
        print(f"TaiwanStockPrice_{stock_id}.csv saved.")
    else:
        print(data["msg"])
```

跟第 2 章的 `crawler_finmind_print` 對照，你會發現前面完全一樣，只多了兩行：`upload_data_to_mysql(df)` 和 `df.to_csv(...)`。這再次印證整套課的主線——**改的永遠只是最後「怎麼處理資料」那一小段**。（`utf-8-sig` 是為了讓 Excel 打開 CSV 時中文不亂碼。）

---

## 一步一步跟著做

### Step 1：確認 MySQL 有起來

```bash
docker compose -f docker-compose-local.yml up -d rabbitmq flower mysql phpmyadmin
docker compose -f docker-compose-local.yml ps
curl -o /dev/null -s -w "phpMyAdmin: %{http_code}\n" http://localhost:8080
```

> ✅ mysql 要是 `Up (healthy)`、curl 回 200。MySQL 第一次啟動要初始化，可能要等 30 秒以上，不 healthy 就再等一下。

### Step 2：先認識 phpMyAdmin

瀏覽器開 http://localhost:8080 ，帳密 `root / 1234`。這是 MySQL 的 Web 管理介面，四個常用動作：

| 動作 | 位置 |
|------|------|
| 選資料庫 | 左側點 `mydb` |
| 看資料表 | 選 `mydb` 後中間會列出所有 table |
| 下 SQL | 上方 **SQL** 頁籤 |
| 看資料 | 點 table → **Browse** 頁籤 |

> ✅ 登入成功、左側看到 `mydb`（此時裡面可能還沒有資料表）就過關。

### Step 3：快速測試 Python 連得到 MySQL

Python 要連 MySQL，靠兩個套件：`pymysql`（驅動，負責實際通訊）和 `sqlalchemy`（上層介面，管理連線）。本專案的 `pyproject.toml` 已經宣告好了，之前 `uv sync` 過就已裝好；若是在自己的新專案，要先手動安裝：

```bash
# 自己的專案手動安裝
uv add pymysql
uv add sqlalchemy

# 本專案：同步安裝即可
uv sync
```

接著在真正跑 pipeline 之前，先用一小段程式確認連線沒問題（問題切小塊，好排查）：

```bash
uv run python -c "
from sqlalchemy import create_engine, text
engine = create_engine('mysql+pymysql://root:1234@127.0.0.1:3306/mydb')
with engine.connect() as conn:
    r = conn.execute(text('SELECT DATABASE();'))
    print('connected to:', r.scalar())
"
```

> ✅ 印出 `connected to: mydb` 就過關。這裡失敗的話，先解決連線問題再往下（見排錯表）。

### Step 4：建好 output 資料夾（給 CSV 用）

```bash
mkdir -p output
```

> ✅ 沒這個資料夾，`to_csv` 會失敗。先建好。

### Step 5：啟動 worker（一樣不用改）

```bash
uv run python -m celery -A crawler.worker worker --loglevel=info
```

### Step 6：派送正式版任務

```bash
uv run crawler/producer_crawler_finmind.py
```

**worker 你會看到**：印出 5 張股價表，每張後面多一行：

```
TaiwanStockPrice_2330.csv saved.
TaiwanStockPrice_0050.csv saved.
...
```

> ✅ 看到 `... .csv saved.` 就代表寫 DB 和存 CSV 這兩步都做完了。

### Step 7：驗證資料真的入庫（三種方式，都試試）

**方式 A：phpMyAdmin 用眼睛看**

http://localhost:8080 → 左邊選 `mydb` → 點 `TaiwanStockPrice` → Browse，看到 5 支股票的每日股價。回專案資料夾看 `output/`，也會有對應的 CSV。

**方式 B：docker exec 直接下 SQL**

```bash
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SHOW TABLES; SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice GROUP BY stock_id;"
```

✅ **預期**：

```
Tables_in_mydb
TaiwanStockPrice

stock_id    cnt
0050        349
2330        349
...
```

**方式 C：Python 查回來變 DataFrame**

```bash
uv run python -c "
import pandas as pd
from sqlalchemy import create_engine
engine = create_engine('mysql+pymysql://root:1234@127.0.0.1:3306/mydb')
df = pd.read_sql('SELECT stock_id, COUNT(*) c FROM TaiwanStockPrice GROUP BY stock_id', engine)
print(df)
"
```

> 💡 `to_sql` 是「DataFrame → 資料表」，`read_sql` 就是反方向「查詢結果 → DataFrame」。之後第 14 章把 MySQL 資料搬去 BigQuery，用的正是 `read_sql` 這一招。

### Step 8：故意重跑一次，觀察「重複」

再跑一次 `producer_crawler_finmind.py`，用方式 B 再查一次筆數——**你會發現筆數翻倍了**。同一支股票、同一天的資料出現兩次。記住這個現象，這就是下一章要解決的問題。

---

## 換一種跑法：全部用 Docker 容器（可選）

上面 worker 跑在本機。也可以整套都進容器（第 3 章方式 B 的延伸）：

```bash
docker compose -f docker-compose-local.yml up -d --build rabbitmq flower mysql phpmyadmin worker_twse worker_tpex
docker compose -f docker-compose-local.yml up producer     # 發 multi_queue 任務（2330 + 00679B）
docker compose -f docker-compose-local.yml logs worker_twse | grep -E "saved|succeeded"
```

> 注意 compose 裡 worker 的環境變數是 `MYSQL_HOST=mysql`、`RABBITMQ_HOST=rabbitmq`（容器名，不是 127.0.0.1）——這就是第 1 章 config.py 那張「本機 vs Docker」對照表的實際應用。

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | `connected to: mydb` | Python 連得到 MySQL |
| 2 | worker 印出 `... .csv saved.` | 寫 DB + 存 CSV 成功 |
| 3 | phpMyAdmin 有 `TaiwanStockPrice` 表且有資料 | 資料真的落地 MySQL |
| 4 | SQL / Python 查得到各股筆數 | 你會用三種方式驗證資料 |
| 5 | `output/` 有 CSV 檔 | 另存備份成功 |
| 6 | 重跑後筆數翻倍 | `if_exists="append"` 會一直疊加 |

---

## 想再深入一點

- **`to_sql` 幫你做了什麼「隱形」的事？** 你沒有寫任何 `CREATE TABLE`，表卻自動出現了——因為 `to_sql` 會看 DataFrame 的欄位名稱和型別，自動幫你推斷出一張表的結構並建立。方便，但也有代價：它推斷的型別不一定是你要的（例如日期可能被存成文字），欄位也沒有主鍵。第 6 章之所以改成自己用 `Table(...)` 明確定義結構，就是為了拿回這個控制權（尤其是要設主鍵）。
- **`engine` 為什麼可以重複使用？** `create_engine` 建立的不是「一條連線」，而是一個「連線池」的管理者。它內部會維護一組連線、需要時借出、用完還回，所以你不用每寫一筆就開關一次連線。這也是為什麼把 `engine` 建好放著重用，比每次都 `create_engine` 更有效率。
- **`if_exists` 還有別的選項。** 除了 `"append"`（附加），還有 `"replace"`（先刪表重建，會清掉舊資料）和 `"fail"`（表已存在就報錯）。這個專案用 `append` 是因為要持續累積歷史股價；但 `append` 不看重複，所以才會有下一章的問題。
- **為什麼要「同時」寫 DB 又存 CSV？** 兩者角色不同：MySQL 是給程式查詢、之後接 Metabase / BigQuery 用的「正式儲存」；CSV 則是一份人可以直接打開、方便備份或臨時檢查的快照。真實專案常常這樣「雙寫」，一份給機器、一份給人。

---

## 補充：SQLAlchemy 完整指南（原理、參數、看見它背後做的事）

本章的程式碼只用到 SQLAlchemy 的一小角。這一節把它攤開講清楚——之後不管接 FastAPI（補充B）、寫測試（補充C）還是搬 BigQuery（第 14 章），你都會一直遇到它。

### SQLAlchemy 在整條路的哪一層

```
你的程式（pandas df.to_sql / read_sql）
        │
SQLAlchemy Core（產生 SQL、管理連線池、包交易）
        │
DBAPI 驅動（pymysql — 真正跟 MySQL 講話的翻譯員）
        │
MySQL（TCP 3306）
```

連線字串 `mysql+pymysql://...` 的 `mysql` 是「方言（dialect）」、`pymysql` 是「驅動（driver）」——SQLAlchemy 負責把同一套 Python 介面翻成各家資料庫的方言，所以之後想換 PostgreSQL，理論上改連線字串就好，程式碼不動。

### 往下看一層：直接用 pymysql 長什麼樣

SQLAlchemy 底下那層（DBAPI）親眼看一次，之後看到別人 `import pymysql` 的程式碼就不會慌（VM 實測可跑）：

```python
import pymysql

conn = pymysql.connect(host="127.0.0.1", port=3306,
                       user="root", password="1234", database="mydb")
try:
    with conn.cursor() as cursor:                      # cursor（游標）= 你跟 DB 對話的把手
        cursor.execute(
            "SELECT date, close FROM TaiwanStockPrice WHERE stock_id = %s "
            "ORDER BY date DESC LIMIT 3",
            ("2330",),                                  # %s 佔位 + 參數分開傳 → 防 SQL injection
        )
        for row in cursor.fetchall():                   # 取回結果（tuple 的 list）
            print(row)        # (datetime.date(2025, 6, 13), Decimal('1000.65')) ...
    conn.commit()                                       # 有寫入的話要自己 commit
finally:
    conn.close()                                        # 用完要自己關
```

**跟 SQLAlchemy 版對照，你就知道上層幫你省了什麼**：

| | 原生 pymysql | SQLAlchemy |
|---|---|---|
| 連線管理 | 自己 connect / close，沒有連線池 | engine 連線池自動借還 |
| 交易 | 自己記得 commit | `engine.begin()` 自動 commit/rollback |
| 佔位符 | `%s`（pymysql 專屬） | `:名字`（跨資料庫統一） |
| 結果 | tuple，欄位靠位置對 | 可直接進 pandas DataFrame |
| 換資料庫 | 整段重寫（各家 DBAPI 不同） | 改連線字串即可 |

所以本課站在 SQLAlchemy + pandas 這層——但底層概念（cursor、佔位符、commit）是通用的，任何語言連任何資料庫都是這一套。

**版本與兩個坑**：

- 本專案 `pyproject.toml` 鎖定 `pymysql==1.1.1`，`uv sync` 就會裝對；自己的新專案 `uv add pymysql` 即可。
- ⚠️ **查版本別用 `pymysql.__version__`**——它會回 `"1.4.6"`，那是 PyMySQL 假扮成舊套件 MySQLdb 的「相容版本號」，不是它自己的版本（歷史包袱：讓檢查 MySQLdb 版本的老程式碼不會爆）。要看真實版本用 `pymysql.VERSION`（回 `(1, 1, 1, 'final', 1)`）或 `uv pip list`。以上皆 VM 實測。
- MySQL 8 預設認證方式（`caching_sha2_password`）需要另裝 `cryptography` 套件才能連。本課的 compose 設了 `--default-authentication-plugin=mysql_native_password`、且專案依賴裡已帶 cryptography，所以你不會踩到；在別的環境看到 `cryptography is required` 錯誤，就是這件事。

**Core vs ORM**：SQLAlchemy 有兩層用法。**Core** 是「用 Python 組 SQL、自己管表」——本課程用的就是它（搭配 pandas）；**ORM** 是「把表映射成 Python class、把資料列當物件操作」——Web 後端（如 FastAPI + 使用者系統）常用，資料工程的批次讀寫用 Core 就夠、也更直觀。知道有這兩層，看到別人的 `class User(Base)` 程式碼時不會慌。

### create_engine 參數詳解

```python
engine = create_engine(
    "mysql+pymysql://root:1234@127.0.0.1:3306/mydb",
    echo=False,           # True = 把它發出的每一句 SQL 印出來（除錯/教學神器，見下）
    pool_size=5,          # 連線池常駐連線數（預設 5）
    max_overflow=10,      # 尖峰時可額外再開幾條（預設 10）→ 最多 5+10=15 條
    pool_recycle=3600,    # 連線活超過 N 秒就換新的（見下面的 8 小時坑）
    pool_pre_ping=True,   # 每次借出連線前先 ping 一下，死連線自動換（建議開）
)
```

- **`engine` 是連線池管理者，不是連線**：`create_engine` 當下並不會連資料庫，第一次真的用到才連。理想用法是**建一次、全程式共用**——`api/main.py`（補充B）就是這樣，engine 放模組層級、app 存活期間重複使用。誠實說：本章的 `tasks_crawler_finmind.py` 是在函式內每次呼叫都建一次——簡單、不會錯，但沒吃到連線池的好處；等你懂了這節，就知道怎麼優化它。
- **`pool_recycle` 對付 MySQL 的 8 小時坑**：MySQL 預設 `wait_timeout=28800`（8 小時），閒置超過就單方面斷線；連線池不知情、把死連線借給你，就出現經典的 `MySQL server has gone away`。設 `pool_recycle=3600` 或開 `pool_pre_ping=True` 都能防——長時間跑的排程任務（第 9 章）尤其需要。
- **爬蟲場景的參數怎麼配**：worker 是多行程（prefork）時，**每個子行程有自己的池**，pool_size 不用開大；gevent 高併發時單行程共用一個池，`pool_size` 才需要跟著併發數調。

### engine → connection → transaction 三層

```python
from sqlalchemy import create_engine, text

engine = create_engine(...)                     # ① 池管理者（全程式一個）

with engine.connect() as conn:                  # ② 借一條連線（用完自動還）
    r = conn.execute(text("SELECT COUNT(*) FROM TaiwanStockPrice"))
    print(r.scalar())

with engine.begin() as conn:                    # ③ 借連線 + 包交易：離開 with 自動 COMMIT，
    conn.execute(text("UPDATE ..."))            #    中途出錯自動 ROLLBACK（補充D 交易一節的程式版）
```

- `text()`：把字串標記成「一句 SQL」。**參數一律用 `:名字` 佔位**，不要用 f-string 拼——這是 SQL injection 的正解：`conn.execute(text("SELECT * FROM t WHERE stock_id = :sid"), {"sid": "2330"})`
- Step 3 測連線用的 `SELECT DATABASE()` 就是這套的最小版。

### to_sql 參數完整表

```python
df.to_sql("TaiwanStockPrice", con=engine, if_exists="append", index=False)
```

| 參數 | 選項與意義 | 本課的選擇（為什麼） |
|------|-----------|--------------------|
| `if_exists` | `"fail"` 表存在就報錯 / `"replace"` **刪表重建**（舊資料全沒） / `"append"` 附加 | `append`——要累積歷史股價。`replace` 很危險：連表結構都會被重建成推斷版 |
| `index` | 要不要把 DataFrame 的索引寫成一欄 | `False`——我們的索引只是 0,1,2… 流水號，寫進去只是垃圾欄 |
| `dtype` | 手動指定欄位型別，如 `{"date": sqlalchemy.Date()}` | 沒用——所以型別是猜的。想拿回控制權：用 dtype，或像第 6 章直接 `Table(...)` 定義 |
| `chunksize` | 每批寫幾筆（預設一次全寫） | 大 DataFrame（十萬筆以上）建議設 1000~5000，避免單一巨大 INSERT 撐爆記憶體 |
| `method` | `None` 逐筆 INSERT / `"multi"` 多筆合併成一句 INSERT | 資料量大時 `"multi"` + `chunksize` 通常快很多 |

`read_sql` 是反方向的兄弟：`pd.read_sql("SELECT ...", con=engine)` 把查詢結果直接變 DataFrame——第 14 章把 MySQL 搬進 BigQuery，用的正是它。

### 打開黑盒子：echo=True 親眼看它做了什麼

把 `create_engine(..., echo=True)` 打開再跑一次寫入，terminal 會印出它背後發的每一句 SQL（VM 實測）：

```
INFO sqlalchemy.engine.Engine BEGIN (implicit)          ← 自動開交易（呼應補充D 第 5 節）
INFO sqlalchemy.engine.Engine DESCRIBE `mydb`.`echo_demo`   ← 先看表存不存在
CREATE TABLE echo_demo ( ... )                          ← 不存在 → 用 DataFrame 推斷建表
INFO sqlalchemy.engine.Engine INSERT INTO echo_demo (stock_id, close) VALUES (%(stock_id)s, %(close)s)
INFO sqlalchemy.engine.Engine COMMIT                    ← 全部成功才提交
```

一行 `to_sql` 背後 = **開交易 → 檢查表 →（必要時）建表 → 參數化 INSERT → COMMIT**。看過一次這個 log，「to_sql 是魔法」就變成「to_sql 是流程」了。確認完記得把 `echo` 關回去——正式跑爬蟲時它會把 log 洗到看不見重點。

> 想更深入 MySQL 本身（索引、外鍵、交易、分區）→ 看 **補充D**。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| `Access denied for user` | 帳密或 host 不符 | 本機預設 root / 1234；確認 MySQL 容器在跑 |
| `Unknown database 'mydb'` | 資料庫還沒建好 | 等 MySQL 初始化完成，或到 phpMyAdmin 手動建 `mydb` |
| `Connection refused`（連 MySQL）| MySQL 還沒 healthy | `docker compose ps` 等它變 healthy 再試 |
| `to_csv` 報找不到資料夾 | 沒有 `output/` | 先 `mkdir -p output` |
| CSV 中文亂碼 | 編碼問題 | 已用 `utf-8-sig`，用支援的軟體開啟 |
| Docker worker 連不到 DB | 容器裡還在用 127.0.0.1 | 確認 compose 的 environment 有 `MYSQL_HOST=mysql` |

---

## 想一想（確認你懂了）

先自己想過再看答案。

**Q1：這一章跟第 2 章的爬蟲任務，前半段有差嗎？差在哪一行之後？**

前半段（組參數、`requests.get`、`resp.json()`、轉 DataFrame）完全一樣。差別從 `print(df)` **之後**才開始：這一章多了 `upload_data_to_mysql(df)` 和 `df.to_csv(...)`。這讓你再次確認：換功能只動「處理資料」那一段。

**Q2：`if_exists="append"` 是什麼意思？為什麼會造成重複？**

`append` 是「表已存在就把新資料附加到後面」。它完全不檢查「這筆是不是已經有了」，所以你每跑一次，就無條件把同一批資料再加一遍。跑三次就有三份，資料越來越髒。

**Q3：那個 `try/except` 重試建表，跟第 1 章哪個觀念有關？**

跟「併發 / 多個 worker 同時做事」有關。多個 worker 第一次同時寫入、表還不存在時，可能同時想建表而衝突；重試一次就好，因為表已被別人建好。這是併發系統常見的小競態。

**Q4：`to_sql` 和 `read_sql` 各是什麼方向？**

`to_sql` 是把 DataFrame **寫進**資料表（爬蟲入庫用）；`read_sql` 是把 SQL 查詢結果**讀出來**變 DataFrame（分析、搬資料用）。一進一出，配起來就是 pandas 跟資料庫互通的完整迴路。

---

## 換你試試看

**練習 1：親眼數出「重複」**

跑 producer 前先用 Step 7 方式 B 記下 `TaiwanStockPrice` 的筆數，跑完再看一次，然後**再跑第三次**。把三次的筆數記下來，你會看到它以固定幅度一直增加。用自己的話解釋為什麼——這會讓你對「不冪等」的痛有很直接的感受，正好接到第 6 章。

**練習 2：用 SQL 看重複到什麼程度**

在 phpMyAdmin 的 SQL 分頁執行：

```sql
SELECT stock_id, date, COUNT(*)
FROM TaiwanStockPrice
GROUP BY stock_id, date
HAVING COUNT(*) > 1
LIMIT 20;
```

你會看到同一支股票、同一天出現不只一次。這條 SQL 讓你學會怎麼「抓出重複資料」，也預告了下一章要用 `stock_id + date` 當唯一身分的想法。

**練習 3：改抓不同股票並確認寫入**

把 producer 清單改成別的股票，跑一次，到 phpMyAdmin 確認新股票的資料也進來了。這讓你確認整條「爬取 → 寫入」的路對任何股票都通。

**練習 4：用模擬資料把表「填厚」，練真正的查詢**

FinMind 免費額度抓回的天數有限。打開 `example/mock_stock_price_data.sql`，把內容貼到 phpMyAdmin 的 **SQL** 頁籤執行——它會往回填充一段模擬歷史股價。然後練幾條查詢：

```sql
-- 某支股票最近 20 天的收盤價
SELECT date, close FROM TaiwanStockPrice
WHERE stock_id = '2330' ORDER BY date DESC LIMIT 20;

-- 每支股票的資料筆數與日期範圍
SELECT stock_id, COUNT(*) AS cnt, MIN(date) AS first_day, MAX(date) AS last_day
FROM TaiwanStockPrice GROUP BY stock_id;
```

資料厚一點，之後第 8 章 Metabase 畫出來的走勢圖也會好看得多。

---

## 收工

```bash
docker compose -f docker-compose-local.yml down       # 保留資料（下一章還要用）
# docker compose -f docker-compose-local.yml down -v  # 連 MySQL 資料一起清掉重來
```

> 💡 下一章要用到這一章寫進去的（含重複的）資料當對照組，**建議先別 `-v`**。

---

## 這一章你學到了

- 用 SQLAlchemy 的 `to_sql` 就能把 DataFrame 落地 MySQL；`read_sql` 則是反向查回來。
- 三種驗證入庫的方式：phpMyAdmin、docker exec 下 SQL、Python 查詢。
- 落地方式改變，但爬蟲前半段完全沿用。
- `if_exists="append"` 會造成重複資料——這是下一章的引子。

## 下一章要做什麼

重跑就重複，這在「每天定期更新」時是大災難。**下一章你會學「冪等」：用主鍵 + upsert，讓同一支任務跑幾次，資料庫結果都一致。**
