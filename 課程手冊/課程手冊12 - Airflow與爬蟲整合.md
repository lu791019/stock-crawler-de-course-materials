# 第 12 章：Airflow 接上爬蟲 pipeline — 三種串法與完整 ETL

> 積木都齊了，這一章整合：讓 Airflow 接上你的台股爬蟲。你會跑三種串法——「Airflow 自己做」、「Airflow 指揮 Celery 做」、「連發任務的程式都容器化」——並理解它們各自適合什麼場景。前面所有章節在這裡會合。

---

## 做完這一章，你會做到

1. 跑 `stock_crawler_dag`：Airflow 直接呼叫爬蟲，10 支股票寫進 MySQL。
2. 跑 `stock_crawler_twse_tpex_dag`：上市/上櫃分組扇出、平行爬取、匯合——實務最常見的 DAG 形狀。
3. 跑 `stock_crawler_producer_dag`：Airflow 只發任務，Celery worker 執行——觀察兩層分工。
4. 跑 `stock_crawler_docker_producer_dag`：連發任務的程式都容器化——DockerOperator 的實戰應用。
5. 跑 `stock_crawler_etl_dag`：爬蟲 + 建 VIEW + 建實體表的完整 ETL。
6. 分得清 LocalExecutor 與 CeleryExecutor，看出後者怎麼回扣你學過的 Celery。
7. 會用 Airflow UI 的 Graph / Grid / Logs 監控與除錯。

---

## 先搞懂：同一件事的兩種基本串法（串法三是串法二的容器化變形，後面介紹）

| | `stock_crawler_dag`（直接呼叫）| `stock_crawler_producer_dag`（透過 Celery）|
|---|---|---|
| 誰執行爬蟲 | Airflow 自己的 worker 行程 | 獨立的 Celery worker 池 |
| DAG 的 task 做什麼 | 跑 `crawler_finmind(stock_id)` | 用 `apply_async(queue=...)` 發任務（只發不做）|
| DAG 等不等結果 | 等（爬完 task 才變綠）| 不等（發完就綠，fire and forget）|
| 需要哪些服務 | Airflow + MySQL | Airflow + MySQL + RabbitMQ + Celery worker |
| 適合 | 量小、流程單純 | 量大、要把執行負載跟編排分開、worker 可獨立 scale |

> **為什麼要多繞一層 Celery？** 直接呼叫簡單，但爬蟲會佔住 Airflow 的執行資源；量一大，Airflow 忙著爬蟲就顧不了編排。改成發任務進佇列，Airflow 只負責「觸發和監控」，實際負載交給 Celery worker 池——而那個池子你第 3 章就會 scale 了。

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `airflow/dags/stock_crawler_dag.py` | 串法一 | 直接呼叫 `crawler_finmind` 爬 10 支股票 |
| `airflow/dags/stock_crawler_twse_tpex_dag.py` | 串法一延伸 | 上市/上櫃**雙分組**平行爬取後匯合 |
| `airflow/dags/stock_crawler_producer_dag.py` | 串法二 | `apply_async(queue="twse")` 發任務給 Celery |
| `airflow/dags/stock_crawler_docker_producer_dag.py` | 串法三 | DockerOperator 起容器跑第 3 章多佇列 producer |
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

> 對比 `stock_crawler_producer_dag`：幾乎一樣，只是 callable 換成一個發任務的小函式：
>
> ```python
> def trigger_stock_crawler(stock_id):
>     crawler_finmind.apply_async(kwargs={"stock_id": stock_id}, queue="twse")
> ```
>
> 一個函式之差，執行的地方就從「Airflow 裡面」變成「Celery worker 池」。**注意用的是 `apply_async(queue="twse")` 而不是 `.delay()`**：worker 池是第 3 章的分流版，只聽 `twse` / `tpex` 佇列——`.delay()` 發到預設佇列會沒有人消費，任務永遠卡在 RabbitMQ 裡。發任務時要跟 worker 聽的佇列對上，這是分流架構的紀律（清單裡十支都是上市標的，所以都進 `twse`）。

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

### 串法一延伸：`stock_crawler_twse_tpex_dag`（分組扇出＋匯合）

