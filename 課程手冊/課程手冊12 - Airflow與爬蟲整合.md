# 第 12 章：Airflow 接上爬蟲 pipeline — 兩種串法與完整 ETL

> 積木都齊了，這一章合體：讓 Airflow 指揮你的台股爬蟲。你會跑兩種串法——「Airflow 自己做」和「Airflow 指揮 Celery 做」——並理解它們各自適合什麼場景。前面所有章節在這裡會合。

---

## 做完這一章，你會做到

1. 跑 `stock_crawler_dag`：Airflow 直接呼叫爬蟲，10 支股票寫進 MySQL。
2. 跑 `stock_crawler_producer_dag`：Airflow 只發任務，Celery worker 執行——親眼看兩層分工。
3. 跑 `stock_crawler_etl_dag`：爬蟲 + 建 VIEW + 建實體表的完整 ETL。
4. 分得清 LocalExecutor 與 CeleryExecutor，看出後者怎麼回扣你學過的 Celery。
5. 會用 Airflow UI 的 Graph / Grid / Logs 監控與除錯。

---

## 先搞懂：同一件事的兩種串法

| | `stock_crawler_dag`（直接呼叫）| `stock_crawler_producer_dag`（透過 Celery）|
|---|---|---|
| 誰執行爬蟲 | Airflow 自己的 worker 行程 | 獨立的 Celery worker 池 |
| DAG 的 task 做什麼 | 跑 `crawler_finmind(stock_id)` | 跑 `crawler_finmind.delay(stock_id)`（只發任務）|
| DAG 等不等結果 | 等（爬完 task 才變綠）| 不等（發完就綠，fire and forget）|
| 需要哪些服務 | Airflow + MySQL | Airflow + MySQL + RabbitMQ + Celery worker |
| 適合 | 量小、流程單純 | 量大、要把執行負載跟編排分開、worker 可獨立 scale |

> **為什麼要多繞一層 Celery？** 直接呼叫簡單，但爬蟲會佔住 Airflow 的執行資源；量一大，Airflow 忙著爬蟲就顧不了編排。改成 `.delay()`，Airflow 只負責「觸發和監控」，實際負載交給 Celery worker 池——而那個池子你第 3 章就會 scale 了。

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `airflow/dags/stock_crawler_dag.py` | 串法一 | 直接呼叫 `crawler_finmind` 爬 10 支股票 |
| `airflow/dags/stock_crawler_producer_dag.py` | 串法二 | 透過 `.delay()` 發任務給 Celery |
| `airflow/dags/stock_crawler_etl_dag.py` | 完整 ETL | 爬蟲 + `crawler/mysql.py` 建 VIEW / 實體表 |
| `airflow/dags/stock_crawler_etl_bigquery_dag.py` | 雲端 ETL | MySQL → BigQuery（需第 14 章 GCP 憑證）|
| `crawler/mysql.py` | 工具模組 | `create_view` / `create_table_from_view` |

---

## 一行一行讀懂 `stock_crawler_dag`

```python
from crawler.tasks_crawler_finmind import crawler_finmind

STOCK_IDS = ["2330", "2317", "2454", "2308", "2382",
             "0050", "0056", "00713", "00878", "006208"]

with DAG(
    dag_id="stock_crawler_dag",
    schedule_interval="0 18 * * 1-5",   # 週一到週五 18:00（收盤後）
    catchup=False,
    max_active_runs=1,
    tags=["stock", "crawler", "finmind"],
) as dag:

    start_task = BashOperator(task_id="start_crawler",
                              bash_command="echo 開始執行台股爬蟲任務...")
    stock_branch = DummyOperator(task_id="stock_branch")

    stock_tasks = []
    for stock_id in STOCK_IDS:
        task = PythonOperator(
            task_id=f"crawl_stock_{stock_id}",
            python_callable=crawler_finmind,   # 直接呼叫我們寫的爬蟲
            op_args=[stock_id],
        )
        stock_tasks.append(task)

    end_task = BashOperator(task_id="end_crawler",
                            bash_command="echo 完成！",
                            trigger_rule="all_success")

    start_task >> stock_branch >> stock_tasks >> end_task
```

