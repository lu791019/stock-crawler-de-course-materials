# 第 11 章：Airflow 基礎 — 架起你的工作流編排引擎

> 接下來三章是全課程的壓軸。你會用工業級的工作流引擎 Airflow，把前面十章的每一段串成一張可管理、可觀察、可補跑的 DAG。這一章先把 Airflow 架起來、跑通第一個 DAG。

---

## 做完這一章，你會做到

1. 講清楚一個常見誤解：**Airflow 取代的是第 6 章的 APScheduler，不是 Celery。**
2. Build 出包含我們爬蟲程式的 Airflow Docker image。
3. 啟動 Airflow（Postgres + init + webserver + scheduler），登入 Web UI。
4. 用 CLI 和 UI 各觸發一次 DAG，看到執行結果和 log。
5. 看懂 DAG、Operator、`>>` 依賴、cron 排程這些核心概念。

---

## 先搞懂（最重要，先講）：Airflow 不是 Celery 的替代品

很多人以為 Airflow 和 Celery 是二選一，其實在這套架構裡它們是**上下層分工**：

- **Airflow = 總指揮 / 編排層**：決定「什麼時候跑、有哪些步驟、誰先誰後、失敗怎麼補跑」，還提供網頁 UI 看歷史。
- **Celery = 執行層**：真正把分散式的活幹掉。

證據就在專案裡：`stock_crawler_producer_dag` 這支 DAG，是在 Airflow 裡呼叫 Celery 的 `.delay()` 把任務發到 RabbitMQ——**Airflow 負責指揮、Celery 負責幹活**（第 13 章會實際跑）。

用一句話定位三個角色：

- 第 6 章 APScheduler = 陽春鬧鐘（只會定時觸發，沒有歷史、沒有依賴管理、沒有 UI）。
- Airflow = 專業總指揮（排程 + 依賴 + 重試 + 補跑 + UI）。
- Celery 從頭到尾都是底層的執行引擎。

**所以 Airflow 取代的是 APScheduler，Celery 依然在最底層幹活。**

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `airflow/Dockerfile` | Image 定義 | Ubuntu + Airflow 2.10 + 我們的 crawler 程式 |
| `airflow/docker-compose-airflow.yml` | 部署（LocalExecutor）| 輕量版，適合開發，這一章用它 |
| `airflow/docker-compose-airflow-celery.yml` | 部署（CeleryExecutor）| 額外起 Redis + Celery Worker（第 13 章談）|
| `airflow/airflow.cfg` | 設定檔 | Airflow 核心設定 |
| `airflow/dags/example_*.py` | 範例 DAG | 這一章與下一章的教材 |
| `airflow/README.md` | 說明 | 啟動方式與 DAG 清單 |

### Airflow 由哪些服務組成

`docker-compose-airflow.yml` 會起四個容器：

| 服務 | 用途 |
|------|------|
| `postgres` | Airflow 的 **metadata 資料庫**（存 DAG 狀態、執行紀錄、排程歷史）|
| `airflow-init` | 初始化資料庫 + 建 admin 帳號（一次性，跑完就 Exit）|
| `airflow-webserver` | Web UI（port 8080）|
| `airflow-scheduler` | 排程器（掃描 DAG、依 cron 觸發、分派 task）|

> **等等，為什麼又多一個 Postgres？我們不是有 MySQL 了嗎？** 兩個資料庫的用途完全不同：**PostgreSQL 是 Airflow 自己的內部資料庫**（存工作流的狀態，就像 Metabase 用 H2 存自己的設定）；**MySQL 是我們的業務資料庫**（存股價）。Airflow 官方預設且支援最完整的是 Postgres，所以照用。兩個各管各的，互不相干：
>
> ```
> Airflow（狀態存 PostgreSQL）→ 排程觸發 → 爬蟲程式 → 股價寫入 MySQL
> ```

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

### Step 7：回 UI 看圖和 log

1. 點 `example_first_dag` → **Graph** 頁。
2. 看到 `start → end` 兩個方格都是綠色（成功）。
3. 點任一方格 → **Logs**，看它執行時印了什麼。

> 💡 「每次執行都有紀錄、每個 task 都有 log、失敗能單獨重跑」——這三件事就是 Airflow 比 APScheduler 高級的地方。

---

## 一行一行讀懂 `example_first_dag`

```python
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator

# DAG 的預設參數：套用到裡面每一個 task
default_args = {
    "owner": "data-team",
    "retries": 1,                          # 失敗自動重試 1 次
    "retry_delay": timedelta(minutes=1),   # 重試間隔 1 分鐘
}

with DAG(
    dag_id="example_first_dag",            # DAG 的唯一名字
    default_args=default_args,
    schedule_interval="0 * * * *",         # cron：每小時整點
    start_date=datetime(2024, 1, 1),       # 從哪天開始生效
    catchup=False,                         # 不補跑歷史排程
) as dag:

    def hello_world():
        print("Hello from Airflow!")

    start_task = PythonOperator(           # 執行一個 Python 函式
        task_id="start",
        python_callable=hello_world,
    )

    end_task = BashOperator(               # 執行一行 shell 指令
        task_id="end",
        bash_command='echo "Hello from Airflow! Success"',
    )

    start_task >> end_task                 # 依賴：start 做完才做 end
```