`stock_crawler_dag` 是「一組全平行」——10 支股票不分類、齊頭並進。實務的清單常常**有分類**：上市 / 上櫃、來源 A / 來源 B、日資料 / 月資料……這時 DAG 的慣用形狀是**每類一個分組節點，組內平行，最後匯合**：

```
                 ┌─ twse_branch ─┬─ crawl_twse_2330 ─┐
                 │               ├─ crawl_twse_2317 ─┤
start_crawler ───┤               └─ crawl_twse_2454 ─┼─── end_crawler
                 │               ┌─ crawl_tpex_6488 ─┤
                 └─ tpex_branch ─┼─ crawl_tpex_3105 ─┤
                                 └─ crawl_tpex_8069 ─┘
```

核心程式碼只比 `stock_crawler_dag` 多一層迴圈：

```python
STOCK_GROUPS = {
    "twse": ["2330", "2317", "2454"],  # 上市
    "tpex": ["6488", "3105", "8069"],  # 上櫃
}

for market, stock_ids in STOCK_GROUPS.items():
    branch = DummyOperator(task_id=f"{market}_branch")

    crawl_tasks = []
    for stock_id in stock_ids:
        task = PythonOperator(
            task_id=f"crawl_{market}_{stock_id}",
            python_callable=crawler_finmind,
            op_args=[stock_id],
        )
        crawl_tasks.append(task)

    start_task >> branch >> crawl_tasks >> end_task
```

逐段白話：

- **dict 分組 + 兩層迴圈**：外層迴圈每個市場生一個分組節點、內層迴圈生組內的爬取 task。之後要加第三組（例如 ETF），只要在 dict 加一個 key——圖上自動多出第三組扇形分支，一行依賴都不用改。
- **分組節點是 `DummyOperator`**：不做事，純粹把圖整理清楚——第 11 章積木 5 的實戰應用。
- **分組概念你早就會**：第 3 章多佇列分流把任務分進 `twse` / `tpex` **佇列**，這裡是把 task 分進兩個**圖形分支**——同一個分類思維，一次用在執行層、一次用在編排層。
- `trigger_rule="all_success"` 的 end 同時接住兩組——**任何一組有一支失敗，end 就不跑**，你會在 Graph 上一眼看到是哪一組的哪一支紅了。

跑起來：

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_twse_tpex_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_twse_tpex_dag
```

**觀察：**

1. Graph 上是兩組扇形分支：`start → 兩個 branch → 各三支平行 → end`。
2. 六個爬取 task **同時**起跑——分組只是圖形上的整理，不影響平行度。

**驗證上櫃資料入庫**（上櫃三支是第一次爬，之前資料庫裡沒有）：

```bash
docker exec compose-advanced-mysql-1 mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice \
   WHERE stock_id IN ('6488','3105','8069') GROUP BY stock_id"
```

> ✅ 三支上櫃股票各有數百筆，代表分組扇出的每一條路都真的跑到了。

### 串法二：`stock_crawler_producer_dag`（Airflow 指揮、Celery 執行）

先把 Celery worker 池起來（第 3 章的網路版 worker）：

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml up -d
```

