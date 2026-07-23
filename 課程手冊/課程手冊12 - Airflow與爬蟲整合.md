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
| DAG 等不等結果 | 等——爬完了 task 才會變綠 | 不等——發送完就變綠（fire and forget）|
| 需要哪些服務 | Airflow + MySQL | Airflow + MySQL + RabbitMQ + Celery worker |
| 適合 | 資料量小、流程單純的情況 | 資料量大、想把執行負載跟編排分開、worker 需要獨立擴充的情況 |

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
- `op_args=[stock_id]`：呼叫 `python_callable` 時要帶進去的**參數清單**。因為上一條掛的是「函式本身」不能加括號，參數就得另外給——到時 Airflow 執行的效果等於 `crawler_finmind(stock_id)`。字典形式的版本是 `op_kwargs={"stock_id": stock_id}`，等於 `crawler_finmind(stock_id=stock_id)`。
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

這一章的服務全部從你用了一整路的 `docker-compose-local.yml` 起——**MySQL 的資料也直接延續前面章節爬進去的那一份**。Airflow 是另一份 compose 檔起的容器，預設連不到這邊的服務（兩份 compose 各自有私有網路、名字互相解析不到）；解法是建一張兩邊共用的網路 `my_network`，把 Airflow 要連的容器掛上去。

**準備 0：改 phpMyAdmin 的對外 port（只需要做一次）**

Airflow 的網頁介面要用 8080，跟 phpMyAdmin 撞了。打開 `docker-compose-local.yml`，找到 phpmyadmin 的 `ports`，把 `"8080:80"` 改成：

```yaml
    ports:
      - "8083:80"
```

之後 phpMyAdmin 改走 http://localhost:8083 ，兩個介面就能同時開。

> 改了這個檔案之後，未來 `git pull` 課程更新時如果剛好也動到它，會出現衝突——遇到就保留你改的 8083 那行。

**準備 1：建共用網路（建過就跳過）＋確認 .env**

```bash
docker network create my_network 2>/dev/null
cp .env.example .env    # 沒有 .env 的話
```

**準備 2：起服務——指定服務名，不要 up 全部**

```bash
docker compose -f docker-compose-local.yml up -d rabbitmq flower mysql phpmyadmin worker_twse worker_tpex
```

> ⚠️ 不帶服務名的 `up -d` 會把整個檔案的服務全部起來（含 MongoDB 等這章用不到的），再疊上 Airflow 會超出 4GB 記憶體的負荷——指定服務名是這一章的紀律。

**準備 3：把四個容器掛上共用網路**

```bash
docker network connect my_network mysql
docker network connect my_network rabbitmq
docker network connect my_network flower
docker network connect my_network phpmyadmin
```

`docker network connect` 是「**加掛**」：容器同時留在 local.yml 自己的內部網路上，又多掛了一張 `my_network`——worker 和服務之間照常互通，Airflow 也連得到它們。

> ⚠️ 這個掛載在容器**重建**後會消失：`docker compose down` 再 `up` 之後，準備 3 要**重新執行一次**（單純 `stop`／`start`／`restart` 不受影響）。忘了重掛的症狀，就是 Airflow 突然連不到 mysql 或 rabbitmq。

**準備 4：起 Airflow**

```bash
docker compose -f airflow/docker-compose-airflow.yml up -d
# 首次啟動照第 10 章 Step 4：等 init 完成 → restart webserver/scheduler
```

> 💡 Airflow 的 compose 檔裡明寫了 `MYSQL_HOST: mysql`、`RABBITMQ_HOST: rabbitmq` 覆蓋 `.env` 的值——因為 `.env` 裡的 `127.0.0.1` 是給「程式跑在主機上」（第 1-9 章）的情境用的；Airflow 自己是容器，要用容器名去找服務。`environment` 的優先序高於 `env_file`，所以 `.env` 不用改、也不用來回切換。

最後確認 MySQL 有 `mydb`：

```bash
docker exec mysql mysql -uroot -p1234 -e "CREATE DATABASE IF NOT EXISTS mydb"
```

