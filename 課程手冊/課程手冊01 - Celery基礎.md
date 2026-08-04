# 第 1 章：跑起你的第一個 Celery — 認識 Producer / Broker / Worker

> 這一章你不會寫任何真實邏輯，只用一個「假任務」把 Celery 的骨架完整跑一遍。目標是搞懂「非同步派送」到底是什麼。這是整套系統的地基，請務必自己動手跑成功再往下走。

---

## 做完這一章，你會做到

1. 用 Docker 把 RabbitMQ 跑起來，並打開它的管理介面看到佇列。
2. 認識整個專案的結構，知道每支檔案在哪一章會用到。
3. 啟動一個 Celery worker，看到它印出「我認得哪些任務」。
4. 用 producer 一次派送 100 個任務。
5. 確認任務是「同時併發」而不是「一個做完才做下一個」。
6. 多開一個 worker，看到兩個 worker 分著做同一批任務——這就是分散式。

---

## Step 0：開始前，先把環境準備好

下面每一步都自己跑一次，確認沒問題再往下。環境沒弄好，後面全部會卡住。

### 0-1 確認 Docker 和 Git 可用

```bash
docker --version
docker compose version
git --version
```

你應該看到類似這樣：

```
Docker version 27.x.x, build ...
Docker Compose version v2.x.x
git version 2.x.x
```

> ✅ 三個都有印出版本號、而且 Docker Desktop 是「執行中」，就過關。如果看到 `Cannot connect to the Docker daemon`，代表 Docker 沒開，先去打開 Docker Desktop。

### 0-2 安裝 uv（一個比 pip 快很多的套件管理器）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

> ✅ 有印出版本號就過關。

### 0-3 把專案抓下來、裝好套件

```bash
git clone https://github.com/lu791019/stock-crawler-de-course-materials.git stock-crawler
cd stock-crawler                          # 之後所有指令都要在這個「根目錄」下執行

uv python install 3.11
uv venv --python 3.11
uv sync                                   # 自動安裝專案需要的所有套件
```

> ✅ `uv sync` 沒有紅字錯誤、而且出現了 `.venv/` 資料夾，就過關。
>
> ⚠️ 提醒你一個之後最常犯的錯：**指令一定要在專案根目錄執行**。因為程式碼裡的 import 都寫成 `crawler.xxx`，你只要跑到別的資料夾去下指令，就會出現 `ModuleNotFoundError`。養成習慣：下指令前先打 `pwd` 確認自己在根目錄。

### 0-4 用 VS Code 打開專案（建議）

```bash
code .
```

接下來每一章都會反覆對照程式碼，用編輯器開著專案邊讀邊做，效率最好。

---

## 先認識專案長什麼樣子

這個 repo 就是接下來所有章節共用的教材。先看一次全貌，之後每一章都只會用到其中幾支檔案：

