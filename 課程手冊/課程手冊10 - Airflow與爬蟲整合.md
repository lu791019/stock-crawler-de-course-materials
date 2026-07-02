# Airflow + 爬蟲整合 實作手冊

> 對象：已完成課程手冊08-09（Airflow 基礎 + 進階）的學員
> 涵蓋：Airflow 直接呼叫爬蟲 → Airflow 透過 Celery 發任務 → ETL DAG（爬蟲 + MySQL VIEW）→ 全流程監控
> 所有指令在 WSL Ubuntu 環境實測

---

## 這集要做什麼？

前兩集學了 Airflow 的各種 Operator，但都是跑 example。
這一集把**真正的台股爬蟲**接上 Airflow，實現：

1. Airflow 定時觸發 → 呼叫 FinMind API → 寫入 MySQL → 自動化完成
2. 兩種串接方式：直接呼叫 vs 透過 Celery（RabbitMQ）
3. ETL pipeline：爬蟲 + VIEW 建立，一條 DAG 搞定

---

## 前置準備

需要同時啟動 Airflow + MySQL + RabbitMQ：

```bash
cd ~/stock-crawler
docker network create my_network 2>/dev/null
cp .env.example .env

# 啟動 MySQL + RabbitMQ
docker compose -f compose-advanced/mysql.yml up -d
docker compose -f compose-advanced/rabbitmq.yml up -d

# 啟動 Airflow
docker compose -f airflow/docker-compose-airflow.yml up -d
```

等 init 完成後重啟：

```bash
# 等 init（約 30-60 秒）
docker logs airflow-airflow-init-1 2>&1 | tail -3
# 看到 User "admin" created 後：
docker restart airflow-webserver airflow-scheduler
```

確認 MySQL 有 mydb：

```bash
docker exec compose-advanced-mysql-1 mysql -uroot -p1234 -e "CREATE DATABASE IF NOT EXISTS mydb"
```

---

## 目錄

