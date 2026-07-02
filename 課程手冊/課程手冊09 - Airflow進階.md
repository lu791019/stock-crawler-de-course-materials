# Airflow 進階 實作手冊

> 對象：已完成課程手冊08（Airflow 基礎）的學員
> 涵蓋：BranchOperator 條件分支 → XCom 跨 task 傳資料 → TriggerDagRunOperator → DockerOperator → DummyOperator 複雜依賴
> 所有指令在 WSL Ubuntu 環境實測

---

## 這集要做什麼？

上一集學了最基礎的 DAG（start → end）。但實務上的工作流程更複雜：
- 「如果是上午就跑 A，下午就跑 B」→ **BranchOperator**
- 「前一步的結果要傳給下一步」→ **XCom**
- 「這個 DAG 跑完要觸發另一個 DAG」→ **TriggerDagRunOperator**
- 「任務要在獨立的 Docker 容器裡跑」→ **DockerOperator**

完成後你會理解 Airflow 的四大進階 Operator。

---

## 前置準備

確保 Airflow 還在跑（如果停了就重新啟動）：

```bash
cd ~/stock-crawler
docker network create my_network 2>/dev/null
cp .env.example .env
docker compose -f airflow/docker-compose-airflow.yml up -d
```

首次啟動需等 init 完成後重啟：

```bash
# 等 init 完成（看到 User "admin" created）
docker logs airflow-airflow-init-1 2>&1 | tail -3

# 重啟 webserver 和 scheduler
docker restart airflow-webserver airflow-scheduler
```

等 20 秒後確認：`curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health` → `200`

---

## 目錄

