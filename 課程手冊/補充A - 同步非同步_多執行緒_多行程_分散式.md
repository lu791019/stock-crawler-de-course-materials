# 補充 A：搞懂「同時做很多事」— 同步/非同步、多執行緒、多行程、分散式

> 這份補充把整個 crawler 專案底層在做的事講清楚。你會發現，前面學的 `.delay()`、worker 的 `concurrency`、`--pool`、多台 worker，其實都是「怎麼同時處理很多件事」的不同層次。全部用我們的 repo 當例子。

---

## 為什麼要學這個

想像你要抓台股全部 1000 多支股票的歷史股價。如果一支抓完才抓下一支，每支等 API 回應 1 秒，就要等 1000 秒。太慢了。

「怎麼讓很多件事一起進行」有好幾種層次，從最輕到最重是：

```
同步 → 非同步 → 多執行緒 → 多行程 → 分散式
（一次一件）（不等它做完）（一個行程多條線）（多個行程）（多台機器）
```

我們的 crawler 專案剛好把後面幾種都用上了。下面一個一個拆。

---

## 先分清楚兩個最容易搞混的詞

- **並發（concurrency）**：交錯處理很多件事，**不一定真的同時**。像**一個廚師**同時顧兩道菜——其實是在切換：趁一鍋在燉的空檔，去炒另一鍋。
- **並行（parallelism）**：**真的同時**執行。像**兩個廚師**、各站一個爐台，同一秒都在炒。

一句話：並發是「看起來同時」，並行是「真的同時」。多執行緒、非同步比較偏並發；多行程、分散式才是真並行。記住這個區分，下面就好懂了。

---

## 1. 同步 vs 非同步 —— 差在「要不要等它做完」

**同步（synchronous）**：呼叫一件事，程式會**停在那裡等它做完**，才往下走。
**非同步（asynchronous）**：呼叫一件事，程式**丟出去就繼續往下走**，不等它做完。

比喻：**同步**＝在餐廳櫃檯點完餐，站在原地盯著廚房做完、拿到餐才肯走——這段時間你什麼都不能做。**非同步**＝點完餐**拿個號碼牌**回座位，餐好了店家叫號——`.delay()` 就是拿號碼牌，RabbitMQ 就是掛在廚房前的那疊單子。差別不在「餐做多快」，在**你要不要站在那裡等**。

### 用我們的 repo 看

```python
# 同步：直接呼叫函式，程式會卡在這裡等整支爬蟲跑完（含等 API）
crawler_finmind(stock_id="2330")

# 非同步：.delay() 把任務丟進 RabbitMQ 就立刻回來，不等它做完
crawler_finmind.delay(stock_id="2330")
```

這就是第 1 章的核心。時間軸長這樣（抓 3 支、每支等 API 3 秒）：

```
同步：
  你的程式 |--抓2330(3s)--|--抓0050(3s)--|--抓2317(3s)--|   共 9 秒，全程卡住

非同步（.delay 丟給 Celery）：
  你的程式 |送2330|送0050|送2317|  ← 幾乎瞬間送完就繼續
  worker         |--抓2330--|
                 |--抓0050--|   ← 交給 worker 併發處理
                 |--抓2317--|
```

`producer.py` 用 `for` 迴圈 `.delay()` 送 100 個任務、幾乎瞬間跑完，就是非同步——它只負責「丟」，不等「做完」。

### `.delay()` 和 `apply_async()`：同一件事的兩種寫法

非同步派送在 Celery 裡有兩種寫法，你在這個 repo 兩種都會看到：

```python
# 寫法一：.delay()  —— 最簡單，適合「只要把任務丟出去」
crawler_finmind.delay(stock_id="2330")

# 寫法二：apply_async()  —— 完整版，可以加一堆選項
crawler_finmind.apply_async(kwargs={"stock_id": "2330"})
```

**這兩個都是非同步**（丟出去就回來、不等做完），差別只在「能不能加進階設定」：

- `.delay(x=1)` 其實就是 `.apply_async(kwargs={"x": 1})` 的**簡寫**，方便但沒有額外參數可調。
- `.apply_async(...)` 是**完整版**，可以指定：
  - `queue="twse"`：把任務送到指定佇列（第 3 章多佇列分流就是靠這個，`.delay()` 做不到）
  - `countdown=10`：10 秒後才執行
  - `eta=某個時間`：指定在某個時間點執行
  - `retry=True`、`link=...`：重試策略、串接後續任務