```
stock-crawler/
├── crawler/                                  ← Python Package（所有程式碼都在這）
│   ├── config.py                             ← 環境變數管理（第 1 章）
│   ├── worker.py                             ← Celery app 定義（第 1 章）
│   ├── tasks.py                              ← 假任務 print 版（第 1 章）
│   ├── producer.py                           ← 派送 100 個假任務（第 1 章）
│   ├── tasks_crawler_finmind.py              ← 真實爬蟲 task：print 版 + 寫 DB 版（第 2、4 章）
│   ├── producer_crawler_finmind_print.py     ← 批次發爬蟲（print 版）（第 2 章）
│   ├── producer_multi_queue_print.py         ← 多佇列分流（print 版）（第 3 章）
│   ├── producer_crawler_finmind.py           ← 批次發爬蟲（寫 DB 版）（第 5 章）
│   ├── producer_multi_queue.py               ← 多佇列分流（寫 DB 版）（第 5 章）
│   ├── upload_data_to_mysql.py               ← MySQL 上傳小工具（第 5 章）
│   ├── tasks_crawler_finmind_duplicate.py    ← 去重 upsert 版 task（第 6 章）
│   ├── producer_crawler_finmind_duplicate.py ← 去重版 producer（第 6 章）
│   ├── scheduler_print.py                    ← 定時排程 print 版（第 9 章）
│   ├── scheduler.py                          ← 定時排程正式版（第 9 章）
│   ├── scheduler_blocking.py                 ← BlockingScheduler 對照版（第 9 章）
│   ├── worker_demo.py                        ← 失敗情境專用 Celery app（第 4 章）
│   ├── tasks_demo_fail.py                    ← 4 種失敗情境 task（第 4 章）
│   ├── producer_demo_fail.py                 ← 發失敗情境任務（第 4 章）
│   ├── mysql.py                              ← MySQL 工具模組：View、查詢（第 12 章）
│   ├── bigquery.py                           ← BigQuery 工具模組（第 15 章）
│   ├── stock_sync_mysql_to_bigquery.py       ← MySQL → BigQuery 回填工具（第 15 章補充）
│   └── stock_bigquery_data_transform.py      ← BigQuery 分析表建立（第 15 章）
├── docker-compose-local.yml                  ← 一鍵啟動基礎服務（第 1 章就會用）
├── compose-advanced/                         ← 進階：拆開的 compose + 多 worker 網路版（第 3 章）
├── docker-compose-all.yml                    ← 全服務整合版（第 13 章壓軸）
├── airflow/                                  ← Airflow：Dockerfile、compose、DAGs（第 10-12 章）
├── metabase/                                 ← Metabase compose（第 8 章）
├── example/                                  ← SQL 範例、pandas 練習、獨立爬蟲範例（隨堂補充）
├── Dockerfile                                ← Worker 容器化（第 3 章）
├── pyproject.toml / uv.lock                  ← Python 依賴管理
└── README.md                                 ← 專案總覽與學習順序
```

> 樹狀圖只列出課程會用到的檔案。repo 裡另有少數輔助腳本（`upload_*.py`、`download_*.py` 等），用途見 README。

### 這個專案的設計哲學：漸進式

每個概念都有「簡化版先跑通，正式版再深入」兩個版本。你每一章只多學一個新概念，不會一次被複雜度淹沒：

| 概念 | 簡化版（先跑通） | 正式版（再深入） |
|------|----------------|----------------|
| Task | `tasks.py`（只 print） | `tasks_crawler_finmind.py`（真的爬 API） |
| Producer | `producer.py`（發假任務） | `producer_crawler_finmind.py`（批次爬蟲） |
| 不寫 DB → 寫 DB | `crawler_finmind_print`（只印出） | `crawler_finmind`（寫 MySQL + CSV） |
| 單佇列 → 多佇列 | 預設 celery 佇列 | `producer_multi_queue.py`（twse/tpex 分流） |
| 會重複 → 冪等 | append 寫入 | `tasks_crawler_finmind_duplicate.py`（upsert） |
| 手動 → 自動 | 手動跑 producer | `scheduler.py`（APScheduler 定時） |
| 成功 → 失敗處理 | 一般 task | `tasks_demo_fail.py`（retry / requeue / reject） |
| 單機 DB → 雲端倉儲 | MySQL | BigQuery |
| 陽春排程 → 專業編排 | APScheduler | Airflow DAG |

---

## 先搞懂觀念：用一間餐廳理解四個角色

把整套系統想像成一間餐廳：

| 角色 | 餐廳裡是誰 | 在程式裡是什麼 |
|------|-----------|---------------|
| **Producer 生產者** | 點餐的客人 | `producer.py`，呼叫 `.delay()` 送出任務 |
| **Broker / RabbitMQ** | 出單機、掛單區 | RabbitMQ 容器，任務在這裡排隊 |
| **Worker 工作者** | 廚師 | 你用 `celery ... worker` 啟動的行程 |
| **Result Backend** | 取餐區（可有可無）| 存放結果的地方，這一章用不到 |

**為什麼要把客人和廚師分開？** 這正是 Celery 存在的全部理由，有三個好處：

1. **不卡住**：客人點完就走，不用站在廚房乾等。→ 你的主程式送出任務後可以立刻繼續做別的事。
2. **好擴充**：客人一多，多請幾個廚師就好，客人端完全不用改。→ 想加速，多開 worker 就行。
3. **不怕出事**：某個廚師突然離場，訂單還在掛單區，換人接手就好。→ worker 掛掉，任務還在 broker，可以由別的 worker 處理。

### 「同步」和「非同步」差在哪（用時間軸看）

假設有 3 個任務、每個要做 3 秒：

