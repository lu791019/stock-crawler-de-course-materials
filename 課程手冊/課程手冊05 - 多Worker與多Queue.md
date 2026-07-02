# 多 Worker 與多 Queue 實作手冊

> 對象：已完成「RabbitMQ 深入與 Web 管理介面」的學員
> 涵蓋：多 Worker（twse / tpex）→ 多 Queue 分流 → Flower 觀察分工 → `--scale` 動態擴充 → 為什麼 Worker 可以 scale
> 實作專案：https://github.com/lu791019/stock-crawler-de-course-materials

---

## 這一集在做什麼

前面只有一個 Worker 消化所有任務。這一集學會**分流**：把上市（twse）和上櫃（tpex）股票分到不同 queue，各由專門的 Worker 處理；再用 `--scale` 動態增加 Worker 數量。

```
                    ┌── twse queue ──→ worker_twse
Producer ──分流──→ │
                    └── tpex queue ──→ worker_tpex

scale 後：twse queue ──→ worker_twse × 3（三個一起搶）
```

---

## 使用前提

```bash
cd ~/stock-crawler
docker --version
docker compose version
```

✅ **預期**：Docker、Compose 可用。

---

## 目錄

- [第一部分：啟動 infra](#第一部分啟動-infra)
- [第二部分：啟動多 Worker（twse + tpex）](#第二部分啟動多-workertwse--tpex)
- [第三部分：發任務到多 Queue](#第三部分發任務到多-queue)
- [第四部分：Flower 觀察多 Worker 分工](#第四部分flower-觀察多-worker-分工)
- [第五部分：--scale 動態擴充](#第五部分--scale-動態擴充)
- [第六部分：為什麼 Worker 可以 scale](#第六部分為什麼-worker-可以-scale)

---

## 第一部分：啟動 infra

先起 broker、監控、資料庫。

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml up -d rabbitmq flower mysql phpmyadmin
```

✅ **驗證**：

```bash
docker compose -f docker-compose-local.yml ps
curl -o /dev/null -w "RabbitMQ:   %{http_code}\n" http://localhost:15672
curl -o /dev/null -w "Flower:     %{http_code}\n" http://localhost:5555
```

✅ **預期**：四個服務 Up、兩個 curl 回 200。

---

## 第二部分：啟動多 Worker（twse + tpex）

用 `docker-compose-local.yml` 裡定義好的 `worker_twse` 和 `worker_tpex` 兩個服務。它們各自用 `-Q` 監聽不同 queue：

- `worker_twse`：`--hostname=twse@%h -Q twse`（只吃 twse queue）
- `worker_tpex`：`--hostname=tpex@%h -Q tpex`（只吃 tpex queue）

### Step 1：build + 啟動兩個 Worker

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml up -d --build worker_twse worker_tpex
```

> 第一次要 build（下載 base image + `uv sync`），需要幾分鐘。

### Step 2：確認兩個 Worker ready

```bash
docker compose -f docker-compose-local.yml logs worker_twse | grep ready
docker compose -f docker-compose-local.yml logs worker_tpex | grep ready
```

✅ **預期**：

```
celery@twse ready.
celery@tpex ready.
```

---

## 第三部分：發任務到多 Queue

`producer_multi_queue.py` 用 `.s()` signature + `apply_async(queue=...)` 把不同股票送到不同 queue：

```python
crawler_finmind.s(stock_id="2330").apply_async(queue="twse")     # 上市 → twse
crawler_finmind.s(stock_id="00679B").apply_async(queue="tpex")   # 上櫃 → tpex
```

### Step 1：發任務

用容器內的 producer 服務發（會寫 DB）：

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml up producer
```

✅ **預期**：前景執行，看到：

```
send task_2330 task
send task_00679b task
```
exit code 0 = 發送成功。

> 若想用「只印出不寫 DB」的版本觀察，可在本地跑：
> `uv run python crawler/producer_multi_queue_print.py`

### Step 2：確認 Worker 各自收到

```bash
docker compose -f docker-compose-local.yml logs worker_twse | grep succeeded
docker compose -f docker-compose-local.yml logs worker_tpex | grep succeeded
```

✅ **預期**：
- `worker_twse` 處理 2330（succeeded）
- `worker_tpex` 處理 00679B（succeeded）

**關鍵**：2330 只被 twse worker 處理、00679B 只被 tpex worker 處理 —— 這就是 queue 分流。

---

## 第四部分：Flower 觀察多 Worker 分工

瀏覽器開 http://localhost:5555

| 頁籤 | 觀察 |
|------|------|
| **Dashboard** | 看到兩個 Worker：`twse@...` 和 `tpex@...`，都 Online |
| **Workers** | 點 `twse@...` 看它的 Registered queues 只有 `twse` |
| **Tasks** | 2330 的 worker 欄是 twse，00679B 的 worker 欄是 tpex |

✅ **預期**：Tasks 頁能清楚看到「哪個任務被哪個 Worker 處理」，證明分流生效。

---

## 第五部分：--scale 動態擴充

這一段改用 `compose-advanced/` 的網路版檔案，示範用 `--scale` 讓同一種 Worker 跑多份。

> ⚠️ 先把上面的整合版停掉，避免 port 衝突：
> `docker compose -f docker-compose-local.yml down`

### Step 1：建立共用 network

`compose-advanced/` 的檔案都連到外部 network `my_network`，要先建：

```bash
cd ~/stock-crawler
docker network create my_network
```

✅ **預期**：印出 network id。

### Step 2：啟動 RabbitMQ + Flower（網路版）

```bash
docker compose -f compose-advanced/rabbitmq-network.yml up -d
```

✅ **驗證**：`curl -o /dev/null -w "%{http_code}\n" http://localhost:15672` → 200

### Step 3：啟動 MySQL + phpMyAdmin（網路版）

```bash
docker compose -f compose-advanced/mysql.yml up -d
```

✅ **驗證**：`curl -o /dev/null -w "%{http_code}\n" http://localhost:8080` → 200

### Step 4：用 --scale 啟動 3 個 twse Worker

`docker-compose-worker-network.yml` 定義了 `crawler_twse` 和 `crawler_tpex`。用 `--scale` 把 `crawler_twse` 開成 3 份：

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml up -d --scale crawler_twse=3
```

> 這裡的 worker service 沒有固定 `container_name`，才能 scale 成多份（若寫死 container_name，scale 會衝突）。

### Step 5：確認起了 3 個 twse Worker

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml ps
```

✅ **預期**：看到 `crawler_twse` 有 3 個實例（名稱結尾 -1 / -2 / -3），`crawler_tpex` 有 1 個。

### Step 6：發一批 twse 任務觀察分工

發 6 支股票到 twse queue，看 3 個 Worker 一起搶：

```bash
uv run python -c "
from crawler.tasks_crawler_finmind import crawler_finmind_print
for sid in ['2330', '2317', '2454', '2412', '1301', '1216']:
    crawler_finmind_print.s(stock_id=sid).apply_async(queue='twse')
    print('sent', sid)
"
```

✅ **預期**：印出 6 行 `sent ...`。

> 若本地沒裝套件，也可用容器發：進任一 worker 容器執行同樣的 python，或用 producer 網路版檔案。

### Step 7：看 log 確認 3 個 Worker 分擔

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml logs crawler_twse | tail -40
```

✅ **預期**：6 個任務被 **3 個不同的 worker 實例**分擔處理（log 前綴的 hostname 不同），總處理時間比單一 Worker 快。

### Step 8：縮回 1 個 Worker

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml up -d --scale crawler_twse=1
```

✅ **預期**：多出來的 twse Worker 被停掉，只剩 1 個。

### Step 9：關閉所有服務

```bash
docker compose -f compose-advanced/docker-compose-worker-network.yml down
docker compose -f compose-advanced/rabbitmq-network.yml down
docker compose -f compose-advanced/mysql.yml down -v
docker network rm my_network
```

✅ **預期**：容器全部移除、network 刪掉。

---

## 第六部分：為什麼 Worker 可以 scale

Celery Worker 能任意增減份數，靠三個設計：

| 特性 | 說明 | 帶來的好處 |
|------|------|-----------|
| **無狀態（Stateless）** | Worker 不在本機保存任何狀態，每個任務都是獨立的 | 隨便加減 Worker 都不會弄亂資料 |
| **不開對外 port** | Worker 只「主動連出去」抓 RabbitMQ 的任務，不需要別人連進來 | 不會 port 衝突，才能開多份 |
| **共用 broker** | 所有 Worker 都連同一個 RabbitMQ，從同一條 queue 搶任務 | 加 Worker = 更多手一起搶，自動負載平衡 |

### 對照：為什麼 RabbitMQ / MySQL 不能隨便 scale

| | Worker | RabbitMQ / MySQL |
|---|---|---|
| 有狀態？ | 無 | 有（訊息 / 資料）|
| 開對外 port？ | 否 | 是（5672 / 3306）|
| scale 多份？ | ✅ 隨意 | ❌ 需要 cluster 設定 |

> 記住這句：**要 scale 的東西必須無狀態、不搶 port、共用同一個資料/訊息來源。** Celery Worker 剛好三者都符合，所以是分散式系統裡最容易水平擴充的部分。

---

## 本集完成清單

- [ ] 啟動 infra（rabbitmq + flower + mysql + phpmyadmin）
- [ ] `up -d --build worker_twse worker_tpex` 起兩個分流 Worker，都 ready
- [ ] 發 multi queue 任務，twse / tpex 各自處理對應股票
- [ ] Flower 看到兩個 Worker 分工
- [ ] `docker network create my_network` + 網路版 compose
- [ ] `--scale crawler_twse=3` 開 3 份，發 6 支股票看分擔
- [ ] `--scale crawler_twse=1` 縮回、關閉所有服務
- [ ] 講得出 Worker 能 scale 的三個原因（無狀態、不開 port、共用 broker）

---

## 下集預告

下一集把爬到的股價**真正寫進 MySQL**：建資料表、用 SQLAlchemy 連線、跑完整 pipeline、用 SQL 驗證資料入庫。