### 串法一：`stock_crawler_dag`（Airflow 直接爬）

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_dag
```

**觀察：**

1. UI → `stock_crawler_dag` → Graph：`start → stock_branch → 10 個爬取 task 平行 → end`，方格逐一變綠。
2. 每個 task 做兩件事：打 FinMind API、寫 MySQL。
3. 點任一 `crawl_stock_XXXX` → Logs，能看到 DataFrame 輸出——跟你第 5 章在 worker log 看到的一模一樣，只是換了執行的地方。

**驗證資料入庫：**

```bash
docker exec mysql mysql -uroot -p1234 mydb -e \
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
- `trigger_rule="all_success"` 的 end 同時接住兩組——**任何一組有一支失敗，end 就不跑**，你可以在 Graph 上直接看到是哪一組的哪一支變紅。

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
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice \
   WHERE stock_id IN ('6488','3105','8069') GROUP BY stock_id"
```

> ✅ 三支上櫃股票各有數百筆，代表分組扇出的每一條路都真的跑到了。

### 串法二：`stock_crawler_producer_dag`（Airflow 指揮、Celery 執行）

worker 在準備段已經起了——`crawler_twse` 和 `crawler_tpex` 兩個容器，各自聽 `twse`／`tpex` 佇列（第 3 章的分流版）。直接觸發：

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_producer_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_producer_dag
```

**觀察（本章的核心對照）：**

| 看哪裡 | 你會看到 | 為什麼 |
|--------|---------|--------|
| Airflow Graph | 10 個 task **立即變綠** | 它們只是發任務進佇列，不等爬完 |
| Flower (5555) | 10 筆 `crawler_finmind` 任務陸續 SUCCESS | 真正的執行在 Celery worker |
| worker log | `docker logs crawler_twse | tail -20` | 看到 DataFrame + succeeded |

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
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice \
   WHERE stock_id IN ('2330','00679B') GROUP BY stock_id"
```

> ✅ 兩支各有數百筆——尤其 `00679B` 走的是 tpex 佇列，它有資料代表分流的兩條路都通了。

**什麼時候選串法三？** 當爬蟲跟 Airflow 的依賴想徹底分離時：爬蟲換 Python 版本、加套件、改程式碼，都只要重 build 爬蟲 image，Airflow image 一動不動。代價是多管一個 image 和 docker.sock 掛載——第 11 章積木 4 講過的取捨，在真實 pipeline 再看一次。

### 完整 ETL：`stock_crawler_etl_dag`

前面三種串法做的都是同一件事：把資料爬回來。這支 DAG 是本章第一支**多階段**的工作流——爬完資料之後，接著在資料庫裡把資料整理成分析用的表。整條流程長這樣：

```
start → stock_branch → [10 個爬取] → etl_task → create_view → create_table → end
```

它分成三段，每一段的工作內容和它在流程裡扮演的角色如下：

**第一段：爬取（10 個平行 task）**——跟 `stock_crawler_dag` 完全相同的做法：10 個 PythonOperator 平行呼叫 `crawler_finmind`，各自打 FinMind API、把股價寫進 MySQL 的 `TaiwanStockPrice`。這一段是整條 DAG 最重的部分——10 個 task 同時執行，每個都是一個獨立的 Python 行程。

**第二段：`etl_task`（匯合點）**——一個 DummyOperator，它自己不做任何事，職責是「守住階段的分界」：**10 支股票全部爬成功，流程才會通過它、進入 ETL 段**。只要有任何一支爬取失敗，後面的 ETL 就不會執行——這樣可以避免「用不完整的資料去建分析表」。這是第 11 章積木 5 的實際應用。

**第三段：ETL（兩個接續的 task）**——兩個 PythonOperator，掛的函式都放在 `crawler/mysql.py`：
- `create_view`：在 MySQL 建**每日去重 VIEW**（`vw_stock_price_daily`）——同一支股票同一天有多筆時只留一筆，這是「查詢端去重」（第 6 章講過的另一端）。
- `create_table`：從 VIEW 把結果**存成實體表**（`stock_price_daily`）——VIEW 每次查詢才即時計算，實體表把結果落地，重複查詢時快得多。

三段合起來，這支 DAG 表達的是前面串法都沒有的能力：**「先全部完成 A 階段、才進入 B 階段」的階段依賴**。而它建出來的 VIEW，正是第 8 章你在 Metabase 接過的那個——跑通這支 DAG 之後，那張分析表就不再需要手動維護，排程到了就自動重爬、重建。

ETL 段的三個 task 長這樣：

```python
etl_task = DummyOperator(task_id="etl_task")   # 匯合點：10 支全爬完才進 ETL

create_view_task = PythonOperator(
    task_id="create_stock_price_daily_view",
    python_callable=create_stock_price_daily_view,      # 來自 crawler/mysql.py
)
create_table_task = PythonOperator(
    task_id="replace_stock_price_daily_table",
    python_callable=replace_stock_price_daily_table,    # 來自 crawler/mysql.py
)

