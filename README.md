# stock-crawler-de-course-materials

> 引用來源：本專案改編自 [TibameSam/crawler](https://github.com/TibameSam/crawler)，加入整合版 Docker Compose、bug 修復與教學文件。

這是一個「台股資料爬蟲系統」的教學專案，帶你從零學會如何用工業界常見的架構，定期自動抓取股票資料並寫入資料庫。

## 這個專案在做什麼？

簡單來說，整個流程像這樣：

```
排程器 (Scheduler)  →  發送任務 (Producer)  →  RabbitMQ 佇列  →  工人 (Worker) 執行爬蟲  →  寫入 MySQL / BigQuery
```

- **Scheduler（排程器）**：每隔一段時間（例如 12 小時）自動觸發，就像鬧鐘
- **Producer（生產者）**：把「要爬哪支股票」這件任務丟到 RabbitMQ 排隊
- **RabbitMQ（訊息佇列）**：像是任務的「候位區」，讓工人依序領工作
- **Worker（工人）**：從佇列拿任務，呼叫 FinMind API 抓股價資料
- **MySQL / BigQuery**：最終把資料存進資料庫，之後可用來做分析

## 為什麼要這樣設計？

初學者可能會想：「直接寫一個 Python script 一次把所有股票抓下來不就好了嗎？」

是可以，但當你面對以下情境時就會卡住：
- **資料量大**：上千支股票一個一個抓，一台電腦跑一整天還沒跑完
- **需要容錯**：抓到一半某支股票失敗了，整支程式崩潰，前面的白跑
- **需要水平擴展**：想多開幾台機器一起跑，script 架構做不到

所以業界會用 **Celery + RabbitMQ** 這種「分散式任務佇列」架構：任務丟進佇列後，可以多個 worker 同時領任務處理，失敗的任務還能自動重試。

## 使用的技術

| 技術 | 用途 | 為什麼用它 |
| --- | --- | --- |
| Python 3.11 | 主要開發語言 | 爬蟲、資料處理套件最豐富 |
| [uv](https://docs.astral.sh/uv/) | 套件管理 | 比 pip/pipenv 快 10～100 倍 |
| [Celery](https://docs.celeryq.dev/) | 分散式任務佇列 | 讓任務可以分派到多台 worker |
| [RabbitMQ](https://www.rabbitmq.com/) | 訊息中介 (broker) | Celery 依賴它來傳遞任務 |
| [Flower](https://flower.readthedocs.io/) | Celery 監控介面 | 可視化看 worker 狀態與任務 |
| [APScheduler](https://apscheduler.readthedocs.io/) | 排程器 | 定時觸發任務 |
| MySQL | 關聯式資料庫 | 儲存爬回來的股價資料 |
| Google BigQuery | 雲端資料倉儲 | 儲存大量歷史資料供分析 |
| SQLAlchemy | ORM | 用 Python 物件操作資料庫，不用寫純 SQL |
| Docker + Docker Compose | 容器化部署 | 讓服務能一鍵啟動、跨平台執行 |

## 資料夾結構速覽

```
crawler/
├── worker.py                         # 建立 Celery app (所有 task 的總入口)
├── config.py                         # 環境變數集中管理
├── tasks.py                          # 範例 task
├── tasks_crawler_finmind.py          # 實際的爬蟲 task (append 模式)
├── tasks_crawler_finmind_duplicate.py # 去重複版本 (upsert 模式)
├── producer.py                       # 最簡單的任務派送範例
├── producer_crawler_finmind.py       # for 迴圈批次派送任務
├── producer_multi_queue.py           # 多佇列分流範例
├── scheduler.py                      # 定時自動派送任務
└── upload_*.py                       # 各種資料上傳腳本 (教學用)
```

## 學習順序建議

如果你是第一次接觸這個專案，建議依序閱讀：

1. `config.py` — 了解環境變數怎麼管理
2. `worker.py` + `tasks.py` — 認識 Celery task 最小範例
3. `producer.py` — 派送第一個任務，親手跑一次
4. `tasks_crawler_finmind.py` — 看真實的爬蟲邏輯
5. `producer_multi_queue.py` — 學習如何分流任務
6. `scheduler.py` — 最後把一切串起來，自動化執行

## 六個服務說明

| 服務 | Image | Port | 角色 |
|------|-------|------|------|
| rabbitmq | rabbitmq:3.13-management-alpine | 5672 / 15672 | 訊息佇列（派工）|
| flower | mher/flower:2.0 | 5555 | Celery 任務監控 |
| mysql | mysql:8.0 | 3306 | 資料庫（存股價資料）|
| phpmyadmin | phpmyadmin:5.2 | 8080 | 資料庫管理介面 |
| worker_twse | 本地 build | — | 執行爬蟲（監聽 twse queue）|
| worker_tpex | 本地 build | — | 執行爬蟲（監聽 tpex queue）|

---

## 指令

### 🔧 環境設定

```bash
# 安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安裝 Python 3.11
uv python install 3.11

# 建立虛擬環境並安裝依賴
uv venv --python 3.11
uv sync

# 安裝新套件
uv add flask
uv add flask==3.0.0
```

### 🌍 環境變數設定

本專案的 `config.py` 已設定預設值，本機開發（RabbitMQ/MySQL 在 localhost Docker）不需要額外設定。

連遠端或需要自訂環境變數時，有兩種方式：

```bash
# 方式一：用 genenv.py 產生 .env（依據 local.ini 的設定）
ENV=DEV python genenv.py
ENV=DOCKER python genenv.py
ENV=PRODUCTION python genenv.py

# 方式二：手動建立 .env，參考 local.ini 的格式
```

### 🔨 程式碼排版

```bash
black -l 80 crawler/
```

### 🐳 Docker Compose（整合版，推薦）

本專案使用 `docker-compose-local.yml` 一個檔案管理所有服務，從 Dockerfile 本地 build，不依賴 DockerHub image。

#### 場景一：基礎設施用 Docker，Worker / Producer 本機跑

```bash
# 啟動基礎設施（RabbitMQ + Flower + MySQL + phpMyAdmin）
docker compose -f docker-compose-local.yml up -d rabbitmq flower mysql phpmyadmin

# 確認服務正常（等 20-30 秒）
docker compose -f docker-compose-local.yml ps -a

# 本機啟動 Worker
uv run python -m celery -A crawler.worker worker --loglevel=info

# 本機發送任務
uv run crawler/producer.py
uv run crawler/producer_crawler_finmind.py
uv run crawler/producer_multi_queue.py
```

#### 場景二：全部用 Docker 跑

```bash
# 啟動 infra + worker（先不起 producer）
docker compose -f docker-compose-local.yml up -d --build rabbitmq flower mysql phpmyadmin worker_twse worker_tpex

# 確認 worker ready
docker compose -f docker-compose-local.yml logs worker_twse | grep ready
docker compose -f docker-compose-local.yml logs worker_tpex | grep ready

# 發送任務
docker compose -f docker-compose-local.yml up producer
```

#### 停止與清理

```bash
# 停止（保留資料）
docker compose -f docker-compose-local.yml down

# 停止（清除資料庫資料）
docker compose -f docker-compose-local.yml down -v
```

### 🚀 完整端到端流程（從零到驗證）

照著跑一遍即可驗證整個系統能正常運作。

```bash
# Step 1：啟動所有服務
docker compose -f docker-compose-local.yml up -d --build rabbitmq flower mysql phpmyadmin worker_twse worker_tpex

# Step 2：等 30 秒，確認服務狀態（全部應該 Up）
docker compose -f docker-compose-local.yml ps -a

# Step 3：確認 Worker ready
docker compose -f docker-compose-local.yml logs worker_twse | grep ready
docker compose -f docker-compose-local.yml logs worker_tpex | grep ready

# Step 4：確認 Web 介面（全部應該 200）
curl -o /dev/null -w "RabbitMQ: %{http_code}\n" http://localhost:15672
curl -o /dev/null -w "Flower: %{http_code}\n" http://localhost:5555
curl -o /dev/null -w "phpMyAdmin: %{http_code}\n" http://localhost:8080

# Step 5：發送任務
docker compose -f docker-compose-local.yml up producer

# Step 6：查看 Worker log（等 10-20 秒，應該看到 succeeded）
docker compose -f docker-compose-local.yml logs worker_twse | grep succeeded
docker compose -f docker-compose-local.yml logs worker_tpex | grep succeeded

# Step 7：驗證 MySQL 資料（應該看到 2330 和 00679B 各 349 筆）
docker exec mysql mysql -uroot -pppWgnb_mfGe2m_ mydb -e \
  "SHOW TABLES; SELECT stock_id, COUNT(*) as cnt FROM TaiwanStockPrice GROUP BY stock_id;"

# Step 8：看 Flower 任務狀態
# 開瀏覽器 http://localhost:5555 → Tasks 頁籤，應該看到 SUCCESS

# Step 9：收工
docker compose -f docker-compose-local.yml down -v
```

### 🔍 Web 介面

| 服務 | 網址 | 帳密 |
|------|------|------|
| RabbitMQ 管理 | http://localhost:15672 | worker / worker |
| Flower 監控 | http://localhost:5555 | （無）|
| phpMyAdmin | http://localhost:8080 | root / ppWgnb_mfGe2m_ |

### 🕷️ 爬蟲與任務執行（本機）

```bash
# 啟動 Worker（預設 queue）
uv run python -m celery -A crawler.worker worker --loglevel=info

# 啟動 Worker（指定 queue）
uv run python -m celery -A crawler.worker worker --loglevel=info -Q twse
uv run python -m celery -A crawler.worker worker --loglevel=info -Q tpex
uv run python -m celery -A crawler.worker worker --loglevel=info -Q twse,tpex

# 啟動 Worker（指定 hostname + concurrency）
uv run python -m celery -A crawler.worker worker --loglevel=info --hostname=worker1@%h --concurrency=1
uv run python -m celery -A crawler.worker worker --loglevel=info --hostname=worker2@%h --concurrency=1

# Producer 發送任務
uv run crawler/producer.py                       # 最簡單範例（1 個假任務）
uv run crawler/producer_crawler_finmind.py       # 批次發送 5 支股票
uv run crawler/producer_multi_queue.py           # 分流到不同 queue

# 同時監聽多個 queue
uv run python -m celery -A crawler.worker worker --loglevel=info -Q twse,tpex

# 連遠端（RabbitMQ/MySQL 在雲端）
uv run --env-file .env python -m celery -A crawler.worker worker --loglevel=info
uv run --env-file .env python -m celery -A crawler.worker worker --loglevel=info -Q twse,tpex
uv run --env-file .env crawler/producer.py
uv run --env-file .env crawler/producer_crawler_finmind.py
uv run --env-file .env crawler/producer_multi_queue.py
```

### 🗄️ 驗證資料

```bash
# MySQL 查資料
docker exec mysql mysql -uroot -pppWgnb_mfGe2m_ mydb -e \
  "SHOW TABLES; SELECT stock_id, COUNT(*) FROM TaiwanStockPrice GROUP BY stock_id;"

# 查看 Worker log
docker compose -f docker-compose-local.yml logs worker_twse | grep succeeded
docker compose -f docker-compose-local.yml logs worker_tpex | grep succeeded

# 查看所有 container 狀況
docker ps -a

# 查看特定 container log
docker logs rabbitmq
docker logs mysql
docker logs crawler_twse
docker logs crawler_tpex
```

### 📥 資料上傳

```bash
# 下載 taiwan_stock_price.csv
wget https://github.com/FinMind/FinMindBook/releases/download/data/taiwan_stock_price.csv

# 上傳 CSV 到 MySQL
uv run crawler/upload_taiwan_stock_price_to_mysql.py

# 上傳到 MySQL（連遠端時）
uv run --env-file .env crawler/upload_taiwan_stock_price_to_mysql.py
```

---

## Dockerfile 說明

專案有三個 Dockerfile，長得很像，差別在於「是否在 build 時產生 `.env`」：

| 檔案 | 用途 | 差別 |
| --- | --- | --- |
| `Dockerfile` | 最基本版本 | 複製整個專案進去，不產生 `.env`（環境變數需執行時給）|
| `with.env.Dockerfile` | 開發/測試用 | build 時跑 `ENV=DOCKER genenv.py` 產生 `.env`（適合 docker 內跑）|
| `prod.with.env.Dockerfile` | 正式環境用 | build 時跑 `ENV=PRODUCTION genenv.py` 產生 `.env`（使用正式環境的 host、帳密）|

### Dockerfile 內部做了什麼？

以 `Dockerfile` 為例，流程大致是：

```
FROM ubuntu:22.04               ← 從乾淨的 Ubuntu 開始
→ 安裝 curl、ca-certificates    ← 下載 uv 需要的工具
→ 安裝 uv                       ← Python 套件管理工具
→ 安裝 Python 3.11              ← 指定 Python 版本
→ COPY 專案檔案進容器
→ uv sync --frozen              ← 根據 uv.lock 安裝所有套件（確保版本一致）
→ 設定 UTF-8 語系              ← 避免中文編碼問題
→ CMD bash                      ← 預設進入 bash
```

---

## .gitignore 說明

`.gitignore` 列出「不要被 git 追蹤的檔案/資料夾」，避免意外把敏感資料或垃圾檔案推上 GitHub。

| 項目 | 為什麼要忽略 |
| --- | --- |
| `*__pycache__/`、`*.pyc` | Python 編譯產生的暫存檔，換台電腦重新產生就好 |
| `.vscode/`、`*.vscode` | 編輯器個人設定，每個人習慣不同 |
| `*.pytest_cache/` | pytest 的快取 |
| `.env` | **最重要！** 裡面有資料庫帳密、API key，絕不能進 git |
| `*.egg-info`、`build/` | Python 打包產生的檔案 |
| `.cache` | 各種工具的暫存 |

**新手常見錯誤**：把 `.env` 推上 public repo，幾分鐘內密碼就會被掃到外洩。養成習慣：加 `.env` 進 `.gitignore` **永遠是第一步**。

---

## 進階：Docker Compose 檔案說明

專案根目錄有很多 `.yml`，這些是 Docker Compose 設定檔，教學用漸進式設計。**日常使用推薦 `docker-compose-local.yml`（整合版）**，以下是所有 yml 的說明。

### 基礎設施

| 檔案 | 啟動什麼 | 說明 |
| --- | --- | --- |
| `rabbitmq.yml` | RabbitMQ + Flower | 本地開發用，使用 `dev` 網路 |
| `rabbitmq-network.yml` | RabbitMQ + Flower | 使用外部 `my_network`，讓多個 compose 檔互通 |
| `mysql.yml` | MySQL 8.0 + phpMyAdmin | MySQL 在 3306，phpMyAdmin 在 8080 |

### Worker

| 檔案 | 說明 |
| --- | --- |
| `docker-compose-worker.yml` | 單一 worker，使用 `my_network`，最簡單的版本 |
| `docker-compose-worker-network.yml` | 兩個 worker（twse、tpex），各自監聽不同 queue |
| `docker-compose-worker-network-version.yml` | 同上，image 版本可用 `DOCKER_IMAGE_VERSION` 環境變數指定 |

### Producer

| 檔案 | 說明 |
| --- | --- |
| `docker-compose-producer-network.yml` | 執行 `producer_multi_queue.py`，派送任務到 twse/tpex queue |
| `docker-compose-producer-network-version.yml` | 同上，image 版本可透過環境變數指定 |
| `docker-compose-producer-duplicate-network-version.yml` | 執行去重複版本的 producer |

### Scheduler

| 檔案 | 說明 |
| --- | --- |
| `docker-compose-scheduler-network-version.yml` | 啟動 `scheduler.py`，按照排程自動派送任務 |

### 整合版

| 檔案 | 說明 |
| --- | --- |
| `docker-compose-local.yml` | **推薦使用**。本地 build，一個檔案包含所有服務，不依賴 DockerHub image |

### 命名規則小抄

檔名看起來很長，其實有規則：
- **`-network`**：使用外部 `my_network`（需先 `docker network create my_network`）
- **沒 `-network`**：使用 compose 檔自己建立的網路
- **`-version`**：image 版本改用 `${DOCKER_IMAGE_VERSION}` 變數
- **`-duplicate`**：使用 on_duplicate_key_update 版本的 task
- **`-local`**：本地 build，不依賴 DockerHub

---

## 進階：分開版 Docker Compose

每個服務一個 compose file，適合教學逐步展示。需先建立共用 network。

```bash
# 建立共用 network（只要做一次）
docker network create my_network

# 啟動 RabbitMQ + Flower
docker compose -f rabbitmq-network.yml up -d

# 啟動 MySQL + phpMyAdmin
docker compose -f mysql.yml up -d

# 啟動 Worker
docker compose -f docker-compose-worker-network.yml up -d
DOCKER_IMAGE_VERSION=0.0.6 docker compose -f docker-compose-worker-network-version.yml up -d

# 發送任務
docker compose -f docker-compose-producer-network.yml up
DOCKER_IMAGE_VERSION=0.0.6 docker compose -f docker-compose-producer-network-version.yml up

# 發送任務（去重複版本）
DOCKER_IMAGE_VERSION=0.0.6 docker compose -f docker-compose-producer-duplicate-network-version.yml up

# 啟動 Scheduler（定時自動派送任務）
DOCKER_IMAGE_VERSION=0.0.6 docker compose -f docker-compose-scheduler-network-version.yml up -d

# 關閉 Scheduler
DOCKER_IMAGE_VERSION=0.0.6 docker compose -f docker-compose-scheduler-network-version.yml down

# 關閉 Worker
docker compose -f docker-compose-worker-network.yml down
DOCKER_IMAGE_VERSION=0.0.6 docker compose -f docker-compose-worker-network-version.yml down

# 關閉基礎設施
docker compose -f rabbitmq-network.yml down
docker compose -f mysql.yml down
docker network rm my_network
```

## 進階：Docker Build / Push

```bash
# 基本版 image（不含 .env）
docker build -f Dockerfile -t linsamtw/tibame_crawler:latest .

# 含 .env 版 image（開發/測試用）
docker build -f with.env.Dockerfile -t linsamtw/tibame_crawler:0.0.6 .

# 正式環境版 image
docker build -f prod.with.env.Dockerfile -t linsamtw/tibame_crawler:prod .

# ARM64 版（Apple Silicon Mac）
docker buildx build -f with.env.Dockerfile --platform linux/arm64 -t linsamtw/tibame_crawler:0.0.6.arm64 .

# Push 到 DockerHub
docker push linsamtw/tibame_crawler:latest
```

## 進階：BigQuery / GCP

```bash
# GCP 登入
gcloud auth application-default login

# 設定 GCP project（替換成你的 project ID）
gcloud config set project your-project-id

# 上傳台股股價到 BigQuery
uv run --env-file .env crawler/upload_taiwan_stock_price_to_bigquery.py

# 上傳台股股價到 BigQuery
uv run --env-file .env crawler/upload_taiwan_stock_price_to_bigquery.py

# 讀取 Secret Manager
uv run --env-file .env crawler/print_secret_manager.py
```