觸發：

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_producer_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_producer_dag
```

**觀察（本章的核心對照）：**

| 看哪裡 | 你會看到 | 為什麼 |
|--------|---------|--------|
| Airflow Graph | 10 個 task **立即變綠** | 它們只是發任務進佇列，不等爬完 |
| Flower (5555) | 10 筆 `crawler_finmind` 任務陸續 SUCCESS | 真正的執行在 Celery worker |
| worker log | `docker compose -f compose-advanced/docker-compose-worker-network.yml logs crawler_twse \| tail -20` | 看到 DataFrame + succeeded |

> ✅ 「Airflow 全綠了，Flower 還在跑」——這個時間差直接顯示兩層分工：Airflow 負責編排，Celery 負責執行。

### 串法三：`stock_crawler_docker_producer_dag`（連發任務的程式也容器化）

串法二的發任務程式碼跑在 **Airflow 的 Python 環境裡**——這表示 Airflow image 必須裝著 `crawler` 模組和它的所有依賴。串法三把這個耦合也拆掉：**用第 11 章積木 4 的 DockerOperator，起一個臨時容器來跑 producer**，Airflow 本身完全不需要認識爬蟲的程式碼：

```python
docker_crawler_task = DockerOperator(
    task_id="docker_stock_crawler",
    image="stock-crawler:latest",                             # 第 3 章 build 的爬蟲 image
    command="uv run python -m crawler.producer_multi_queue",  # 第 3 章的多佇列 producer
    network_mode="my_network",                                # 跟 RabbitMQ / MySQL 同網路
    environment={
        "TZ": "Asia/Taipei",
        "RABBITMQ_HOST": "rabbitmq",
        "MYSQL_HOST": "mysql",
    },
    auto_remove=True,                                         # 容器跑完自動刪除
)
```

三個關鍵設定，各對應一個會踩的坑：

- **`environment` 必須明給連線資訊**：這個臨時容器不是 compose 起的，不會讀 `.env`、也沒有 compose 檔幫你塞環境變數。漏了 `RABBITMQ_HOST`，容器內預設連 `127.0.0.1`（容器自己），直接 Connection refused。
- **`network_mode="my_network"`**：不掛進同一個網路，`rabbitmq` 這個名字解析不到。
- **`command` 跑的是第 3 章的 `producer_multi_queue`**：它用 `apply_async(queue=...)` 把任務分流到 `twse` / `tpex` 佇列——跟 worker 池聽的佇列對上（串法二講過的同一條紀律）。

執行鏈變成四層：**Airflow（編排）→ Docker 臨時容器（producer）→ RabbitMQ（佇列）→ Celery worker（執行）**。每一層都是你學過的積木，這支 DAG 只是把它們接起來。

跑起來：

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_docker_producer_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_docker_producer_dag
```

**觀察：**

1. `docker_stock_crawler` 的 Logs 裡有 producer 的輸出（send task 訊息）——DockerOperator 會把容器的 stdout 接回 Airflow log。
2. `docker ps -a` 看不到那個臨時容器——`auto_remove=True` 跑完就清掉了。
3. Flower / worker log 看到任務被 twse、tpex worker 分別消化。

**驗證資料入庫**（`producer_multi_queue` 發的是 2330 → twse、00679B → tpex）：

```bash
docker exec compose-advanced-mysql-1 mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice \
   WHERE stock_id IN ('2330','00679B') GROUP BY stock_id"
```

> ✅ 兩支各有數百筆——尤其 `00679B` 走的是 tpex 佇列，它有資料代表分流的兩條路都通了。

**什麼時候選串法三？** 當爬蟲跟 Airflow 的依賴想徹底分離時：爬蟲換 Python 版本、加套件、改程式碼，都只要重 build 爬蟲 image，Airflow image 一動不動。代價是多管一個 image 和 docker.sock 掛載——第 11 章積木 4 講過的取捨，在真實 pipeline 再看一次。

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

這個版本額外啟動 Redis + Celery Worker。你學過的 Celery 在這裡以「Airflow 的執行引擎」身分再次出現。

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
| 2 | twse_tpex_dag 兩組同時平行、上櫃三支入庫 | 分組扇出＋匯合的 DAG 形狀 |
| 3 | producer_dag 立即全綠、Flower 陸續 SUCCESS | 編排層與執行層分工 |
| 4 | docker_producer_dag 成功、`00679B` 入庫 | DockerOperator 跑 producer、佇列分流兩條路都通 |
| 5 | ETL DAG 產出 VIEW + 實體表 | 一條 DAG 涵蓋完整 ETL |
| 6 | 失敗的 task 能單獨 Clear 重跑 | 編排引擎的核心價值 |

---

## 想一想（確認你懂了）

**Q1：`stock_crawler_dag`（直接呼叫）和 `stock_crawler_producer_dag`（用 `.delay()`）差在哪？各適合什麼情況？**

前者在 Airflow 的 worker 裡直接跑爬蟲，簡單、步驟少，適合量不大或想單純用 Airflow 的情況；後者把爬蟲丟給獨立的 Celery worker 池，Airflow 只觸發和監控，適合量大、想把執行負載跟編排分開、方便獨立擴充 worker 的情況。

**Q2：串法二時，Airflow 的 task 全綠是不是代表爬蟲成功了？**