```
同步（直接呼叫函式）：
  你的程式 |--task1(3s)--|--task2(3s)--|--task3(3s)--|   總共 9 秒，全程動彈不得

非同步（用 .delay 丟給 Celery）：
  你的程式 |送1|送2|送3|  ← 幾乎瞬間送完就繼續
  worker        |--task1--|
                |--task2--|   ← 三個任務一起做，大約 3 秒完成
                |--task3--|
```

這張圖就是這一章要驗證的東西。待會實作時你會自己驗證它。

---

## 這四支檔案怎麼串在一起

它們的 import（誰依賴誰）方向是往下收斂的：

```
producer.py  ──import──▶  tasks.py  ──import app──▶  worker.py  ──import──▶  config.py
（送任務）                （定義任務）              （建立 app）           （連線設定）
```

| 檔案 | 角色 | 一句話 |
|------|------|--------|
| `crawler/config.py` | 設定中心 | 集中管理 RabbitMQ / MySQL 連線 |
| `crawler/worker.py` | Celery app 核心 | 建立 `app`、指定 broker、`include` 任務 |
| `crawler/tasks.py` | 任務定義 | 用 `@app.task` 註冊假任務 `crawler(x)` |
| `crawler/producer.py` | 生產者 | 迴圈派送 100 個任務 |

> 有件事先記住：這個專案把 Celery 的 `app` 放在 **`worker.py`** 裡（不是常見的 `celery_app.py`）。所以 `worker.py` 既是「app 定義檔」，也是等一下 `celery` 指令要指向的目標。

---

## 一行一行讀懂這四支檔案

### ① `config.py`：為什麼需要一個「設定中心」

```python
import os

# os.environ.get(key, default)：有設環境變數就用它，沒有就用預設值
WORKER_ACCOUNT  = os.environ.get("WORKER_ACCOUNT", "worker")
WORKER_PASSWORD = os.environ.get("WORKER_PASSWORD", "worker")

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "127.0.0.1")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))   # int() 是因為環境變數讀出來是字串

MYSQL_HOST     = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT     = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_ACCOUNT  = os.environ.get("MYSQL_ACCOUNT", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "1234")
```

這裡有兩個觀念你一定要懂：

- **為什麼不把 `127.0.0.1`、`worker` 直接寫死在每個檔案裡？** 因為連線資訊會隨環境改變（你自己的電腦 vs 雲端主機）。全部集中在這一支，之後要改只改一個地方。
- **`os.environ.get(key, default)` 的巧妙**：你在自己電腦開發時用預設值（方便），部署到正式環境時用環境變數覆蓋（安全又有彈性），而**程式碼一行都不用改**。
- `RABBITMQ_PORT` 外面包了一層 `int()`：環境變數讀出來一律是字串，但連線需要數字，忘了轉型會在連線時報錯。

先預告一個之後會反覆遇到的情境——**同一份程式，在本機跑和在 Docker 容器裡跑，連線目標不一樣**：

| 變數 | 本機執行（預設值） | 在 Docker 容器裡跑時 |
|------|------------------|--------------------|
| `RABBITMQ_HOST` | `127.0.0.1` | `rabbitmq`（容器名） |
| `MYSQL_HOST` | `127.0.0.1` | `mysql`（容器名） |

靠的就是環境變數覆蓋，程式碼不用改。第 3 章把 worker 搬進 Docker 時你會用到。

### ② `worker.py`：建立 app、接上 broker

```python
from celery import Celery
from crawler.config import (
    RABBITMQ_HOST, RABBITMQ_PORT, WORKER_ACCOUNT, WORKER_PASSWORD,
)

app = Celery(
    "task",                                  # 這個應用程式的名字
    include=[                                # 告訴 Celery 去哪些檔案找 @app.task
        "crawler.tasks",
        "crawler.tasks_crawler_finmind",
        "crawler.tasks_crawler_finmind_duplicate",
    ],
    broker=f"pyamqp://{WORKER_ACCOUNT}:{WORKER_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/",
)
```

一段一段看：