repo 裡的 `producer_multi_queue.py` 就是因為要**指定佇列**，所以改用 `.s(...).apply_async(queue=...)` 而不是 `.delay()`：

```python
# 因為要指定 queue，不能用 .delay()，改用 signature + apply_async
crawler_finmind.s(stock_id="2330").apply_async(queue="twse")
```

一句話：**要簡單就 `.delay()`，要控制（指定佇列、延遲、重試）就 `apply_async()`。** 兩者都是非同步。

> 補充：Python 還有另一種非同步寫法叫 `asyncio`（`async def` / `await`），那是「單一程式內」的非同步。我們的專案不是用 `asyncio`，而是用 Celery 把任務丟給別的 worker 去做，達到「呼叫端不用等」的效果。兩者精神相同（都是「不卡住等待」），但實作層次不同。

---

## 2. 多執行緒 multi-threading —— 一個行程內，多條執行緒，共享記憶體

**多執行緒**：在**同一個行程**裡開很多條執行緒（thread），它們**共享同一塊記憶體**。

比喻：一個廚師（一個行程），但他很會安排——趁一鍋湯在燉（等待），就去切菜、擺盤。看起來一個人同時在弄好幾道菜。這是**並發**。

### Python 有個關鍵限制：GIL

CPython 有一個「全域直譯器鎖（GIL）」，代表**同一時間只有一條執行緒能真正在跑 Python 程式碼**。所以多執行緒在 Python 裡：

- **適合 I/O 密集**（一直在等網路、等硬碟）：一條執行緒在等 API 回應時，GIL 會放開，讓另一條執行緒去跑。等於「等待的空檔被塞滿」，很有效。
- **不適合 CPU 密集**（一直在算）：因為 GIL 卡著，多條執行緒還是輪流跑，快不起來。

### 用我們的 repo 看

我們的爬蟲**大部分時間在等 FinMind 回應**（第 2 章講過，這是 I/O 密集），所以非常適合這種「單行程、高並發」的做法。Celery 提供對應的 pool：

```bash
# threads pool：一個 worker 行程內開很多執行緒
uv run python -m celery -A crawler.worker worker --pool=threads --concurrency=50

# gevent pool：更輕量的「協程」版本（概念類似，但比執行緒還省），實務上爬蟲最常用
uv run python -m celery -A crawler.worker worker --pool=gevent --concurrency=200
```

一個 worker 就能同時「等」幾十上百個 API 回應，記憶體成本很低。（`gevent` 嚴格講是協程/綠色執行緒，不是作業系統執行緒，但你可以先把它理解成「超輕量的多執行緒」，都是為了在單行程內塞滿 I/O 等待。）

---

## 3. 多行程 multi-processing —— 多個行程，各自獨立，真正用滿多核

**多行程**：開很多個**獨立的行程（process）**，每個有自己的記憶體、自己的 Python 直譯器。因為各自獨立，**繞過了 GIL**，可以真正在多顆 CPU 核心上**同時**跑——這是真正的**並行**。

比喻：多請幾個廚師（多個行程），每人站一個爐台，同一秒都在炒菜。

### 用我們的 repo 看

**這正是 Celery 的預設行為。** 還記得第 1 章啟動 worker 時，banner 上那行嗎：

```
.> concurrency: 8 (prefork)
```

`prefork` 就是多行程 pool，`concurrency: 8` 代表這個 worker **fork 出 8 個子行程**，可以真正同時跑 8 個任務。預設數量等於你的 CPU 核心數。

```bash
# prefork（預設）：開 4 個子行程，適合「一直在算」的 CPU 密集任務
uv run python -m celery -A crawler.worker worker --pool=prefork --concurrency=4
```

**代價**：每個子行程都是一個真正的作業系統行程，**吃記憶體、啟動成本高**，所以數量受核心數和 RAM 限制，不可能像 gevent 那樣開幾百個。

### Celery 的 pool 選項一覽（prefork 之外還有誰）

前面出現過 prefork、threads、gevent 三種，這裡把常見的 pool 一次排開：

