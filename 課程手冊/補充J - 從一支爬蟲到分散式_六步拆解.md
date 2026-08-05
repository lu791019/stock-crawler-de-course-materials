# 補充 J：從一支爬蟲到分散式 — 六步拆解

> 你已經有一支能正常執行的爬蟲程式，它同時負責建立任務、呼叫 API、寫入資料庫。你也知道最終架構是 producer → RabbitMQ → Celery task → client → repository。這一篇處理中間那段：從第一支程式走到最終架構，一共要改幾次，每次改什麼，每次改完怎麼確認沒有改壞。

---

## 這一篇要解決的問題

- 一支可以正常運作的爬蟲程式，應該先拆成哪些模組。
- 拆解的依據是什麼，怎麼判斷某段程式該不該獨立成一個檔案。
- 六個步驟的先後順序為什麼是這樣排，能不能跳過中間某一步。
- 每一步做完之後，用什麼方式確認程式仍然是對的。

---

## 做完這一篇，你會做到

1. 說得出「三個職責」分別是什麼，並在自己的爬蟲程式裡指出它們的位置。
2. 說得出拆解模組的判斷依據，不必依賴架構圖也能決定要拆成幾個檔案。
3. 把一支單體爬蟲改寫成 config、client、repository 三層。
4. 把整批處理的迴圈改寫成「一顆任務」的形式，並說得出這一步為什麼是分散式的前提。
5. 在不更動爬蟲邏輯的前提下接上 Celery 與 RabbitMQ。
6. 用 Airflow 取代人工執行 producer，並說得出 DAG 裡為什麼不放爬蟲本身。

---

## 兩條判準

整篇拆解只用到兩條判準，六個步驟都是這兩條的套用。

### 判準一：拆的依據是「會為了不同理由改變」

同一支程式裡，不同段落改動的理由不同、頻率也不同。改動理由相同的放在一起，改動理由不同的分開。

| 改動的理由 | 實際情境 | 應該只動哪一層 |
|---|---|---|
| 要抓的範圍變了 | 增加股票代碼、改日期區間、改成每天抓一次 | producer |
| 資料來源變了 | FinMind 改欄位、改參數名稱、換成別的 API | client |
| 儲存目標變了 | CSV 換成 MySQL、MySQL 再加一份 BigQuery | repository |
| 環境變了 | 本機換成容器、容器換成雲端主機 | config |
| 執行方式變了 | 單機循序執行換成多台機器同時執行 | worker、producer |
| 觸發時機變了 | 手動執行換成每天定時執行 | Airflow DAG |

依據不是「架構圖上有幾個框」。架構圖是結果，判準是原因。先用判準決定要拆幾層，拆完之後畫出來的圖自然會接近最終架構。

### 判準二：每一步都要能執行

- 每一步改完，程式都必須能跑，而且輸出結果與前一步相同。
- 不能出現「拆到一半不能跑，等全部拆完再一起測」的狀態。
- 這條判準同時決定了步驟順序：能獨立完成又能立刻驗證的改動排前面。

依照這條判準，Celery 一定排在很後面。原因是 Celery 換掉的是「誰來執行任務」，它需要「任務」這個東西已經存在。任務的邊界還沒切出來之前接 Celery，等於同時改兩件事，出錯時無法判斷是拆解錯還是佇列設定錯。

---

## 六步全景

| 步驟 | 這一步做的事 | 這一步沒有動的東西 | 驗收方式 |
|---|---|---|---|
| Step 0 | 起點，單體程式 | — | 程式可以執行，產生 CSV |
| Step 1 | 同一支檔案內拆成三個函式 | 檔案數量、執行結果 | 輸出與 Step 0 相同 |
| Step 2 | 拆成 config、client、repository 三個檔案 | 三個函式的內容 | 只改環境變數就能把 CSV 換成 MySQL，client 不動 |
| Step 3 | 任務參數化，producer 與 task 分家 | client、repository | 輸出與 Step 2 相同，此時仍未使用 Celery |
| Step 4 | 接上 Celery 與 RabbitMQ | 任務函式的主體 | worker log 出現 task succeeded |
| Step 5 | Airflow 定時發任務 | 所有爬蟲相關程式 | DAG 的 task 變綠，worker log 出現任務紀錄 |