- `app = Celery("task", ...)`：建立整個 Celery 的核心。所有任務都要靠這個 `app` 來註冊。
- `include=[...]`：列出「要去哪些檔案載入任務」。**注意它一開始就把後面第 2、5 章才會用到的任務檔都掛進來了**——意思是，你等一下啟動的這個 worker，從第一天起就認得所有任務。所以之後換章節時，你常常不用重開 worker、也不用改這裡，只要換一支 producer 來跑。
- `broker=f"pyamqp://..."`：RabbitMQ 的連線字串。把它拆開唸一次你就懂了：

  ```
  pyamqp://  worker  :  worker  @  127.0.0.1  :  5672  /
  └協定──┘   └帳號┘    └密碼┘    └──主機──┘   └埠┘
  ```

- 這支檔案**沒有設 result backend**，所以任務結果不會被保存。這一章的假任務也不需要結果，剛好。
- 另外它啟動時會用 `logger.info()` 把讀到的連線設定印出來——之後你懷疑「環境變數到底有沒有吃到」，看 worker 啟動的前幾行 log 就知道。

### ③ `tasks.py`：把普通函式變成「可以派送的任務」

```python
import time, random
from crawler.worker import app        # 匯入那個唯一的 app

@app.task()                           # ← 關鍵：這個裝飾器讓函式變成「可派送任務」
def crawler(x):
    print("crawler")
    print(f"execute task: {x}...")
    time.sleep(random.randint(1, 10)) # 假裝這是要花 1~10 秒的工作
    print(f"{x} done.")
    print("upload db")
    return x
```

- `@app.task()` 是這一章最重要的一行。**加了它**，`crawler` 才會被註冊成可以透過 RabbitMQ 派送的任務；**沒加它**，`crawler` 就只是個普通函式，只能在本地呼叫。
- `time.sleep(random.randint(1, 10))`：故意隨機睡 1~10 秒。這個「隨機」很關鍵——待會你會看到任務**完成順序是亂的**，這正好證明它們是同時併發在跑。
- 這個任務什麼真事都沒做（只印字 + 睡覺），就是要讓你先專心看「機制」，不要被爬蟲邏輯分心。

#### 深入：`@app.task` 到底幫你做了什麼？

這個裝飾器很關鍵，值得多花一點時間。它做的事情，一句話講就是：**把你的普通函式「包裝成一個 Task 物件」，並用同樣的名字取代原本的函式。**

也就是說，加上 `@app.task()` 之後，`crawler` 已經不是原本那個普通函式了，它變成了一個「任務物件」。而你在後面看到的三種能力，全部都是「因為它變成了 Task 物件」才有的：

1. **因為變成 Task 物件，才會「被註冊」。** 裝飾的當下，Celery 會把這個任務登記到 app 的「任務名冊」裡（名字像 `crawler.tasks.crawler`）。worker 啟動時載入這個模組，就從名冊認得它——這就是為什麼 worker 的 `[tasks]` 會列出它、之後收到訊息才知道「這個名字對應哪個函式該執行」。

2. **因為變成 Task 物件，才有 `.delay()`。** `.delay()`、`.apply_async()` 這些「非同步派送」的方法，是 Task 物件才有的方法，普通函式根本沒有。所以 producer 能寫 `crawler.delay(...)`，前提就是 `crawler` 已經被裝飾成 Task 物件。

3. **因為變成 Task 物件，才有 `.s()`（signature）。** 第 3 章你會用到的 `.s(stock_id="2330")`，也是 Task 物件才有的方法，用來把「任務 + 參數」打包成可派送的簽章物件。

反過來想就很清楚：如果你把 `@app.task()` 拿掉，`crawler` 就退回成普通函式，你會發現 `crawler.delay(...)`、`crawler.s(...)` 全都會報錯（`AttributeError`，因為普通函式沒有這些方法），worker 的 `[tasks]` 也不會有它。你唯一能做的就是 `crawler(x)` 直接呼叫——也就是本地同步執行。

> 一句話記法：**`@app.task` 把「函式」升級成「任務」，而「註冊、`.delay()`、`.apply_async()`、`.s()`」是任務才有的能力。** 這也是為什麼整個 Celery 世界裡，所有要派送的東西都一定要先戴上這個裝飾器。
>
> 補充：裝飾器括號裡還能放選項，例如 `@app.task(bind=True, max_retries=3)`。`bind=True` 會讓函式的第一個參數變成 `self`（指向這個 Task 物件本身），這樣就能在任務裡用 `self.retry()` 重試——第 4 章失敗處理會用到。