| pool | 底層是什麼 | 屬於哪一層（廚房版）| 併發模型 | 合理併發 | 適合 | 注意 |
|------|-----------|------------------|---------|:------:|------|------|
| `prefork`（預設）| 多個子行程（fork） | **多行程**——多請幾個廚師，每人一個爐台 | 並行（繞過 GIL）| ≈ CPU 核心數 | CPU 密集 | 吃記憶體、啟動慢；容器內要留意 RAM 上限 |
| `threads` | 作業系統執行緒 | **多執行緒**——一個廚師開好幾條工作線 | 並發（受 GIL）| 數十 | I/O 密集 | 標準庫就有、不用裝套件，最無腦的 I/O 選項 |
| `gevent` | 協程（綠色執行緒）| **協程**——可視為「更輕的多執行緒」：還是一個廚師，但超會利用空檔，幾百鍋湯同時燉 | 並發（受 GIL）| 數百 | I/O 密集（**爬蟲首選**）| 要先 `uv add gevent`；靠 monkey-patch 把阻塞 I/O 換成非阻塞，極少數 C 擴充套件不相容 |
| `eventlet` | 協程（gevent 的同類替代品）| **協程**——同 gevent | 並發（受 GIL）| 數百 | I/O 密集 | 與 gevent 同定位、二選一即可；近年維護趨緩，新專案建議選 gevent |
| `solo` | 單行程單線，任務在主行程裡直接跑 | **都不是**——一次只做一道菜的實習生 | 無併發 | 1 | 除錯、教學 | 一次只跑一個任務、log 最乾淨；查單一任務的問題時很好用 |

> 註：**協程不是作業系統的執行緒**，它是「同一條執行緒裡」由程式自己安排的快速切換（所以更省），但目的和多執行緒一樣——把 I/O 等待的空檔塞滿。分類上可以記成「多執行緒陣營的輕量版」。

一句話選型：**在算的用 prefork、在等的用 gevent、想看清楚單一任務怎麼跑用 solo**。我們的爬蟲整天在等 FinMind → gevent。

### 多行程 vs 多執行緒：並排比一次（最容易混淆的一組）

前面比過「同步 vs 非同步」（差在**要不要等**），這一組比的是「**人手怎麼開**」。兩個詞只差一個字，差別卻是本質的：

| | 多執行緒 threading | 多行程 multiprocessing |
|---|---|---|
| 記憶體 | 同一行程內**共享** | 各自獨立、**不共享** |
| 資料交換 | 直接讀寫同一個變數（方便，但要小心互搶）| 得靠佇列/管線傳遞（要序列化，成本高）|
| GIL 影響 | 受限——同一時間只有一條在跑 Python | 每個行程有自己的 GIL，互不卡 |
| 併發 or 並行 | 並發（輪流跑＋等待重疊）| 並行（多核真同時）|
| 啟動成本 | 低（很輕量）| 高（複製出一整個行程）|
| 一個掛掉 | 可能拖垮整個行程（大家同住一間房）| 只死自己，其他行程照跑 |
| 適合 | I/O 密集：等網路、等硬碟 | CPU 密集：運算、壓縮、跑模型 |
| Celery 對應 | `--pool=threads` / `gevent`（協程同陣營）| `--pool=prefork`（預設）|

三個最常見的誤解，順手拆掉：

- **「執行緒開得多，應該比較快？」**——在 Python，CPU 密集時多執行緒**不會**變快（GIL 讓它們輪流跑）；只有「在等」的時間能被重疊利用。
- **「多行程之間改個全域變數溝通？」**——不行。子行程是複製出去的，各改各的副本，彼此看不到。這也是為什麼 Celery 任務之間不靠變數傳資料，而是靠 broker 和資料庫。
- **廚房版記法**：多執行緒＝**一個廚師**很會利用燉湯的空檔切菜；多行程＝**多個廚師**每人一個爐台。**人數**才是兩者的本質差別，「會不會利用空檔」是執行緒的強項、「多顆爐同時開火」是行程的強項。

---

## 4. 分散式 Distributed —— 跨機器，靠 broker 協調

**分散式**：把工作分給**多台機器**（或多個獨立行程），它們**不共享記憶體**，靠**網路 + 一個中介（broker）**互相協調。

