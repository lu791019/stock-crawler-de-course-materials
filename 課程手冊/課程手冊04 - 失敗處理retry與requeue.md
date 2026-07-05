# 第 4 章：任務失敗、Worker 掛掉怎麼辦 — retry、requeue 與訊息的命運

> 這是「會用」和「懂原理」差最多的一章。前面都在讓任務成功，這一章你要故意讓它失敗、故意把 worker 殺掉，親眼看訊息在 RabbitMQ 裡到底發生什麼事。

---

## 做完這一章，你會做到

1. 親手驗證 config.py 的「環境變數覆蓋」，搞懂同一份程式為什麼本機和 Docker 都能跑。
2. 分得清 `self.retry()`（重試）和 `Reject(requeue=True)`（放回佇列）本質差在哪。
3. 懂 `acks_late=True` 的意義：做完才確認，沒做完就回佇列。
4. 會用 RabbitMQ 管理介面觀察 Ready / Unacked 的變化。
5. 建立「分散式系統要為失敗而設計」的心態。

---

## 熱身：親手驗證環境變數覆蓋（5 分鐘）

第 1 章讀過 `config.py` 的 `os.environ.get(key, default)`，這裡花 5 分鐘親手驗證它，順便把「本機 vs Docker」的環境切換觀念釘死——這觀念跟這一章的「掛掉重連」一樣，都是部署時的基本功。

**實驗 1：不設環境變數（用預設值）**

```bash
uv run python -c "from crawler.config import RABBITMQ_HOST; print('RABBITMQ_HOST =', RABBITMQ_HOST)"
```

✅ **預期**：`RABBITMQ_HOST = 127.0.0.1`（預設值）

**實驗 2：設環境變數覆蓋**

```bash
RABBITMQ_HOST=rabbitmq uv run python -c "from crawler.config import RABBITMQ_HOST; print('RABBITMQ_HOST =', RABBITMQ_HOST)"
```

✅ **預期**：`RABBITMQ_HOST = rabbitmq`（被覆蓋了，程式碼一行沒改）

**實驗 3：看 worker 啟動時印出的設定**

```bash
uv run python -c "import crawler.worker"
```

✅ **預期**：loguru 印出當前的 `RABBITMQ_HOST / RABBITMQ_PORT / WORKER_ACCOUNT / WORKER_PASSWORD`。之後你懷疑「環境變數到底有沒有吃到」，看這幾行就知道。

**這就是本機和 Docker 能共用一份程式的原因**——看 `docker-compose-local.yml` 裡 worker 服務的設定：

```yaml
worker_twse:
  environment:
    - RABBITMQ_HOST=rabbitmq    # 覆蓋預設 127.0.0.1
    - MYSQL_HOST=mysql          # 覆蓋預設 127.0.0.1
```

| | 本機執行 | Docker 容器內 |
|---|---|---|
| `RABBITMQ_HOST` | `127.0.0.1`（預設值） | `rabbitmq`（compose 覆蓋）|
| `MYSQL_HOST` | `127.0.0.1`（預設值） | `mysql`（compose 覆蓋）|
| 為什麼不同 | 服務 port 有映射到本機 | 容器之間用**服務名稱**當主機名互連 |

---

## 先搞懂：ack 是什麼

Worker 從 RabbitMQ 拿到一則訊息、成功處理後，要回報一個 **ack（確認）**，RabbitMQ 收到 ack 才會把這則訊息刪掉。反過來說：

- **沒 ack 的訊息不會消失**，RabbitMQ 會認為「可能還沒處理完」而保留它。
- **`acks_late=True`** 表示「**做完才 ack**」。所以如果 worker 做到一半掛掉、還沒 ack，這則訊息會回到佇列給別人重做。（預設 `acks_late=False` 是「一拿到就先 ack」，worker 掛掉任務就沒了。）

這一章用一個**獨立的 Celery app**（`worker_demo.py`）來示範，不影響你前面用的 `worker.py`。

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `crawler/worker_demo.py` | 獨立的 app | `task_demo`，全域開啟 `acks_late` 與 `task_reject_on_worker_lost` |
| `crawler/tasks_demo_fail.py` | 任務定義 | 四個模擬失敗的任務 |
| `crawler/producer_demo_fail.py` | 生產者 | 發送 demo 任務 |
| `crawler/DEMO_FAIL_README.md` | 官方說明 | 情境說明與對照表 |

`worker_demo.py` 的關鍵設定：

