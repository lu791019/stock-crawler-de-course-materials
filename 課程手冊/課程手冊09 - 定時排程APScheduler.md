# 第 9 章：讓 pipeline 自己動起來 — 用 APScheduler 定時排程

> 前面每次要抓資料，你都得自己下 producer 指令。真實系統不會有人半夜守著按按鈕。這一章你會裝上一個「鬧鐘」，讓任務時間到就自動派送。

---

## 做完這一章，你會做到

1. 說得出為什麼需要工作排程管理，看懂 crontab 的「分 時 日 月 星期」五欄位語法。
2. 看懂怎麼用 APScheduler 的 cron 定時呼叫 `.delay()`。
3. 讓爬蟲不用你手動觸發，自動定時跑。
4. 分得清 `BackgroundScheduler` 和 `BlockingScheduler` 的差別。
5. 順便搞懂 worker 的 concurrency 該怎麼配。

---

## 先認識：工作排程管理與 cron

### 為什麼需要工作排程管理？

- **不用人工執行**：定時自動跑，晚上或假日都可工作。
- 只要先把工作（腳本）準備好，系統就能定期幫你執行。
- 一套排程工具的基本功能有四件事：**執行時間設定**、**執行命令設定**、**一次管理多個排程**、**查看工作執行狀態**。

### 什麼是 cron 和 crontab？

- **cron** 是 Linux/Unix 系統**內建**的排程工具，讓系統在指定的時間自動執行任務。
- **crontab**（cron table）就是使用者的「任務排程清單」——裡面每一行寫著：什麼時間 → 執行什麼指令。
- 適合用來：定時跑備份、定時清理 log、定期發送報告、定時啟動 script（Python、Shell…）。
- 常用指令：`crontab -e` 編輯清單、`crontab -l` 查看目前清單。

### crontab 基本格式：分 時 日 月 星期 指令

一行代表一個任務，前五個欄位是時間、最後一個是要執行的指令：

| 欄位 | 範圍 | 說明 |
|------|------|------|
| 分 | 0–59, `*` | 幾分 |
| 時 | 0–23, `*` | 幾點 |
| 日 | 1–31, `*` | 幾號 |
| 月 | 1–12, `*` | 幾月 |
| 星期 | 0–7, `*` | 星期幾（0 和 7 都是星期日）|
| 指令 | — | 要執行的命令或腳本 |

`*` 代表「每一個都要」、`*/N` 代表「每 N 個一次」。看幾個範例：

```bash
# 1. 每分鐘執行一次
* * * * * echo "Hello World" >> /tmp/hello.log

# 2. 每天凌晨 3 點執行
0 3 * * * /home/user/backup.sh

# 3. 每週一早上 8 點執行
0 8 * * 1 python3 /home/user/report.py

# 4. 每個月 1 號凌晨 0 點執行
0 0 1 * * /home/user/cleanup.sh

# 5. 每 30 分鐘執行一次
*/30 * * * * python3 /home/user/script.py
```

