# 第 9 章：讓 pipeline 自己動起來 — 用 APScheduler 定時排程

> 前面每次要抓資料，你都得自己下 producer 指令。真實系統不會有人半夜守著按按鈕。這一章你會裝上一個「鬧鐘」，讓任務時間到就自動派送。

---

## 做完這一章，你會做到

1. 看懂怎麼用 APScheduler 的 cron 定時呼叫 `.delay()`。
2. 讓爬蟲不用你手動觸發，自動定時跑。
3. 分得清 `BackgroundScheduler` 和 `BlockingScheduler` 的差別。
4. 順便搞懂 worker 的 concurrency 該怎麼配。

---

## 先搞懂：排程器是鬧鐘，不是工人

前面每次抓資料都要你手動下 `producer` 指令。**排程器就是那個鬧鐘**：時間到，它自動幫你把任務丟進 RabbitMQ，剩下的交給 Celery。

請把分工記清楚：**排程器決定「何時發」，Celery（worker）決定「怎麼做」。** 排程器本身不爬蟲，它只是定時呼叫 `.delay()`，真正的爬蟲還是 worker 在跑。這一章不會取代前面任何東西，只是在最前面加一個自動觸發器。

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `crawler/scheduler_print.py` | 排程（print 版）| 定時派送 print 版任務，方便你觀察 |
| `crawler/scheduler.py` | 排程（正式版）| 定時派送會寫 DB 的任務 |
| `crawler/scheduler_blocking.py` | 排程（阻塞版）| 用 `BlockingScheduler` 做對照 |

---

## 一行一行讀懂 `scheduler.py`

### 定時要做的事：發一批爬蟲任務

```python
from crawler.tasks_crawler_finmind import crawler_finmind

def send_crawler_stock_price_task():
    for stock_id in ["2330", "0050", "2317", "0056", "00713"]:
        logger.info(stock_id)
        crawler_finmind.delay(stock_id=stock_id)   # 定時觸發 Celery 任務
```

這就是「鬧鐘響了要做的事」——把那批股票的任務 `.delay()` 出去。注意它做的事跟你前面手動跑的 producer 一模一樣，只是現在改由排程器來呼叫。

### 建立排程器、註冊工作

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler(timezone="Asia/Taipei")

# 工作 A：每 5 秒印一次 hello_world（純粹讓你馬上看到排程在動）
scheduler.add_job(
    id="hello_world", func=hello_world, trigger="cron",
    second="*/5", coalesce=True,
)

# 工作 B：每 12 小時整點發一批爬蟲
scheduler.add_job(
    id="send_crawler_stock_price_task", func=send_crawler_stock_price_task,
    trigger="cron", hour="*/12", minute="0", second="0", coalesce=True,
)

scheduler.start()
```

一段一段看：

- `BackgroundScheduler(timezone="Asia/Taipei")`：建立一個「背景執行」的排程器，時區設台北（不設的話排程時間會跑掉）。
- `add_job(...)`：註冊一個定時工作。`trigger="cron"` 表示用 cron 風格排程：
  - 工作 A 用 `second="*/5"`：每 5 秒跑一次。這個是**故意放的教學用工作**，讓你上課當下就看到排程在動，不用真的等 12 小時。
  - 工作 B 用 `hour="*/12", minute="0", second="0"`：每 12 小時的整點跑一次真正的爬蟲。
- `coalesce=True`：如果程式當機、錯過了好幾次排程，醒來只補跑一次，不會一次爆發一堆。

### 為什麼結尾有一個 `while True: sleep`

```python
if __name__ == "__main__":
    main()
    while True:
        time.sleep(600)   # 保持主程式存活
```

因為 `BackgroundScheduler` 是在**背景執行緒**跑的，如果主程式跑完就結束，背景的排程器也會跟著被收掉。這個 `while True: sleep` 是為了讓主程式一直活著，排程器才能持續運作。（下面會看到 `BlockingScheduler` 就不需要這一段。）

---

## Background vs Blocking（`scheduler_blocking.py`）

```python
from apscheduler.schedulers.blocking import BlockingScheduler
scheduler = BlockingScheduler(timezone="Asia/Taipei")
# ...add_job 相同...
scheduler.start()          # 這一行會「卡住」主執行緒，之後的程式不會執行
```

差別是：

- **`BackgroundScheduler`**：在背景執行緒跑，`start()` 之後主程式可以繼續做別的事（所以要自己寫 `while True` 保持存活）。
- **`BlockingScheduler`**：`start()` 會**卡住**主執行緒，程式就停在那裡專心當排程器（所以不需要 `while True`）。適合「這支程式就是專門在跑排程」的情況，例如丟進一個容器單獨跑。

---

## 補充：worker 的 concurrency 怎麼配

任務開始頻繁自動跑了，正好講一下 worker 併發：**關鍵不在 CPU 核心數，而在任務是「CPU 密集」還是「I/O 密集」。**

我們的爬蟲是**典型 I/O 密集**（大部分時間在等 FinMind 回應，第 2 章講過）。這種任務用預設的 prefork 綁核心數太浪費，可以用協程池開高併發：

```bash
# I/O 密集：用 gevent 池，開幾百個協程都很輕量（要先 uv add gevent）
uv run python -m celery -A crawler.worker worker --pool=gevent --concurrency=100

