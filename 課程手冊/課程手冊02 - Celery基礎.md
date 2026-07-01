# Celery 基礎 實作手冊

> 對象：已完成「爬蟲概念與 stock-crawler 入門」的學員
> 涵蓋：啟動 RabbitMQ + Flower → 本地啟動 Celery Worker → 發第一個 task → 發 FinMind 爬蟲 task → Flower 監控
> 實作專案：https://github.com/lu791019/stock-crawler-de-course-materials

---

## 這一集在做什麼

把上一集認識的元件真正串起來，完整走一次 Celery 的 Producer → Broker → Worker 流程：

```
Producer 發任務 → RabbitMQ 排隊 → Celery Worker 取出並執行
   (.delay())       (broker)          (@app.task 的函式)
                        ↑
                   Flower 監控任務狀態
```

這一集 Worker 跑在**本地**（不是 Docker），只有 RabbitMQ 和 Flower 用 Docker 起。

---

## 使用前提

```bash
cd ~/stock-crawler
uv sync                   # 確認套件已裝
docker --version          # Docker 可用
```

✅ **預期**：`uv sync` 完成，`.venv` 存在。

---

## 目錄

- [第一部分：啟動 RabbitMQ + Flower](#第一部分啟動-rabbitmq--flower)
- [第二部分：本地啟動 Celery Worker](#第二部分本地啟動-celery-worker)
- [第三部分：發第一個 print 版 task](#第三部分發第一個-print-版-task)
- [第四部分：發 FinMind 爬蟲 task](#第四部分發-finmind-爬蟲-task)
- [第五部分：Flower 監控](#第五部分flower-監控)
- [第六部分：停止服務](#第六部分停止服務)

---

## 第一部分：啟動 RabbitMQ + Flower

Broker（RabbitMQ）和監控介面（Flower）用 Docker 起。

### Step 1：啟動

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml up -d rabbitmq flower
```

> 只起 `rabbitmq` 和 `flower` 兩個服務，其他先不動。

### Step 2：確認服務 Up

```bash
docker compose -f docker-compose-local.yml ps
```

✅ **預期**：`rabbitmq` 和 `flower` 兩個都是 `Up`。

### Step 3：確認 Web 介面

| 服務 | 網址 | 帳密 |
|------|------|------|
| RabbitMQ 管理 | http://localhost:15672 | worker / worker |
| Flower 監控 | http://localhost:5555 | （無需登入） |

```bash
curl -o /dev/null -w "RabbitMQ: %{http_code}\n" http://localhost:15672
curl -o /dev/null -w "Flower: %{http_code}\n" http://localhost:5555
```

✅ **預期**：兩個都回 `200`。

> Flower 剛啟動時 log 可能有短暫的 Connection refused（RabbitMQ 還沒 ready），幾秒後會自動重連，屬正常。

---

## 第二部分：本地啟動 Celery Worker

Worker 是「消費者」，從 RabbitMQ 取出任務執行。這一集在本地跑（不是 Docker）。

### Step 1：開一個新終端機，啟動 Worker

```bash
cd ~/stock-crawler
uv run celery -A crawler.worker worker --loglevel=info
```

- `-A crawler.worker`：指定 Celery app 在 `crawler/worker.py`
- `worker`：啟動 worker 模式
- `--loglevel=info`：顯示詳細日誌

✅ **預期**：log 印出設定與 ready 訊息：

```
    RABBITMQ_HOST: 127.0.0.1
    RABBITMQ_PORT: 5672
    WORKER_ACCOUNT: worker
    WORKER_PASSWORD: worker

 -------------- celery@你的主機名 v5.5.0
[tasks]
  . crawler.tasks.crawler
  . crawler.tasks_crawler_finmind.crawler_finmind
  . crawler.tasks_crawler_finmind.crawler_finmind_print
celery@你的主機名 ready.
```

看到 `ready.` 和 `[tasks]` 列出的 task 清單 = Worker 已連上 RabbitMQ，隨時待命。

> ⚠️ 這個終端機**保持不要關**，Worker 要一直跑著。下面發任務要另開新終端機。

---

## 第三部分：發第一個 print 版 task

回到**原本的終端機**（Worker 那個保持開著），發一個最簡單的 print task。

### Step 1：發送 task

```bash
cd ~/stock-crawler
uv run python -c "from crawler.tasks import crawler; crawler.delay(x=0)"
```

`crawler.delay(x=0)` = 把 `crawler` 任務丟進 RabbitMQ，Worker 會取出來執行。

### Step 2：回 Worker 終端機看 log

✅ **預期**：Worker 那邊出現：

```
[INFO] Task crawler.tasks.crawler[...] received
crawler
execute task: 0...
0 done.
upload db
[INFO] Task crawler.tasks.crawler[...] succeeded in Xs: 0
```

看到 `received` → 執行 → `succeeded` = Producer/Broker/Worker 三方打通了。

---

## 第四部分：發 FinMind 爬蟲 task

換成真正抓股價的 task（print 版，只抓不寫 DB）。

### Step 1：發送批次爬蟲任務

```bash
cd ~/stock-crawler
uv run python crawler/producer_crawler_finmind_print.py
```

這支 producer 用 for 迴圈一次發 5 支股票（2330、0050、2317、0056、00713）到預設 queue。

✅ **預期**：producer 終端機印出：

```
2330
0050
2317
0056
00713
```

### Step 2：回 Worker 終端機看 log

✅ **預期**：Worker 依序收到 5 個任務，每個都印出對應股票的 DataFrame，最後 `succeeded`：

```
[INFO] Task crawler.tasks_crawler_finmind.crawler_finmind_print[...] received
         date stock_id  Trading_Volume  ...   close ...
0  2024-01-02     2330       ...
...
[INFO] Task ...crawler_finmind_print[...] succeeded in Xs: None
```

看到 5 支股票的 DataFrame 都被印出 = 爬蟲 task 透過 Celery 分散式執行成功。

---

## 第五部分：Flower 監控

Flower 是 Celery 的 Web 監控介面。

### Step 1：開 Flower

瀏覽器開 http://localhost:5555

### Step 2：觀察重點

| 頁籤 | 看什麼 |
|------|--------|
| **Dashboard** | Worker 清單、線上狀態、已處理任務數 |
| **Tasks** | 每個任務的名稱、狀態（SUCCESS / FAILURE）、耗時、參數 |
| **Workers** | 點進 worker 看它監聽哪些 queue、concurrency 幾個 |

✅ **預期**：
- Dashboard 看到你的 worker 是 Online
- Tasks 頁籤看到剛剛發的 6 個任務（1 個 print + 5 個爬蟲），狀態都是 `SUCCESS`

> Flower 是排錯時第一個要看的地方：任務是不是有到、有沒有失敗、耗時多久，一目了然。

---

## 第六部分：停止服務

### Step 1：停 Worker

回 Worker 終端機，按 `Ctrl+C`。

✅ **預期**：看到 `worker: Warm shutdown` 後 Worker 退出。

### Step 2：停 Docker 服務

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml down
```

✅ **預期**：`rabbitmq`、`flower` 被移除。

> 若要連 volume 一起清掉（RabbitMQ 資料）：`docker compose -f docker-compose-local.yml down -v`

---

## 本集完成清單

- [ ] `docker compose -f docker-compose-local.yml up -d rabbitmq flower` 啟動 broker + 監控
- [ ] curl 確認 15672 / 5555 都是 200
- [ ] 本地啟動 Celery Worker，看到 `ready.` 和 task 清單
- [ ] 發第一個 print task，Worker log 看到 `succeeded`
- [ ] 發 FinMind 爬蟲 task，看到 5 支股票 DataFrame
- [ ] Flower 看到任務狀態 SUCCESS
- [ ] 正常停止 Worker 和 Docker 服務

---

## 下集預告

下一集深入 RabbitMQ 管理介面，並把 MySQL + phpMyAdmin + Portainer 一起加進來，學會用四個 Web 介面觀察整個系統、建立排錯 SOP。