補充說明六步之外的兩件事：

- **課程手冊 09 的 APScheduler 沒有出現在這條線上**。APScheduler 與 Airflow 在架構上位於同一個位置，兩者都只回答「誰來呼叫 producer」。這條演進線每個位置只示範一種做法，所以直接用 Airflow。APScheduler 的語法與使用時機仍然在手冊 09 說明。
- **上雲不是第七步**。六步做完之後，程式碼裡所有連線資訊都已經在 config 讀環境變數，換到雲端要改的是環境變數的值，不是程式碼。這件事在手冊 14、16 說明。

---

## 這一篇會用到的檔案

全部在 `example/evolution/` 目錄下，每一步一個資料夾或一支檔案，方便你逐步比對。

| 路徑 | 內容 |
|---|---|
| `example/evolution/step0_single_file.py` | Step 0，單體版 |
| `example/evolution/step1_functions.py` | Step 1，同檔三函式版 |
| `example/evolution/step2_modules/` | Step 2，config、client、repository、main |
| `example/evolution/step3_task/` | Step 3，多了 task、producer |
| `example/evolution/step4_celery/` | Step 4，多了 worker，task 加上裝飾器 |
| `example/evolution/step5_airflow/` | Step 5，DAG 檔 |

Step 2 到 Step 4 的資料夾裡都有各自的 `config.py`、`client.py`、`repository.py`。內容刻意重複，目的是讓你可以直接用 `diff` 比較兩個步驟之間到底改了什麼：

```bash
diff example/evolution/step2_modules/client.py example/evolution/step3_task/client.py
# 沒有任何輸出，代表兩個步驟之間 client 完全沒改
```

---

## Step 0：單體版

### 這一步的狀態

- 一支檔案、一個函式，從頭做到尾。
- 三個職責寫在同一個函式裡：決定要抓什麼、怎麼拿、怎麼存。
- 設定值寫死在函式內部：股票清單、日期範圍、API 位址、資料庫連線字串。
- 程式可以正常執行，沒有錯誤。

### 程式檔說明

`step0_single_file.py` 只有一個函式 `crawl_taiwan_stock_price()`，內部依序做三件事：

| 位置 | 職責 | 內容 |
|---|---|---|
| 函式開頭 | 決定要抓什麼 | `stock_ids` 清單、`start_date`、`end_date` |
| 迴圈中段 | 決定怎麼拿 | 組 `parameter`、`requests.get`、轉成 DataFrame |
| 迴圈結尾 | 決定怎麼存 | `df.to_csv`，以及 `write_mysql` 為真時的 `df.to_sql` |

程式碼中的 `write_mysql` 是一個寫死在函式裡的布林值。它示範了設定與程式綁在一起的狀態：要改用資料庫，必須編輯程式碼本身。

### 執行方式

```bash
uv run python example/evolution/step0_single_file.py
```

預期輸出：

```
2330 取得 107 筆
0050 取得 102 筆
2317 取得 107 筆
0056 取得 107 筆
00713 取得 107 筆
```

### 這一步留下的問題

- 想改抓哪些股票，要編輯這個函式。
- 想改儲存目標，要編輯這個函式。
- FinMind 改了回傳欄位，要編輯這個函式。
- 三種完全不同的改動理由，全部落在同一段程式碼上。
- 沒有辦法只測試「呼叫 API」這件事，因為它跟寫檔綁在一起。

---

## Step 1：同一支檔案內拆成三個函式

### 這一步的狀態

- 檔案數量沒有變，仍然是一支。
- 執行結果沒有變，輸出與 Step 0 完全相同。
- 唯一的變化是：原本一個函式裡的三段程式碼，變成三個各自獨立的函式。

這一步刻意不拆檔案。理由是先讓職責的邊界清楚，再談檔案怎麼放。邊界沒想清楚就拆檔案，結果是檔案之間互相呼叫、彼此依賴，比放在一支檔案裡更難維護。

### 程式檔說明

