# stock-crawler-de-course-materials

> 引用來源：本專案改編自 [TibameSam/crawler](https://github.com/TibameSam/crawler)，加入整合版 Docker Compose、Airflow / Metabase / BigQuery 教學模組、bug 修復與完整課程手冊。

這是一個「台股資料爬蟲系統」的教學專案，帶你從零學會如何用工業界常見的架構，定期自動抓取股票資料、寫入資料庫、視覺化，並用 Airflow 編排成生產級工作流。

## 這個專案在做什麼？

簡單來說，整個流程像這樣：

```
Airflow / Scheduler（排程編排）
   →  發送任務 (Producer)  →  RabbitMQ 佇列  →  工人 (Worker) 執行爬蟲
   →  寫入 MySQL（冪等 upsert）  →  同步 BigQuery（分析）  →  Metabase（視覺化）
```

- **Airflow / APScheduler（排程編排）**：定時自動觸發，管理步驟依賴與失敗補跑
- **Producer（生產者）**：把「要爬哪支股票」這件任務丟到 RabbitMQ 排隊
- **RabbitMQ（訊息佇列）**：像是任務的「候位區」，讓工人依序領工作
- **Worker（工人）**：從佇列拿任務，呼叫 FinMind API 抓股價資料
- **MySQL / BigQuery**：資料落地（營運庫）與雲端倉儲（分析庫）
- **Metabase**：把資料變成看得到的 Dashboard

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
| [APScheduler](https://apscheduler.readthedocs.io/) | 輕量排程器 | 定時觸發任務 |
| [Airflow](https://airflow.apache.org/) | 工作流編排 | 排程 + 依賴 + 補跑 + UI，生產級的 APScheduler 升級版 |
| MySQL | 關聯式資料庫 | 儲存爬回來的股價資料 |
| [Metabase](https://www.metabase.com/) | 開源 BI 工具 | 把 MySQL 資料變成互動式圖表 |
| [FastAPI](https://fastapi.tiangolo.com/) | API 框架 | 把 MySQL 資料開成 REST API（補充B）|
| [pytest](https://docs.pytest.org/) | 測試框架 | 單元測試 + 整合測試（補充C）|
| Google BigQuery | 雲端資料倉儲 | 儲存大量歷史資料供分析（OLAP）|
| SQLAlchemy | ORM | 用 Python 物件操作資料庫，不用寫純 SQL |
| Docker + Docker Compose | 容器化部署 | 讓服務能一鍵啟動、跨平台執行 |

## 資料夾結構速覽

```
stock-crawler/
├── crawler/                              # Python Package（所有程式碼）
│   ├── config.py                         # 環境變數集中管理
│   ├── worker.py                         # 建立 Celery app（所有 task 的總入口）
│   ├── tasks.py                          # 範例 task（print 版假任務）
│   ├── producer.py                       # 最簡單的任務派送範例
│   ├── tasks_crawler_finmind.py          # 實際的爬蟲 task（print 版 + append 寫 DB 版）
│   ├── producer_crawler_finmind_print.py # 批次派送（print 版）
│   ├── producer_crawler_finmind.py       # 批次派送（寫 DB 版）
│   ├── producer_multi_queue_print.py     # 多佇列分流（print 版）
│   ├── producer_multi_queue.py           # 多佇列分流（寫 DB 版）
│   ├── tasks_crawler_finmind_duplicate.py # 去重複版本（upsert 模式）
│   ├── producer_crawler_finmind_duplicate.py # 去重版 producer
│   ├── scheduler_print.py / scheduler.py / scheduler_blocking.py  # APScheduler 排程三版本
│   ├── worker_demo.py                    # 失敗情境教學專用 Celery app
│   ├── tasks_demo_fail.py                # retry / requeue / reject / slow 四情境
│   ├── producer_demo_fail.py             # 發送失敗情境任務
│   ├── mysql.py                          # MySQL 工具模組（View、查詢、上傳）
│   ├── bigquery.py                       # BigQuery 工具模組
│   ├── stock_sync_mysql_to_bigquery.py   # MySQL → BigQuery 同步
│   ├── stock_bigquery_data_transform.py  # BigQuery 分析表建立
│   └── upload_*.py 等                    # 各種資料上傳輔助腳本（教學用）
├── docker-compose-local.yml              # 整合版：一鍵啟動基礎服務（推薦日常使用）
├── docker-compose-all.yml                # 全服務整合版：11 容器一次啟動（含 Airflow + Metabase）
├── compose-advanced/                     # 進階：拆開的 compose（network 版、--scale 用）
├── api/                                  # FastAPI：MySQL 資料的 REST 出口（補充B）
├── tests/                                # pytest 測試：單元 + 整合（補充C）
├── airflow/                              # Airflow：Dockerfile、compose、DAGs、README
├── metabase/                             # Metabase：compose、README
├── example/                              # SQL 範例、mock 資料、pandas 練習、獨立爬蟲範例
├── 課程手冊/                              # 完整課程手冊（14 章 + 補充）
├── Dockerfile                            # Worker 容器化（Ubuntu + uv）
├── pyproject.toml / uv.lock              # Python 依賴管理
└── README.md
```

## 課程手冊（建議的學習路徑）

`課程手冊/` 資料夾有一套完整的實作教材，每一章都是「觀念 → 逐行讀懂程式 → 動手跑 → 驗證 → 練習」的結構。第一次接觸這個專案，照著順序走就對了：

### Phase A：Celery 任務系統（第 1~7 章）

| 章 | 主題 | 用到的關鍵檔案 |
|----|------|---------------|
| 01 | Celery 基礎：Producer / Broker / Worker | `tasks.py`、`producer.py`、`worker.py`、`config.py` |
| 02 | 真實爬蟲（只印出）：FinMind API | `tasks_crawler_finmind.py`、`producer_crawler_finmind_print.py` |
| 03 | 多佇列分流 + `--scale` 水平擴充 | `producer_multi_queue_print.py`、`compose-advanced/` |
| 04 | 失敗處理：retry / requeue / acks_late | `worker_demo.py`、`tasks_demo_fail.py` |
| 05 | 寫入 MySQL | `producer_crawler_finmind.py`、phpMyAdmin |
| 06 | 去重與冪等（upsert）| `tasks_crawler_finmind_duplicate.py` |
| 07 | Web 管理介面與排錯 SOP | RabbitMQ UI、Flower、phpMyAdmin、Portainer |

### Phase B：資料出口與自動化（第 8~9 章）

| 章 | 主題 | 用到的關鍵檔案 |
|----|------|---------------|
| 08 | Metabase BI 視覺化 | `metabase/`、`example/vw_stock_price_daily.sql` |
| 09 | 定時排程 APScheduler | `scheduler_print.py`、`scheduler.py` |

### Phase C：工作流編排與整合（第 10~13 章）

| 章 | 主題 | 用到的關鍵檔案 |
|----|------|---------------|
| 10 | Airflow 基礎 | `airflow/Dockerfile`、`docker-compose-airflow.yml`、`dags/example_*` |
| 11 | Airflow 進階 Operator | Branch / XCom / Trigger / DockerOperator 範例 DAG |
| 12 | Airflow 接上爬蟲 pipeline | `dags/stock_crawler_*.py`、`crawler/mysql.py` |
| 13 | 完整系統整合（一鍵啟動 + 七步驟驗證）| `docker-compose-all.yml` |

### 延伸：雲端資料倉儲（第 14 章）

| 章 | 主題 | 用到的關鍵檔案 |
|----|------|---------------|
| 14 | BigQuery 資料倉儲（OLTP → OLAP）| `crawler/bigquery.py`、`stock_sync_mysql_to_bigquery.py` |

### 補充教材

| 篇 | 主題 | 用到的關鍵檔案 |
|----|------|---------------|
| 補充A | 同步/非同步、多執行緒、多行程、分散式（含術語速查表）| — |
| 補充B | MySQL to FastAPI（資料的 API 出口）| `api/main.py` |
| 補充C | Unit Test 與整合測試（pytest + mock + 冪等驗證）| `tests/` |
| 補充D | MySQL 深入：約束/索引/外鍵/交易/權限/分區 + phpMyAdmin 實戰 | `example/ecommerce.sql`、`example/mock_stock_price_data.sql` |
| 補充E | .env 與環境變數：${} 替換 vs env_file 注入、三層哲學、三個坑 | `docker-compose-dotenv-demo.yml`、`.env.dotenv-demo.example` |
| 補充F | ACID 與 CAP：交易保證、三選二、MongoDB+pymongo 對照實戰（mongo-express 8082）| `crawler/tasks_crawler_finmind_mongo.py`、`producer_crawler_finmind_mongo.py` |
| 補充G | 對外服務：API 上雲與 Cloud Run（image 倉庫、發佈流程、revision 換版）| `api/main.py`、`api/Dockerfile` |
| 補充H | 系統架構圖：用 draw.io 畫本地端與雲端（含 GCP 圖示庫與 Mermaid 對照）| `課程手冊/drawio/` |

---

## 快速開始

### 🔧 環境設定

```bash
# 安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone 專案
git clone https://github.com/lu791019/stock-crawler-de-course-materials.git stock-crawler
cd stock-crawler

# 安裝 Python 3.11 + 建立虛擬環境 + 安裝依賴
uv python install 3.11
uv venv --python 3.11
uv sync

# 安裝新套件（需要時）
uv add flask
uv add flask==3.0.0
```

### 🌍 環境變數設定

本專案的 `config.py` 已設定預設值，本機開發（RabbitMQ/MySQL 在 localhost Docker）不需要額外設定。

連遠端或需要自訂環境變數時：

```bash
# 方式一：從範本建立 .env（Airflow compose 需要它）
cp .env.example .env

# 方式二：用 genenv.py 產生 .env（依據 local.ini 的設定）
ENV=DEV python genenv.py
ENV=DOCKER python genenv.py
ENV=PRODUCTION python genenv.py
```

### 🔨 程式碼排版

```bash
black -l 80 crawler/
```

---

## 三種啟動方式（由簡到全）

### 方式一：docker-compose-local.yml（整合版，日常推薦）

一個檔案管理基礎服務（RabbitMQ + Flower + MySQL + phpMyAdmin + Worker + Producer），從 Dockerfile 本地 build，不依賴 DockerHub image。

#### 場景 A：基礎設施用 Docker，Worker / Producer 本機跑（開發時最常用）

```bash
# 啟動基礎設施
docker compose -f docker-compose-local.yml up -d rabbitmq flower mysql phpmyadmin

# 確認服務正常（等 20-30 秒）
docker compose -f docker-compose-local.yml ps -a

# 本機啟動 Worker
uv run python -m celery -A crawler.worker worker --loglevel=info

# 本機發送任務
uv run crawler/producer.py                       # 最簡單範例（100 個假任務）
uv run crawler/producer_crawler_finmind_print.py # 5 支股票（print 版，不寫 DB）
uv run crawler/producer_crawler_finmind.py       # 5 支股票（寫 DB 版）
uv run crawler/producer_multi_queue.py           # 分流到 twse / tpex queue
```

#### 場景 B：全部用 Docker 跑

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
docker compose -f docker-compose-local.yml down       # 停止（保留資料）
docker compose -f docker-compose-local.yml down -v    # 停止（清除資料庫資料）
```

### 方式二：compose-advanced/（拆開版，教學逐步展示 + --scale）

每類服務一個 compose 檔，全部掛在外部網路 `my_network` 上互通。適合逐步展示，以及 `--scale` 水平擴充實驗（課程手冊 03）。

```bash
# 建立共用 network（只要做一次）
docker network create my_network

# 啟動 RabbitMQ + Flower、MySQL + phpMyAdmin
docker compose -f compose-advanced/rabbitmq.yml up -d
docker compose -f compose-advanced/mysql.yml up -d

# 啟動 Worker（twse + tpex 各一）
docker compose -f compose-advanced/docker-compose-worker-network.yml up -d

# --scale：twse worker 開成 3 份
docker compose -f compose-advanced/docker-compose-worker-network.yml up -d --scale crawler_twse=3

# 關閉
docker compose -f compose-advanced/docker-compose-worker-network.yml down
docker compose -f compose-advanced/rabbitmq.yml down
docker compose -f compose-advanced/mysql.yml down
docker network rm my_network
```

### 方式三：docker-compose-all.yml（全服務整合，課程手冊 13）

11 個容器一次啟動：基礎服務 + Celery Worker + **Airflow**（Postgres/init/webserver/scheduler）+ **Metabase**。

```bash
# 前置：先 build Airflow image（一次即可）
docker build -f airflow/Dockerfile -t stock-airflow:latest .
cp .env.example .env

# 一鍵啟動（其他 compose 先 down 掉避免 port 衝突）
docker compose -f docker-compose-all.yml up -d

# 收工
docker compose -f docker-compose-all.yml down
```

完整的七步驟端到端驗證流程，見 `課程手冊/課程手冊13 - 完整系統整合.md`。

---

## 🔍 Web 介面總覽

| 服務 | 網址 | 帳密 | 來自哪個 compose |
|------|------|------|------------------|
| RabbitMQ 管理 | http://localhost:15672 | worker / worker | local / advanced / all |
| Flower 監控 | http://localhost:5555 | （無）| local / advanced / all |
| phpMyAdmin | http://localhost:8080 | root / 1234 | local / advanced / all |
| Airflow | http://localhost:8080（單獨跑）/ **8081**（all 版）| admin / admin | airflow / all |
| Metabase | http://localhost:3000 | 首次自設 | metabase / all |

> ⚠️ Airflow 單獨跑（`airflow/docker-compose-airflow.yml`）用 8080，會跟 phpMyAdmin 撞——擇一啟動。`docker-compose-all.yml` 已把 Airflow 改到 8081，無衝突。

---

## 🕷️ 爬蟲與任務執行（本機指令速查）

```bash
# 啟動 Worker（預設 queue）
uv run python -m celery -A crawler.worker worker --loglevel=info

# 多開幾個 worker（各取名字）
uv run python -m celery -A crawler.worker worker --loglevel=info --hostname=worker1@%h
uv run python -m celery -A crawler.worker worker --loglevel=info --hostname=worker2@%h

# 指定 queue
uv run python -m celery -A crawler.worker worker --loglevel=info -Q twse
uv run python -m celery -A crawler.worker worker --loglevel=info -Q tpex
uv run python -m celery -A crawler.worker worker --loglevel=info -Q twse,tpex

# 控制併發數（觀察順序用 1；I/O 密集可用 gevent 開高）
uv run python -m celery -A crawler.worker worker --loglevel=info --concurrency=1
uv run python -m celery -A crawler.worker worker --loglevel=info --pool=gevent --concurrency=100

# 失敗情境教學專用 app（課程手冊 04）
uv run python -m celery -A crawler.worker_demo worker --loglevel=info --concurrency=1

# Producer 發送任務
uv run crawler/producer.py                        # 100 個假任務
uv run crawler/producer_crawler_finmind_print.py  # 5 支股票 print 版
uv run crawler/producer_crawler_finmind.py        # 5 支股票寫 DB 版
uv run crawler/producer_multi_queue.py            # twse / tpex 分流
uv run crawler/producer_crawler_finmind_duplicate.py  # 去重 upsert 版
uv run crawler/producer_demo_fail.py              # 失敗情境

# 排程（APScheduler）
uv run crawler/scheduler_print.py                 # print 版觀察
uv run crawler/scheduler.py                       # 正式版

# 連遠端（RabbitMQ/MySQL 在雲端）
uv run --env-file .env python -m celery -A crawler.worker worker --loglevel=info
uv run --env-file .env crawler/producer.py
```

## 🗄️ 驗證資料

```bash
# MySQL 查資料
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SHOW TABLES; SELECT stock_id, COUNT(*) FROM TaiwanStockPrice GROUP BY stock_id;"

# 沒資料想快速補一批？載入模擬資料（10 支股票）
docker exec -i mysql mysql -uroot -p1234 mydb < example/mock_stock_price_data.sql

# 查看 Worker log
docker compose -f docker-compose-local.yml logs worker_twse | grep succeeded

# 查看所有 container 狀況
docker ps -a

# 查看特定 container log
docker logs rabbitmq
docker logs crawler_twse
```

## 📊 Airflow 與 Metabase

```bash
# Airflow（詳見 airflow/README.md 與課程手冊 10-12）
docker build -f airflow/Dockerfile -t stock-airflow:latest .   # 先 build image
cp .env.example .env
docker compose -f airflow/docker-compose-airflow.yml up -d
# 首次啟動：等 init 完成（docker logs airflow-airflow-init-1）後
docker restart airflow-webserver airflow-scheduler
# UI: http://localhost:8080 (admin/admin)

# CLI 觸發 DAG
docker exec airflow-webserver airflow dags unpause stock_crawler_dag
docker exec airflow-webserver airflow dags trigger stock_crawler_dag
docker exec airflow-webserver airflow dags list-runs --dag-id stock_crawler_dag

# Metabase（詳見 metabase/README.md 與課程手冊 08）
docker network create my_network
docker compose -f metabase/docker-compose-metabase.yml up -d
# UI: http://localhost:3000（JVM 啟動慢，等 30-60 秒）
# 連資料來源時 Host 填 mysql（服務名），不是 127.0.0.1
```

## 🧪 測試與 API（補充教材）

```bash
# 單元測試（不需要任何服務，秒級）
uv run pytest -m "not integration" -v

# 整合測試（需先起 MySQL，驗證 upsert 冪等）
docker compose -f docker-compose-local.yml up -d mysql
uv run pytest -m integration -v

# FastAPI 資料出口
uv run uvicorn api.main:app --reload --port 8000
# Swagger 文件: http://localhost:8000/docs
```

## 📥 資料上傳（輔助腳本）

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

專案有多個 Dockerfile，差別在用途與「是否在 build 時產生 `.env`」：

| 檔案 | 用途 | 差別 |
| --- | --- | --- |
| `Dockerfile` | Worker 基本版 | 複製整個專案進去，不產生 `.env`（環境變數執行時給）|
| `with.env.Dockerfile` | 開發/測試用 | build 時跑 `ENV=DOCKER genenv.py` 產生 `.env` |
| `prod.with.env.Dockerfile` | 正式環境用 | build 時跑 `ENV=PRODUCTION genenv.py` 產生 `.env` |
| `airflow/Dockerfile` | Airflow image | Ubuntu 24.04 + Airflow 2.10 + 本專案 crawler 程式 |

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

## 進階：Docker Compose 檔案總覽

專案的 compose 檔案採漸進式設計。**日常使用推薦根目錄的 `docker-compose-local.yml`（整合版）**；拆開版都在 `compose-advanced/` 子目錄。

### 根目錄

| 檔案 | 說明 |
| --- | --- |
| `docker-compose-local.yml` | **推薦**。本地 build，一個檔案包含基礎服務 + worker + producer |
| `docker-compose-all.yml` | 全服務版：再加上 Airflow 四件套 + Metabase，共 11 容器（課程手冊 13）|
| `docker-compose-dotenv-demo.yml` | 教學範例：帳密/port 全用 ${} 從 .env 帶入（搭配 `.env.dotenv-demo.example`；port 與主課程錯開，可同時共存）|

### compose-advanced/（拆開版）

課堂實際只用這三份（課程手冊03、13 與速查手冊第三部分）：

| 檔案 | 啟動什麼 | 說明 |
| --- | --- | --- |
| `rabbitmq.yml` | RabbitMQ + Flower | 掛外部 `my_network`，與其他 compose 互通 |
| `mysql.yml` | MySQL 8.0 + phpMyAdmin | MySQL 3306、phpMyAdmin 8080 |
| `docker-compose-worker-network.yml` | twse + tpex 雙 worker | 本地 build、**支援 `--scale`**（沒寫死 container_name）|

其餘舊版檔案（原課程的 DockerHub image 路線等）已移至 `compose-advanced/legacy/`，說明見 `compose-advanced/README.md`。

### airflow/ 與 metabase/

| 檔案 | 說明 |
| --- | --- |
| `airflow/docker-compose-airflow.yml` | Airflow LocalExecutor 版（開發用）|
| `airflow/docker-compose-airflow-celery.yml` | Airflow CeleryExecutor 版（+Redis+Worker，生產架構示範）|
| `metabase/docker-compose-metabase.yml` | Metabase（設定庫放 MySQL 的 `metabasedb`，資料來源為 `mydb`）|

### 命名規則小抄

- **`-network`**：使用外部 `my_network`（需先 `docker network create my_network`）
- **`-version`**：image 版本改用 `${DOCKER_IMAGE_VERSION}` 變數（拉 DockerHub image）
- **`-duplicate`**：使用 on_duplicate_key_update（upsert）版本的 task
- **`-local`**：本地 build，不依賴 DockerHub

---

## 進階：Docker Build / Push

```bash
# 基本版 image（不含 .env）——把 your-dockerhub-user 換成你自己的帳號
docker build -f Dockerfile -t your-dockerhub-user/stock_crawler:latest .

# 含 .env 版 image（開發/測試用）
docker build -f with.env.Dockerfile -t your-dockerhub-user/stock_crawler:0.0.1 .

# ARM64 版（Apple Silicon Mac）
docker buildx build -f with.env.Dockerfile --platform linux/arm64 -t your-dockerhub-user/stock_crawler:0.0.1.arm64 .

# Push 到 DockerHub
docker push your-dockerhub-user/stock_crawler:latest
```

## 進階：BigQuery / GCP（課程手冊 14）

```bash
# GCP 登入
gcloud auth application-default login

# 設定 GCP project（替換成你的 project ID）
gcloud config set project your-project-id

# 使用前：取消 crawler/config.py 與 crawler/bigquery.py 中 GCP 設定的註解

# MySQL → BigQuery 同步（在 Airflow 容器內或 Python 3.10~3.12 環境執行）
uv run --env-file .env crawler/stock_sync_mysql_to_bigquery.py

# 在 BigQuery 建分析 View / Table
uv run --env-file .env crawler/stock_bigquery_data_transform.py

# 舊版輔助腳本
uv run --env-file .env crawler/upload_taiwan_stock_price_to_bigquery.py
uv run --env-file .env crawler/print_secret_manager.py
```