- [第一部分：BranchOperator 條件分支](#第一部分branchoperator-條件分支)
- [第二部分：XCom 跨 task 傳資料](#第二部分xcom-跨-task-傳資料)
- [第三部分：TriggerDagRunOperator](#第三部分triggerdagrunoperator)
- [第四部分：DockerOperator](#第四部分dockeroperator)
- [第五部分：DummyOperator 複雜依賴](#第五部分dummyoperator-複雜依賴)

---

## 第一部分：BranchOperator 條件分支

### 概念

有時候工作流程需要「根據條件走不同路線」，例如：
- 上午跑任務 A，下午跑任務 B
- 資料量大走批次處理，資料量小走即時處理

`BranchPythonOperator` 就是做這件事的。

### Step 1：看程式碼

```bash
cat airflow/dags/example_branch_operator_dag.py
```

重點：

```python
def decide_morning_or_afternoon(**context):
    current_hour = datetime.now().hour
    if current_hour < 12:
        return 'morning_task'      # 回傳 task_id
    else:
        return 'afternoon_task'    # 回傳另一個 task_id

time_branch = BranchPythonOperator(
    task_id='decide_time_path',
    python_callable=decide_morning_or_afternoon,
)
```

`BranchPythonOperator` 的函式要 **return task_id**（字串），Airflow 就只跑那條路線。

### Step 2：觸發

```bash
docker exec airflow-webserver airflow dags unpause example_branch_operator_dag
docker exec airflow-webserver airflow dags trigger example_branch_operator_dag
```

### Step 3：觀察結果

1. 開 Web UI → 點 `example_branch_operator_dag` → Graph
2. 會看到 `start` → `decide_time_path` → 兩條分支
3. 根據你跑的時間，只有一條路線是綠色（成功），另一條是粉紅色（skipped）

---

## 第二部分：XCom 跨 task 傳資料

### 概念

每個 task 是獨立執行的，但有時候需要把前一步的結果傳給下一步。
**XCom**（Cross-Communication）就是 Airflow 內建的 task 間資料傳遞機制。

### Step 1：看程式碼

```bash
cat airflow/dags/example_xcom_dag.py
```

重點：

**推送資料（Push）** — 兩種方式：

```python
# 方式 1：return 自動推送
def step1_create_data(**context):
    data = {'id': 1234, 'name': '小明', 'value': 50}
    return data   # 自動存到 XCom

# 方式 2：手動推送
def step2_process_data(**context):
    context['task_instance'].xcom_push(key='processed_data', value=result)
```

**拉取資料（Pull）：**

```python
def step3_combine_data(**context):
    ti = context['task_instance']
    original = ti.xcom_pull(task_ids='step1_create_data')          # 拉 return 值
    processed = ti.xcom_pull(task_ids='step2_process_data', key='processed_data')  # 拉指定 key
```

### Step 2：觸發

```bash
docker exec airflow-webserver airflow dags unpause example_xcom_coffee_shop_dag
docker exec airflow-webserver airflow dags trigger example_xcom_coffee_shop_dag
```

### Step 3：觀察 XCom

1. Web UI → 點 `example_xcom_coffee_shop_dag`
2. 等所有 task 變綠色
3. 點任一 task → 「XCom」分頁 → 可以看到推送的資料內容

---

## 第三部分：TriggerDagRunOperator

### 概念

大型系統常常需要「DAG A 跑完後，自動觸發 DAG B」。
`TriggerDagRunOperator` 讓一個 DAG 可以觸發另一個 DAG。

### Step 1：看程式碼

```bash
cat airflow/dags/example_trigger_dag_operator_dag.py
```

這個檔案定義了**兩個 DAG**：

```python
# 主 DAG
trigger_data_processing = TriggerDagRunOperator(
    task_id='trigger_data_processing_dag',
    trigger_dag_id='example_triggered_data_processing_dag',  # 被觸發的 DAG ID
    wait_for_completion=True,  # 等被觸發的 DAG 跑完才繼續
)

# 被觸發的 DAG（同一個檔案裡）
with DAG(dag_id='example_triggered_data_processing_dag', ...):
    ...
```

### Step 2：觸發

```bash
docker exec airflow-webserver airflow dags unpause example_trigger_main_dag
docker exec airflow-webserver airflow dags unpause example_triggered_data_processing_dag
docker exec airflow-webserver airflow dags trigger example_trigger_main_dag
```

> 注意：被觸發的 DAG 也要 unpause，否則觸發不了。

### Step 3：觀察

1. Web UI 先看 `example_trigger_main_dag`：跑到 `trigger_data_processing_dag` 時會等待
2. 切到 `example_triggered_data_processing_dag`：會看到一個新的 run 被觸發
3. 被觸發的 DAG 跑完後，主 DAG 才繼續跑 `end`

---

## 第四部分：DockerOperator

### 概念

有時候任務需要特定的環境（不同 Python 版本、特定套件），
`DockerOperator` 讓你在獨立的 Docker 容器裡執行任務。

### Step 1：看程式碼

```bash
cat airflow/dags/example_docker_operator_dag.py
```

重點：

```python
python_docker_task = DockerOperator(
    task_id='run_python_script',
    image='python:3.9-slim',           # 用哪個 Docker Image
    command='python -c "print(\'Hello from Docker!\')"',
    auto_remove=True,                  # 跑完自動刪容器
)
```

### Step 2：觸發

```bash
docker exec airflow-webserver airflow dags unpause example_docker_operator_dag
docker exec airflow-webserver airflow dags trigger example_docker_operator_dag
```

### Step 3：觀察

1. Web UI → `example_docker_operator_dag` → Graph
2. 三個 Docker task 平行執行（分別跑 Python、Alpine、Ubuntu 容器）
3. 點任一 task → Logs，可以看到容器內的輸出

> 注意：DockerOperator 需要容器內能存取 Docker（docker.sock 已在 compose 裡掛載）。
> 如果執行失敗，可能是 docker.sock 權限問題，可忽略，概念理解即可。

---

## 第五部分：DummyOperator 複雜依賴

### 概念

`DummyOperator` 不做任何事，只作為「分支點」或「合併點」，讓 DAG 結構更清晰。

### Step 1：看程式碼

```bash
cat airflow/dags/example_dummy_tasks_dag.py
```

依賴結構：

```
start → [prepare_data_1, prepare_data_2] → validate_data → [process_data_1, process_data_2] → merge_results → end
```

這就是一個典型的 ETL 流程：準備 → 驗證 → 處理 → 合併。

### Step 2：觸發

```bash
docker exec airflow-webserver airflow dags unpause example_dummy_tasks_dag
docker exec airflow-webserver airflow dags trigger example_dummy_tasks_dag
```

### Step 3：觀察

Web UI → Graph 頁面可以清楚看到分支和合併的結構。

---

## Operator 速查表

| Operator | 用途 | 回傳值 |
|----------|------|--------|
| `PythonOperator` | 執行 Python 函式 | return 值存 XCom |
| `BashOperator` | 執行 Shell 指令 | stdout 最後一行存 XCom |
| `BranchPythonOperator` | 條件分支 | return task_id 字串 |
| `DummyOperator` | 佔位（不做事） | 無 |
| `TriggerDagRunOperator` | 觸發另一個 DAG | 無 |
| `DockerOperator` | 在 Docker 容器裡執行 | 容器 stdout |

---

## 本集完成清單

- [ ] BranchOperator：觸發 + 觀察條件分支（一條綠、一條 skipped）
- [ ] XCom：觸發 + 在 Web UI 看 XCom 傳遞的資料
- [ ] TriggerDagRunOperator：主 DAG 觸發子 DAG，觀察兩個 DAG 的關聯
- [ ] DockerOperator：在獨立容器裡跑任務
- [ ] DummyOperator：觀察複雜依賴結構（分支 + 合併）

---

## 停止服務

```bash
docker compose -f airflow/docker-compose-airflow.yml down
```

---

## 下集預告

下一集把 Airflow 和爬蟲串起來：
- 用 Airflow DAG 自動排程跑 FinMind 爬蟲
- Producer → RabbitMQ → Worker → MySQL 全流程自動化
- 在 Airflow UI 監控爬蟲任務狀態
