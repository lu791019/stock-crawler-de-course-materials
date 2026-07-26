# 第 10 章：Airflow 基礎 — 架起你的工作流編排引擎

> 接下來三章是全課程的壓軸。你會用工業級的工作流引擎 Airflow，把前面九章的每一段串成一張可管理、可觀察、可補跑的 DAG。這一章先把 Airflow 架起來、跑通第一個 DAG。

---

## 做完這一章，你會做到

1. 說得出 Airflow 是什麼（出身、定位）、為什麼業界用它。
2. 講清楚一個常見誤解：**Airflow 取代的是第 9 章的 APScheduler，不是 Celery。**
3. Build 出包含我們爬蟲程式的 Airflow Docker image。
4. 啟動 Airflow（Postgres + init + webserver + scheduler），說得出架構圖上每個元件的角色。
5. 用 CLI 和 UI 各觸發一次 DAG，會用 Graph / Grid / Logs / Clear 四個 UI 操作。
6. 看懂 DAG、Operator、`>>` 依賴、cron 排程這些核心概念。

---

## 先認識工具：Airflow 是什麼

- **出身**：Airbnb 於 2014 年內部開發、後來開源並捐給 Apache 基金會（現為 Apache 頂級專案）。今天它是資料工程領域**工作流編排的事實標準**——資料工程師職缺的技能要求裡幾乎都有它。
- **定義**：一套**工作流程管理系統（Workflow Management System）**——你用程式碼描述「有哪些工作、什麼順序、什麼時間跑」，它負責照表執行、記錄每一次結果。
- **以 Python 開發，也用 Python 撰寫工作流**：定義工作流不用學新語言，寫的就是 Python 檔（這章下面就會逐行讀一支）。
- **適用場景**：Data Pipeline、ETL、自動化排程——正是我們這套爬蟲系統在做的事。

### 為什麼要用 Airflow？

五個核心能力，對照第 9 章的工具看最清楚：

| 能力 | APScheduler | Airflow |
|------|:----:|:----:|
| 定期（自動化）執行工作 | ✅ | ✅ |
| 設定工作之間的**相依性**（Dependencies）| ❌ | ✅ |
| 各個工作失敗時**自動重試**（auto-retry）| 自己寫 | ✅ 參數一行 |
| **Web GUI** 管理所有工作（可設權限）| ❌ | ✅ |
| 透過 Web **查詢 Logs** | ❌ | ✅ |

第一項 APScheduler 也做得到——所以 Airflow 的價值在後四項，而後四項正好就是第 9 章結尾「執行狀態去哪看？」留下的缺口。

---

## 先搞懂（最重要，先講）：Airflow 不是 Celery 的替代品

很多人以為 Airflow 和 Celery 是二選一，其實在這套架構裡它們是**上下層分工**：

- **Airflow = 編排層**：決定「什麼時候跑、有哪些步驟、誰先誰後、失敗怎麼補跑」，還提供網頁 UI 看歷史。
- **Celery = 執行層**：真正把分散式的活幹掉。

證據就在專案裡：`stock_crawler_producer_dag` 這支 DAG，是在 Airflow 裡呼叫 Celery 的 `.delay()` 把任務發到 RabbitMQ——**Airflow 負責編排、Celery 負責執行**（第 12 章會實際跑）。

用一句話定位三個角色：

- 第 9 章 APScheduler = 陽春鬧鐘（只會定時觸發，沒有歷史、沒有依賴管理、沒有 UI）。
- Airflow = 專業編排引擎（排程 + 依賴 + 重試 + 補跑 + UI）。
- Celery 從頭到尾都是底層的執行引擎。

**所以 Airflow 取代的是 APScheduler，Celery 依然在最底層執行任務。**

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `airflow/Dockerfile` | Image 定義 | 以 Ubuntu 為基底，裝好 Airflow 2.10 和我們的 crawler 程式 |
| `airflow/docker-compose-airflow.yml` | 部署（LocalExecutor）| 輕量的部署版本，適合開發環境，這一章用它 |
| `airflow/docker-compose-airflow-celery-stock.yml` | 部署（CeleryExecutor 瘦身版）| 用同一顆 stock-airflow image，多起 Redis 和獨立 worker，第 12 章會示範 |
| `airflow/docker-compose-airflow-celery.yml` | 部署（CeleryExecutor 官方範本）| 官方 image 的完整版本，留作參考，第 12 章會談到 |
| `airflow/airflow.cfg` | 設定檔 | Airflow 的核心設定檔，下面有專節說明它的角色 |
| `airflow/dags/example_*.py` | 範例 DAG | 這一章與下一章使用的範例 DAG |
| `airflow/README.md` | 說明 | 記錄啟動方式與 DAG 清單 |

