# Airflow

## 快速啟動

### 前置準備

```bash
# 1. 建立外部網路（如果還沒建過）
docker network create my_network

# 2. 從範本建立 .env 檔（首次使用時）
cp .env.example .env
```

### LocalExecutor 版本（輕量，適合開發）

```bash
docker compose -f airflow/docker-compose-airflow.yml up -d
```

啟動後：
- Airflow Web UI：http://localhost:8080
- 預設帳密：admin / admin（可在 .env 修改）

### CeleryExecutor 版本（分散式，適合生產）

```bash
docker compose -f airflow/docker-compose-airflow-celery.yml up -d
```

此版本額外啟動 Redis + Celery Worker，適合需要平行執行大量 task 的場景。

## DAGs 說明

### 通用範例 DAG（學習用）

| DAG | 學習重點 |
|-----|---------|
| `example_first_dag` | 最基礎的 DAG：PythonOperator + BashOperator |
| `example_parallel_dag` | 10 個 task 平行執行 |
| `example_dummy_tasks_dag` | 複雜依賴關係（分支 → 合併） |
| `example_branch_operator_dag` | BranchPythonOperator 條件分支 |
| `example_xcom_dag` | XCom 跨 task 傳遞資料 |
| `example_trigger_dag_operator_dag` | TriggerDagRunOperator：DAG 觸發 DAG |
| `example_docker_operator_dag` | DockerOperator：在容器裡跑任務 |

### 台股爬蟲 DAG

| DAG | 說明 |
|-----|------|
| `stock_crawler_dag` | 直接在 Airflow 裡呼叫 crawler_finmind 爬 10 支股票 |
| `stock_crawler_producer_dag` | 透過 Celery .delay() 發任務到 RabbitMQ |
| `stock_crawler_docker_producer_dag` | 用 DockerOperator 執行爬蟲容器 |
| `stock_crawler_etl_dag` | 爬蟲 + MySQL View 建立（完整 ETL） |
| `stock_crawler_etl_bigquery_dag` | MySQL → BigQuery 同步 + 分析 View（需 GCP 憑證） |

## 注意事項

- Airflow compose 需要根目錄的 `.env` 檔，首次使用先 `cp .env.example .env`
- LocalExecutor 版 volume 掛載 `../crawler`，需從 stock-crawler 根目錄的相對路徑啟動
- BigQuery 相關 DAG 需要 GCP 憑證，EP16+ 才會用到