```python
app = Celery("task_demo", include=["crawler.tasks_demo_fail"], broker=...)
app.conf.task_acks_late = True                 # 做完才確認
app.conf.task_reject_on_worker_lost = True     # worker 掛掉時，任務重新排隊
```

---

## 四個情境，一行一行讀懂

### 情境 1：`task_might_fail` — 失敗自動重試

```python
@app.task(bind=True, acks_late=True, max_retries=3, default_retry_delay=5)
def task_might_fail(self, stock_id):
    print(f"開始處理 {stock_id}...（第 {self.request.retries + 1} 次嘗試）")
    if random.random() < 0.5:                        # 50% 機率失敗
        print(f"❌ {stock_id} 失敗！5 秒後重試")
        raise self.retry(exc=Exception(f"{stock_id} 模擬錯誤"))
    print(f"✅ {stock_id} 處理成功！")
    return f"{stock_id} done"
```

- `bind=True`：讓第一個參數變成 `self`（指向這個任務物件），才能用 `self.retry()` 和 `self.request.retries`（第 1 章的深入段落提過）。
- `max_retries=3, default_retry_delay=5`：最多重試 3 次，每次間隔 5 秒。
- **`self.retry()` 的本質**：它**發一則新任務**回佇列去重試，有次數上限，超過就標記為 FAILURE 並 ack（訊息消失）。

### 情境 2：`task_requeue` — 訊息放回佇列（重點）

```python
@app.task(bind=True, acks_late=True)
def task_requeue(self, stock_id):
    print(f"❌ {stock_id} 處理失敗！訊息放回 queue")
    raise Reject(reason="處理失敗", requeue=True)     # 原訊息放回 queue
```

- `Reject(requeue=True)` 把**原本那則訊息**丟回佇列。
- **它沒有次數限制** → worker 又拿出來、又失敗、又放回……**無限循環**，訊息永遠不消失，直到你停掉 worker。
- 這是 RabbitMQ 管理介面上最好看的示範：Ready ↔ Unacked 一直跳。

### 情境 3：`task_reject_no_requeue` — 訊息丟棄

```python
raise Reject(reason="處理失敗", requeue=False)        # 直接丟棄，不放回
```

失敗就把訊息扔掉，效果等同 `acks_late=False` 失敗時的行為——訊息直接消失。

### 情境 4：`task_slow` — 做到一半殺掉 worker

```python
@app.task(acks_late=True)
def task_slow(stock_id, seconds=30):
    for i in range(seconds):
        time.sleep(1)
        print(f"  {stock_id} 進度 {i+1}/{seconds}")
    return f"{stock_id} done"
```

- 這任務要跑 30 秒；你在第 10 秒 `Ctrl+C` 殺掉 worker。
- 因為 `acks_late=True`、還沒 ack，**訊息回到佇列**；你重開 worker，任務會**從頭再跑一次**。

### retry vs requeue 對照（背下這張表）

| | `self.retry()` | `Reject(requeue=True)` |
|---|---|---|
| 訊息行為 | 發**新任務**到 queue | **原訊息**放回 queue |
| 有次數限制？ | 有（`max_retries`）| 沒有 |
| 最終結果 | 成功、或 FAILURE | 永遠留在 queue |
| RabbitMQ 看到 | 一則新訊息 | 同一則訊息 |

---

## 一步一步跟著做

### Step 1：只需要 RabbitMQ + Flower

```bash
docker compose -f docker-compose-local.yml up -d rabbitmq flower
curl -o /dev/null -s -w "RabbitMQ: %{http_code}\n" http://localhost:15672
```

> ✅ curl 回 200。

### Step 2：先「不開 worker」就發任務

```bash
uv run crawler/producer_demo_fail.py
```

`producer_demo_fail.py` 預設發**情境 1（2330）**和**情境 2（REQUEUE_TEST）**兩個任務。

✅ **預期**：印出 `sent 2330`、`sent REQUEUE_TEST`、發送完畢的提示。

### Step 3：去 RabbitMQ UI 看「還沒被處理」的訊息

打開 http://localhost:15672（worker/worker）→ Queues → `celery`，看 **Messages Ready**。

> ✅ 因為還沒開 worker，情境 1、2 的兩則任務會停在 Ready = 2，沒人處理。這就證明了：訊息送進佇列後會**等**，不會因為沒人處理就消失。

### Step 4：開 worker（併發設 1，才看得清楚）

```bash
uv run python -m celery -A crawler.worker_demo worker --loglevel=info --concurrency=1
```