`step1_functions.py` 內含四個函式。

| 函式 | 職責 | 輸入 | 輸出 | 它不知道的事 |
|---|---|---|---|---|
| `build_jobs()` | 決定要抓什麼 | 無 | 工作清單（list of dict） | 資料怎麼拿、怎麼存 |
| `fetch_stock_price()` | 決定怎麼拿 | 股票代碼、起訖日期 | DataFrame | 資料會被存到哪裡 |
| `save_to_csv()` | 決定怎麼存 | DataFrame、股票代碼 | 無 | 資料從哪裡來 |
| `main()` | 串接順序 | 無 | 無 | API 細節、儲存細節 |

三個職責函式之間沒有互相呼叫，全部由 `main()` 串接。這一點很重要：如果 `fetch_stock_price()` 內部直接呼叫了 `save_to_csv()`，那兩者仍然是綁在一起的，換掉儲存方式還是要動到抓資料的函式。

設定值從函式內部搬到模組最上方，成為 `FINMIND_URL`、`STOCK_IDS`、`START_DATE`、`END_DATE` 四個常數。此時設定仍然寫在程式碼裡，但至少集中在一個位置。

### 執行方式

```bash
uv run python example/evolution/step1_functions.py
```

預期輸出與 Step 0 相同。輸出相同就是這一步的驗收：拆解沒有改變程式行為。

### 這一步留下的問題

- 設定值仍然寫在程式碼裡，換環境（本機、容器、雲端）就要改程式碼。
- 三個職責雖然分開了，但仍在同一支檔案裡，無法單獨替換其中一個。
- 想加第二種儲存方式，還是得回到這支檔案裡加。

---

## Step 2：拆成 config、client、repository 三個檔案

### 這一步的狀態

- 一支檔案變成四支檔案。
- 三個職責函式的內容沒有改，只是搬到不同檔案。
- 設定值改用 `os.environ.get()` 讀環境變數，讀不到才用預設值。
- 儲存層多了 MySQL 的實作，用環境變數 `STORAGE` 決定要用哪一個。

### 程式檔說明

#### `config.py`：設定層

- 職責：集中管理所有會因環境而變的值。
- 寫法：`os.environ.get("鍵名", "預設值")`。
- 效果：同一份程式在本機、容器、雲端都不用改程式碼，只換環境變數的值。
- 內容分成四組：要抓什麼（`STOCK_IDS`、日期）、怎麼拿（`FINMIND_URL`、`FINMIND_DATASET`）、怎麼存（`STORAGE`、`CSV_OUTPUT_DIR`、MySQL 連線資訊）。
- 這個檔案的寫法與課程正式版 `crawler/config.py` 相同，環境變數的完整說明見補充 G。

#### `client.py`：資料來源層

- 職責：只負責跟外部系統拿資料。
- 它知道的事：FinMind 的網址、參數名稱、回傳格式。
- 它不知道的事：資料會被存到哪裡、誰會呼叫它。
- 對外只有一個函式 `fetch_stock_price(stock_id, start_date, end_date)`，回傳 DataFrame。
- API 回傳非 200 時回傳空的 DataFrame，由呼叫端決定要不要繼續。錯誤處理的位置放在這裡，是因為「什麼算是抓取失敗」屬於資料來源的知識。

#### `repository.py`：資料儲存層

- 職責：只負責把資料存下去。
- 它知道的事：CSV 的輸出目錄、MySQL 的連線字串與資料表名稱。
- 它不知道的事：資料從哪裡來、是誰決定要存這一份。
- 內含三個函式：

| 函式 | 作用 |
|---|---|
| `save_to_csv(df, stock_id)` | 存成 CSV，目錄不存在時先建立 |
| `save_to_mysql(df, stock_id)` | 用 SQLAlchemy 追加寫入 MySQL |
| `save(df, stock_id)` | 依 `config.STORAGE` 的值選擇上面兩者之一 |

- 兩個實作的函式簽名相同，都是 `(df, stock_id)`。簽名相同，呼叫端才能在不修改的情況下換掉實作。
- `save()` 遇到不認得的 `STORAGE` 值時直接丟出例外，不做略過處理。設定值打錯時要立刻停下來，不能安靜地什麼都沒存。

