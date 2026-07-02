# Celery 進階與錯誤處理 實作手冊

> 對象：已完成「MySQL 與爬蟲資料入庫」的學員
> 涵蓋：config.py 環境變數實驗 → 本地 vs Docker 環境切換 → demo_fail 四情境（retry / requeue / reject / slow）→ 完整系統預演
> 實作專案：https://github.com/lu791019/stock-crawler-de-course-materials

---

## 這一集在做什麼

前面任務都成功了。真實世界任務會失敗 —— API 逾時、資料錯誤、Worker 被殺。這一集學 Celery 的**錯誤處理**：任務失敗時訊息在 RabbitMQ 裡的四種不同命運。

```
任務失敗時，訊息會怎樣？
  ├─ retry              → 發「新任務」回 queue，重試有次數上限
  ├─ requeue            → 「原訊息」放回 queue，無限循環
  ├─ reject no requeue  → 訊息直接丟棄
  └─ 殺 Worker (slow)   → acks_late 讓沒做完的訊息回 queue
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

- [第一部分：config.py 環境變數實驗](#第一部分configpy-環境變數實驗)
- [第二部分：本地 vs Docker 環境切換](#第二部分本地-vs-docker-環境切換)
- [第三部分：demo_fail 四情境](#第三部分demo_fail-四情境)
- [第四部分：完整系統預演](#第四部分完整系統預演)

---

## 第一部分：config.py 環境變數實驗

`config.py` 用 `os.environ.get(key, default)` 讀設定。這一段親手驗證「環境變數會覆蓋預設值」。

### Step 1：不設環境變數（用預設值）

```bash
cd ~/stock-crawler
uv run python -c "from crawler.config import RABBITMQ_HOST; print('RABBITMQ_HOST =', RABBITMQ_HOST)"
```

✅ **預期**：`RABBITMQ_HOST = 127.0.0.1`（預設值）

### Step 2：設環境變數覆蓋

```bash
RABBITMQ_HOST=rabbitmq uv run python -c "from crawler.config import RABBITMQ_HOST; print('RABBITMQ_HOST =', RABBITMQ_HOST)"
```

✅ **預期**：`RABBITMQ_HOST = rabbitmq`（被環境變數覆蓋）

### Step 3：看 worker.py 啟動時印出的設定

```bash
uv run python -c "import crawler.worker"
```

✅ **預期**：loguru 印出當前 `RABBITMQ_HOST / RABBITMQ_PORT / WORKER_ACCOUNT / WORKER_PASSWORD`。

> **重點**：程式碼不用改，靠環境變數就能在不同環境跑。開發時用預設 `127.0.0.1`，Docker 裡用 `RABBITMQ_HOST=rabbitmq` 覆蓋。

---

## 第二部分：本地 vs Docker 環境切換

同一份程式碼在兩種環境跑，差別只在環境變數：

| | 本地執行 | Docker 容器內 |
|---|---|---|
| `RABBITMQ_HOST` | `127.0.0.1`（預設） | `rabbitmq`（compose environment 覆蓋）|
| `MYSQL_HOST` | `127.0.0.1`（預設） | `mysql`（compose environment 覆蓋）|
| 為什麼不同 | 服務 port 映射到本機 | 容器間用**服務名稱**當主機名互連 |

### 觀察 compose 裡的覆蓋

看 `docker-compose-local.yml` 的 worker 服務：

```yaml
worker_twse:
  environment:
    - RABBITMQ_HOST=rabbitmq    # 覆蓋預設 127.0.0.1
    - MYSQL_HOST=mysql          # 覆蓋預設 127.0.0.1
    - PYTHONPATH=/crawler