逐段白話：

- `schedule_interval="0 18 * * 1-5"`：**週一到週五下午 6 點**（台股收盤後）自動跑。這正是取代第 9 章 APScheduler 的位置，但多了歷史、依賴、補跑、UI。
- `max_active_runs=1`：同時最多一個 run 在跑，避免上一輪還沒完下一輪又開。
- **用 for 迴圈生 task**：10 支股票 = 10 個 `PythonOperator`，跟第 1 章 producer 的 for 迴圈異曲同工——只是這次生的是「DAG 的步驟」而不是「佇列訊息」。
- `python_callable=crawler_finmind`：直接掛你第 5 章寫的函式。**注意掛的是函式本身**（沒有括號、沒有 .delay）——Airflow 的 worker 到時會自己呼叫它。
- `trigger_rule="all_success"`：end 要等**全部**爬取成功才跑。
- 依賴鏈 `start >> branch >> [10 個平行] >> end`：Graph 上就是一張扇形圖。

> 對比 `stock_crawler_producer_dag`：幾乎一樣，只是 callable 換成一個包了 `.delay()` 的小函式。一字之差，執行的地方就從「Airflow 裡面」變成「Celery worker 池」。

---

## 一步一步跟著做

### 準備：把需要的服務全部起來

這一章要同時跑 Airflow + MySQL +（串法二再加）RabbitMQ 和 Celery worker：

```bash
docker network create my_network 2>/dev/null
cp .env.example .env    # 沒有 .env 的話

# MySQL + RabbitMQ（compose-advanced 網路版，跟 Airflow 同一個 my_network）
docker compose -f compose-advanced/mysql.yml up -d
docker compose -f compose-advanced/rabbitmq.yml up -d

# Airflow
docker compose -f airflow/docker-compose-airflow.yml up -d
# 首次啟動照第 10 章 Step 4：等 init 完成 → restart webserver/scheduler
```

確認 MySQL 有 `mydb`：

```bash
docker exec compose-advanced-mysql-1 mysql -uroot -p1234 -e "CREATE DATABASE IF NOT EXISTS mydb"
```

> ⚠️ 這裡 phpMyAdmin（8080）不能跟 Airflow 同時開，前面章節提過。用 `docker exec ... mysql` 驗證資料即可。

### 串法一：`stock_crawler_dag`（Airflow 直接爬）

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_dag
```

**觀察：**

1. UI → `stock_crawler_dag` → Graph：`start → stock_branch → 10 個爬取 task 平行 → end`，方格逐一變綠。
2. 每個 task 約 1~2 秒（打 FinMind API + 寫 MySQL）。
3. 點任一 `crawl_stock_XXXX` → Logs，能看到 DataFrame 輸出——跟你第 5 章在 worker log 看到的一模一樣，只是換了執行的地方。

**驗證資料入庫：**

```bash
docker exec compose-advanced-mysql-1 mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice GROUP BY stock_id ORDER BY stock_id"
```

> ✅ 10 支股票各有數百筆，就過關。

### 串法二：`stock_crawler_producer_dag`（Airflow 指揮、Celery 幹活）

先把 Celery worker 池起來（第 3 章的網路版 worker）：

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml up -d
```