start_task >> stock_branch >> stock_tasks >> etl_task
etl_task >> create_view_task >> create_table_task >> end_task
```

補一個程式碼層面的觀察：**DAG 檔裡沒有半行 SQL**——建 VIEW、建表的 SQL 全部住在 `crawler/mysql.py`。「DAG 只描述流程、業務邏輯放在 crawler/」的原則再驗證一次：要改 VIEW 的定義就去改 `mysql.py`，DAG 完全不用動。

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_etl_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_etl_dag
```

**驗證 ETL 產物：**

```bash
# VIEW 建出來了
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SHOW FULL TABLES WHERE Table_type = 'VIEW'"

# 實體表有資料
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) FROM stock_price_daily GROUP BY stock_id"
```

> ✅ 看到 `vw_stock_price_daily` 這個 VIEW 和 `stock_price_daily` 實體表，代表「爬取 → 清理 → 產出分析表」一條 DAG 全包了。這個 VIEW 正是第 8 章你在 Metabase 用過的那個——現在它由 Airflow 自動維護。

### （選做）CeleryExecutor：讓 Airflow 把自己的 task 也交給 Celery

上面所有串法，Airflow 自己都用 LocalExecutor（task 在 scheduler 容器的子行程跑）。生產環境常用 CeleryExecutor——Airflow 把**自己的 task** 丟進佇列、交給獨立的 Celery worker 執行，可跨機器水平擴充。你學過的 Celery 在這裡以「Airflow 的執行引擎」的身分再次出現。

課程附了瘦身示範版 `airflow/docker-compose-airflow-celery-stock.yml`——**跟主線同一顆 `stock-airflow` image**，本質差異只有一個環境變數：

```yaml
AIRFLOW__CORE__EXECUTOR: CeleryExecutor
```

外加多起兩個容器：Redis（當 broker）和 `airflow-celery-worker`（領 task 的獨立 worker）。

> 另有一份官方完整範本 `docker-compose-airflow-celery.yml`（官方 image、含 triggerer / flower）留作參考——它沒有課程程式碼與依賴，跑不了股票 DAG，全家桶也塞不進 4GB VM。

**跑法**（它佔 8080，先把主線 Airflow 讓開）：

```bash
docker compose -f airflow/docker-compose-airflow.yml down
docker compose -f airflow/docker-compose-airflow-celery-stock.yml up -d
# 等 init 完成（第 10 章 Step 4 同款：看到 User "admin" created）後：
docker restart airflow-celery-webserver airflow-celery-scheduler airflow-celery-worker
```

**觸發同一支股票 DAG（一行都不用改）：**

```bash
docker exec airflow-celery-webserver airflow dags unpause stock_crawler_dag
docker exec airflow-celery-webserver airflow dags trigger stock_crawler_dag
```

**觀察重點（跟 LocalExecutor 的對照就在這裡）：**

1. `docker logs airflow-celery-worker` 出現 `Running <TaskInstance: stock_crawler_dag.crawl_stock_XXXX ...>`——task 不再是 scheduler 的子行程，而是被**獨立 worker 容器**從佇列領走執行。
2. DAG 全綠、MySQL 筆數照樣增加——同一支 DAG、同一顆 image，只換了「誰執行」。
3. 結論：**executor 是設定，不是程式**。`AIRFLOW__CORE__EXECUTOR` 一個環境變數，決定 task 的執行模式；DAG 程式碼對此完全無感。

| | LocalExecutor | CeleryExecutor |
|---|---|---|
| task 在哪跑 | Airflow 主機的子行程 | Celery worker（可跨機器）|
| 類比 | 第 9 章單機排程 | 第 1 章分散式 |
| 適合 | 開發、小量 | 生產、大量、要水平擴充 |

### 跟串法二差在哪？（最容易混淆的一對，停下來分清楚）

串法二和 CeleryExecutor 都有「Celery」三個字，但它們管的是**不同層**的事，不是同一件事的兩種做法：

> **串法二改的是「task 的內容」——task 要做什麼事；CeleryExecutor 改的是「執行引擎」——task 這件事由誰來做。**