注意這裡指向的是 `crawler.worker_demo`，不是平常的 `crawler.worker`——失敗情境的任務註冊在這個獨立的 app 裡。

### Step 5：邊看 worker log、邊看 RabbitMQ UI

- `task_might_fail`（2330）：可能一次就成功，或「❌ 失敗 → 5 秒後重試」幾次後成功 / 3 次後放棄（FAILURE）。
- `task_requeue`（REQUEUE_TEST）：**一直重複消費、一直放回**，你會看到 log 不停印「處理失敗」，RabbitMQ UI 的 Ready ↔ Unacked 不停跳。

> ✅ 看到 REQUEUE_TEST 無限循環，就代表你抓到 requeue 的行為了。

**再做一個關鍵觀察**：`Ctrl+C` 停掉 worker，回 RabbitMQ UI 看 `celery` 佇列——REQUEUE_TEST 的訊息**還躺在 Ready 裡**。它從來沒被成功 ack 過，所以永遠留在佇列。

### Step 6：測情境 3 — 訊息丟棄

編輯 `crawler/producer_demo_fail.py`，取消情境 3 的註解：

```python
task_reject_no_requeue.delay(stock_id="REJECT_TEST")
```

重新發送、開 worker。

✅ **預期**：worker 印出「訊息丟棄」，然後 RabbitMQ 的 Ready **歸 0**——訊息真的消失了，不像情境 2 那樣循環。這就是 `requeue=False` 和 `requeue=True` 的差別。

### Step 7：測情境 4 — 中途殺 worker，驗證 acks_late

取消 `producer_demo_fail.py` 情境 4 的註解：

```python
task_slow.delay(stock_id="SLOW_TEST", seconds=30)
```

操作順序：

1. 發任務 → 開 worker，看到 `進度 1/30、2/30...`
2. 大約第 10 秒按 `Ctrl+C` 殺掉 worker
3. 回 RabbitMQ UI → ✅ SLOW_TEST 的訊息**回到 Ready**
4. 重開 worker → ✅ 任務**從頭**再跑（進度從 1/30 重來）

> **關鍵**：`acks_late=True` 代表「做完才確認」。worker 中途掛掉 → 沒 ack → 訊息不遺失、重新排隊。這是保證任務不丟的核心設定。

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | 環境變數實驗：預設值 vs 覆蓋 | 同一份程式靠環境變數跑不同環境 |
| 2 | 開 worker 前，celery 佇列 Ready = 2 | 訊息會在佇列等待 |
| 3 | REQUEUE_TEST 無限重複消費 | `Reject(requeue=True)` 沒有次數上限 |
| 4 | 停 worker 後 REQUEUE_TEST 還在 Ready | 它從沒被成功處理過 |
| 5 | REJECT_TEST 後 Ready 歸 0 | `requeue=False` 直接丟棄訊息 |
| 6 | 殺 worker 後 SLOW_TEST 從頭再跑 | `acks_late` 讓被殺的任務不遺失 |

---

## 收工

```bash
docker compose -f docker-compose-local.yml down     # 保留資料
```

---

## 想再深入一點

- **為什麼要用一個獨立的 `worker_demo` app？** 因為這一章要全域開啟 `acks_late` 和 `task_reject_on_worker_lost` 這些「危險」設定來做實驗，作者不想污染你平常在用的 `worker.py`。這也示範了一個好習慣：做破壞性實驗時，開一個獨立環境。
- **`Reject` 的效果依賴 `acks_late`。** `Reject(requeue=True)` 之所以能把訊息放回佇列，前提是 `acks_late=True`（訊息還沒被確認）。如果用預設的 `worker.py`（沒開 acks_late），你看不到一樣的效果。
- **情境 2 是一個「毒訊息（poison message）」的教學陷阱。** 一則永遠處理失敗、又一直被放回的訊息，會卡住 worker、佔用資源。正式系統要防這個：設定「重試上限」或「死信佇列（DLQ）」——超過幾次就把它移到另一條佇列冷處理，而不是無限循環。
- **`acks_late` 是可靠性的雙面刃。** 它保證「worker 掛掉不遺失任務」，但代價是任務可能被**執行兩次**（做到一半掛掉、重跑一次）。所以搭配 `acks_late` 的任務最好是**冪等的**——重跑也不會出問題。什麼是冪等、怎麼做到，第 6 章會完整教。

---

## 想一想（確認你懂了）

**Q1：`self.retry()` 和 `Reject(requeue=True)` 最大的差別是什麼？哪個會無限循環？**