#### `main.py`：進入點

- 職責：決定要抓什麼，以及串接順序。
- 內含 `build_jobs()` 與 `main()`，本身不含任何 API 細節與儲存細節。
- 它對儲存層的呼叫只有一行 `repository.save(df, job["stock_id"])`，不需要知道實際存到哪裡。

### 執行方式

存成 CSV：

```bash
uv run python example/evolution/step2_modules/main.py
```

預期輸出：

```
2330 取得 107 筆
已寫入 output/TaiwanStockPrice_2330.csv
0050 取得 102 筆
已寫入 output/TaiwanStockPrice_0050.csv
...
```

改存到 MySQL，先確認 MySQL 已啟動：

```bash
docker compose -f docker-compose-local.yml up -d mysql
STORAGE=mysql uv run python example/evolution/step2_modules/main.py
```

預期輸出：

```
2330 取得 107 筆
已寫入 MySQL mydb.TaiwanStockPrice（2330）
...
```

到 phpMyAdmin 或用指令確認資料進了資料庫：

```bash
docker exec mysql mysql -uroot -p1234 -e "USE mydb; SHOW TABLES; SELECT COUNT(*) FROM TaiwanStockPrice;"
```

### 這一步的驗收重點

第二個指令是這一步的核心驗收：

- 你只設定了一個環境變數 `STORAGE=mysql`。
- `client.py` 一行都沒有改。
- `main.py` 一行都沒有改。
- 資料從 CSV 換成進了資料庫。

能做到這件事，代表「怎麼拿」與「怎麼存」確實已經分開。做不到，代表兩者之間還有隱藏的依賴，要回頭檢查是不是有哪個函式同時碰了兩件事。

### 這一步留下的問題

- `main.py` 裡仍然有一個 for 迴圈，一次跑完整批。
- 整批綁在一起，代表沒辦法把其中一支股票交給另一台機器處理。
- 中間失敗時，無法只重跑失敗的那一支。

---

## Step 3：任務參數化

### 這一步的狀態

- `main.py` 拆成兩支檔案：`task.py` 與 `producer.py`。
- `client.py`、`repository.py`、`config.py` 完全沒有改。
- 執行結果與 Step 2 相同。
- 此時程式裡仍然沒有任何 Celery 的痕跡。

這一步是整條演進線的樞紐。前面兩步是把「橫向的三個職責」分開，這一步是把「縱向的整批與單顆」分開。

### 為什麼這一步是分散式的前提

- 任務要能被丟進佇列，前提是它有明確的邊界：輸入是一組參數，輸出是一次完成的工作。
- 參數還寫在函式內部時，任務沒有邊界。整批處理只能整批搬，不能切分給多台機器。
- 一顆任務要能被獨立執行，必須滿足三個條件：
  1. 所有輸入都由參數帶進來，函式內部沒有寫死的清單。
  2. 不依賴其他任務的執行結果，單獨呼叫就能完成。
  3. 不把結果回傳給呼叫端，結果直接寫進儲存層。
- 這三個條件與 Celery 無關，是任務本身的性質。先滿足這三個條件，之後換成任何一種佇列工具都能接。

### 程式檔說明

#### `task.py`：任務層

- 職責：處理一顆任務，也就是一組參數對應的一次完整工作。
- 對外只有一個函式 `crawl(stock_id, start_date, end_date)`。
- 函式內部依序做兩件事：呼叫 `client.fetch_stock_price()`，再呼叫 `repository.save()`。
- 這個函式此時是一個普通的 Python 函式，可以直接 import 進來單機呼叫。
- DataFrame 為空時印出訊息並直接返回，不進行儲存。

#### `producer.py`：派工層

- 職責：決定這一輪要處理哪些任務。
- 內含 `build_jobs()` 與 `main()`。
- `build_jobs()` 產生任務清單，每個元素是一顆任務要用的參數。
- **任務顆粒度在這個函式決定**。目前是「一支股票一顆任務」。要改成「一支股票 × 一天一顆任務」，只需要改這個函式，`task.py` 不用動。
- `main()` 逐一取出清單裡的參數，呼叫 `task.crawl(**job)`。此時是直接呼叫函式，所以整批仍然循序執行。