觸發：

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_producer_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_producer_dag
```

**觀察（這是本章最有意思的一段）：**

| 看哪裡 | 你會看到 | 為什麼 |
|--------|---------|--------|
| Airflow Graph | 10 個 task **秒變綠** | 它們只是 `.delay()` 發任務，不等爬完 |
| Flower (5555) | 10 筆 `crawler_finmind` 任務陸續 SUCCESS | 真正的執行在 Celery worker |
| worker log | `docker compose -f compose-advanced/docker-compose-worker-network.yml logs crawler_twse \| tail -20` | 看到 DataFrame + succeeded |

> ✅ 「Airflow 全綠了，Flower 還在跑」——這個時間差就是兩層分工的鐵證。Airflow 是總指揮，Celery 是施工隊。

### 完整 ETL：`stock_crawler_etl_dag`

這支 DAG 在爬完之後多兩步：用 `crawler/mysql.py` 建每日去重 VIEW、再從 VIEW 建實體表：

```
start → stock_branch → [10 個爬取] → etl_task → create_view → create_table → end
```

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_etl_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_etl_dag
```

**驗證 ETL 產物：**

```bash
# VIEW 建出來了
docker exec compose-advanced-mysql-1 mysql -uroot -p1234 mydb -e \
  "SHOW FULL TABLES WHERE Table_type = 'VIEW'"

# 實體表有資料
docker exec compose-advanced-mysql-1 mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) FROM stock_price_daily GROUP BY stock_id"
```

> ✅ 看到 `vw_stock_price_daily` 這個 VIEW 和 `stock_price_daily` 實體表，代表「爬取 → 清理 → 產出分析表」一條 DAG 全包了。這個 VIEW 正是第 8 章你在 Metabase 用過的那個——現在它由 Airflow 自動維護。

### （選做）CeleryExecutor 版 Airflow

上面 Airflow 自己用的是 LocalExecutor（單機子行程）。生產環境常用 CeleryExecutor——Airflow 把**自己的 task** 也丟給 Celery worker 跑：

```bash
docker compose -f airflow/docker-compose-airflow-celery.yml up -d
```

這個版本額外啟動 Redis + Celery Worker。你學過的 Celery 在這裡以「Airflow 的執行引擎」身分再登場一次。

| | LocalExecutor | CeleryExecutor |
|---|---|---|
| task 在哪跑 | Airflow 主機的子行程 | Celery worker（可跨機器）|
| 類比 | 第 9 章單機排程 | 第 1 章分散式 |
| 適合 | 開發、小量 | 生產、大量、要水平擴充 |

---

## 監控與除錯

| UI 頁面 | 看什麼 |
|---------|--------|
| **Graph** | 這一次 run 的依賴圖與各 task 狀態 |
| **Grid** | 歷史每次 run 的矩陣（哪天失敗一眼看出）|
| **Task Logs** | 單一 task 的完整輸出（除錯第一站）|
| **Flower** | 串法二時看 Celery 端的執行狀態 |

| 症狀 | 先看哪裡 | 可能原因 |
|------|---------|---------|
| task 紅了 | 該 task 的 Logs | API 失敗、DB 連不上……看錯誤訊息 |
| DAG 沒出現在列表 | scheduler log | DAG 檔案語法錯誤 |
| producer_dag 全綠但資料沒進 DB | Flower / worker log | Celery worker 沒開、或連錯 broker |
| 爬蟲 task 超時 | Logs + FinMind 限流 | 調大 `execution_timeout`、減少股票數 |
| ETL 階段失敗 | create_view 的 Logs | MySQL 連線（host 要是 `mysql`）|

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | `stock_crawler_dag` 10 個 task 綠、MySQL 有 10 支股票 | Airflow 能直接指揮爬蟲 |
| 2 | producer_dag 秒綠、Flower 陸續 SUCCESS | 編排層與執行層分工 |
| 3 | ETL DAG 產出 VIEW + 實體表 | 一條 DAG 涵蓋完整 ETL |
| 4 | 失敗的 task 能單獨 Clear 重跑 | 編排引擎的核心價值 |

---

## 想一想（確認你懂了）

**Q1：`stock_crawler_dag`（直接呼叫）和 `stock_crawler_producer_dag`（用 `.delay()`）差在哪？各適合什麼情況？**