| | 串法二（`producer_dag`）| CeleryExecutor |
|---|---|---|
| 改變的東西 | DAG 裡 task 的**內容**：從「自己爬」改成「發任務」| Airflow 執行 task 的**方式**：從本機子行程改成丟給 worker |
| 在哪裡改 | DAG 程式碼（`apply_async`）| 環境變數（DAG 程式碼零改動）|
| 用到誰的 Celery | **你的爬蟲 Celery**：RabbitMQ ＋ 第 3 章的 crawler worker | **Airflow 自用的 Celery**：Redis ＋ airflow-celery-worker |
| 佇列裡裝的是什麼 | 爬蟲任務（「去爬 2330」）| Airflow 的 task 執行指令（「去執行 DAG 的某個 task」）|

因為在不同層，兩者其實**可以疊起來用**。假設串法二的 DAG 跑在 CeleryExecutor 上，一個 task 的完整旅程是：

```
scheduler ──(Redis)──> airflow-celery-worker 執行「發任務」這個 task
                             │
                             └ apply_async ──(RabbitMQ)──> crawler worker 真正去爬
```

兩套 Celery 同時上工、各管一段：**Redis 那段運的是「Airflow 的內部派工」，RabbitMQ 那段運的是「你的爬蟲工作」**。課程沒有讓你實際跑這個組合（服務太多、對教學沒有額外收穫），但看懂這張圖，兩者的分工就分清楚了。

判斷口訣，之後遇到任何 Airflow 架構問題都適用：

- 問「這支 DAG 的 task 是自己做、還是發給爬蟲 worker 做？」→ 這是**串法**的問題（串法一、二、三的選擇）
- 問「Airflow 執行 task 時，是用本機子行程、還是丟給自己的 worker 池？」→ 這是 **executor** 的問題（LocalExecutor 或 CeleryExecutor 的選擇）

**資源注意（4GB VM 的實測經驗）：**

- 瘦身版已把 webserver 限 2 個 gunicorn worker、Celery worker 的 `AIRFLOW__CELERY__WORKER_CONCURRENCY` 降為 2。**concurrency 用預設值（=CPU 核心數 4）時，爬取高峰會觸發 OOM、系統隨機殺掉 mysqld**——這本身就是一課：分散式元件的併發數要跟著記憶體上限算，不是「能起來就好」。
- 示範前先把用不到的容器（RabbitMQ / 課程 worker / Metabase 等）down 掉騰記憶體；示範完把這套 down 掉、主線起回來。

---

## 監控與除錯

| UI 頁面 | 看什麼 |
|---------|--------|
| **Graph** | 這一次 run 的依賴圖與各 task 狀態 |
| **Grid** | 歷史每次 run 的矩陣（快速定位哪天失敗）|
| **Task Logs** | 單一 task 的完整輸出（除錯第一站）|
| **Flower** | 串法二時看 Celery 端的執行狀態 |

| 症狀 | 先看哪裡 | 可能原因 |
|------|---------|---------|
| 某個 task 紅了 | 點進該 task 的 Logs | 可能是 API 請求失敗或資料庫連不上，錯誤訊息會寫在 log 裡 |
| DAG 沒有出現在列表上 | scheduler 的 log | DAG 檔案有語法錯誤，scheduler 解析失敗 |
| producer_dag 全綠但資料沒進資料庫 | Flower 和 worker 的 log | Celery worker 沒有啟動，或是連到了錯誤的 broker |
| 爬蟲 task 執行超時 | task 的 Logs，並考慮 FinMind 的流量限制 | 可以調大 `execution_timeout`，或減少一次爬的股票數量 |
| ETL 階段失敗 | create_view 那個 task 的 Logs | 多半是 MySQL 連線問題——容器內的 host 要用 `mysql` 這個服務名 |

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | `stock_crawler_dag` 的 10 個 task 全部變綠，MySQL 裡有 10 支股票的資料 | Airflow 能直接指揮爬蟲執行 |
| 2 | twse_tpex_dag 的兩組分支同時平行執行，上櫃三支股票的資料入庫 | 你跑通了分組扇出加匯合的 DAG 形狀 |
| 3 | producer_dag 觸發後立即全綠，Flower 上的任務陸續變成 SUCCESS | 編排層和執行層確實是分工的兩層 |
| 4 | docker_producer_dag 執行成功，`00679B` 的資料入庫 | DockerOperator 能跑 producer，而且佇列分流的兩條路都是通的 |
| 5 | ETL DAG 產出了 VIEW 和實體表 | 一條 DAG 就能涵蓋完整的 ETL 流程 |
| 6 | 失敗的 task 能夠單獨 Clear 重跑 | 你用到了編排引擎的核心價值 |