### 執行方式

```bash
uv run python example/evolution/step3_task/producer.py
```

預期輸出：

```
送出任務: 2330
2330 取得 107 筆
已寫入 output/TaiwanStockPrice_2330.csv
送出任務: 0050
0050 取得 102 筆
已寫入 output/TaiwanStockPrice_0050.csv
...
```

「送出任務」與「取得 N 筆」交錯出現，代表目前是循序執行：送出一顆、執行完，才輪到下一顆。

### 這一步留下的問題

- 任務已經有邊界，但仍然全部在同一個行程裡循序執行。
- 一支股票抓得慢，後面所有股票都要等。
- 增加機器並不會讓它變快，因為沒有任何機制把任務分給別台機器。

---

## Step 4：接上 Celery 與 RabbitMQ

### 這一步的狀態

- 多了一支 `worker.py`。
- `task.py` 的函式主體一行都沒有改，只多了一行裝飾器。
- `producer.py` 只改了一行：`task.crawl(**job)` 改成 `task.crawl.delay(**job)`。
- `client.py`、`repository.py` 的函式內容沒有改，只有 import 的寫法改了。

### 三處差異的完整說明

| 檔案 | 差異 | 差異的性質 |
|---|---|---|
| `worker.py` | 新增檔案 | 宣告任務送到哪裡排隊、哪些模組要註冊 |
| `task.py` | 函式上方加 `@app.task()` | 把函式註冊成可派送的任務 |
| `producer.py` | `crawl(...)` 改成 `crawl.delay(...)` | 從當場執行改成送進佇列 |
| `client.py`、`repository.py` | import 改用完整套件路徑 | 與爬蟲邏輯無關，原因見下方 |

爬蟲邏輯的改動量是零。這就是「Celery 換掉的是誰來執行、在哪裡執行，不是執行什麼」的具體證據。

### 為什麼 import 的寫法要改

- Step 2、Step 3 是用 `python 檔案路徑` 執行，Python 會把「檔案所在目錄」加進模組搜尋路徑，所以 `from config import ...` 找得到同目錄的 `config.py`。
- Step 4 是用 `celery -A example.evolution.step4_celery.worker` 啟動，Celery 以模組路徑載入程式，搜尋路徑是專案根目錄，同目錄那種寫法會找不到檔案。
- 因此 Step 4 改用完整套件路徑 `from example.evolution.step4_celery.config import ...`，並在每一層資料夾放一個空的 `__init__.py`。
- 這是 Python 的模組載入規則，與拆解無關。課程正式版 `crawler/` 目錄從第一章開始就用完整套件路徑，原因相同。

### 程式檔說明

#### `worker.py`：Celery app 定義

- 職責：宣告任務要送到哪裡排隊、哪些模組裡的任務要被註冊。
- 不含任何爬蟲邏輯，也不知道 task 內部在做什麼。
- 兩個關鍵參數：

| 參數 | 作用 |
|---|---|
| `broker` | 任務排隊的位置，格式為 `pyamqp://帳號:密碼@主機:埠號/` |
| `include` | 要載入的模組清單，只有列在這裡的模組，其中的 `@app.task` 才會被註冊 |

- `include` 漏掉某個模組時的症狀是：worker 啟動時的 `[tasks]` 區塊看不到那個任務，發任務後 worker 回報 `Received unregistered task`。

#### `task.py`：任務層

- 函式主體與 Step 3 相同。
- `@app.task()` 裝飾器不改變函式的行為：`crawl(...)` 直接呼叫時仍然是同步執行的普通函式，`crawl.delay(...)` 才是送進 RabbitMQ。
- 參數必須是可以被序列化的型別（字串、數字、list、dict）。任務會被轉成訊息送進 RabbitMQ，DataFrame 或資料庫連線物件無法這樣傳遞。這一點反過來說明了 Step 3 的參數設計為什麼要用字串。

#### `producer.py`：派工層