比喻：一間連鎖餐廳開了很多分店，共用同一套中央訂單系統。訂單進中央系統，哪間分店有空就接來做。

### 用我們的 repo 看

這是整個 Celery 架構的重點。**多個 worker 連到同一個 RabbitMQ**，一起消費任務：

```bash
# 機器 A（或終端機 A）
uv run python -m celery -A crawler.worker worker -l info -n w1@%h
# 機器 B（或終端機 B）
uv run python -m celery -A crawler.worker worker -l info -n w2@%h
```

只要這些 worker 都連到同一個 broker，它們就自動組成一個「worker 池」分著做任務。這些 worker 可以在同一台機器、也可以在**完全不同的機器**——只要連得到同一個 RabbitMQ。

專案的 `docker-compose-local.yml` 裡的 `worker_twse`、`worker_tpex` 就是兩個獨立的 worker 容器，連同一個 broker，這已經是分散式的雛形了。

**分散式和多行程的差別**：多行程是「一台機器、多顆核心」；分散式是「多台機器」。分散式突破了單機的極限——你可以無限加機器。而且因為 producer 和 worker 被 broker 徹底隔開（第 1 章講的解耦），某台 worker 掛掉，任務還在 broker，別台會接手。

---

## 把四層疊起來看（我們的 repo 剛好全都有）

這四種不是互斥的，而是可以**疊在一起**。我們的專案從外到內是這樣：

```
分散式：多台機器 / 多個 worker  ← 連同一個 RabbitMQ
   └─ 每台機器上，一個 worker 行程
        └─ 這個 worker 用某種 pool 開併發：
             ├─ prefork（多行程，用滿多核）
             └─ 或 gevent / threads（單行程多並發，塞滿 I/O 等待）
                  └─ 而任務本身是被 .delay() 非同步派送進來的
```

換句話說：

| 你做的事 | 對應概念 | repo 裡是什麼 |
|---------|---------|--------------|
| `crawler_finmind.delay(...)` | 非同步 | producer 派送任務 |
| `--pool=gevent --concurrency=200` | 多執行緒 / 並發 | 單 worker 塞滿 I/O 等待 |
| `--pool=prefork --concurrency=8` | 多行程 / 並行 | 單 worker 用滿多核 |
| 多開 worker / 多台機器連同一 broker | 分散式 | worker_twse、worker_tpex…… |

---

## 到底該選哪個？看你的任務是「CPU 密集」還是「I/O 密集」

這是最實用的決策依據：

| 任務類型 | 特徵 | 該用什麼 | 為什麼 |
|---------|------|---------|--------|
| **I/O 密集** | 大部分時間在等（網路、硬碟、DB）| 非同步 + gevent/threads 高併發 | CPU 在發呆，開再多也不搶 CPU，塞滿等待就好、成本低 |
| **CPU 密集** | 大部分時間在算（運算、壓縮、模型）| 多行程 prefork，貼齊核心數 | GIL 讓執行緒沒用，要用多行程才能真的用滿多核 |
| **量超大、單機不夠** | 不管哪種，就是量太大 | 分散式，加機器 / 加 worker | 突破單機極限，水平擴充 |

**我們的爬蟲屬於哪種？** I/O 密集（一直在等 FinMind 回應）。所以最有效率的做法是 `--pool=gevent` 開高併發，或多開幾個 worker 分散式處理；**不需要**為了單機 CPU 拼命。這也解釋了第 9 章為什麼建議爬蟲用 gevent。

---

## 逐項驗證（用 repo 實際執行）

### 實驗 1：prefork（多行程）vs gevent（多並發）

準備一批任務（例如把 `producer_crawler_finmind_print.py` 的股票清單加到 20 支），分別用兩種 pool 跑，比較速度感受：

```bash
# A. prefork，開 4 個行程
uv run python -m celery -A crawler.worker worker -l info --pool=prefork --concurrency=4

# B. gevent，開 50 個協程（要先 uv add gevent）
uv run python -m celery -A crawler.worker worker -l info --pool=gevent --concurrency=50
```

因為爬蟲是 I/O 密集，B 通常能同時「等」更多支股票，整批更快做完。

### 實驗 2：分散式（多 worker 分工）