```

✅ **理解**：
- 本地跑 Worker → 連 `127.0.0.1:5672`（因為 Docker 把 rabbitmq 的 5672 映射到本機）
- 容器內 Worker → 連 `rabbitmq:5672`（Docker 網路內用服務名解析）

> 這就是為什麼**本地開發**用 `uv run celery ...`（走 127.0.0.1）、**部署**用 compose（走服務名），完全不用改程式碼。

---

## 第三部分：demo_fail 四情境

這一段用專門的失敗教學檔案：
- `worker_demo.py`：獨立的 Celery app（設了 `task_acks_late = True`）
- `tasks_demo_fail.py`：4 個模擬失敗的 task
- `producer_demo_fail.py`：發送 demo task

### 準備：啟動 RabbitMQ + Flower

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml up -d rabbitmq flower
```

✅ **驗證**：`curl -o /dev/null -w "%{http_code}\n" http://localhost:15672` → 200

### retry vs requeue 的核心差別

| | `self.retry()` | `Reject(requeue=True)` |
|---|---|---|
| 訊息行為 | 發**新任務**到 queue | **原訊息**放回 queue |
| 有次數限制？ | 有（`max_retries`）| 沒有 |
| 最終結果 | 成功或 FAILURE | 永遠留在 queue |
| RabbitMQ 看到 | 新訊息 | 同一個訊息一直循環 |

---

### 情境 1：retry —— 失敗自動重試

`task_might_fail`：50% 機率失敗，失敗就 `self.retry()`，最多重試 3 次。

```python
@app.task(bind=True, acks_late=True, max_retries=3, default_retry_delay=5)
def task_might_fail(self, stock_id):
    if random.random() < 0.5:
        raise self.retry(exc=Exception("模擬錯誤"))   # 發新任務回 queue，5 秒後重試
    return f"{stock_id} done"
```

### 情境 2：requeue —— 訊息放回 queue（重點教學）

`task_requeue`：失敗就 `Reject(requeue=True)`，**原訊息**放回 queue，Worker 又拿出來、又失敗、又放回 —— 無限循環，訊息永遠不消失。

```python
@app.task(bind=True, acks_late=True)
def task_requeue(self, stock_id):
    raise Reject(reason="處理失敗", requeue=True)   # 原訊息放回 queue
```

### 操作：先發任務（不開 Worker）

```bash
cd ~/stock-crawler
uv run python crawler/producer_demo_fail.py
```

`producer_demo_fail.py` 預設發**情境 1（2330）**和**情境 2（REQUEUE_TEST）**兩個任務。

✅ **預期**：印出 `sent 2330`、`sent REQUEUE_TEST`、`發送完畢`。

### 觀察：RabbitMQ UI 看 Ready

開 http://localhost:15672 → **Queues and Streams** → `celery` queue

✅ **預期**：Messages **Ready = 2**（兩個任務排隊中，還沒 Worker 消費）。

### 開 demo Worker 觀察行為

```bash
uv run celery -A crawler.worker_demo worker --loglevel=info --concurrency=1
```

> 用 `crawler.worker_demo`（不是 `crawler.worker`），因為失敗情境 task 註冊在這個 app。`--concurrency=1` 讓觀察更清楚。

✅ **預期**：
- **情境 1（2330）**：可能一次成功，也可能「❌ 失敗 → 5 秒後重試」，最終成功或 3 次後 FAILURE
- **情境 2（REQUEUE_TEST）**：`❌ 處理失敗！訊息放回 queue` **一直重複**
- RabbitMQ UI：REQUEUE_TEST 讓 Ready ↔ Unacked 之間一直跳

### 停 Worker 看訊息還在

按 `Ctrl+C` 停 Worker，回 RabbitMQ UI 看 `celery` queue。

✅ **預期**：REQUEUE_TEST 的訊息還躺在 **Ready** 裡 —— 因為它從來沒被成功 ack，永遠留在 queue。

---

### 情境 3：reject no requeue —— 訊息丟棄

`task_reject_no_requeue`：`Reject(requeue=False)`，訊息直接丟棄，不放回。

測試方式：編輯 `crawler/producer_demo_fail.py`，取消情境 3 那兩行的註解：

```python
task_reject_no_requeue.delay(stock_id="REJECT_TEST")
```

重發 → 開 Worker，✅ **預期**：Worker 印 `❌ 訊息丟棄`，之後 RabbitMQ 的 Ready 歸 0（訊息消失，不像情境 2 那樣循環）。