四個核心概念：

- **DAG**：一張「工作流程圖」的容器，有名字、有排程、有起始日。
- **Operator**：「一個步驟的做法」。`PythonOperator` 跑函式、`BashOperator` 跑指令、`DummyOperator` 佔位。task 就是 Operator 的一次實例化。
- **`>>`**：定義依賴方向。`a >> b` = a 成功後才跑 b。這個符號串起來的圖，就是 DAG（有向無環圖）本人。
- **`catchup=False`**：假設 start_date 是去年，Airflow 預設會把「去年到今天沒跑到的每小時」全部補跑一遍——通常不是你要的，所以關掉。

### cron 排程速查

| 寫法 | 意思 |
|------|------|
| `0 * * * *` | 每小時整點 |
| `0 18 * * 1-5` | 週一到週五 18:00（台股收盤後）|
| `0 11,23 * * *` | 每天 11:00 和 23:00 |
| `None` | 不自動跑，只能手動觸發 |

> 跟第 6 章 APScheduler 的 `CronTrigger` 是同一套 cron 語法——你已經會了。

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
| 1 | `stock-airflow:latest` build 成功 | 爬蟲程式進了 Airflow 環境 |
| 2 | init log 出現 `User "admin" created` | metadata DB 初始化完成 |
| 3 | UI 登入看到 DAG 列表 | webserver 正常 |
| 4 | `example_first_dag` state = success | 排程器能執行 DAG |
| 5 | Graph 上 10 個 task 同時變綠 | Airflow 能平行跑 task |

---

## 想再深入一點

- **DAG（有向無環圖）到底是什麼？** 「有向」= 步驟有先後方向；「無環」= 不會繞回自己（不會 A→B→A 無限循環）。Airflow 用它描述「一整套工作的步驟與依賴」。這比 APScheduler 的「時間到就跑一個函式」強大太多——它能表達複雜的流程圖。
- **Airflow 的可觀察性（observability）是它最大價值之一。** 每次執行都留下紀錄：哪天跑的、哪個 task 花多久、哪個失敗、log 是什麼。出事時你能只重跑失敗的那個 task，不用整批重來。這是 APScheduler 完全給不了的。
- **為什麼 DAG 檔案改了不用重啟？** compose 把 `airflow/dags/` 掛載進容器，scheduler 會定期重新掃描這個資料夾。你在本機改 DAG 存檔，過幾十秒 UI 就會更新。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| 8080 打不開 / 衝突 | phpMyAdmin 也用 8080 | 先 `docker compose -f docker-compose-local.yml down` |
| webserver 報 `You need to initialize the database` | webserver 比 init 先跑 | 等 init 完成後 `docker restart airflow-webserver airflow-scheduler` |
| 一啟動就報錯少設定 | 沒有 `.env` | 先 `cp .env.example .env` |
| DAG 列表是空的 | dags 資料夾沒掛到 | 確認從專案根目錄啟動 compose |
| DAG 觸發了沒反應 | DAG 還是 paused | 先 unpause 再 trigger |
| image 不存在 | 沒 build 過 | `docker build -f airflow/Dockerfile -t stock-airflow:latest .` |

---

## 想一想（確認你懂了）

**Q1：Airflow 取代的是我們前面哪一章的東西？它跟 Celery 是競爭還是分工？**

取代的是第 6 章的 APScheduler（排程 / 觸發那一層）。它跟 Celery 是**分工**不是競爭：Airflow 負責「何時做、依賴順序、失敗補跑、監控」，Celery 負責「實際分散式執行」。專案的 `stock_crawler_producer_dag` 就是 Airflow 呼叫 Celery `.delay()` 的實例（第 13 章會跑）。

**Q2：第 6 章的 APScheduler 有哪些做不到、而 Airflow 做得到的事？**

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

---

## 這一章你學到了

- Airflow 是編排總指揮，取代 APScheduler；Celery 仍是底層執行引擎。
- Airflow 四件套：Postgres（狀態）、init（初始化）、webserver（UI）、scheduler（排程）。
- DAG = Operator + `>>` 依賴，一張有向無環圖。
- 每次執行都有紀錄和 log，失敗可以單獨補跑——這是生產級編排的核心價值。

## 下一章要做什麼

基礎會了，**下一章學 Airflow 的進階 Operator：條件分支（Branch）、task 間傳資料（XCom）、DAG 觸發 DAG（TriggerDagRun）、在容器裡跑任務（DockerOperator）**——這些是拼出複雜工作流的積木。