> 💡 **時間格式模擬器**：cron 表達式不確定寫得對不對，丟到 [crontab.guru](https://crontab.guru/) 驗證——貼上表達式，它會用白話告訴你「什麼時候會跑」和下一次執行時間。

兩個補充：

- crontab 還支援簡寫：`@hourly`（每小時）、`@daily`（每天 0 點）、`@reboot`（開機時跑一次）……crontab.guru 頁面下方就列著這些寫法。
- **Windows 沒有 cron**：Windows 內建的對應工具是「工作排程器（Task Scheduler）」。WSL 裡的 Linux 有 `crontab` 指令，但 cron 服務預設不會啟動、WSL 一關排程也跟著停。所以本課的**正式排程**不用系統 cron——排程放在 Python 層（本章的 APScheduler）或專門的排程服務（第 10 章的 Airflow），在哪個作業系統上行為都一致。不過 cron 值得實際跑一次——下面就來動手做。

### 動手示範：讓 cron 幫你發一批任務

概念都講完了，實際讓 cron 動一次：排一條「每分鐘執行一次 print 版 producer」的工作，把任務發進 RabbitMQ 給 worker 做。這跟你前面章節手動打 producer 指令是同一件事——差別只是改由 cron 到點自動打。

**前置：把接任務的環境起起來**（等一下 cron 發的任務要有人接）：

```bash
# 起 RabbitMQ（佇列）和 Flower（監控）
docker compose -f docker-compose-local.yml up -d rabbitmq flower

# 另開一個視窗，啟動 worker（print 版任務不寫資料庫，這裡不需要 MySQL）
uv run python -m celery -A crawler.worker worker --loglevel=info
```

**1. 確認 cron 服務在跑**（Mac 內建、不用啟動；WSL / Ubuntu 用下面的指令）：

```bash
sudo service cron start
service cron status    # 顯示 running 就可以了
```

**2. 排一條每分鐘的工作。** cron 執行指令時的環境非常精簡：PATH 只有幾個系統目錄（找不到 `uv`）、工作目錄也不在專案裡（找不到 `crawler` 模組）。與其把落落長的指令塞進 crontab，實務的標準做法是**把要執行的內容包成一支腳本，crontab 只寫一行**——這正是前面說 cron「適合定時啟動 script」的原因。repo 已附好這支腳本 `example/cron_producer.sh`：

```bash
#!/bin/bash
# 補 PATH：PATH 是 shell 找指令的目錄清單。平常打 uv 找得到，是因為
# ~/.local/bin 在你的 PATH 裡；但 cron 只給極簡的 PATH（通常只有
# /usr/bin 和 /bin），找不到 uv——這行把 uv 住的目錄接到 PATH 最前面。
export PATH="$HOME/.local/bin:$PATH"
# 進入專案根目錄（此腳本位於 example/，上一層就是專案根目錄）
cd "$(dirname "$0")/.." || exit 1
# 發送一批 print 版任務（worker 收到後只印出、不寫資料庫）
uv run python -m crawler.producer_crawler_finmind_print
```

髒細節都被腳本吸收了，crontab 排程就是乾淨的一行、不需要改任何路徑：

```bash
echo '* * * * * ~/stock-crawler/example/cron_producer.sh >> /tmp/cron_producer.log 2>&1' | crontab -

crontab -l    # 確認排程真的排進去了
```

這行指令做了什麼，拆開來看：

- `echo '...'`：印出單引號裡那行排程文字。
- `|`（管線）：把左邊印出的文字，交給右邊的指令當輸入。
- `crontab -`：結尾的 `-` 表示「從輸入讀取排程清單」——把管線送進來的那行文字，設定成你的 crontab 內容。跟 `crontab -e` 開編輯器手動編輯是同一件事，只是用一行指令完成。
- 排程行本身由三段組成：`* * * * *`（五個欄位全是星號＝每分鐘執行）→ 要執行的腳本路徑 → `>> /tmp/cron_producer.log 2>&1`（把腳本的輸出**附加**寫進這個檔案；`>>` 是附加、`>` 是覆蓋；`2>&1` 表示錯誤訊息也一起導進同一個檔案——cron 在背景執行、沒有畫面，輸出不寫進檔案的話，跑成功或跑失敗你都看不到）。

> ⚠️ 一個要知道的行為：`crontab -` 會**整份取代**你目前的排程清單，不是往裡面加一行。現在你的清單是空的所以沒影響；如果哪天已經有其他排程，就改用 `crontab -e` 開編輯器加行，才不會把舊排程蓋掉。

**3. 等到下一個整分**（cron 的最小單位是一分鐘，這是它做不到秒級的具體體驗）。時間到了看兩個地方：

```bash
tail /tmp/cron_producer.log
# 會看到 producer 印出這一批發送的股票代碼：
# 2330
# 0050
# 2317
# ...
```

同時看 worker 的視窗：出現一批 `crawler_finmind_print` 任務 `received`、接著印出爬到的資料——**你沒有打任何指令，是 cron 到點幫你打的**。

**4. 看完就把排程清掉**，不然它會每分鐘一直發：

```bash
crontab -r    # 移除目前使用者的全部 crontab 排程
```

worker 和服務先留著別關——下面的 APScheduler 主線會繼續用。

cron 版跑通了，它的限制你也體驗到了：最小單位一分鐘、到點只能執行 shell 指令。把它跟等一下要跑的 APScheduler 版放在一起比較：

| | cron 版（剛剛做的）| APScheduler 版（本章主線，等下就做）|
|---|---|---|
| 誰在計時 | 作業系統的 cron 服務 | 你的 Python 程式裡的排程器 |
| 到點做什麼 | 執行一條 shell 指令（就是你以前手動打的 producer 指令）| 呼叫一個 Python 函式（`.delay()`）|
| 最小時間單位 | 一分鐘 | 一秒（`second` 欄位）|
| 程式關掉之後 | 排程還在——cron 是系統服務，跟你的程式無關 | 排程跟著消失——它跑在你的程式行程裡 |

> 最後一列是 cron 的優勢：它不依賴你的程式活著。但它到點只能執行 shell 指令、拿不到程式裡的物件，秒級也做不到——這正是本章接下來改用 APScheduler、下一章再升級 Airflow 的原因。

### 在自己的電腦上做這個示範，要注意什麼

上面的指令以課程的 Linux 環境為準。換到自己的機器上做，先對照下面的差異：

- **WSL（Windows 的 Linux 子系統）**：cron 服務預設沒有啟動，示範前要先執行 `sudo service cron start`（每次重開 WSL 都要再啟動一次）。另外 WSL 視窗一關，裡面的 cron 排程也跟著停——所以它只適合當課堂示範，不適合掛真正的長期排程。
- **Mac**：`crontab` 內建可用、cron 服務不用手動啟動。第一次使用時系統可能跳出權限詢問（詢問終端機是否能管理電腦），允許即可。
- **專案路徑**：crontab 那行寫的是 `~/stock-crawler`——如果你把專案 clone 在別的位置，把這段換成你實際的專案路徑。
- **uv 的安裝位置**：腳本假設 uv 裝在 `~/.local/bin`（官方安裝腳本的預設位置）。如果你是用別的方式裝的（例如 Homebrew），先用 `which uv` 查出實際位置，再把腳本裡 `export PATH` 那行的目錄改成你的。
- **示範完記得清理**：`crontab -r` 一定要執行——忘了的話，這條排程會每分鐘持續發任務，worker 沒開時任務就一直堆在 RabbitMQ 裡。

---

## 從 cron 到 APScheduler

cron 很好用，但它到點只能執行一條 **shell 指令**。我們要做的事是「到點呼叫 Celery 任務的 `.delay()`」——這是 Python 程式裡的函式呼叫，用 cron 就得繞一圈（包一支腳本再讓 cron 執行它）。這一章改用 **APScheduler**（**A**dvanced **P**ython **Scheduler**）：Python 的排程套件，在程式裡註冊「什麼時間、執行哪個函式」，它到點自動呼叫。專案的 `pyproject.toml` 已列入 `apscheduler==3.10.4`，`uv sync` 過就能用，不需另外安裝。

三個定位重點：

- **跑在你的程式行程內（in-process）**：它不是獨立服務。排程只在你的 Python 程式執行期間有效；程式一關，排程就停（本章結尾的常見錯誤表會再遇到這件事）。
- **跟 cron 的差別**：cron 是作業系統層級，到點執行一條 shell 指令；APScheduler 在程式內排程，到點呼叫一個 **Python 函式**——能直接使用程式裡的物件。另外 APScheduler 的 cron 觸發器比 crontab 多一個 `second` 欄位（crontab 最小單位是分鐘），所以排得出「每 5 秒」這種工作。
- **三種觸發器（trigger）**：`cron`（指定時刻，例如每天 18:00）、`interval`（固定間隔，例如每 30 秒一次）、`date`（一次性，指定某個時間點跑一次）。本章主線用 `cron`——上一節學的五欄位語法直接沿用；章末練習 4 會用 `interval` 對照兩者的語意差別。

---

## 先搞懂：排程器是鬧鐘，不是工人

前面每次抓資料都要你手動下 `producer` 指令。**排程器就是那個鬧鐘**：時間到，它自動幫你把任務丟進 RabbitMQ，剩下的交給 Celery。

請把分工記清楚：**排程器決定「何時發」，Celery（worker）決定「怎麼做」。** 排程器本身不爬蟲，它只是定時呼叫 `.delay()`，真正的爬蟲還是 worker 在跑。這一章不會取代前面任何東西，只是在最前面加一個自動觸發器。

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `crawler/scheduler_print.py` | 排程（print 版）| 定時派送「只印出、不寫資料庫」的任務，教學時先用這一版觀察流程 |
| `crawler/scheduler.py` | 排程（正式版）| 定時派送會寫入資料庫的正式爬蟲任務，流程確認沒問題後切換到這一版 |
| `crawler/scheduler_blocking.py` | 排程（阻塞版）| 改用 `BlockingScheduler`，作為 Background 版的對照組 |

---

## 一行一行讀懂 `scheduler.py`

### 定時要做的事：發一批爬蟲任務

```python
from crawler.tasks_crawler_finmind import crawler_finmind

# 發送一批股票的爬蟲任務。內容跟你前面手動執行的 producer 完全相同——
# 差別只是「誰來呼叫它」：以前是你在終端機打指令，現在是排程器到點自動呼叫。
def send_crawler_stock_price_task():
    for stock_id in ["2330", "0050", "2317", "0056", "00713"]:
        logger.info(stock_id)  # 印出目前發送的股票代碼，方便對照 log
        crawler_finmind.delay(stock_id=stock_id)  # 把任務訊息丟進 RabbitMQ，發完立刻返回、不等爬完
```

這就是「鬧鐘響了要做的事」——把那批股票的任務 `.delay()` 出去。注意它做的事跟你前面手動跑的 producer 一模一樣，只是現在改由排程器來呼叫。

### 建立排程器、註冊工作

```python
from apscheduler.schedulers.background import BackgroundScheduler

# timezone 一定要明寫，否則會用系統時區（容器常是 UTC，跟台北差 8 小時）
scheduler = BackgroundScheduler(timezone="Asia/Taipei")

# 工作 A：每 5 秒印一次 hello_world——教學觀察用，讓你馬上看到排程在動
scheduler.add_job(
    id="hello_world",    # 工作的唯一識別名稱，重複註冊同名工作會報錯
    func=hello_world,    # 到點要執行的函式（傳函式本身，不加括號）
    trigger="cron",      # 用 cron 風格指定時間
    second="*/5",        # 秒數每 5 秒符合一次——這個秒欄位是系統 crontab 沒有的
    coalesce=True,       # 錯過多次排程時，恢復後只補跑一次
)

# 工作 B：每 12 小時的整點發一批爬蟲（正式任務）
scheduler.add_job(
    id="send_crawler_stock_price_task",
    func=send_crawler_stock_price_task,
    trigger="cron",
    hour="*/12", minute="0", second="0",  # 小時每 12 小時符合一次、分和秒都是 0＝整點
    coalesce=True,
)

scheduler.start()  # 啟動排程器；Background 版這一行不會卡住，程式會繼續往下走
```

一段一段看：

- `BackgroundScheduler(timezone="Asia/Taipei")`：建立一個「背景執行」的排程器，時區明寫台北。**不設的話會用系統時區**——容器和雲端主機的系統時區常常是 UTC，跟台北差 8 小時：你以為排的是 18:00，實際卻在台北時間凌晨 2 點跑。所以排程程式一律明寫時區。
- `add_job(...)`：註冊一個定時工作。`trigger="cron"` 表示用 cron 風格排程：
  - 工作 A 用 `second="*/5"`：每 5 秒跑一次。這個是**故意放的教學用工作**，讓你上課當下就看到排程在動，不用真的等 12 小時。
  - 工作 B 用 `hour="*/12", minute="0", second="0"`：每 12 小時的整點跑一次真正的爬蟲。
- `coalesce=True`：如果程式當機、錯過了好幾次排程，恢復後只補跑一次，不會連續補跑多次。
- 順帶一提：如果上一輪還沒跑完、下一輪時間又到了，APScheduler 預設同一個工作**最多同時一個實例**（`max_instances=1`），新的那輪會被跳過並在 log 印警告。所以排程間隔要抓得比任務執行時間長。

### 為什麼結尾有一個 `while True: sleep`

```python
if __name__ == "__main__":
    main()
    # 主程式一結束，背景執行緒的排程器也跟著消失——所以用無限迴圈保持主程式存活。
    # sleep 的秒數不影響排程精準度，排程由背景執行緒自己計時。
    while True:
        time.sleep(600)
```

因為 `BackgroundScheduler` 是在**背景執行緒**跑的，如果主程式跑完就結束，背景的排程器也會跟著被收掉。這個 `while True: sleep` 是為了讓主程式持續執行，排程器才能持續運作。（下面會看到 `BlockingScheduler` 就不需要這一段。）

---

## Background vs Blocking（`scheduler_blocking.py`）

```python
from apscheduler.schedulers.blocking import BlockingScheduler
scheduler = BlockingScheduler(timezone="Asia/Taipei")
# ...add_job 的寫法跟 Background 版完全相同...
scheduler.start()  # 這一行會「卡住」主執行緒：程式停在這裡專心跑排程，之後的程式碼不會被執行
```

差別是：

- **`BackgroundScheduler`**：在背景執行緒跑，`start()` 之後主程式可以繼續做別的事（所以要自己寫 `while True` 保持存活）。
- **`BlockingScheduler`**：`start()` 會**卡住**主執行緒，程式停在該行，只執行排程工作（所以不需要 `while True`）。適合「這支程式就是專門在跑排程」的情況，例如丟進一個容器單獨跑。

---

## 排程在跑了，執行狀態去哪看？

本章開頭列過排程工具的第四項基本功能：「能夠查看工作執行狀態」。逐項檢查手上這兩個工具：

- **cron**：預設只能翻系統 log（Ubuntu 在 `/var/log/syslog`，`grep CRON` 過濾），只記「有沒有執行」，指令失敗了不會主動通知你。
- **APScheduler**：只有你自己用 `logger` 印的訊息。哪天跑過、哪次失敗、失敗了要不要補——全部要自己寫程式處理。

也就是說，這兩個工具都只做好了前三項（時間設定、命令設定、管理多個排程），第四項「查看執行狀態」都很弱。**這正是下一章 Airflow 要解決的問題**：每次執行都有紀錄、每個步驟都有 log、失敗能在網頁上單獨重跑。

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

> 如果你剛做完前面的 cron 示範：RabbitMQ、Flower 和 worker 已經在跑了，這裡只是補起 MySQL 和 phpMyAdmin（`up -d` 對已經在跑的服務不會重複啟動），worker 那行不用再執行一次。

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

### Step 4：跑 blocking 版，觀察差別

```bash
uv run crawler/scheduler_blocking.py
```

在 `scheduler.start()` 後面加一行 `print("這行會執行嗎？")`，它**不會被印出**——因為 `start()` 卡住了主執行緒。這就是 blocking 的意思。

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | hello_world 的訊息每 5 秒固定出現一次 | 排程器真的在照設定的時間觸發工作 |
| 2 | 你沒有手動執行 producer，任務仍然自動進了 RabbitMQ | 定時自動派送的機制成功運作 |
| 3 | blocking 版在 `start()` 之後的程式碼不會被執行 | 你分得清 blocking 和 background 兩種排程器的差別 |
| 4 | crontab 排的工作每到整分自動發任務、worker 收到 | 系統層的 cron 也能驅動同一條 pipeline，而且你體驗到它的一分鐘粒度限制 |

---

## 想一想（確認你懂了）

先自己想過再看答案。

**Q1：排程器和 worker，誰在「決定何時做」、誰在「實際做」？**

排程器決定「何時做」——時間到就呼叫 `.delay()` 把任務丟出去；worker 負責「實際做」——從 RabbitMQ 拿任務、真的去爬。排程器自己不爬蟲。所以就算你沒開排程器，手動下 producer 一樣能觸發 worker；排程器只是把「手動」變「自動」。

**Q2：我們的爬蟲是 CPU 密集還是 I/O 密集？concurrency 該往哪個方向調？**

I/O 密集（大部分時間在等網路）。這種任務可以開遠高於核心數的併發，甚至改用 `--pool=gevent --concurrency=100` 之類的協程池，讓一大堆任務同時「等」，吞吐量會大幅提升。反之 CPU 密集才綁核心數。

**Q3：`BackgroundScheduler` 為什麼要在結尾加 `while True: sleep`，`BlockingScheduler` 卻不用？**

因為 Background 是在背景執行緒跑，主程式一結束它就被收掉，所以要用 `while True` 讓主程式持續執行。Blocking 的 `start()` 本身就會卡住主執行緒、讓程式停在那裡，主程式不會結束，所以不需要額外保活。

**Q4：Celery 不是自帶排程器（Celery Beat）嗎？為什麼這章用 APScheduler？**

可以用 Beat——它做的事一樣：定時把任務丟進佇列。本課選 APScheduler 有兩個理由：一是它是**通用**排程套件，不綁 Celery，之後在任何 Python 專案（就算沒有 Celery）都能用同一套；二是它的觸發器概念（cron / interval / date）跟下一章 Airflow 的排程設定一脈相承。Beat 的用法需要時查官方文件就好——分工概念跟本章完全相同：排程器發任務、worker 執行。

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

**練習 4：換一種觸發器——interval**

把 hello_world 的觸發方式從 cron 改成固定間隔：

```python
scheduler.add_job(
    id="hello_world", func=hello_world,
    trigger="interval", seconds=10,
)
```

重跑，確認一樣是每 10 秒一次。差別在語意：**cron 適合「指定時刻」**（每天 18:00、每週一 8 點），**interval 適合「固定頻率」**（每 10 秒、每 30 分鐘）——「每 10 秒」用 interval 寫比 cron 的 `second="*/10"` 更直白。做完這題，三種觸發器裡最常用的兩種你都摸過了。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| 排程時間跑掉、對不上 | 建立排程器時沒有設定時區，用到了系統時區（常常是 UTC，跟台北差 8 小時）| 建立排程器時加上 `timezone="Asia/Taipei"` |
| 關掉終端機排程就停 | APScheduler 跑在你的程式行程裡，程式結束排程就跟著結束 | 正式環境要用容器或 systemd 讓程式常駐（這也是第 10 章 Airflow 的動機之一）|
| 錯過排程後連續補跑多次 | 註冊工作時沒有設定 coalesce | 在 `add_job` 加上 `coalesce=True`，恢復後只會補跑一次 |
| Background 版一啟動就結束 | 主程式跑完就退出，背景的排程器跟著被收掉 | 在檔案結尾加上 `while True: time.sleep(...)` 保持主程式存活 |

---

## 這一章你學到了

- crontab 用「分 時 日 月 星期 指令」五個欄位描述一個排程任務；Windows 沒有 cron，對應的內建工具是工作排程器（Task Scheduler）。
- cron 是作業系統層級的排程，到點執行一條 shell 指令；APScheduler 是程式內的排程，到點呼叫一個 Python 函式，所以能直接觸發 `.delay()`，而且多了 crontab 沒有的 `second` 欄位。
- 排程器扮演的是鬧鐘：時間到就呼叫 `.delay()` 把任務發出去，實際的爬蟲和寫入仍然交給 Celery worker 執行。
- cron 觸發搭配 `coalesce=True` 是常用組合；排程程式一律明確寫上時區，避免系統時區是 UTC 造成排程時間對不上。
- BackgroundScheduler 需要保活迴圈才不會跟著主程式結束；BlockingScheduler 的 `start()` 會卡住主執行緒。I/O 密集的任務適合開遠高於核心數的併發。
- cron 和 APScheduler 都看不到執行歷史、也沒有管理介面——這正是下一章 Airflow 要解決的問題。

## 下一章要做什麼

APScheduler 是輕量鬧鐘：時間到就觸發，但它看不到任務之間的依賴、失敗了也只能自己寫補償邏輯。**接下來三章進入工業級的工作流引擎 Airflow：先架起來跑通第一個 DAG（第 10 章）、學進階 Operator（第 11 章），最後把整條爬蟲 pipeline 編排成生產級工作流（第 12 章）。**
