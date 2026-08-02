# Crawler 實作操作手冊（台股爬蟲系統）

> 📖 這是一份**指令速查手冊**：不講觀念、只給步驟，適合已經學過、要快速重建環境的人。
> 第一次學習請走 `課程手冊/`（14 章 + 補充 B/B/C），每章有完整的觀念講解、逐行程式解讀與練習。

> 對象：已照《Docker 安裝教學手冊》裝好 Docker 的學員
> 涵蓋：專案介紹 → 整合版（一鍵啟動）→ 分開版（逐步啟動）→ 驗證閉環
> 所有指令都在 Docker 29.6.1 / Compose v5.2.0 / Ubuntu 22.04 實測通過

---

## 目錄

- [專案介紹](#專案介紹)
- [第一部分：前置準備](#第一部分前置準備)
- [第二部分：整合版（一鍵啟動）](#第二部分整合版一鍵啟動)
- [第三部分：分開版（逐步啟動）](#第三部分分開版逐步啟動)
- [第四部分：驗證完整閉環（7 步驟）](#第四部分驗證完整閉環7-步驟)
- [第五部分：進階操作](#第五部分進階操作)
- [附錄：排錯與清理](#附錄排錯與清理)

---

## 專案介紹

### 這個專案在做什麼

用 FinMind API 抓台股歷史股價，透過分散式架構自動處理多支股票：

```
Producer 發任務 → RabbitMQ 排隊 → Worker 執行爬蟲 → MySQL 儲存
  (股票代碼)        (broker)       (呼叫 FinMind API)   (股價資料)
                                      ↑
                                 Flower 監控
                                 phpMyAdmin 管理 DB
```

### 和 hahow-crawler 的關係

| | crawler（本專案） | hahow-crawler |
|---|---|---|
| 資料來源 | FinMind 台股 API | Hahow 線上課程 API |
| 迴圈維度 | stock_id（2330, 0050...）| category（programming, marketing...）|
| 核心架構 | 完全相同：Producer → RabbitMQ → Celery Worker → MySQL |
| 排程 | APScheduler | Airflow |
| 定位 | 實作用（先學這個） | 教學用（學完對照）|

### 六個服務說明

| 服務 | Image | Port | 角色 |
|------|-------|------|------|
| rabbitmq | rabbitmq:3.13-management-alpine | 5672 / 15672 | 訊息佇列（派工）|
| flower | mher/flower:latest | 5555 | Celery 任務監控 |
| mysql | mysql:8.0 | 3306 | 資料庫（存股價資料）|
| phpmyadmin | phpmyadmin:latest | 8080 | 資料庫管理介面 |
| worker_twse | 本地 build | — | 執行爬蟲（監聽 twse queue）|
| worker_tpex | 本地 build | — | 執行爬蟲（監聽 tpex queue）|

### 和 hahow-crawler 不能同時跑

兩個專案共用 4 個 port（3306、5672、15672、5555），**同時跑會衝突**。

```bash
# 先拆一個再起另一個
cd ~/hahow-crawler
docker compose -f docker-compose-local.yml down -v

cd ~/stock-crawler
docker compose -f docker-compose-local.yml up -d --build
```

---

## 第一部分：前置準備

### Step 1：取得專案

```bash
cd ~
git clone https://github.com/lu791019/stock-crawler-de-course-materials.git
cd crawler
ls
# Dockerfile  docker-compose-local.yml  crawler/  pyproject.toml  uv.lock ...
```

### Step 2：確認 Docker 可用

```bash
docker --version          # Docker version 29.x.x
docker compose version    # Docker Compose version v2+
```

---

## 第二部分：整合版（一鍵啟動）

用 `docker-compose-local.yml` 從 Dockerfile 本地 build，不依賴 DockerHub image。

### Step 1：build + 啟動 infra 和 worker

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml up -d --build rabbitmq flower mysql phpmyadmin worker_twse worker_tpex
```

> 第一次 build 需要幾分鐘（下載 ubuntu base image + uv sync）。
> 不要一次 `up -d` 全起 — producer 會因為 RabbitMQ 還沒 ready 而失敗。

### Step 2：確認服務正常（等 20-30 秒）

```bash
docker compose -f docker-compose-local.yml ps -a
# rabbitmq/flower/mysql/phpmyadmin/worker_twse/worker_tpex 都是 Up
```

Web 介面：

| 服務 | 網址 | 帳密 |
|------|------|------|
| RabbitMQ 管理 | http://localhost:15672 | worker / worker |
| Flower 監控 | http://localhost:5555 | （無）|
| phpMyAdmin | http://localhost:8080 | root / 1234 |

確認 worker ready：

```bash
docker compose -f docker-compose-local.yml logs worker_twse | grep ready
# celery@twse ready.

docker compose -f docker-compose-local.yml logs worker_tpex | grep ready
# celery@tpex ready.
```

### Step 3：發送任務 — Producer

```bash
docker compose -f docker-compose-local.yml up producer
# 前景跑，看到：
# send task_2330 task
# send task_00679b task
# exit code 0 = 成功
```

Producer 會把 2330 發到 twse queue、00679B 發到 tpex queue。

### Step 4：驗證完整閉環

```bash
# 1. Worker log 確認 task succeeded
docker compose -f docker-compose-local.yml logs worker_twse | grep succeeded
docker compose -f docker-compose-local.yml logs worker_tpex | grep succeeded

# 2. Flower 看 task 狀態
#    http://localhost:5555 → Tasks

# 3. MySQL 查資料
docker exec mysql mysql -uroot -p1234 -e "USE mydb; SHOW TABLES; SELECT stock_id, COUNT(*) FROM TaiwanStockPrice GROUP BY stock_id;"
```

預期：

```
stock_id    COUNT(*)
2330        349
00679B      349
```

### Step 5：停止全部

```bash
docker compose -f docker-compose-local.yml down -v    # 含刪 volume
```

---

## 第三部分：分開版（逐步啟動）

每個服務一個 compose file，適合教學逐步展示。Worker 走本地 build，Apple Silicon / amd64 都能跑。與課程手冊03 的 `--scale` 段落用同一組檔案。

### Step 1：建立共用 network

```bash
cd ~/stock-crawler
docker network create my_network
```

### Step 2：RabbitMQ + Flower

```bash
docker compose -f compose-advanced/rabbitmq.yml up -d
```

驗證：http://localhost:15672（worker / worker）、http://localhost:5555

### Step 3：MySQL + phpMyAdmin

```bash
docker compose -f compose-advanced/mysql.yml up -d
```

驗證：http://localhost:8080（root / 1234）

### Step 4：Worker（本地 build）

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml up -d --build
```

確認 worker ready：

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml logs | grep ready
# twse / tpex 各出現一行 celery@... ready.
```

### Step 5：Producer（本機發任務）

```bash
uv run crawler/producer_multi_queue.py
```

### Step 6：驗證

同第二部分 Step 4，但注意：分開版的 compose 沒有寫死 `container_name`，MySQL 容器名是 `compose-advanced-mysql-1` 而不是 `mysql`，所以 DB 驗證改用 `docker compose exec`（用 service 名，不受容器名影響）：

```bash
docker compose -f compose-advanced/mysql.yml exec mysql \
  mysql -uroot -p1234 mydb -e "SHOW TABLES; SELECT stock_id, COUNT(*) FROM TaiwanStockPrice GROUP BY stock_id;"
```

### Step 7：停止所有服務

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml down
docker compose -f compose-advanced/rabbitmq.yml down
docker compose -f compose-advanced/mysql.yml down -v
docker network rm my_network
```

---

## 第四部分：驗證完整閉環（7 步驟）

不管用整合版或分開版，驗證流程都一樣。**跑不完這 7 步就不能宣稱「測試通過」。**

### Step 1：服務啟動

```bash
docker compose -f docker-compose-local.yml ps -a
# 全部 Up（producer 是 Exited(0)，一次性腳本正常）
```

### Step 2：Web 介面

```bash
curl -o /dev/null -w "RabbitMQ: %{http_code}\n" http://localhost:15672
curl -o /dev/null -w "Flower: %{http_code}\n" http://localhost:5555
curl -o /dev/null -w "phpMyAdmin: %{http_code}\n" http://localhost:8080
# 全部 200
```

### Step 3：Logs 判讀

```bash
docker compose -f docker-compose-local.yml logs
```

| 服務 | 正常 log | 要注意的 |
|------|---------|---------|
| rabbitmq | `Time to start RabbitMQ` | 啟動前有 warning → 正常 |
| flower | `Connected to amqp://` | 啟動前 Connection refused → 正常（幾秒後重連）|
| worker | `celery@twse ready.` | 啟動前 Connection refused → 正常（restart 重試）|
| mysql | `ready for connections` | CA certificate warning → 正常 |

### Step 4：發任務

```bash
docker compose -f docker-compose-local.yml up producer
# exit code 0 = 成功
```

### Step 5：Worker 執行

```bash
docker compose -f docker-compose-local.yml logs worker_twse | grep succeeded
docker compose -f docker-compose-local.yml logs worker_tpex | grep succeeded
# 看到 Task ... succeeded
```

### Step 6：DB 驗證

```bash
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SHOW TABLES; SELECT stock_id, COUNT(*) as cnt FROM TaiwanStockPrice GROUP BY stock_id;"
```

預期：

```
Tables_in_mydb
TaiwanStockPrice

stock_id    cnt
2330        349
00679B      349
```

### Step 7：Flower 驗證

開 http://localhost:5555 → Tasks 頁籤，看到 task 狀態是 SUCCESS。

---

## 第五部分：進階操作

### 5.1 多 Queue 分流

Producer 可以指定任務送到不同 queue：

```python
# crawler/producer_multi_queue.py
task_2330 = crawler_finmind.s(stock_id="2330")
task_2330.apply_async(queue="twse")     # 送到 twse queue

task_00679b = crawler_finmind.s(stock_id="00679B")
task_00679b.apply_async(queue="tpex")   # 送到 tpex queue
```

Worker 啟動時用 `-Q` 指定要監聽的 queue：

```bash
# twse worker 只處理 twse queue
python -m celery -A crawler.worker worker -Q twse

# tpex worker 只處理 tpex queue
python -m celery -A crawler.worker worker -Q tpex
```

### 5.2 重複資料處理（Upsert）

`tasks_crawler_finmind_duplicate.py` 使用 `ON DUPLICATE KEY UPDATE`，同一筆資料重複寫入時會更新而非報錯：

```bash
# 用 duplicate 版 producer（詳見課程手冊06）
uv run crawler/producer_crawler_finmind_duplicate.py
```

### 5.3 APScheduler 定時排程

`scheduler.py` 使用 APScheduler 每 12 小時自動觸發爬蟲：

```bash
# 啟動 scheduler（會持續執行，詳見課程手冊09；正式排程建議用 Airflow，見課程手冊10-12）
uv run crawler/scheduler.py
```

---

## 第六部分：延伸服務速查（Airflow / Metabase / API / 測試）

### Airflow（課程手冊 10-12）

```bash
docker build -f airflow/Dockerfile -t stock-airflow:latest .   # 首次 build
cp .env.example .env
docker compose -f airflow/docker-compose-airflow.yml up -d
docker logs airflow-airflow-init-1 2>&1 | tail -3              # 等 init 完成
docker restart airflow-webserver airflow-scheduler             # 首次啟動後重啟
# UI: http://localhost:8080 (admin/admin)；注意與 phpMyAdmin 8080 衝突，擇一啟動

docker exec airflow-webserver airflow dags unpause stock_crawler_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_dag
```

### Metabase（課程手冊 08）

```bash
docker network create my_network
docker compose -f metabase/docker-compose-metabase.yml up -d
docker network connect my_network mysql    # 若 mysql 來自 docker-compose-local.yml
# UI: http://localhost:3000（JVM 慢，等 30-60 秒）；資料來源 Host 填 mysql
```

### FastAPI（補充 E）

```bash
uv run uvicorn api.main:app --reload --port 8000
# 文件: http://localhost:8000/docs
curl http://localhost:8000/stocks/2330/latest
```

### 測試（補充 F）

```bash
uv run pytest -m "not integration" -v      # 單元測試（免服務）
uv run pytest -m integration -v            # 整合測試（需 mysql）
uv run pytest -v                           # 全部
```

### 全服務一鍵啟動（課程手冊 13）

```bash
docker compose -f docker-compose-all.yml up -d     # 11 容器；Airflow 在 8081
docker compose -f docker-compose-all.yml down
```

---

## 附錄：排錯與清理

### 常見問題

| 問題 | 解法 |
|------|------|
| producer `Connection refused` exit(1) | RabbitMQ 還沒 ready，等 20-30 秒再跑 producer |
| worker `exec format error` | DockerHub image 是 amd64，Apple Silicon 用整合版（本地 build）|
| `network my_network not found` | 分開版要先 `docker network create my_network` |
| `port already in use` | 確認 hahow-crawler 已停止：`docker ps` 找佔用的 → `docker stop` |
| phpMyAdmin 頁面空白 | 確認 MySQL 已啟動且 PMA_HOST 設定正確 |
| worker 爬完但 MySQL 沒資料 | 查 worker log 有無 error；確認 `MYSQL_HOST=mysql` 有設定 |

### 重新 build

```bash
# 一般重 build
docker compose -f docker-compose-local.yml up -d --build

# 完全從零 build（不用快取）
docker compose -f docker-compose-local.yml build --no-cache
docker compose -f docker-compose-local.yml up -d
```

### 清理

```bash
# 停止 + 刪 container + volume
docker compose -f docker-compose-local.yml down -v

# 清理未使用資源
docker system prune
```