### ④ `producer.py`：把任務丟出去

```python
from crawler.tasks import crawler

for i in range(100):
    print(f"sent task{i} to broker")
    crawler.delay(x=f"task{i}")       # 非同步派送，丟完立刻回來
```

- `crawler.delay(x=f"task{i}")` **不會真的去執行 `crawler`**。它只是把「請執行 crawler，參數是 taskN」打包成一則訊息丟進 RabbitMQ，然後立刻返回。
- 對照一下：如果你寫成 `crawler(x=0)`（沒有 `.delay`），那就會在**你的電腦上同步執行**，整個分散式的意義就沒了。
- `.delay(...)` 其實是 `crawler.apply_async(kwargs={"x": ...})` 的簡寫。之後第 3 章你要「指定佇列」時，就得改用完整的 `apply_async`。

---

## 一步一步跟著做

> 建議你開三個終端機分頁：**T1 跑 worker、T2 跑 producer、瀏覽器開 RabbitMQ / Flower**。

### Step 1：把基礎設施跑起來

```bash
docker compose -f docker-compose-local.yml up -d rabbitmq flower mysql phpmyadmin
```

等個 20~30 秒，然後確認：

```bash
docker compose -f docker-compose-local.yml ps
```

你應該看到四個服務都在跑：

```
NAME          STATUS
rabbitmq      Up (healthy)
flower        Up
mysql         Up (healthy)
phpmyadmin    Up
```

> ✅ 四個容器都在跑就過關。RabbitMQ 要幾秒暖機，如果一開始 unhealthy，等一下再 `ps` 一次。
>
> 💡 Flower 剛啟動的 log 可能出現短暫的 `Connection refused`——那是 RabbitMQ 還沒 ready，幾秒後會自動重連，屬正常現象，不用處理。

也可以用 curl 快速確認兩個 Web 介面活著：

```bash
curl -o /dev/null -s -w "RabbitMQ: %{http_code}\n" http://localhost:15672
curl -o /dev/null -s -w "Flower:   %{http_code}\n" http://localhost:5555
```

> ✅ 兩個都回 `200` 就過關。

### Step 2：打開 RabbitMQ 管理介面，先看它「空的」樣子

瀏覽器開 http://localhost:15672 ，帳密 `worker / worker`。

進去後點上方的 **Queues and Streams**。**現在應該是空的**（你還沒送任何任務）。先把這個空畫面記在腦中，待會送出任務後再回來看差別。

> ✅ 能登入 RabbitMQ UI 就過關。如果登不進去，多半是 RabbitMQ 還沒完全起來，或帳密打錯。

### Step 3：啟動一個 worker

在 T1 輸入：

```bash
uv run python -m celery -A crawler.worker worker --loglevel=info
```

拆解一下這行指令：`-A crawler.worker` 指定「app 在 `crawler/worker.py`」，`worker` 是啟動模式，`--loglevel=info` 顯示詳細日誌。

你會看到 Celery 的啟動畫面，其中最重要的是中間 `[tasks]` 這一段：

```
 -------------- celery@your-host v5.x.x
--- ***** -----
- ** ---------- .> transport:   amqp://worker:**@127.0.0.1:5672//
- ** ---------- .> results:     disabled://
- *** --- * --- .> concurrency: 8 (prefork)
[tasks]
  . crawler.tasks.crawler
  . crawler.tasks_crawler_finmind.crawler_finmind
  . crawler.tasks_crawler_finmind.crawler_finmind_print
  . crawler.tasks_crawler_finmind_duplicate.crawler_finmind_duplicate

celery@your-host ready.
```

你可以自己讀出三件事：

- `transport: amqp://worker:**@127.0.0.1:5672` → 它成功連上了你的 RabbitMQ。
- `results: disabled` → 沒設結果後端，符合預期。
- `concurrency: 8 (prefork)` → 你這台機器預設開 8 個並行（等於 CPU 核心數）。
- `[tasks]` 列出的四個任務 → 印證了前面說的「這個 worker 一開始就認得所有任務」。

> ✅ 最後一行出現 `ready.`，而且 `[tasks]` 裡有 `crawler`，就過關。如果卡在 `Connection refused`，代表連不到 RabbitMQ，回 Step 1 確認。
>
> ⚠️ 這個終端機**保持不要關**，worker 要一直跑著。發任務要用另一個終端機。