```bash
# 開兩個 worker
uv run python -m celery -A crawler.worker worker -l info -n w1@%h
uv run python -m celery -A crawler.worker worker -l info -n w2@%h
# 再跑一次 producer，到 Flower 看兩個 worker 各分到幾個任務
```

---

## 想一想（確認你懂了）

**Q1：`concurrency: 8 (prefork)` 這行，代表 worker 用了上面哪一種？**

多行程。`prefork` 就是 fork 出 8 個獨立子行程，能真正在多核上並行。這是 Celery 的預設 pool。

**Q2：我們的爬蟲是 I/O 密集，為什麼用 gevent 開 200 併發，比 prefork 開 8 行程還划算？**

因為爬蟲大部分時間在「等 API」，CPU 在發呆。gevent 的協程超輕量，一個行程就能同時掛著 200 個「正在等」的任務，記憶體成本極低；而 prefork 每個併發都是一個真行程，很吃記憶體，開不到那麼多。對「等待型」的工作，塞滿等待比用滿 CPU 更重要。

**Q3：多行程和分散式，都是「很多個一起做」，差在哪？**

多行程是「同一台機器、多顆核心」，受限於這台機器的核心數與記憶體；分散式是「多台機器」，靠 broker 協調，可以一直加機器、突破單機極限。而且分散式的 worker 彼此獨立，一台掛掉別台會接手。

**Q4：GIL 對「多執行緒」有什麼影響？**

GIL 讓同一時間只有一條執行緒能跑 Python 程式碼。所以多執行緒對 CPU 密集任務幫助不大（還是輪流跑），但對 I/O 密集很有用（一條在等網路時，GIL 放開讓另一條跑）。這就是為什麼「多執行緒適合 I/O、多行程適合 CPU」。

---

## 換你試試看

**練習 1：看見多行程**

用預設 prefork 啟動 worker，另開一個終端機執行 `ps aux | grep celery`（Mac/Linux）。你會看到不只一個 celery 行程——一個主行程加上好幾個子行程（數量約等於 concurrency）。這確認了 prefork 真的開了多個作業系統行程。

**練習 2：對照 I/O 密集下兩種 pool 的吞吐**

把 producer 的股票清單加到 20 支，分別用 `--pool=prefork --concurrency=4` 和 `--pool=gevent --concurrency=50` 跑，用手機碼錶大略計時整批做完的時間。想一想：為什麼 I/O 密集的任務，gevent 高併發會贏？

**練習 3：把分散式跑起來**

同時開 3 個 worker（不同 `-n` 名字），跑一次 producer，到 Flower 的 Workers 頁看任務怎麼被三個 worker 分掉。這就是分散式最直觀的樣子——你沒改任何程式碼，只是多開了幾個執行單位。

---

## 一頁總結

| 概念 | 一句話 | 餐廳比喻 | 並發還是並行 | repo 例子 | 適合 |
|------|--------|---------|-------------|-----------|------|
| 同步 | 呼叫後等它做完才往下 | 站在櫃檯等餐做完才走 | — | `crawler_finmind(...)` | 簡單、有先後依賴 |
| 非同步 | 丟出去就繼續，不等 | 拿號碼牌回座等叫號 | — | `.delay(...)` / `.apply_async(...)` | 不想被耗時工作卡住 |
| 多執行緒 | 一行程多條線、共享記憶體 | 一個廚師利用燉湯空檔切菜 | 偏並發（受 GIL）| `--pool=threads/gevent` | I/O 密集 |
| 多行程 | 多個獨立行程、各用一核 | 多請廚師、每人一個爐台 | 並行 | `--pool=prefork`（預設）| CPU 密集 |
| 分散式 | 多台機器靠 broker 協調 | 連鎖分店＋中央訂單系統 | 並行 | 多個 worker 連同一 RabbitMQ | 量太大、要水平擴充 |

**餐廳版一條龍**：客人點餐拿號碼牌（`.delay()` 非同步）→ 單子掛上廚房（RabbitMQ）→ 店裡的廚師各自開工：一個超會利用空檔（gevent）、或多請幾個各站一爐（prefork）→ 生意做大就開分店、共用中央訂單系統（分散式）。