- `build_jobs()` 與 Step 3 完全相同，因為「要做哪些任務」與「任務由誰執行」是兩件事。
- `main()` 的迴圈改成呼叫 `.delay()`。`.delay()` 送完就返回，不等待執行結果，所以這支程式會很快結束。
- 抓資料的過程要看 worker 的 log 或 Flower，不會出現在 producer 的輸出裡。

### 執行方式

啟動 RabbitMQ：

```bash
docker compose -f docker-compose-local.yml up -d rabbitmq
```

啟動 worker（另開一個終端機視窗，這個指令會持續執行）：

```bash
uv run celery -A example.evolution.step4_celery.worker worker --loglevel=info
```

worker 啟動後，確認 `[tasks]` 區塊列出了任務：

```
[tasks]
  . example.evolution.step4_celery.task.crawl
```

發送任務（回到原本的終端機視窗）：

```bash
uv run python -m example.evolution.step4_celery.producer
```

producer 的輸出：

```
發送任務: 2330
發送任務: 0050
發送任務: 2317
發送任務: 0056
發送任務: 00713
```

五行立刻印完，程式就結束了，這代表任務已經送出、不等執行結果。

worker 視窗的輸出：

```
Task example.evolution.step4_celery.task.crawl[...] received
2317 取得 107 筆
已寫入 output/TaiwanStockPrice_2317.csv
Task example.evolution.step4_celery.task.crawl[...] succeeded in ...
```

### 這一步的驗收重點

- worker log 出現 `received` 代表任務有送到、有被取走。
- worker log 出現 `succeeded` 代表任務真的執行完成。只看到 `received` 不算通過。
- 多支股票的 `取得 N 筆` 訊息由不同的 `ForkPoolWorker-N` 印出，代表它們是同時執行的，不是循序。
- 把 `@app.task()` 那一行與 `.delay` 拿掉，程式應該仍然可以單機執行。這是反向驗證：能拿掉，代表爬蟲邏輯確實沒有跟 Celery 綁在一起。

### 這一步留下的問題

- 任務可以分散執行了，但仍然要人在終端機下指令才會發送。
- 沒有排程、沒有執行紀錄、沒有失敗重跑的介面。

---

## Step 5：Airflow 定時發任務

### 這一步的狀態

- 多了一支 DAG 檔。
- 爬蟲相關的程式（config、client、repository、task、worker）全部沒有改。
- `producer.py` 的角色被 DAG 取代，檔案本身可以留著手動執行。

### 這一步只換了一件事

- Step 4：人在終端機下指令發任務。
- Step 5：Airflow 到排定的時間自動發任務。

換掉的是「誰來呼叫 producer」。爬蟲怎麼抓、資料存到哪裡，完全沒有變。

### 為什麼 DAG 裡不放爬蟲本身

| 做法 | 結果 |
|---|---|
| DAG 直接執行爬蟲 | 爬取工作跑在 Airflow 的執行環境裡，要加快就要調整 Airflow 本身 |
| DAG 只發任務 | 爬取工作跑在 Celery worker，要加快只要增加 worker 數量，Airflow 不動 |

- Airflow 負責排程與相依關係，它的工作是決定什麼時候發、發什麼、失敗了怎麼處理。
- 爬取工作放在 worker，水平擴充的對象就是 worker，與排程器互不影響。
- 這個分工的代價是：Airflow 介面上 task 變綠只代表任務已送出，不代表爬蟲成功。爬蟲的成敗要看 worker log 或 Flower。這一點必須在監控上補回來，否則會出現「Airflow 全綠但資料沒進來」的情況。

### 程式檔說明

`step5_airflow/evolution_producer_dag.py` 的結構：

| 區塊 | 內容 | 說明 |
|---|---|---|
| import | `from example.evolution.step4_celery.task import crawl` | 匯入的是任務物件，呼叫 `.delay()` 只是發送訊息 |
| `default_args` | owner、start_date、retries、retry_delay | 這裡的 retries 是「發送任務」的重試，不是爬蟲的重試 |
| `send_one_task()` | 呼叫 `crawl.delay(...)` | DAG 與 Celery 之間的唯一接點，內容與 Step 4 producer 的迴圈主體相同 |
| `schedule_interval` | `"0 18 * * 1-5"` | 週一到週五 18:00 發送，語法為「分 時 日 月 星期」 |
| for 迴圈 | 依股票清單產生 PythonOperator | 每個 task 只負責送出一顆任務 |