### Step 4：派送 100 個任務

在 T2（另一個終端機，一樣在根目錄）輸入：

```bash
uv run crawler/producer.py
```

**T2（producer）你會看到**——飛快跑完，因為它只是在丟訊息：

```
sent task0 to broker
sent task1 to broker
...
sent task99 to broker
```

**T1（worker）你會看到**——開始忙起來，而且注意 done 的順序是亂的：

```
crawler
execute task: task0...
crawler
execute task: task1...
task3 done.        ← task3 比 task0 先做完（因為睡的秒數隨機）
upload db
task0 done.
...
```

> ✅ producer 幾乎瞬間跑完 100 行，而 worker 那邊還在慢慢消化。這個「一邊秒完、一邊還在做」的對比，就是非同步的鐵證。

### Step 5：仔細看「併發」這件事

回到 worker 畫面，注意兩件事：

1. 同時有好幾個 `execute task: ...` 交錯出現（不是一個 done 才換下一個）。
2. `taskN done.` 的數字順序是**亂的**——因為每個任務睡的秒數隨機，先睡完的先 done。

這就對應到前面那張「非同步時間軸」圖。你剛剛把它驗證出來了。

### Step 6：用 Flower 看板觀察

瀏覽器開 http://localhost:5555 （Flower）。三個頁籤各看什麼：

| 頁籤 | 看什麼 |
|------|--------|
| **Dashboard** | 有幾個 worker 在線、每個已處理多少任務 |
| **Tasks** | 每個任務的名稱、狀態（PENDING / STARTED / SUCCESS / FAILURE）、耗時、參數 |
| **Workers** | 點進單一 worker，看它監聽哪些佇列、concurrency 是多少 |

> 💡 把 Flower 記成「排錯時第一個打開的地方」：任務有沒有送到、有沒有失敗、跑了多久，一目了然。第 7 章會再帶你把 RabbitMQ UI、Flower、phpMyAdmin 三個介面串起來看。

### Step 7：體驗分散式（最有感的一步）

先在 T1 按 `Ctrl+C` 停掉 worker。然後開**兩個** worker，各給一個名字：

```bash
# 終端機 A
uv run python -m celery -A crawler.worker worker -l info -n w1@%h
# 終端機 B
uv run python -m celery -A crawler.worker worker -l info -n w2@%h
```

再跑一次 producer：

```bash
uv run crawler/producer.py
```

> ✅ 你會看到兩個 worker 的畫面**各自都在做任務**，100 個任務被兩個 worker 分著消化，整批做完的時間明顯變短。**而你一行程式碼都沒改。** 這就是水平擴充。

### Step 8：收工——把東西關掉

做完實驗，養成好習慣把服務收乾淨：

```bash
# 1. worker：回到跑 worker 的終端機按 Ctrl+C
#    你會看到 "worker: Warm shutdown"——它會把手上的任務做完才退出

# 2. Docker 服務
docker compose -f docker-compose-local.yml down
```

> 💡 `down` 會停掉並移除容器，但保留資料（volume）。想連資料一起清掉重來，用 `down -v`。
> 下一章開始，每章開頭都會再把需要的服務 `up -d` 起來。

---

## 檢查你是不是真的看到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | producer 秒跑完 100 行 | `.delay()` 是非同步、不會卡住 |
| 2 | worker `[tasks]` 列出 4 個任務 | `include` 一次註冊了所有任務 |
| 3 | 任務併發、done 順序亂 | 任務是同時併發執行的 |
| 4 | RabbitMQ UI 有流量 | 任務真的經過 broker 排隊 |
| 5 | 兩個 worker 分工、變快 | 分散式就是多開 worker |

---

## 想再深入一點