**一條龍記法**：`.delay()` 非同步把任務丟進 broker → 每個 worker 用 pool（prefork 用滿核心 / gevent 塞滿 I/O）在單機併發 → 多開 worker、多台機器就成了分散式。我們的 crawler 專案，這四層剛好全用上了。

---

# 附錄：術語速查表

這裡把前面各章出現過的技術名詞集中整理，看不懂哪個詞就翻到這裡查。「詳見」欄標出哪一章有完整說明。

## Celery 核心

| 名詞 | 白話說明 | 詳見 |
|------|---------|------|
| Celery | 分散式任務佇列框架，把耗時工作丟到背景 worker 執行 | 第 1 章 |
| Producer 生產者 | 發送任務的角色，呼叫 `.delay()` / `apply_async()` | 第 1 章 |
| Broker 訊息中介 | 任務排隊的中間站，本專案用 RabbitMQ | 第 1 章 |
| Worker 工作者 | 從 broker 取出任務、實際執行的行程 | 第 1 章 |
| Result Backend 結果後端 | 存放任務回傳結果的地方（選用），本專案未啟用 | 第 1 章 |
| `app`（Celery app）| 整個 Celery 應用的核心實例，所有任務靠它註冊；本專案定義在 `worker.py` | 第 1 章 |
| `@app.task`（裝飾器 / decorator）| 加在函式上，讓普通函式變成「可派送任務」 | 第 1 章 |
| `include` | Celery app 的參數，列出要載入哪些「模組（檔案）」的任務 | 第 1 章 |
| `.delay()` | 非同步派送的簡寫，丟出去立刻回傳、不等執行 | 第 1 章 |
| `.apply_async()` | 完整版非同步派送，可指定 `queue`、`countdown`、`eta`、重試等 | 第 3 章、補充上半 |
| `.s()`（signature 簽章）| 把「任務 + 參數」綁成物件（還沒送出），方便再加 queue 等設定 | 第 3 章 |
| AsyncResult | `.delay()` 回傳的物件，像一張「取件單」，可查狀態 / 取結果（需 result backend）| 第 1 章 |
| concurrency 併發數 | 一個 worker 同時能跑幾個任務 | 第 1、6 章 |
| pool 執行池 | worker 用哪種方式開併發：prefork / threads / gevent / eventlet / solo | 第 9 章、補充上半 |
| prefork | 預設 pool，開多個子行程（多行程），適合 CPU 密集 | 第 1、6 章 |
| gevent | 協程 pool，單行程開大量並發，適合 I/O 密集 | 第 9 章、補充上半 |
| `-Q` | 啟動 worker 時指定「只消費哪一條佇列」 | 第 3 章 |
| `-n` / `--hostname` | 幫 worker 取名字，多 worker 時好辨識（`%h` 會換成主機名）| 第 1、3 章 |
| ack（確認）| worker 處理完回報 broker、broker 才刪掉訊息；`acks_late` 的細節在第 4 章 | 第 3 → 7 章 |

## 訊息佇列 / RabbitMQ

| 名詞 | 白話說明 | 詳見 |
|------|---------|------|
| RabbitMQ | 本專案用的 broker，任務在這裡排隊；管理介面在 :15672（worker/worker）| 第 1 章 |
| 佇列 queue | 任務排隊的通道；預設佇列叫 `celery`，本專案還有 `twse` / `tpex` | 第 1、3 章 |
| pyamqp / AMQP | Celery 連 RabbitMQ 用的協定；連線字串格式 `pyamqp://帳號:密碼@主機:埠/` | 第 1 章 |
| Flower | Celery 的網頁監控面板，看任務與 worker 狀態，在 :5555 | 第 1 章 |
| Ready / Unacked | RabbitMQ UI 上的訊息狀態：Ready = 排隊中還沒被拿、Unacked = 被拿走但還沒確認 | 第 3 章 |

## 資料庫