# CPU 密集（大量運算）：維持 prefork，貼齊核心數
uv run python -m celery -A crawler.worker worker --pool=prefork --concurrency=4
```

---

## 一步一步跟著做

### Step 1：基礎設施 + worker

```bash
docker compose -f docker-compose-local.yml up -d rabbitmq flower mysql phpmyadmin
uv run python -m celery -A crawler.worker worker --loglevel=info
```

### Step 2：啟動排程器（先用 print 版，馬上看得到）

```bash
uv run crawler/scheduler_print.py
```

**你會看到**：排程器每 5 秒印一次

```
========================hello_world=====================
```

> ✅ 看到 hello_world 每 5 秒固定跳一次，就代表排程真的在動。

### Step 3：確認自動派送

你**不用**手動下 producer。等排程時間到（工作 B 是每 12 小時，教學時可以先把它的 `hour` 暫時改成 `"*"`、`minute="*/1"` 讓它每分鐘跑，方便看效果），就會自動有任務進 RabbitMQ、worker 開始抓。

### Step 4：試試 blocking 版，感受差別

```bash
uv run crawler/scheduler_blocking.py
```

在 `scheduler.start()` 後面加一行 `print("這行會執行嗎？")`，你會發現它**永遠不會被印出**——因為 `start()` 卡住了主執行緒。這就是 blocking 的意思。

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | hello_world 每 5 秒固定跳 | 排程器在定時觸發 |
| 2 | 不手動下 producer，任務也會自動進 RabbitMQ | 自動派送成功 |
| 3 | blocking 版 `start()` 之後的程式不執行 | 理解 blocking vs background |

---

## 想一想（確認你懂了）

先自己想過再看答案。

**Q1：排程器和 worker，誰在「決定何時做」、誰在「實際做」？**

排程器決定「何時做」——時間到就呼叫 `.delay()` 把任務丟出去；worker 負責「實際做」——從 RabbitMQ 拿任務、真的去爬。排程器自己不爬蟲。所以就算你沒開排程器，手動下 producer 一樣能觸發 worker；排程器只是把「手動」變「自動」。

**Q2：我們的爬蟲是 CPU 密集還是 I/O 密集？concurrency 該往哪個方向調？**

I/O 密集（大部分時間在等網路）。這種任務可以開遠高於核心數的併發，甚至改用 `--pool=gevent --concurrency=100` 之類的協程池，讓一大堆任務同時「等」，吞吐量會大幅提升。反之 CPU 密集才綁核心數。

**Q3：`BackgroundScheduler` 為什麼要在結尾加 `while True: sleep`，`BlockingScheduler` 卻不用？**

因為 Background 是在背景執行緒跑，主程式一結束它就被收掉，所以要用 `while True` 讓主程式一直活著。Blocking 的 `start()` 本身就會卡住主執行緒、讓程式停在那裡，主程式不會結束，所以不需要額外保活。

---

## 換你試試看

**練習 1：讓爬蟲每分鐘自動跑一次**

把 `scheduler_print.py` 裡工作 B 的觸發條件暫時改成每分鐘：

```python
trigger="cron", minute="*/1", second="0", coalesce=True,
```

跑起來後不要碰它，等一分鐘，你會看到任務自動被送出、worker 自動開始抓。這讓你確認「自動化」真的成立——你已經離開一整分鐘沒動手了。（測完記得改回去。）

**練習 2：對照 Background 與 Blocking**

分別跑 `scheduler.py` 和 `scheduler_blocking.py`，各自在 `start()` 後面加一行 `print("after start")`。觀察哪一個印得出來、哪一個印不出來，並用自己的話解釋。這會讓你把兩種 scheduler 的差別記牢。

**練習 3：把 hello_world 改成每 10 秒**

把 `second="*/5"` 改成 `second="*/10"`，重跑，確認間隔真的變成 10 秒。這讓你熟悉 cron 欄位的寫法（秒 / 分 / 時 / 星期），之後要排「每天收盤後跑一次」就會寫了。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| 排程時間跑掉、對不上 | 沒設時區 | 加 `timezone="Asia/Taipei"` |
| 關掉終端機排程就停 | APScheduler 跟著程式生命週期 | 正式環境要用容器 / systemd 常駐（這也是第 10 章 Airflow 的動機之一）|
| 錯過排程被瘋狂補跑 | 沒設 coalesce | 加 `coalesce=True` |
| Background 版一啟動就結束 | 少了保活迴圈 | 結尾加 `while True: time.sleep(...)` |

---

## 這一章你學到了

- 排程器是鬧鐘，定時呼叫 `.delay()`，執行仍交給 Celery。
- cron 觸發 + `coalesce` 是常用組合。
- Background 要保活、Blocking 會卡住主執行緒；I/O 密集任務適合開高併發。

## 下一章要做什麼

APScheduler 是輕量鬧鐘：時間到就觸發，但它看不到任務之間的依賴、失敗了也只能自己寫補償邏輯。**接下來三章進入工業級的工作流引擎 Airflow：先架起來跑通第一個 DAG（第 10 章）、學進階 Operator（第 11 章），最後把整條爬蟲 pipeline 編排成生產級工作流（第 12 章）。**