- [第一部分：方式一 — Airflow 直接呼叫爬蟲](#第一部分方式一--airflow-直接呼叫爬蟲)
- [第二部分：方式二 — Airflow 透過 Celery 發任務](#第二部分方式二--airflow-透過-celery-發任務)
- [第三部分：ETL DAG（爬蟲 + MySQL VIEW）](#第三部分etl-dag爬蟲--mysql-view)
- [第四部分：監控與除錯](#第四部分監控與除錯)

---

## 第一部分：方式一 — Airflow 直接呼叫爬蟲

### 概念

最簡單的方式：Airflow 的 PythonOperator 直接呼叫 `crawler_finmind()` 函式。
爬蟲在 Airflow Worker 程序內執行。

### Step 1：看 stock_crawler_dag.py

```bash
cat airflow/dags/stock_crawler_dag.py
```

重點：

```python
from crawler.tasks_crawler_finmind import crawler_finmind

STOCK_IDS = ["2330", "2317", "2454", "2308", "2382",
             "0050", "0056", "00713", "00878", "006208"]

# 每支股票建一個 task
for stock_id in STOCK_IDS:
    task = PythonOperator(
        task_id=f"crawl_stock_{stock_id}",
        python_callable=crawler_finmind,    # 直接呼叫爬蟲函式
        op_args=[stock_id],                 # 傳入股票代碼
    )
```

排程：`schedule_interval="0 18 * * 1-5"` = 週一到五 18:00 自動跑。

### Step 2：觸發

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_dag
```

### Step 3：觀察執行

1. Web UI → `stock_crawler_dag` → Graph
2. 會看到 `start` → `stock_branch` → 10 個爬蟲 task 平行 → `end`
3. 每個 task 約需 1-2 秒（呼叫 FinMind API + 寫入 MySQL）

### Step 4：驗證 MySQL 資料

```bash
docker exec compose-advanced-mysql-1 mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) as cnt FROM TaiwanStockPrice GROUP BY stock_id ORDER BY stock_id"
```

✅ **預期**：10 支股票各有數百筆資料。

---

## 第二部分：方式二 — Airflow 透過 Celery 發任務

### 概念

進階做法：Airflow 只負責「發任務」（Producer），
實際爬蟲由 Celery Worker 從 RabbitMQ 取出來執行。

好處：Airflow 不會因為爬蟲太慢而卡住，Worker 可以水平擴展。

### Step 1：啟動 Celery Worker

先確認 RabbitMQ 已啟動，然後啟動 Worker 容器：

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml up -d
```

### Step 2：看 stock_crawler_producer_dag.py

```bash
cat airflow/dags/stock_crawler_producer_dag.py
```

關鍵差異：

```python
def trigger_stock_crawler(stock_id):
    crawler_finmind.delay(stock_id=stock_id)   # .delay() = 丟到 RabbitMQ

# PythonOperator 呼叫的是 trigger（發任務），不是 crawler（執行爬蟲）
task = PythonOperator(
    task_id=f"crawl_stock_{stock_id}",
    python_callable=trigger_stock_crawler,      # 只發任務，不等結果
    op_args=[stock_id],
)
```

### Step 3：觸發

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_producer_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_producer_dag
```

### Step 4：觀察

1. Airflow Web UI：10 個 task 會很快變成綠色（只是發任務，不等執行）
2. Flower（http://localhost:5555）：看到 10 個 task 出現在 Tasks 列表
3. Worker log：

```bash
docker logs compose-advanced-crawler_twse-1 2>&1 | tail -20
```

✅ **預期**：Worker log 顯示 `Task crawler.tasks_crawler_finmind.crawler_finmind succeeded`

### 兩種方式比較

| | 方式一（直接呼叫） | 方式二（透過 Celery） |
|--|-------------------|---------------------|
| Airflow 負擔 | 高（自己跑爬蟲） | 低（只發任務） |
| 擴展性 | 受限 Airflow Worker 數量 | Worker 可水平擴展（--scale） |
| 等待結果 | DAG 會等爬蟲完成 | DAG 不等（fire and forget） |
| 適合場景 | 少量任務、簡單流程 | 大量任務、需要分散處理 |

---

## 第三部分：ETL DAG（爬蟲 + MySQL VIEW）

### 概念

完整的 ETL（Extract-Transform-Load）pipeline：
1. **Extract**：爬 FinMind API 取得股價
2. **Transform**：建立 MySQL VIEW 去重 + 彙總
3. **Load**：從 VIEW 建實體表供下游使用

### Step 1：看 stock_crawler_etl_dag.py

```bash
cat airflow/dags/stock_crawler_etl_dag.py
```

DAG 結構：

```
start → stock_branch → [10 個爬蟲 task] → etl_task → create_view → create_table → end
```

先爬完所有股票，再建 VIEW 和實體表。

### Step 2：觸發

```bash
docker exec airflow-webserver airflow dags unpause stock_crawler_etl_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_etl_dag
```

> 注意：這個 DAG 需要 `crawler.mysql` 模組中的 `create_view` 和 `create_table_from_view`。
> 如果 ETL 階段失敗，先確認 MySQL 連線正常。

### Step 3：驗證

```bash
# 確認 VIEW 存在
docker exec compose-advanced-mysql-1 mysql -uroot -p1234 mydb -e "SHOW FULL TABLES WHERE Table_type = 'VIEW'"

# 確認實體表資料
docker exec compose-advanced-mysql-1 mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) FROM stock_price_daily GROUP BY stock_id"
```

---

## 第四部分：監控與除錯

### Airflow Web UI 監控

| 頁面 | 看什麼 |
|------|--------|
| DAGs 列表 | 各 DAG 最近執行狀態（綠=成功、紅=失敗、黃=執行中） |
| Graph | 視覺化 task 依賴和執行狀態 |
| Grid | 歷史執行紀錄矩陣 |
| Task Logs | 單一 task 的詳細 log（除錯必看） |

### 常見問題排查

| 問題 | 原因 | 解法 |
|------|------|------|
| task 變紅（failed） | 點 task → Logs 看錯誤 | 根據 log 修正 |
| DAG 沒出現在列表 | Python 語法錯誤 | `docker exec airflow-webserver python3 -c "import importlib; importlib.import_module('stock_crawler_dag')"` |
| 爬蟲 task 超時 | FinMind API 回應慢 | 調大 `execution_timeout` |
| MySQL 連不上 | 容器不在同一個 network | 確認都在 `my_network` |

---

## 本集完成清單

- [ ] 方式一：stock_crawler_dag 直接呼叫爬蟲，10 支股票寫入 MySQL
- [ ] 方式二：stock_crawler_producer_dag 透過 Celery 發任務，Worker 執行
- [ ] ETL DAG：爬蟲 + VIEW + 實體表建立
- [ ] 在 Airflow Web UI 觀察 Graph、Grid、Task Logs
- [ ] 在 Flower 觀察 Celery task 狀態（方式二）

---

## 停止服務

```bash
docker compose -f airflow/docker-compose-airflow.yml down
docker compose -f compose-advanced/docker-compose-worker-network.yml down
docker compose -f compose-advanced/rabbitmq.yml down
docker compose -f compose-advanced/mysql.yml down
```

---

## 下集預告

下一集做**完整系統整合**：
- 一個 docker-compose 跑全部服務
- 端到端 7 步驟驗證
- 全架構圖回顧