**不是。** task 綠只代表「任務發送成功」——訊息進了 RabbitMQ。爬蟲真正的成敗要看 Flower / worker log / MySQL 資料。這是 fire-and-forget 模式的代價：編排層看不到執行結果。要嚴謹追蹤就得（a）用串法一、（b）讓 DAG 再加一步「驗證資料筆數」、或（c）用 CeleryExecutor 把執行結果接回 Airflow。

**Q3：LocalExecutor 和 CeleryExecutor 的關係，像你前面學過的哪兩章？**

LocalExecutor 像第 9 章：單機、自己的行程做事。CeleryExecutor 像第 1 章：把工作丟進 broker、由一群 worker 分散消化。Airflow 只是把你學過的東西「換一層再用一次」——編排層的執行引擎本身就可以是 Celery。

---

## 換你試試看

**練習 1：故意讓一支股票失敗，再單獨補跑**

把 `stock_crawler_dag` 裡某個股票代碼改成不存在的（例如 `"9999999"`），觸發後那個 task 會失敗、end 卡住。改回正確代碼，然後在 UI 上**只 Clear 那一個失敗的 task**，看整條 DAG 接著完成。這是「只補跑失敗那一步」——APScheduler 做不到、Airflow 的核心能力。

**練習 2：幫 producer_dag 加一步驗證**

在 `stock_crawler_producer_dag` 的最後加一個 PythonOperator，用 `crawler/mysql.py` 的 `query_to_dataframe` 查 `TaiwanStockPrice` 筆數並 print。這樣「發完任務」之後 DAG 會多一步「確認資料有進來」，弭平 Q2 講的盲區。

**練習 3：幫 twse_tpex_dag 加第三組**

在 `STOCK_GROUPS` 加一組 `"etf": ["0050", "0056", "00713"]`，重新觸發，確認 Graph 自動多出第三組扇形分支、三組同時平行。確認「加一組 = 加一個 key」——迴圈生 task 的擴充只改資料，逐一手寫 task 則要同步改依賴設定。

**練習 4：對照 APScheduler 和 Airflow**

把你第 9 章寫的 APScheduler 排程，和這章的 `stock_crawler_dag` 放在一起，列出三件「Airflow 做得到、APScheduler 做不到」的事。這個對照會讓你真正理解為什麼生產環境要用 Airflow。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| DAG 抓不到 `crawler` 模組 | volume 沒掛好 `../crawler` | 從 stock-crawler 根目錄啟動 compose |
| producer_dag 發了但沒人做 | Celery worker 沒開 | `docker compose -f compose-advanced/docker-compose-worker-network.yml up -d` |
| 發了任務、worker 也開著，但佇列一直堆積 | 佇列對不上：發到預設佇列，worker 只聽 `-Q twse`/`tpex` | 發送端用 `apply_async(queue=...)` 指定 worker 聽的佇列；`rabbitmqctl list_queues name messages consumers` 看哪條佇列有訊息沒消費者 |
| docker_producer 的容器 Connection refused | 臨時容器沒讀 .env，`RABBITMQ_HOST` 預設 127.0.0.1 | DockerOperator 的 `environment` 明給 `RABBITMQ_HOST` / `MYSQL_HOST` |
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

- 三種串法：Airflow 直接做（簡單）、指揮 Celery（分工、可擴充）、DockerOperator 跑 producer（依賴徹底分離）。
- 發任務要跟 worker 聽的佇列對上：分流版 worker 只聽 `-Q` 指定的佇列，`apply_async(queue=...)` 指定、`.delay()` 進預設佇列會沒人消費。
- 分組扇出＋匯合：dict 分組 + 兩層迴圈生 task，加一組只要加一個 key。
- 「Airflow 全綠 ≠ 爬蟲成功」——fire-and-forget 要自己補驗證。
- ETL DAG 讓「爬取 → 清理 → 分析表」變成一張可補跑、可監控的圖。
- LocalExecutor / CeleryExecutor：你學過的單機與分散式，在編排層重演。

## 下一章要做什麼

每個部件都會了、也串起來了。**下一章把全部服務用一個 compose 一鍵啟動，跑一次七步驟端到端驗證——看見整套系統的全貌。**