- **`.delay()`、`.apply_async()`、直接呼叫，三者差在哪？** `.delay(x=1)` 是 `.apply_async(kwargs={"x":1})` 的簡寫。想指定佇列、延遲執行、設定重試，就得用 `apply_async`（第 3 章會用到）。而直接 `crawler(x=1)` 是在本地同步執行，不經過 broker。
- **為什麼 producer 秒回？** 因為 `.delay()` 只做「打包訊息 + 丟進 RabbitMQ」兩件事，不等執行。真正耗時的 `sleep` 是發生在 worker 那邊。
- **`concurrency: 8` 哪來的？** Celery 預設用 prefork（多行程），數量預設等於 CPU 核心數。這對「一直在算」的任務合理，但我們之後的爬蟲是「一直在等網路」，第 9 章會教你怎麼調。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| `ModuleNotFoundError: crawler` | 你不在專案根目錄 | `cd` 回根目錄，先 `pwd` 確認 |
| `Connection refused` | RabbitMQ 沒起來或帳密錯 | `docker compose ps` 確認 rabbitmq healthy；帳密是 worker/worker |
| worker 有開、送出後卻沒反應 | producer 用了直接呼叫、不是 `.delay()` | 確認寫的是 `.delay()` |
| RabbitMQ UI 登不進去 | 還沒暖機好 / 帳密錯 | 等幾秒再試；帳密 worker/worker |
| Flower log 有 Connection refused | RabbitMQ 比 Flower 晚 ready | 正常現象，幾秒後自動重連 |

---

## 想一想（確認你懂了）

先自己想過再看答案，效果最好。

**Q1：`crawler.delay(x=0)` 和 `crawler(x=0)` 差在哪？哪一個是非同步？**

差別在於「誰來執行、什麼時候執行」。

- `crawler(x=0)` 是**直接呼叫函式**。跟你平常呼叫任何 Python 函式一樣，程式會**當場、在這支 producer 的行程裡**把整個函式從頭跑到尾（包含那個 `sleep`），跑完才回到下一行，回傳的是真正的結果 `0`。這條路**完全用不到 RabbitMQ、也用不到 worker**——Celery 等於沒參與。
- `crawler.delay(x=0)` 是**非同步派送**。它不執行函式，只做兩件事：把「請執行 crawler、參數 x=0」打包成一則訊息丟進 RabbitMQ，然後**立刻返回**。返回給你的不是 `0`，而是一個 `AsyncResult`（一張「取件單」）。真正的執行是**之後由 worker** 從佇列拿出來做的。

一句話：`crawler(x=0)` 是「我自己現在做」，`crawler.delay(x=0)` 是「我丟給別人待會做」。第 1 章整套分散式靠的都是後者。

**Q2：為什麼 producer 幾乎秒跑完，worker 卻還在慢慢做？**

因為 `.delay()` 只做「打包訊息 + 丟進 RabbitMQ」兩件事，不等執行，所以 producer 100 行瞬間跑完。真正耗時的 `sleep` 是發生在 worker 那邊——它才是實際幹活的人。

**Q3：`[tasks]` 為什麼一開始就列出四個任務，明明你只寫了一支 producer？**

因為任務清單是由 `worker.py` 的 `include` 決定的，不是由 producer 決定的。`include` 一開始就掛了三個任務模組，worker 啟動時就把裡面所有 `@app.task` 都註冊好了。producer 只是「決定這次要送哪一個」，不影響 worker 認得幾個。

那為什麼是「三個模組」卻列出「四個任務」？因為 `[tasks]` 數的是**任務（函式）數，不是模組（檔案）數**——一個檔案裡可以放很多個 `@app.task`。關鍵在第二個模組 `crawler.tasks_crawler_finmind`，它一支檔案裡就放了兩個任務：`crawler_finmind_print`（第 2 章的只印出版）和 `crawler_finmind`（第 5 章的寫入 DB 版）。所以：

| 模組（檔案）| 裡面的 `@app.task` | 任務數 |
|------|-------------------|--------|
| `crawler.tasks` | `crawler` | 1 |
| `crawler.tasks_crawler_finmind` | `crawler_finmind_print`、`crawler_finmind` | 2 |
| `crawler.tasks_crawler_finmind_duplicate` | `crawler_finmind_duplicate` | 1 |

3 個檔案、加起來 4 個任務。這也是為什麼 `[tasks]` 用「模組路徑 + 函式名」的完整格式列出來（例如 `crawler.tasks_crawler_finmind.crawler_finmind_print`）——它要精確標出每個任務住在哪個檔案裡。

**Q4：如果你想讓這批任務更快做完，可以怎麼做？**

多開 worker（Step 7 做過），或把單一 worker 的 concurrency 調高，讓同時在跑的任務變多。程式碼都不用改。

**Q5（進階，很多人會誤解）：畫面上任務交錯出現，我把 concurrency 調高就能照順序嗎？**