### Airflow 由哪些服務組成

`docker-compose-airflow.yml` 會起四個容器：

| 服務 | 用途 |
|------|------|
| `postgres` | Airflow 的 **metadata 資料庫**（存 DAG 狀態、執行紀錄、排程歷史）|
| `airflow-init` | 初始化資料庫 + 建 admin 帳號（一次性，跑完就 Exit）|
| `airflow-webserver` | Web UI（port 8080）|
| `airflow-scheduler` | 排程器（掃描 DAG、依 cron 觸發、分派 task）|

> **等等，為什麼又多一個 Postgres？我們不是有 MySQL 了嗎？** 兩個資料庫的用途完全不同：**PostgreSQL 是 Airflow 自己的內部資料庫**（存工作流的狀態，就像第 8 章 Metabase 用 `metabasedb` 存自己的設定）；**MySQL 是我們的業務資料庫**（存股價）。Airflow 官方預設且支援最完整的是 Postgres，所以照用。兩個各管各的，互不相干：
>
> ```
> Airflow（狀態存 PostgreSQL）→ 排程觸發 → 爬蟲程式 → 股價寫入 MySQL
> ```

### 架構圖：概念元件 ↔ 實際容器

把上面的服務表畫成圖，並對應到 `docker ps` 會看到的容器名稱：

```
                       ┌──────────────────┐
                       │ Metadata DB      │ ← container: airflow-database
                       └────────▲─────────┘
                                │ 讀寫 DAG 狀態、執行紀錄
  ┌───────────────────────┐  ┌──┴──────────┐  ┌─────────────┐
  │ Workers（執行 task）  │◄─│ Scheduler   │  │ Webserver   │◄── 你的瀏覽器
  │                       │  │ └ Executor  │  │ (port 8080) │
  └──────────▲────────────┘  └──▲──────────┘  └──▲──────────┘
             │                  │                │
             └────────── DAG Directory（airflow/dags/）──────────┘
```

三個閱讀重點：

- **Scheduler 裡藏著一個 Executor**——它是「task 交給誰執行」的機制。本章用 **LocalExecutor**：worker 就是 scheduler 自己 fork 出來的子行程，所以 `docker ps` 看不到獨立的 worker 容器（圖上的 Workers 和 Scheduler 住在同一個 `airflow-scheduler` 容器裡）。第 12 章會看到 CeleryExecutor 把 worker 拆成獨立容器、甚至跨機器。
- **三方都讀同一個 DAG Directory**：scheduler 掃描它決定何時觸發、webserver 讀它顯示在 UI、worker 執行它的程式碼——這就是為什麼 compose 把 `airflow/dags/` 掛載進容器。
- **概念圖和實際容器的對應**：Metadata DB 對應 `airflow-database`、Scheduler（連同 Executor 和 LocalExecutor 的 workers）對應 `airflow-scheduler`、Webserver 對應 `airflow-webserver`。之後 `docker ps` 看到這三個名字，就知道各自是圖上的哪一塊。

### airflow.cfg 是什麼？

檔案表裡那個 `airflow.cfg` 是 Airflow 的**核心設定檔**——executor 用哪種、metadata DB 連哪裡、時區、DAG 資料夾位置……幾百個選項都在裡面。本課的用法你需要知道兩件事：

- **compose 用環境變數覆蓋了關鍵設定**。`docker-compose-airflow.yml` 裡的 `AIRFLOW__CORE__EXECUTOR`、`AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`、`AIRFLOW__CORE__DEFAULT_TIMEZONE` 這些環境變數，優先權**高於** cfg 檔。命名規則：`AIRFLOW__{區塊}__{選項}` 對應 cfg 檔裡 `[core]` 區塊的 `executor = ...`。用環境變數蓋設定是容器化部署的慣例——改設定不用改檔案、不用 rebuild image。
- **本課不需要動它**。知道「設定從哪裡來、誰覆蓋誰」，之後看到別人的 Airflow 專案才知道去哪找設定。

---

## 一步一步跟著做

### Step 1：Build Airflow image

Airflow 需要一個「裝了 Airflow、也裝了我們爬蟲程式」的 image。從專案根目錄 build：