`default_args` 的 `retries` 值得單獨說明：它重試的是 `send_one_task()` 這個動作，也就是「把訊息送進 RabbitMQ」。爬蟲本身失敗要重試的話，是 Celery task 的 `retry` 設定，兩者是不同層級的重試機制，設定的位置也不同。Celery 的失敗處理見手冊 04。

### 部署方式

```bash
cp example/evolution/step5_airflow/evolution_producer_dag.py airflow/dags/
```

Airflow 會自動載入 `airflow/dags/` 目錄下的檔案。啟動與操作方式見手冊 10。

### 驗收方式

1. Airflow 介面上 DAG 出現，且沒有 import 錯誤訊息。
2. 手動觸發後，每個 task 變綠。
3. worker log 出現對應的 `received` 與 `succeeded`。
4. 資料庫或 CSV 有新的資料。

第 3 步與第 4 步不能省略。只確認第 1、2 步，只證明了任務送得出去。

---

## 六步與課程正式程式的對照

示範程式刻意寫得比正式版單純，目的是讓每一步只呈現一個變化。對照表如下：

| 示範檔案 | 課程正式版對應檔案 | 正式版多出來的內容 | 相關章節 |
|---|---|---|---|
| `step2_modules/config.py` | `crawler/config.py` | RabbitMQ、MongoDB、GCP 相關設定 | 補充 G |
| `step2_modules/client.py` | `crawler/tasks_crawler_finmind.py` 的抓取段落 | 正式版尚未把抓取獨立成檔案 | 手冊 02 |
| `step2_modules/repository.py` | `crawler/tasks_crawler_finmind.py` 的 `upload_data_to_mysql` | 正式版多了 BigQuery 與 Spanner 的寫入 | 手冊 05、15 |
| `step3_task/task.py` | `crawler/tasks_crawler_finmind.py` 的 `crawler_finmind` | 正式版多了 CSV 備份與雙寫 | 手冊 05 |
| `step4_celery/worker.py` | `crawler/worker.py` | 正式版 include 了多個 task 模組 | 手冊 01 |
| `step4_celery/producer.py` | `crawler/producer_crawler_finmind.py` | 正式版有多佇列版本 `producer_multi_queue.py` | 手冊 02、03 |
| `step5_airflow/evolution_producer_dag.py` | `airflow/dags/stock_crawler_producer_dag.py` | 正式版多了交易日分支判斷與指定佇列 | 手冊 12 |

正式版的 `crawler/tasks_crawler_finmind.py` 目前是把抓取與儲存放在同一支檔案的狀態，相當於本篇的 Step 1 到 Step 2 之間。這是實務上常見的取捨：檔案數量少、閱讀成本低，代價是儲存目標增加時這支檔案會持續變長。要判斷什麼時候該拆，回到判準一：這支檔案是不是已經為了三種以上不同的理由被修改過。

---

## 常見疑問

**問：可以跳過 Step 1，直接從 Step 0 拆成三個檔案嗎？**

可以，但不建議在第一次拆解時這樣做。Step 1 的作用是先確認職責邊界劃對了，這件事在同一支檔案裡驗證最快。邊界劃錯時，Step 1 只要搬幾行程式碼就能修正，Step 2 之後要改的是檔案之間的依賴關係。

**問：Step 3 看起來只是把迴圈搬到另一支檔案，為什麼說它是樞紐？**

搬動的位置不是重點，重點是搬完之後 `task.crawl()` 的所有輸入都來自參數。這代表任務可以被任何呼叫者用任何參數執行，包括另一台機器上的 worker。參數化之前，任務只能被那一支寫死清單的程式執行。

**問：一定要用 RabbitMQ 嗎？**