---

## 想一想（確認你懂了）

**Q1：`stock_crawler_dag`（直接呼叫）和 `stock_crawler_producer_dag`（`apply_async` 發任務）差在哪？各適合什麼情況？**

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
| DAG 報錯說找不到 `crawler` 模組 | `../crawler` 這個 volume 沒有掛載成功 | 確認你是從 stock-crawler 專案根目錄啟動 compose 的 |
| producer_dag 發了任務但沒有人執行 | Celery worker 沒有啟動 | 回準備 2，確認 `worker_twse`、`worker_tpex` 有列在 up 的服務名裡 |
| 任務發了、worker 也開著，但佇列一直堆積 | 佇列對不上——任務發到了預設佇列，但 worker 只聽 `-Q twse` / `tpex` 這兩條 | 發送端改用 `apply_async(queue=...)` 指定 worker 在聽的佇列；用 `rabbitmqctl list_queues name messages consumers` 查哪條佇列有訊息卻沒有消費者 |
| docker_producer 起的容器報 Connection refused | 臨時容器不會讀 .env，`RABBITMQ_HOST` 沒給就預設連 127.0.0.1（容器自己）| 在 DockerOperator 的 `environment` 明確給 `RABBITMQ_HOST` 和 `MYSQL_HOST` |
| Airflow 連不到 mysql 或 rabbitmq | 容器重建（down 再 up）後，network connect 的掛載消失了 | 重新執行準備 3 的四行 `docker network connect` |
| ETL 的 create_view 失敗 | MySQL 的 host 設定不對 | Airflow 的 compose 已在 `environment` 明寫 `MYSQL_HOST: mysql` 覆蓋 .env——若仍錯，確認你用的是最新版的 compose 檔 |
| BigQuery DAG 跑不動 | 它需要 GCP 憑證才能執行 | 接第 14 章的 GCP 設定；還沒有 GCP 帳號就先跳過這一支 |

---

## 收工

```bash
docker compose -f airflow/docker-compose-airflow.yml down
docker compose -f docker-compose-local.yml down
# 提醒：down 會重建容器，下次上課重跑準備 2 之後，準備 3 的 network connect 也要重做
```

---

## 三種串法怎麼選（帶著走的判斷準則）

| 你的情況 | 選哪個 | 理由 |
|---|---|---|
| 你的資料量不大、流程單純、不想多管理額外的服務 | **串法一**（直接呼叫）| 因為只需要 Airflow 和 MySQL 兩個服務，操作步驟最少 |
| 資料量大、要把執行負載跟編排分開、worker 需要能獨立擴充 | **串法二**（發任務給 Celery）| 因為 Airflow 只負責觸發和監控，重的工作交給 worker 池去消化 |
| 連「爬蟲的依賴」都要跟 Airflow 徹底隔離，例如兩邊用不同的 Python 版本、各自獨立演進 | **串法三**（DockerOperator 跑 producer）| 因為爬蟲改版時只需要重新 build 爬蟲的 image，Airflow 完全不用動 |

一個常見的演進路徑就是照這個順序走：專案初期用串法一快速上線 → 量大了改串法二 → 團隊分工細了改串法三。三種不是互斥的選擇題，是規模長大的三個階段。

---

## 這一章你學到了

- 三種串法各有定位：Airflow 直接做最簡單、指揮 Celery 能分工和擴充、用 DockerOperator 跑 producer 則把依賴徹底分離。
- 發任務時要跟 worker 在聽的佇列對上：分流版 worker 只聽 `-Q` 指定的佇列，所以要用 `apply_async(queue=...)` 明確指定；用 `.delay()` 會發進預設佇列，沒有人消費。
- 分組扇出加匯合的寫法是「dict 分組加兩層迴圈生 task」；之後要加一組，只需要在 dict 加一個 key。
- Airflow 的 task 全綠不等於爬蟲成功——fire-and-forget 模式下，編排層看不到執行結果，要自己補一步驗證。
- ETL DAG 讓「爬取 → 清理 → 產出分析表」變成一張可以補跑、可以監控的圖。
- LocalExecutor 和 CeleryExecutor 的關係，就是你學過的單機與分散式兩種模式在編排層重演一次。

## 下一章要做什麼

每個部件都會了、也串起來了。**下一章把全部服務用一個 compose 一鍵啟動，跑一次七步驟端到端驗證——看見整套系統的全貌。**