前者在 Airflow 的 worker 裡直接跑爬蟲，簡單、步驟少，適合量不大或想單純用 Airflow 的情況；後者把爬蟲丟給獨立的 Celery worker 池，Airflow 只觸發和監控，適合量大、想把執行負載跟編排分開、方便獨立擴充 worker 的情況。

**Q2：串法二時，Airflow 的 task 全綠是不是代表爬蟲成功了？**

**不是。** task 綠只代表「`.delay()` 發送成功」——訊息進了 RabbitMQ。爬蟲真正的成敗要看 Flower / worker log / MySQL 資料。這是 fire-and-forget 模式的代價：編排層看不到執行結果。要嚴謹追蹤就得（a）用串法一、（b）讓 DAG 再加一步「驗證資料筆數」、或（c）用 CeleryExecutor 把執行結果接回 Airflow。

**Q3：LocalExecutor 和 CeleryExecutor 的關係，像你前面學過的哪兩章？**

LocalExecutor 像第 9 章：單機、自己的行程做事。CeleryExecutor 像第 1 章：把工作丟進 broker、由一群 worker 分散消化。Airflow 只是把你學過的東西「換一層再用一次」——編排層的執行引擎本身就可以是 Celery。

---

## 換你試試看

**練習 1：故意讓一支股票失敗，再單獨補跑**

把 `stock_crawler_dag` 裡某個股票代碼改成不存在的（例如 `"9999999"`），觸發後那個 task 會失敗、end 卡住。改回正確代碼，然後在 UI 上**只 Clear 那一個失敗的 task**，看整條 DAG 接著完成。這是「只補跑失敗那一步」——APScheduler 做不到、Airflow 的招牌能力。

**練習 2：幫 producer_dag 加一步驗證**

在 `stock_crawler_producer_dag` 的最後加一個 PythonOperator，用 `crawler/mysql.py` 的 `query_to_dataframe` 查 `TaiwanStockPrice` 筆數並 print。這樣「發完任務」之後 DAG 會多一步「確認資料有進來」，弭平 Q2 講的盲區。

**練習 3：對照 APScheduler 和 Airflow**

把你第 9 章寫的 APScheduler 排程，和這章的 `stock_crawler_dag` 放在一起，列出三件「Airflow 做得到、APScheduler 做不到」的事。這個對照會讓你真正理解為什麼生產環境要用 Airflow。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| DAG 抓不到 `crawler` 模組 | volume 沒掛好 `../crawler` | 從 stock-crawler 根目錄啟動 compose |
| producer_dag 發了但沒人做 | Celery worker 沒開 | `docker compose -f compose-advanced/docker-compose-worker-network.yml up -d` |
| worker 連不上 rabbitmq | 不在同一個 my_network | 確認 rabbitmq / worker compose 都掛 my_network |
| ETL 的 create_view 失敗 | MySQL host 不對 | Airflow 容器內要用 `MYSQL_HOST=mysql`（compose 已設）|
| BigQuery DAG 跑不動 | 需要 GCP 憑證 | 接第 14 章的 GCP 設定，沒帳號先跳過 |

---

## 收工

```bash
docker compose -f airflow/docker-compose-airflow.yml down
docker compose -f compose-advanced/docker-compose-worker-network.yml down
docker compose -f compose-advanced/rabbitmq.yml down
docker compose -f compose-advanced/mysql.yml down
```

---

## 這一章你學到了

- 兩種串法：Airflow 直接做（簡單）vs Airflow 指揮 Celery（分工、可擴充）。
- 「Airflow 全綠 ≠ 爬蟲成功」——fire-and-forget 要自己補驗證。
- ETL DAG 讓「爬取 → 清理 → 分析表」變成一張可補跑、可監控的圖。
- LocalExecutor / CeleryExecutor：你學過的單機與分散式，在編排層重演。

## 下一章要做什麼

每個部件都會了、也串起來了。**下一章把全部服務用一個 compose 一鍵啟動，跑一次七步驟端到端驗證——看見整套系統的全貌。**