Celery 支援多種 broker，RabbitMQ 只是其中一種。Step 3 完成之後，換 broker 只要改 `worker.py` 的 `broker` 字串。這也是 Step 3 排在 Step 4 前面的好處：任務的定義與傳遞任務的工具是分開的。

**問：任務顆粒度要怎麼決定？**

在 `producer.py` 的 `build_jobs()` 決定，判斷依據有三個：

- 單顆任務的執行時間：太長時，中間失敗要重跑的成本高。
- 佇列裡的任務數量：切太細時，訊息數量大幅增加，管理成本上升。
- 重跑的最小單位：想要能只重跑某一天，就必須把日期放進參數。

**問：拆完之後怎麼確認沒有拆錯？**

三個檢查方式：

1. 把 Celery 拿掉，程式應該仍然可以單機執行。
2. 換掉 `STORAGE` 的值，`client.py` 應該不需要改。
3. 改 `build_jobs()` 的清單內容，`task.py`、`client.py`、`repository.py` 應該都不需要改。

**問：新聞資料也適用這條演進線嗎？**

適用，六個步驟完全相同，`FINMIND_DATASET` 從 `TaiwanStockPrice` 換成 `TaiwanStockNews` 即可。要注意的差異在去重：股價資料的天然唯一鍵是「股票代碼 + 日期」，新聞資料沒有這樣的組合，重跑時用什麼欄位判斷重複必須自己決定。去重與冪等的做法見手冊 06。

---

## 檢查你是不是真的做到了

- [ ] 你能在自己的爬蟲程式裡，指出「決定要抓什麼」「怎麼拿」「怎麼存」三段程式碼各自的位置。
- [ ] 你執行了 Step 0 到 Step 3，四步的輸出結果相同。
- [ ] 你用 `STORAGE=mysql` 執行 Step 2，且沒有修改 `client.py` 任何一行。
- [ ] 你進資料庫確認過資料表存在、裡面有資料。
- [ ] 你啟動了 Step 4 的 worker，`[tasks]` 區塊有列出 `crawl`。
- [ ] 你在 worker log 看到 `succeeded`，不只是 `received`。
- [ ] 你能說出 Step 4 相對於 Step 3 一共改了哪三個地方。
- [ ] 你能說出 DAG 裡為什麼不直接放爬蟲程式。

---

## 換你試試看

1. **改任務顆粒度**：修改 `step3_task/producer.py` 的 `build_jobs()`，把「一支股票一顆任務」改成「一支股票 × 一個月一顆任務」。完成後確認 `task.py`、`client.py`、`repository.py` 都不需要修改。
2. **加第三種儲存方式**：在 `step2_modules/repository.py` 新增 `save_to_json()`，並讓 `STORAGE=json` 能夠使用它。完成後確認 `main.py` 不需要修改。
3. **換資料集**：把 `FINMIND_DATASET` 改成 `TaiwanStockNews`，執行 Step 2。觀察回傳欄位與股價資料的差異，並回答：這份資料要用哪些欄位判斷重複。
4. **反向驗證**：複製一份 `step4_celery/`，把 `@app.task()` 與 `.delay` 拿掉，確認程式仍然可以單機執行。
5. **接上正式版**：對照 `crawler/tasks_crawler_finmind.py`，用本篇的判準把它拆成 client 與 repository 兩個檔案，並確認 `crawler/producer_crawler_finmind.py` 不需要修改。

---

## 這一篇你學到了

- 拆解模組的依據是「會為了不同理由改變」，不是架構圖上有幾個框。
- 步驟順序的依據是「每一步都要能執行」，不能拆到一半不能跑。
- 三個職責分別是：決定要抓什麼（producer）、怎麼拿（client）、怎麼存（repository）。
- 任務參數化是分散式的前提，這一步與 Celery 無關，做完之後任何佇列工具都能接。
- Celery 換掉的是「誰來執行、在哪裡執行」，不是「執行什麼」，所以接上它時爬蟲邏輯的改動量是零。
- Airflow 換掉的是「誰來呼叫 producer」，DAG 內不搬運資料，爬取工作留在 worker。
- 六步做完之後，所有連線資訊都在 config 讀環境變數，換環境要改的是環境變數的值。