**剛好相反——調高 concurrency 會讓交錯更嚴重，不是更整齊。** 因為 concurrency 的定義就是「**同時**能跑幾個任務」：

- `concurrency=8`（預設等於核心數）：worker 一次抓 8 個任務**同時**跑，所以畫面上 8 個 `execute task:` 交錯出現。又因為每個任務睡的秒數是**隨機**的，先睡完的先 `done`，所以 done 的順序是亂的。
- `concurrency=1`：worker 一次只跑一個，task0 從頭做完才換 task1，畫面才會**乖乖照順序、一個 done 才換下一個**。

所以要「照順序、不交錯」，是把 concurrency **調到 1**，而不是調高。但要注意：設成 1 等於**放棄了平行處理能力**，100 個任務又變回一個一個慢慢做。實務上我們不會為了「好看的順序」去設 1——如果任務之間真的有先後依賴，那是另一個主題（要用 Celery 的 chain 串接、或設計成有依賴的工作流），不是靠壓低 concurrency 來解決。交錯執行本來就是我們要的，那代表它真的在平行幹活。

> 再補一個易混點：就算你設 `concurrency=1`，只要你**同時開兩個 worker**，兩個各跑一個，畫面一樣會交錯——因為順序是由「幾個執行單位在搶佇列」決定的，不是單看一個 worker 的 concurrency。

---

## 換你試試看

**練習 1：改任務數量，感受非同步**

把 `producer.py` 的 `range(100)` 改成 `range(10)`，重跑一次。你會看到 producer 一樣秒送完，worker 這次很快就把 10 個消化完。這讓你確認：producer 的速度跟任務多寡幾乎無關（它只負責丟），真正的工作量壓在 worker 身上。

**練習 2：多開 worker，看任務怎麼被分掉**

開三個 worker（各取不同名字），跑同一批任務，然後到 Flower 的 **Workers** 頁看每個 worker 各分到幾個。

```bash
uv run python -m celery -A crawler.worker worker -l info -n w1@%h
uv run python -m celery -A crawler.worker worker -l info -n w2@%h
uv run python -m celery -A crawler.worker worker -l info -n w3@%h
```

你會看到 100 個任務被三個 worker 大致平均分掉、整批更快做完。這就是水平擴充最直觀的樣子。

**練習 3（重點）：對照 concurrency 對「順序」的影響**

這個練習把 Q5 的觀念釘死。用同一批任務，分別用兩種 concurrency 跑，比較畫面：

```bash
# 先用 concurrency=1：你會看到「一個 done 才換下一個」，乖乖照順序
uv run python -m celery -A crawler.worker worker -l info --concurrency=1

# 再用 concurrency=8：你會看到多個 execute task 交錯、done 順序是亂的
uv run python -m celery -A crawler.worker worker -l info --concurrency=8
```

（每次換 concurrency 前先 `Ctrl+C` 停掉舊的 worker，再跑一次 `producer.py`。）

**觀察並解釋**：`concurrency=1` 為什麼會照順序？`concurrency=8` 為什麼會交錯？如果你把 `tasks.py` 的 `time.sleep` 從 `random.randint(1,10)` 固定成 `3`（大家睡一樣久），在 `concurrency=8` 下 done 的順序會變整齊嗎？

> 提示：固定睡眠後，8 個任務幾乎同時開始、也幾乎同時結束，所以 done 的順序會比較接近送出的順序，但仍不保證完全一致——因為「同時開始」和「同時結束」只是接近，不是精準對齊。這正好讓你體會：**併發下的順序永遠不該被依賴**，要順序就得靠明確的依賴設計。

---

## 這一章你學到了

- Celery 的精髓：用 broker 把「發任務的人」和「做任務的人」隔開。
- 整個專案的結構與漸進式設計：每個概念都有 print 版先跑通、正式版再深入。
- `@app.task` 讓函式變成可派送任務；`.delay()` 把任務丟進佇列、立刻返回。
- 想加速不用改程式碼，多開 worker 就對了。

## 下一章要做什麼

這一章的 `crawler(x)` 是假的。**下一章你會把它換成真的去打 FinMind API 抓台股股價**——而你會發現一件神奇的事：worker 完全不用改、啟動指令也完全不用改。
