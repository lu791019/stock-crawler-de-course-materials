# MySQL 與爬蟲資料入庫 實作手冊

> 對象：已完成「多 Worker 與多 Queue」的學員
> 涵蓋：啟動 MySQL + phpMyAdmin → phpMyAdmin 操作 → 建資料表 → Python 連線 MySQL → 完整 pipeline → SQL 驗證入庫
> 實作專案：https://github.com/lu791019/stock-crawler-de-course-materials

---

## 這一集在做什麼

前面爬到的股價只有 print 出來就消失了。這一集把它**真正存進 MySQL**，完成整條資料流：

```
Producer → RabbitMQ → Worker 爬 FinMind → 寫進 MySQL → phpMyAdmin / SQL 查詢
                                              ↑
                                    upload_data_to_mysql()
```

---

## 使用前提

```bash
cd ~/stock-crawler
uv sync
docker --version
```

✅ **預期**：套件已裝、Docker 可用。

---

## 目錄

- [第一部分：啟動 MySQL + phpMyAdmin](#第一部分啟動-mysql--phpmyadmin)
- [第二部分：phpMyAdmin 操作](#第二部分phpmyadmin-操作)
- [第三部分：建資料表](#第三部分建資料表)
- [第四部分：Python 連線 MySQL](#第四部分python-連線-mysql)
- [第五部分：完整 pipeline](#第五部分完整-pipeline)
- [第六部分：SQL 查詢驗證](#第六部分sql-查詢驗證)

---

## 第一部分：啟動 MySQL + phpMyAdmin

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml up -d mysql phpmyadmin
```

### 驗證

```bash
docker compose -f docker-compose-local.yml ps
curl -o /dev/null -w "phpMyAdmin: %{http_code}\n" http://localhost:8080
```

✅ **預期**：`mysql`、`phpmyadmin` 都 Up（等 20-30 秒讓 MySQL 初始化完），curl 回 200。

> MySQL 設定（來自 docker-compose-local.yml）：
> - 資料庫：`mydb`
> - root 密碼：`1234`
> - port：3306

---

## 第二部分：phpMyAdmin 操作

瀏覽器開 http://localhost:8080，帳密 `root` / `1234`。

### 操作重點

| 動作 | 位置 |
|------|------|
| 選資料庫 | 左側點 `mydb` |
| 看資料表 | 選 `mydb` 後中間列出所有 table |
| 下 SQL | 上方 **SQL** 頁籤 |
| 看資料 | 點 table → **Browse** 頁籤 |

✅ **預期**：登入成功、左側看到 `mydb`（此時裡面還沒有資料表）。

---

## 第三部分：建資料表

有兩種方式建 `TaiwanStockPrice` 表。實務上我們讓程式自動建（見第五部分），這裡先示範用 phpMyAdmin 手動建，理解表結構。

### 方式 A：phpMyAdmin 的 SQL 介面

在 phpMyAdmin → 選 `mydb` → **SQL** 頁籤，貼上：

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

按 **Go** 執行。

✅ **預期**：`mydb` 左側出現 `TaiwanStockPrice` 表。

### 方式 B：讓程式自動建（推薦）

`df.to_sql(..., if_exists="append")` 在表不存在時會**自動依 DataFrame 欄位建表**。所以實際跑 pipeline 時不必手動建 —— 第五部分會直接讓 Worker 建好。

> 若剛剛用方式 A 建過，也沒關係，`if_exists="append"` 會直接往裡面塞資料。

---

## 第四部分：Python 連線 MySQL

爬蟲寫 DB 的邏輯在 `crawler/tasks_crawler_finmind.py` 的 `upload_data_to_mysql()`：

```python
from sqlalchemy import create_engine
from crawler.config import MYSQL_ACCOUNT, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT

def upload_data_to_mysql(df: pd.DataFrame):
    # 連線字串格式：mysql+pymysql://使用者:密碼@主機:port/資料庫名稱
    address = f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/mydb"
    engine = create_engine(address)
    df.to_sql("TaiwanStockPrice", con=engine, if_exists="append", index=False)
```

### 重點

| 元件 | 說明 |
|------|------|
| `create_engine(address)` | SQLAlchemy 建立資料庫連線引擎 |
| `mysql+pymysql://` | 用 pymysql 當 MySQL driver |
| `df.to_sql(...)` | 把 DataFrame 直接寫進資料表 |
| `if_exists="append"` | 表不存在則自動建、存在則往後追加 |
| `index=False` | 不把 DataFrame 的 index 當一欄寫進去 |

### 快速測試連線（可選）

```bash
cd ~/stock-crawler
uv run python -c "
from sqlalchemy import create_engine, text
engine = create_engine('mysql+pymysql://root:1234@127.0.0.1:3306/mydb')
with engine.connect() as conn:
    r = conn.execute(text('SELECT DATABASE();'))
    print('connected to:', r.scalar())
"
```

✅ **預期**：`connected to: mydb`

---

## 第五部分：完整 pipeline

現在把 broker、監控、資料庫、Worker 全部串起來，用寫 DB 版 producer 跑完整流程。

### Step 1：啟動所有服務 + Worker

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml up -d --build rabbitmq flower mysql phpmyadmin worker_twse worker_tpex
```

> Worker 容器裡 `MYSQL_HOST=mysql`、`RABBITMQ_HOST=rabbitmq`（見 compose 的 environment），才能連到同網路的服務。

### Step 2：確認 Worker ready

```bash
docker compose -f docker-compose-local.yml logs worker_twse | grep ready
docker compose -f docker-compose-local.yml logs worker_tpex | grep ready
```

✅ **預期**：`celery@twse ready.` / `celery@tpex ready.`

### Step 3：發任務（寫 DB 版）

`producer_crawler_finmind.py` 用寫 DB 版的 `crawler_finmind` task，一次發 5 支股票：

```bash
docker compose -f docker-compose-local.yml run --rm \
  -e RABBITMQ_HOST=rabbitmq -e PYTHONPATH=/crawler \
  producer uv run python crawler/producer_crawler_finmind.py
```

> 若想用預設的 multi_queue producer（發 2330 + 00679B）：
> `docker compose -f docker-compose-local.yml up producer`

✅ **預期**：印出 5 支股票代碼、exit code 0。

### Step 4：確認 Worker 有寫 DB

```bash
docker compose -f docker-compose-local.yml logs worker_twse | grep -E "saved|succeeded"
```

✅ **預期**：看到 `TaiwanStockPrice_XXXX.csv saved.` 與 `succeeded`，代表資料已寫進 MySQL + 存了 CSV。

---

## 第六部分：SQL 查詢驗證

### 方式 A：docker exec 進 MySQL

```bash
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SHOW TABLES; SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice GROUP BY stock_id;"
```

✅ **預期**：

```
Tables_in_mydb
TaiwanStockPrice

stock_id    cnt
2330        349
0050        349
...
```

### 方式 B：phpMyAdmin SQL 介面

http://localhost:8080 → `mydb` → **SQL**：

```sql
SELECT COUNT(*) FROM TaiwanStockPrice;
SELECT * FROM TaiwanStockPrice WHERE stock_id = '2330' ORDER BY date DESC LIMIT 5;
```

✅ **預期**：COUNT 有數字（>0）、能看到 2330 最近幾天的股價。

### 方式 C：Python 查詢

```bash
cd ~/stock-crawler
uv run python -c "
import pandas as pd
from sqlalchemy import create_engine
engine = create_engine('mysql+pymysql://root:1234@127.0.0.1:3306/mydb')
df = pd.read_sql('SELECT stock_id, COUNT(*) c FROM TaiwanStockPrice GROUP BY stock_id', engine)
print(df)
"
```

✅ **預期**：印出各股票的筆數統計。

---

## 清理

```bash
docker compose -f docker-compose-local.yml down       # 保留資料
docker compose -f docker-compose-local.yml down -v    # 連 MySQL 資料一起清
```

> `down -v` 會刪掉 `mysql` volume，下次啟動資料會清空。

---

## 本集完成清單

- [ ] 啟動 mysql + phpmyadmin，curl 8080 = 200
- [ ] phpMyAdmin 登入 root/1234，看到 mydb
- [ ] 理解 `upload_data_to_mysql` 的 SQLAlchemy 連線與 `to_sql`
- [ ] Python 測試連線成功（connected to: mydb）
- [ ] 完整 pipeline：infra + worker 全開 → 寫 DB 版 producer 發任務
- [ ] Worker log 看到 saved / succeeded
- [ ] SQL 查詢驗證 TaiwanStockPrice 有資料

---

## 下集預告

下一集學 Celery 進階與錯誤處理：環境變數切換、retry / requeue / reject 三種失敗行為、殺 Worker 看訊息回 queue，以及完整系統預演。