`self.retry()` 是「發一則新任務」去重試，有 `max_retries` 上限，超過就放棄（FAILURE）。`Reject(requeue=True)` 是把「原訊息」放回佇列，**沒有次數上限**，所以會無限循環，直到你停掉 worker 或訊息被成功處理。會無限循環的是後者。

**Q2：`acks_late=True` 為什麼能讓「被殺掉的 worker」不遺失任務？**

因為 ack 是「做完才回報」。worker 被殺時任務還沒做完、還沒 ack，RabbitMQ 就認為這則訊息還沒被處理完，於是把它放回佇列給別的 worker（或重開後的 worker）重做。所以任務不會因為 worker 中途掛掉而消失。

**Q3：情境 2 那種「毒訊息」在正式系統會造成什麼災難？該怎麼防？**

一則永遠失敗又一直被放回的訊息，會讓 worker 不停地拿它、失敗、放回，白白吃掉處理能力，甚至卡住整條佇列讓正常任務也慢下來。防法：設「重試上限」，或設「死信佇列（DLQ）」，超過次數就把它移去別的地方冷處理、發警報，而不是讓它無限循環。

**Q4：同一份程式碼，在本機連 `127.0.0.1`、在容器裡連 `rabbitmq`，是怎麼做到的？**

靠 `config.py` 的 `os.environ.get(key, default)`：本機沒設環境變數就用預設值 `127.0.0.1`；compose 裡用 `environment` 設了 `RABBITMQ_HOST=rabbitmq`，容器裡的程式讀到的就是服務名。程式碼一行不用改——這是熱身實驗親手驗證過的。

---

## 換你試試看

**練習 1：讓重試「看得見」**

只發情境 1（`task_might_fail`），開 worker（`--concurrency=1`），連續觀察好幾輪。你會看到 log 印出「第 N 次嘗試」，有時第一次就成功，有時重試兩三次才成功、或最後放棄。把「重試次數」和「最後結果」記幾筆下來，你就理解 `max_retries` 和 `default_retry_delay` 實際怎麼運作。

**練習 2：親手製造「毒訊息」再看 RabbitMQ**

只發情境 2（REQUEUE_TEST），開一個 worker，打開 RabbitMQ UI 的 `celery` 佇列頁面，盯著 **Ready** 和 **Unacked** 這兩個數字。你會看到它們一直在 0↔1 之間跳——訊息被拿走（Unacked=1）、失敗放回（Ready=1）、又被拿走……用自己的話描述這個循環，你就懂 requeue 了。看完把 worker 停掉，確認那則訊息還在 Ready 裡。

**練習 3：驗證 `acks_late` 保住任務**

發情境 4（`task_slow`，把 producer 對應註解打開），開 worker，等它印到「進度 10/30」左右時 `Ctrl+C` 殺掉。到 RabbitMQ UI 確認那則訊息回到 Ready，然後重開 worker——你會看到它**從進度 1 重新開始跑**。這讓你親眼證明「acks_late 讓被中斷的任務不遺失」，也讓你體會為什麼這種任務最好是冪等的。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| `Reject` 好像沒效果 | 用了平常的 `worker.py`（沒開 acks_late）| 這章要用 `-A crawler.worker_demo`，它有開 acks_late |
| 看不清訊息命運 | 併發太高，多個任務交錯 | 加 `--concurrency=1` |
| worker 一直被 REQUEUE_TEST 佔住 | 這是情境 2 的預期行為 | 看夠了就 `Ctrl+C`；正式環境要設重試上限 / DLQ |
| 指向錯的 app | 用了 `-A crawler.worker` | 這章要 `-A crawler.worker_demo` |
| 情境 3/4 沒反應 | producer 裡的註解沒打開 | 編輯 `producer_demo_fail.py` 取消對應註解再發 |

---

## 這一章你學到了

- 環境變數覆蓋讓同一份程式在本機（127.0.0.1）和 Docker（服務名）都能跑。
- ack 是訊息生命的開關；`acks_late` 決定「何時確認」。
- retry 是發新訊息、有上限；requeue 是放回原訊息、無上限。
- `acks_late` 保證不遺失任務，但可能重跑，所以任務最好冪等（第 6 章會教）。
- 分散式系統要為失敗而設計。

## 下一章要做什麼

訊息的可靠性有了保障，但資料到目前都只是印出來、看過就忘。**下一章你會正式把資料存下來——拿掉 `_print`，改用會寫進 MySQL 的 `crawler_finmind`，讓爬回來的股價真正落地。**