---

### 情境 4：slow task —— 中途殺 Worker

`task_slow`：跑 30 秒（`acks_late=True`）。做到一半殺掉 Worker，因為還沒 ack，訊息會回到 queue，重開 Worker 從頭再跑。

取消 `producer_demo_fail.py` 情境 4 的註解：

```python
task_slow.delay(stock_id="SLOW_TEST", seconds=30)
```

操作：
1. 發任務 → 開 Worker，看到 `進度 1/30、2/30...`
2. 大約第 10 秒按 `Ctrl+C` 殺 Worker
3. 回 RabbitMQ UI，✅ **預期**：SLOW_TEST 訊息回到 **Ready**
4. 重開 Worker，✅ **預期**：任務**從頭**再跑（進度從 1/30 重來）

> **關鍵**：`acks_late=True`（在 `worker_demo.py` 全域設定）代表「做完才確認」。Worker 中途掛掉 → 沒 ack → 訊息不會遺失，會重新排隊。這是保證任務不丟失的重要設定。

### 清理

```bash
docker compose -f docker-compose-local.yml down -v
```

---

## 第四部分：完整系統預演

最後把**所有服務一起跑**，走一次完整的正式流程，把前面幾集的內容整合起來。

### Step 1：全開（build + 啟動所有服務 + Worker）

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml up -d --build rabbitmq flower mysql phpmyadmin worker_twse worker_tpex
```

### Step 2：確認全部 Up + Web 介面

```bash
docker compose -f docker-compose-local.yml ps
curl -o /dev/null -w "RabbitMQ:   %{http_code}\n" http://localhost:15672
curl -o /dev/null -w "Flower:     %{http_code}\n" http://localhost:5555
curl -o /dev/null -w "phpMyAdmin: %{http_code}\n" http://localhost:8080
```

✅ **預期**：六個服務 Up、三個 curl 都 200。

### Step 3：確認 Worker ready

```bash
docker compose -f docker-compose-local.yml logs worker_twse | grep ready
docker compose -f docker-compose-local.yml logs worker_tpex | grep ready
```

✅ **預期**：`celery@twse ready.` / `celery@tpex ready.`

### Step 4：發任務

```bash
docker compose -f docker-compose-local.yml up producer
```

✅ **預期**：`send task_2330 task` / `send task_00679b task`、exit code 0。

### Step 5：驗證完整閉環

```bash
# Worker 執行成功
docker compose -f docker-compose-local.yml logs worker_twse | grep succeeded
docker compose -f docker-compose-local.yml logs worker_tpex | grep succeeded

# DB 有資料
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SHOW TABLES; SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice GROUP BY stock_id;"
```

✅ **預期**：
- Worker log 有 `succeeded`
- MySQL 有 `TaiwanStockPrice` 表、2330 / 00679B 各有資料
- Flower（5555）Tasks 頁狀態是 SUCCESS

### Step 6：清理

```bash
docker compose -f docker-compose-local.yml down -v
```

---

## 本集完成清單

- [ ] config.py 實驗：預設值 vs 環境變數覆蓋
- [ ] 理解本地（127.0.0.1）vs Docker（服務名）環境切換
- [ ] 情境 1 retry：看到自動重試
- [ ] 情境 2 requeue：看到訊息無限循環、停 Worker 後仍在 Ready
- [ ] 情境 3 reject：訊息丟棄
- [ ] 情境 4 slow：殺 Worker 後訊息回 queue、重開從頭跑
- [ ] 講得出 retry vs requeue 的差別、acks_late 的作用
- [ ] 完整系統預演：全服務啟動 → 發任務 → 驗證閉環

---

## 課程總結

你已經走完 stock-crawler 的完整旅程：從單一容器、Celery 基礎、RabbitMQ 監控、多 Worker 分流、MySQL 入庫，到錯誤處理。這套 **Producer → RabbitMQ → Celery Worker → MySQL** 的分散式架構，是資料工程最核心的骨架，可以套用到任何爬蟲或批次處理場景。