```bash
docker build -f airflow/Dockerfile -t stock-airflow:latest .
```

第一次要下載 base image + 裝 Airflow 全家桶，需要幾分鐘。

驗證 image 能用：

```bash
docker run --rm stock-airflow:latest python3 -c "import airflow; print(f'Airflow {airflow.__version__}')"
```

> ✅ 印出 `Airflow 2.10.4` 就過關。

### Step 2：前置準備

```bash
docker network create my_network 2>/dev/null    # 建過就跳過
cp .env.example .env                             # 首次使用
```

> ⚠️ **8080 埠衝突**：`docker-compose-local.yml` 的 phpMyAdmin 用 8080，Airflow UI 也用 8080。**做這一章前先把 phpMyAdmin 關掉**：
> ```bash
> docker compose -f docker-compose-local.yml down
> ```

### Step 3：啟動 Airflow

```bash
docker compose -f airflow/docker-compose-airflow.yml up -d
```

### Step 4：等 init 完成（第一次啟動的關鍵坑）

初始化資料庫 + 建帳號需要 30~60 秒。確認 init 跑完：

```bash
docker logs airflow-airflow-init-1 2>&1 | tail -3
```

> ✅ 看到 `User "admin" created with role "Admin"` 才算完成。

**首次啟動時 webserver 可能比 init 先跑而報錯**（資料庫還沒好）。init 完成後重啟一次就好：

```bash
docker restart airflow-webserver airflow-scheduler
```

等 15~20 秒，驗證：

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health
```

> ✅ 回 `200` 就過關。

### Step 5：登入 Web UI，認識介面

開 http://localhost:8080 ，帳密 `admin / admin`。

- 首頁是 **DAG 列表**：左邊 DAG 名稱、右邊每個 DAG 有個開關（pause / unpause）。
- 所有 DAG 預設 **paused（暫停）**——不會自動跑，這是安全設計。
- 你會看到 `example_*` 開頭的範例 DAG 和 `stock_*` 開頭的台股實戰 DAG，全部來自 `airflow/dags/` 資料夾。

### Step 6：用 CLI 觸發第一個 DAG

也可以全用 UI 點，但 CLI 更適合寫進腳本。先解除暫停、再觸發：

```bash
docker exec airflow-webserver airflow dags unpause example_first_dag
docker exec airflow-webserver airflow dags trigger example_first_dag
```

等 10~15 秒，查執行結果：

```bash
docker exec airflow-webserver airflow dags list-runs --dag-id example_first_dag
```

> ✅ `state` 欄顯示 `success` 就過關。

### Step 7：回 UI 看圖、看 log，並學會 UI 操作

CLI 觸發過了，這一步把 UI 的四個常用動作走一遍——之後排錯都靠它們：

1. **Graph 頁**：點 `example_first_dag` → Graph。看到 `start → end` 兩個方格都是綠色（成功）。Graph 是「**單次執行**」的流程圖——看這一輪誰成功誰失敗、依賴怎麼走。
2. **Grid 頁**：切到 Grid。它是「**歷次執行**」的總表——每一直欄是一次執行、每一格是一個 task，顏色就是狀態。要回答「昨天那輪跑了沒、最近哪次失敗」看 Grid，不是 Graph。
3. **UI 手動觸發**：DAG 頁右上角的 **▶（Trigger DAG）** 按鈕，等於剛才 CLI 的 `dags trigger`。按一次，看 Grid 多出一欄。
4. **Logs**：點任一 task 方格 → Logs，看它執行時印了什麼。
5. **Clear（重跑的鑰匙）**：點 task 方格 → **Clear**，這個 task 會清掉狀態重新排隊執行。現在對綠色的 task 按一次感受流程就好——第 12 章你會用它做「只重跑失敗那一支」的招牌操作。

> 💡 「每次執行都有紀錄、每個 task 都有 log、失敗能單獨重跑」——這三件事就是 Airflow 比 APScheduler 高級的地方。UI 的 Grid / Logs / Clear 正是這三件事的入口。

---

## 一行一行讀懂 `example_first_dag`

```python
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator

# DAG 的預設參數：會套用到這個 DAG 裡面的每一個 task
default_args = {
    "owner": "data-team",                  # 這個 DAG 的負責人（顯示在 UI 上）
    "retries": 1,                          # task 失敗時自動重試 1 次
    "retry_delay": timedelta(minutes=1),   # 每次重試之間間隔 1 分鐘
}

