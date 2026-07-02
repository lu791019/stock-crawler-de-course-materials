# Airflow 基礎 實作手冊

> 對象：已完成課程手冊01-07 的學員
> 涵蓋：Airflow 概念 → Docker Compose 架設 → 第一個 DAG → 手動觸發 → 看執行結果
> 所有指令在 WSL Ubuntu 環境實測

---

## 這集要做什麼？

前面我們手動跑 Producer 發任務。但實務上，爬蟲要「每天自動跑」。
**Airflow** 就是做這件事的工具 — 把任務排成 DAG（有向無環圖），設定排程，自動執行。

完成後你會有：
- Airflow Web UI 跑起來
- 第一個 DAG 成功執行
- 理解 DAG、Task、Operator 的關係

---

## 目錄

- [第一部分：Build Airflow Image](#第一部分build-airflow-image)
- [第二部分：啟動 Airflow](#第二部分啟動-airflow)
- [第三部分：Airflow Web UI](#第三部分airflow-web-ui)
- [第四部分：跑第一個 DAG](#第四部分跑第一個-dag)
- [第五部分：看懂 DAG 程式碼](#第五部分看懂-dag-程式碼)
- [第六部分：平行任務 DAG](#第六部分平行任務-dag)

---

## 第一部分：Build Airflow Image

Airflow 需要一個包含我們爬蟲程式碼的 Docker Image。

### Step 1：Build Image

```bash
cd ~/stock-crawler
docker build -f airflow/Dockerfile -t stock-airflow:latest .
```

這會花幾分鐘（首次需要下載 Ubuntu + 安裝 Airflow 及所有依賴）。

✅ **預期**：最後一行顯示 `naming to docker.io/library/stock-airflow:latest done`

### Step 2：驗證 Image

```bash
docker run --rm stock-airflow:latest python3 -c "import airflow; print(f'Airflow {airflow.__version__}')"
```

✅ **預期**：`Airflow 2.10.4`

---

## 第二部分：啟動 Airflow

### Step 1：準備環境

```bash
cd ~/stock-crawler
docker network create my_network 2>/dev/null
cp .env.example .env
```

### Step 2：啟動 Airflow

```bash
docker compose -f airflow/docker-compose-airflow.yml up -d
```

Airflow 由以下服務組成：

| 服務 | 用途 |
|------|------|
| `postgres` | Airflow 的 metadata 資料庫（存 DAG 狀態、執行紀錄） |
| `airflow-init` | 初始化資料庫 + 建立 admin 帳號（一次性） |
| `airflow-webserver` | Web UI（port 8080） |
| `airflow-scheduler` | 排程器（監控 DAG、觸發任務） |

### Step 3：等待初始化完成

初始化需要約 30-60 秒。確認 init 完成：

```bash
docker logs airflow-airflow-init-1 2>&1 | tail -3
```

✅ **預期**：看到 `User "admin" created with role "Admin"`

### Step 4：重啟 Webserver

首次啟動時，Webserver 可能比 init 早跑，需要重啟一次：

```bash
docker restart airflow-webserver airflow-scheduler
```

等 15-20 秒後驗證：

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health
```

✅ **預期**：`200`

---

## 第三部分：Airflow Web UI

### Step 1：開啟 Web UI

瀏覽器開啟 http://localhost:8080

| 欄位 | 值 |
|------|-----|
| Username | `admin` |
| Password | `admin` |

### Step 2：認識介面

登入後看到 DAG 列表頁：

- 左側是 DAG 名稱，右側有開關（pause/unpause）
- 所有 DAG 預設是 **paused**（暫停），不會自動執行
- 點 DAG 名稱可以看詳細資訊

你會看到 7 個 example DAG 和 5 個 stock_crawler DAG，都來自 `airflow/dags/` 資料夾。

---

## 第四部分：跑第一個 DAG

### Step 1：用 CLI 觸發

```bash
docker exec airflow-webserver airflow dags unpause example_first_dag
docker exec airflow-webserver airflow dags trigger example_first_dag
```

### Step 2：確認執行結果

等 10-15 秒後：

```bash
docker exec airflow-webserver airflow dags list-runs --dag-id example_first_dag
```

✅ **預期**：看到 `state` 欄位顯示 `success`

### Step 3：在 Web UI 確認

1. 開啟 http://localhost:8080
2. 點 `example_first_dag`
3. 看到 Graph 頁面，`start` → `end` 兩個 task 都是綠色（成功）
4. 點任一 task → Logs，可以看到執行日誌

---

## 第五部分：看懂 DAG 程式碼

### example_first_dag.py

```bash
cat airflow/dags/example_first_dag.py
```

重點拆解：

**1. default_args** — DAG 的預設參數

```python
default_args = {
    'owner': 'data-team',
    'retries': 1,                          # 失敗時重試 1 次
    'retry_delay': timedelta(minutes=1),   # 重試間隔 1 分鐘
}
```

**2. DAG 定義** — 一個「工作流程」的容器

```python
with DAG(
    dag_id='example_first_dag',            # DAG 名稱（唯一）
    schedule_interval='0 * * * *',         # Cron 格式：每小時執行
    start_date=datetime(2024, 1, 1),       # 開始生效日期
    catchup=False,                         # 不補跑歷史任務
) as dag:
```

**3. Task 定義** — DAG 裡的每一步

```python
# PythonOperator：執行 Python 函式
start_task = PythonOperator(
    task_id='start',
    python_callable=hello_world,
)

# BashOperator：執行 Shell 指令
end_task = BashOperator(
    task_id='end',
    bash_command='echo "Hello from Airflow! Success"',
)
```

**4. 依賴關係** — 定義執行順序

```python
start_task >> end_task   # start 做完才做 end
```

### Cron 格式速查

| 格式 | 說明 |
|------|------|
| `0 * * * *` | 每小時 |
| `0 18 * * 1-5` | 週一到五 18:00 |
| `0 11,23 * * *` | 每天 11:00 和 23:00 |
| `None` | 不自動執行，只能手動觸發 |

---

## 第六部分：平行任務 DAG

### Step 1：觸發 example_parallel_dag

```bash
docker exec airflow-webserver airflow dags unpause example_parallel_dag
docker exec airflow-webserver airflow dags trigger example_parallel_dag
```

### Step 2：在 Web UI 觀察

1. 點 `example_parallel_dag` → Graph
2. 會看到 `start` → 10 個平行 task → `end` 的結構
3. 10 個 task 同時變成綠色（平行執行）

### Step 3：看程式碼差異

```bash
cat airflow/dags/example_parallel_dag.py
```

關鍵差異：

```python
# 一對多的依賴
start_task >> [task1, task2, task3, ..., task10] >> end_task
```

用 `[]` 把多個 task 包起來 = 平行執行。

---

## 本集完成清單

- [ ] Build stock-airflow:latest Image
- [ ] 啟動 Airflow（postgres + init + webserver + scheduler）
- [ ] 登入 Web UI（admin/admin）
- [ ] 觸發 example_first_dag 並確認 success
- [ ] 看懂 DAG 程式碼（default_args、DAG、Task、>>）
- [ ] 觸發 example_parallel_dag 觀察平行執行

---

## 停止服務

```bash
docker compose -f airflow/docker-compose-airflow.yml down
```

加 `-v` 會清除 postgres volume（所有 DAG 執行紀錄）：
```bash
docker compose -f airflow/docker-compose-airflow.yml down -v
```

---

## 下集預告

下一集學習 Airflow 進階 Operator：
- BranchPythonOperator（條件分支）
- XCom（跨 task 傳資料）
- TriggerDagRunOperator（DAG 觸發 DAG）
- DockerOperator（在容器裡跑任務）