| 名詞 | 白話說明 | 詳見 |
|------|---------|------|
| MySQL | 本專案存股價的關聯式資料庫，在 :3306 | 第 5 章 |
| mydb | 本專案使用的資料庫名稱 | 第 5 章 |
| phpMyAdmin | MySQL 的網頁管理介面，:8080，帳密 root/1234 | 第 5 章 |
| SQLAlchemy | Python 連資料庫、操作資料庫的工具庫 | 第 5 章 |
| engine / `create_engine` | SQLAlchemy 的連線引擎，代表「怎麼連到這個資料庫」 | 第 5 章 |
| `to_sql` | pandas 把整個 DataFrame 直接寫進資料表的方法 | 第 5 章 |
| `if_exists="append"` | 表已存在就把資料附加上去（會一直疊加、造成重複）| 第 5 章 |
| 主鍵 primary key | 唯一辨識一筆資料的欄位 | 第 6 章 |
| 複合主鍵 composite key | 用多個欄位組合當主鍵，本專案用 `stock_id + date` | 第 6 章 |
| upsert | update + insert：主鍵有就更新、沒有就新增 | 第 6 章 |
| `on_duplicate_key_update` | MySQL 專用語法，主鍵重複時改成更新而非報錯，用來做 upsert | 第 6 章 |
| 冪等 idempotent | 同一個操作做幾次，結果都一樣 | 第 6 章 |
| transaction 交易 | 一組「要嘛全成功、要嘛全失敗」的資料庫操作；`engine.begin()` | 第 6 章 |

## 爬蟲與資料格式

| 名詞 | 白話說明 | 詳見 |
|------|---------|------|
| API | 程式對外要資料的介面，本專案用 FinMind API | 第 2 章 |
| endpoint | API 的網址入口 | 第 2 章 |
| HTTP GET / `requests.get` | 發出網路請求去抓資料 | 第 2 章 |
| query string | 網址問號後面帶的一串參數 | 第 2 章 |
| JSON / `resp.json()` | API 回傳的文字格式 / 把它轉成 Python dict | 第 2 章 |
| status_code 200 | HTTP 狀態碼，200 代表請求成功 | 第 2 章 |
| DataFrame / pandas | 表格型資料結構 / 處理它的套件 | 第 2 章 |
| CSV / `to_csv` / `utf-8-sig` | 逗號分隔的表格檔 / 存檔方法 / 讓 Excel 開中文不亂碼的編碼 | 第 2、4 章 |

## 排程

| 名詞 | 白話說明 | 詳見 |
|------|---------|------|
| APScheduler | Python 的排程套件，定時觸發函式 | 第 9 章 |
| BackgroundScheduler | 背景執行的排程器，需自己用 `while True` 保活 | 第 9 章 |
| BlockingScheduler | 會卡住主執行緒的排程器，適合「專職跑排程」 | 第 9 章 |
| cron / trigger | 用「秒 分 時 星期」格式定時的觸發方式 | 第 9 章 |
| coalesce | 錯過排程時只補跑一次，避免一次爆發 | 第 9 章 |

## 環境與工具

| 名詞 | 白話說明 | 詳見 |
|------|---------|------|
| Docker / container / image | 容器技術 / 執行中的容器 / 容器的範本 | 第 1 章 |
| docker compose | 用一個檔案定義並一次啟動多個容器 | 第 1 章 |
| uv | 比 pip 快很多的 Python 套件 / 環境管理器 | 第 1 章 |
| 環境變數 | 從系統傳給程式的設定值，讓連線資訊不用寫死在程式碼裡 | 第 1 章 |

## 效能與併發觀念

| 名詞 | 白話說明 | 詳見 |
|------|---------|------|
| I/O 密集 | 任務大部分時間在「等」（網路、硬碟、DB）| 第 2、6 章、補充上半 |
| CPU 密集 | 任務大部分時間在「算」 | 第 9 章、補充上半 |
| 並發 concurrency / 並行 parallelism | 「看起來同時」／「真的同時」 | 補充上半 |
| GIL | Python 的全域直譯器鎖，同時只有一條執行緒能跑 Python | 補充上半 |

## 專案裡的慣例

| 名詞 | 白話說明 | 詳見 |
|------|---------|------|
| `_print` 版 | 只印出、不寫資料庫的教學版本，用來先驗證流程再上正式版 | 第 2 章起 |
| 模組 vs 任務 | 一個「模組（檔案）」可含多個 `@app.task`；`include` 以檔案為單位掛入，任務以函式為單位註冊 | 第 1 章 |
| twse / tpex | 本專案自訂的兩條佇列名稱，分別代表上市 / 上櫃 | 第 3 章 |