with DAG(
    dag_id="example_first_dag",            # DAG 的唯一名字，UI 列表顯示的就是它
    default_args=default_args,
    schedule_interval="0 * * * *",         # cron 語法：每小時的整點執行一次
    start_date=datetime(2024, 1, 1),       # 排程從這一天開始生效
    catchup=False,                         # 不補跑 start_date 到今天之間錯過的歷史排程
) as dag:

    def hello_world():
        print("Hello from Airflow!")

    start_task = PythonOperator(           # PythonOperator：這一步執行一個 Python 函式
        task_id="start",
        python_callable=hello_world,       # 掛函式本身（不加括號），到點由 Airflow 呼叫
    )

    end_task = BashOperator(               # BashOperator：這一步執行一行 shell 指令
        task_id="end",
        bash_command='echo "Hello from Airflow! Success"',
    )

    start_task >> end_task                 # 依賴方向：start 成功之後才會執行 end
```

四個核心概念：

- **DAG（Directed Acyclic Graph，有向無環圖）**：一個工作流程的單位——**一支 Python 檔就是一個工作流**，裡面是多個工作任務的組合（至少一個），定義「工作之間的執行順序與依賴關係」＋「什麼時間、什麼週期執行」。例如：每天 12:00 執行「a. 爬蟲 → b. 匯出檔案 → c. 發送通知」。它比直線型的 pipeline 強在**能表達分支與匯合**——直線 pipeline 只能 A→B→C→D 一路走；DAG 可以 A 之後同時走 B、C、D 三條路，各自處理完再匯合到 G。下一節的平行任務 DAG 就是最簡單的例子。
- **Task（Operator）**：一個工作的**最小單位**（一段 function），定義「這一步做什麼」。task 就是 Operator 的一次實例化。Airflow 內建大量現成的 Operator，常用的有：
  | Operator | 做什麼 | 本課哪裡用 |
  |---|---|---|
  | `PythonOperator` | 執行一個 Python 函式 | 從本章開始全程使用 |
  | `BashOperator` | 執行一行 bash 指令 | 從本章開始全程使用 |
  | `DummyOperator` | 不做事，用來佔位和整理圖形 | 第 11 章的積木範例 |
  | `DockerOperator` | 臨時起一個容器來執行任務 | 第 11 章介紹、第 12 章實戰 |
  | GCP / AWS / Azure 系列 | 串接各家雲端服務 | 第 15 章的 BigQuery |
  | Slack / Email 系列 | 發送通知訊息 | 本課沒有用到，知道有這類積木就好 |

  這個生態系是 Airflow 的護城河之一：大部分「跟外部系統對接」的步驟都有現成積木，不用自己造。
- **`>>`**：定義依賴方向。`a >> b` = a 成功後才跑 b。這個符號串起來的圖，就是 DAG（有向無環圖）本人。
- **`catchup=False`**：假設 start_date 是去年，Airflow 預設會把「去年到今天沒跑到的每小時」全部補跑一遍——通常不是你要的，所以關掉。

### cron 排程速查

| 寫法 | 意思 |
|------|------|
| `0 * * * *` | 每小時的整點執行一次 |
| `0 18 * * 1-5` | 週一到週五的 18:00 執行（台股收盤後）|
| `0 11,23 * * *` | 每天的 11:00 和 23:00 各執行一次 |
| `None` | 不自動執行，只能手動觸發 |

> 跟第 9 章 APScheduler 的 `CronTrigger` 是同一套 cron 語法——你已經會了。

### 排程什麼時候真的觸發？（跟直覺不同的地方）

Airflow 的排程有一個跟 APScheduler 不同、常讓新手以為「排程壞了」的特性：**它以「資料區間」思考，一輪排程要等該區間結束才執行**。

- APScheduler 的想法是「時間到了 → 跑」；Airflow 的想法是「`0 18 * * 1-5` 定義了一段段的資料區間，**某個區間結束時，跑那一輪**」。
- 最常撞到的體感：你在 17:00 unpause 一個「每天 18:00」的 DAG，它**不會立刻跑**——要等到今天 18:00（依 start_date 的設定，甚至可能等到下一輪）才執行第一次。這不是壞了，是設計如此：Airflow 出身是「處理昨天的資料」的批次思維，一輪執行代表「這個區間的資料已經齊了，可以處理了」。
- 課堂上我們大多用**手動 trigger**（立即執行、不等區間），就是為了避開這個等待。你自己開真排程時記得這個特性：unpause 之後沒動靜，先想「下一個區間結束點是什麼時候」，再判斷是不是真的有問題。
- 它跟 `catchup` 是同一套思維的兩面：catchup 問的是「**過去**沒跑的區間要不要補」，這裡講的是「**下一輪**什麼時候才算到期」。

---

## 再跑一個：平行任務 DAG

```bash
docker exec airflow-webserver airflow dags unpause example_parallel_dag
docker exec airflow-webserver airflow dags trigger example_parallel_dag
```

到 UI 看 `example_parallel_dag` 的 Graph：`start → 10 個平行 task → end`。10 個方格會**同時**變綠。

程式碼裡的關鍵一行：

```python
start_task >> [task1, task2, ..., task10] >> end_task
```

用 `[]` 把多個 task 包起來 = 平行執行。像不像第 1 章「一批任務被 worker 併發消化」？同一個概念，換到編排層再演一次。

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | `stock-airflow:latest` 成功 build 完成 | 爬蟲程式已經被裝進 Airflow 的環境裡 |
| 2 | init 的 log 出現 `User "admin" created` | metadata DB 初始化完成、管理帳號建好了 |
| 3 | 打開 UI 登入後看得到 DAG 列表 | webserver 正常運作 |
| 4 | `example_first_dag` 的 state 顯示 success | 排程器能夠正常執行 DAG |
| 5 | Graph 上 10 個 task 同時變綠 | Airflow 能平行執行多個 task |

---

## 想再深入一點

- **DAG（有向無環圖）到底是什麼？** 「有向」= 步驟有先後方向；「無環」= 不會繞回自己（不會 A→B→A 無限循環）。Airflow 用它描述「一整套工作的步驟與依賴」。這比 APScheduler 的「時間到就跑一個函式」強大太多——它能表達複雜的流程圖。
- **Airflow 的可觀察性（observability）是它最大價值之一。** 每次執行都留下紀錄：哪天跑的、哪個 task 花多久、哪個失敗、log 是什麼。出事時你能只重跑失敗的那個 task，不用整批重來。這是 APScheduler 完全給不了的。
- **為什麼 DAG 檔案改了不用重啟？** compose 把 `airflow/dags/` 掛載進容器，scheduler 會定期重新掃描這個資料夾。你在本機改 DAG 存檔，過幾十秒 UI 就會更新。
- **反過來的代價：DAG 檔的「頂層程式碼」會被反覆執行——別放重活。** 上一條的「定期重新掃描」，實際動作是 scheduler **每幾十秒重新執行一次每支 DAG 檔的頂層程式碼**（import、變數定義、`with DAG(...)` 的宣告）來重建 DAG 結構。這代表：如果你在頂層連資料庫、打 API、讀大檔案，這些動作會**每幾十秒跑一次**，把 scheduler 拖垮，而且你完全看不出來為什麼變慢。規則只有一條：**頂層只放「宣告」（DAG、task、依賴、常數清單），「動作」全部包進 task 的函式裡**——函式只有在 task 被觸發時才會執行。對照我們的 DAG 檔可以驗證這個規則：`stock_crawler_dag` 頂層只有 import 和 `STOCK_IDS` 清單，`crawler_finmind` 是包在 PythonOperator 裡、被觸發才呼叫——正確示範。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| 8080 打不開或衝突 | phpMyAdmin 也佔用 8080，兩個服務撞在同一個 port | 先執行 `docker compose -f docker-compose-local.yml down` 把 phpMyAdmin 關掉 |
| webserver 報 `You need to initialize the database` | webserver 比 init 先啟動，資料庫還沒初始化完成 | 等 init 完成後執行 `docker restart airflow-webserver airflow-scheduler` |
| 一啟動就報錯說缺少設定 | 專案根目錄沒有 `.env` 檔案 | 先執行 `cp .env.example .env` 建立它 |
| DAG 列表是空的 | dags 資料夾沒有被掛載進容器 | 確認你是從專案根目錄啟動 compose 的 |
| DAG 觸發了卻沒有反應 | 這個 DAG 還在 paused 狀態，觸發不會執行 | 先 unpause 再 trigger |
| 報錯說 image 不存在 | 還沒有 build 過 stock-airflow image | 執行 `docker build -f airflow/Dockerfile -t stock-airflow:latest .` |

---

## 想一想（確認你懂了）

**Q1：Airflow 取代的是我們前面哪一章的東西？它跟 Celery 是競爭還是分工？**

取代的是第 9 章的 APScheduler（排程 / 觸發那一層）。它跟 Celery 是**分工**不是競爭：Airflow 負責「何時做、依賴順序、失敗補跑、監控」，Celery 負責「實際分散式執行」。專案的 `stock_crawler_producer_dag` 就是 Airflow 呼叫 Celery `.delay()` 的實例（第 12 章會跑）。

**Q2：第 9 章的 APScheduler 有哪些做不到、而 Airflow 做得到的事？**

APScheduler 只會「時間到就跑一個函式」，看不到執行歷史、不能管理 task 之間的依賴、失敗不好單獨補跑、也沒有 UI。Airflow 這些全都有：依賴圖、每次執行的紀錄與 log、只重跑失敗的 task、網頁監控。所以從「玩具排程」升級成「生產級編排」。

**Q3：Airflow 的 Postgres 和我們的 MySQL 各存什麼？可以共用一個嗎？**

Postgres 存 Airflow 自己的 metadata（DAG 狀態、執行紀錄）；MySQL 存我們的業務資料（股價）。技術上 Airflow 也能用 MySQL 當 metadata DB，但官方對 Postgres 支援最完整，而且**把「系統狀態」和「業務資料」分開本來就是好習慣**——任何一邊出問題不會拖累另一邊。

---

## 換你試試看

**練習 1：把 example_first_dag 的排程改成每分鐘**

把 `schedule_interval` 改成 `"* * * * *"`、unpause，等兩三分鐘後看 UI——它會自己跑起來，每分鐘一筆紀錄。看完記得改回去或 pause，不然它會一直跑。這讓你確認 scheduler 真的在照 cron 觸發。

**練習 2：看懂一次失敗長什麼樣**

把 `example_first_dag` 的 `bash_command` 改成一個會失敗的指令（例如 `exit 1`），觸發一次。Graph 上 end 會變紅，點進 Logs 看錯誤。然後改回來、只 Clear 那個失敗的 task，看它單獨重跑成功。這是下一章排錯的基本功。

**練習 3：用 CLI 列出所有 DAG**

```bash
docker exec airflow-webserver airflow dags list
```

對照 `airflow/dags/` 資料夾裡的檔案，確認每支 .py 都被載入了。注意 `example_trigger_dag_operator_dag.py` 一個檔案裡有**兩個** DAG——跟第 1 章「一個模組多個任務」同一個道理。

**練習 4：全程只用 UI 完成一輪**

不碰終端機，只用滑鼠把整個流程走一遍：在 UI 上把 `example_parallel_dag` unpause（列表左邊的開關）→ 按右上角 ▶ 觸發 → 到 Grid 頁看新的一欄出現、逐格變綠 → 點一個 task 看 Logs → 對其中一個 task 按 Clear，看它重新排隊執行。做完這題，Step 7 的五個 UI 動作你就全部實際操作過一遍了——第 12 章排錯時不會在介面上迷路。

---

## 這一章你學到了

- Airflow 是 Airbnb 開發開源、現在屬於 Apache 基金會的工作流管理系統，用 Python 撰寫工作流，是業界 Data Pipeline 和 ETL 編排的標準工具。
- Airflow 是編排引擎，它取代的是第 9 章的 APScheduler；Celery 仍然是最底層的執行引擎。
- Airflow 由四個服務組成：Postgres 存狀態、init 做初始化、webserver 提供 UI、scheduler 負責排程（Executor 就藏在 scheduler 裡）。設定來自 airflow.cfg，關鍵項目被 compose 的環境變數覆蓋。
- DAG 是由 Operator 和 `>>` 依賴組成的一張有向無環圖；一支 Python 檔就是一個工作流，而且能表達直線型 pipeline 做不到的分支與匯合。
- DAG 檔案的頂層只放宣告，實際動作要包進 task 的函式裡；Airflow 的排程是「區間結束才執行」，unpause 之後沒有立刻動不代表壞掉。
- 每次執行都有紀錄和 log，失敗的 task 可以單獨補跑（入口就是 UI 的 Grid、Logs、Clear）——這是生產級編排的核心價值。

## 下一章要做什麼

基礎會了，**下一章學 Airflow 的進階 Operator：條件分支（Branch）、task 間傳資料（XCom）、DAG 觸發 DAG（TriggerDagRun）、在容器裡跑任務（DockerOperator）**——這些是拼出複雜工作流的積木。
