# Demo Fail — Celery 失敗處理教學

示範 Celery Worker 處理失敗時，訊息在 RabbitMQ 中的不同行為。

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `worker_demo.py` | 獨立的 Celery app（不影響原本的 worker.py） |
| `tasks_demo_fail.py` | 4 個模擬失敗的 task |
| `producer_demo_fail.py` | 發送 demo task 的 producer |

## 4 個情境

### 情境 1：task_might_fail — 自動重試

```
Producer 發任務 → RabbitMQ → Worker 拿出來
  → 50% 成功 → ack → 訊息消失 ✅
  → 50% 失敗 → self.retry() → 發新任務回 queue → 5 秒後重試
  → 重試 3 次都失敗 → FAILURE → ack → 訊息消失
```

程式碼關鍵：
```python
@app.task(bind=True, acks_late=True, max_retries=3, default_retry_delay=5)
def task_might_fail(self, stock_id):
    if random.random() < 0.5:
        raise self.retry(exc=Exception("模擬錯誤"))  # 發新任務回 queue
```

### 情境 2：task_requeue — 訊息留在 MQ（重點教學）

```
Producer 發任務 → RabbitMQ → Worker 拿出來
  → 失敗 → Reject(requeue=True) → 原訊息放回 queue
  → Worker 又拿出來 → 又失敗 → 又放回 → 無限循環 ♻️
  → 訊息永遠不會消失，直到你停掉 Worker
```

程式碼關鍵：
```python
@app.task(bind=True, acks_late=True)
def task_requeue(self, stock_id):
    raise Reject(reason="處理失敗", requeue=True)  # 原訊息放回 queue
```

### 情境 3：task_reject_no_requeue — 訊息丟棄

```
Producer 發任務 → RabbitMQ → Worker 拿出來
  → 失敗 → Reject(requeue=False) → 訊息直接丟棄
```

### 情境 4：task_slow — 中途殺 Worker

```
Producer 發任務 → RabbitMQ → Worker 拿出來
  → 跑 30 秒 → 你在第 10 秒 Ctrl+C 殺 Worker
  → 因為 acks_late=True，還沒 ack → 訊息回到 queue
  → 重新開 Worker → 任務從頭再跑
```

## retry vs requeue 的差別

| | self.retry() | Reject(requeue=True) |
|---|---|---|
| 訊息行為 | 發**新任務**到 queue | **原訊息**放回 queue |
| 有次數限制？ | 有（max_retries） | 沒有 |
| 最終結果 | 成功或 FAILURE | 永遠留在 queue |
| RabbitMQ 看到 | 新訊息 | 同一個訊息 |

## 操作步驟

```bash
# 1. 啟動 RabbitMQ + Flower
docker compose -f docker-compose-local.yml up -d rabbitmq flower

# 2. 發任務（先不開 Worker）
uv run crawler/producer_demo_fail.py

# 3. 去 RabbitMQ UI 看 Queues → celery → Messages Ready（應該有 2 個）
#    http://localhost:15672（worker / worker）

# 4. 開 Worker 觀察行為
uv run python -m celery -A crawler.worker_demo worker --loglevel=info --concurrency=1

# 5. 觀察：
#    - task_might_fail：成功或重試後成功/失敗
#    - task_requeue：一直重複 ❌ → requeue → ❌ → requeue...
#    - RabbitMQ UI：Ready ↔ Unacked 一直跳

# 6. Ctrl+C 停 Worker
#    去 RabbitMQ UI 看：REQUEUE_TEST 訊息還在 Ready 裡

# 7. 清理
docker compose -f docker-compose-local.yml down -v
```

## 進階：測試情境 3 和 4

取消 `producer_demo_fail.py` 裡的註解，發送情境 3（丟棄）或情境 4（慢任務）。
