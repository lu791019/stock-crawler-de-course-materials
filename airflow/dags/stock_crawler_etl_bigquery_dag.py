"""
Stock BigQuery ETL DAG（雙寫版的每日資料線）
每個交易日 20:00：發爬蟲任務（worker 雙寫 Cloud SQL/MySQL＋BigQuery raw）
→ 等 worker 消化 → 重算 BigQuery 分析層（stage view＋app 實體表）

跟舊版的差別：沒有「把 MySQL 整批搬進 BigQuery」的 sync task——
雙寫讓資料在寫入當下就落 raw 層, 排程只剩「產生新資料」和「重算分析層」兩件事。
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator

# 發任務用的 Celery task（發到佇列, 不在 Airflow 裡執行爬蟲——串法二）
from crawler.tasks_crawler_finmind import crawler_finmind
from crawler.stock_bigquery_data_transform import (
    create_stage_layer,
    create_app_layer,
)

STOCK_IDS = [
    "2330", "2317", "2454", "2308", "2382",
    "0050", "0056", "00713", "00878", "006208",
]


def send_crawler_tasks():
    """把整批股票的爬蟲任務發到 twse 佇列, worker 收到後執行雙寫。

    用 apply_async 指定佇列（同 producer DAG 的理由：分流版 worker 只聽 twse/tpex）。
    發完就返回——爬蟲的成敗看 Flower 或 worker log, 不在這個 task 裡等。
    """
    for stock_id in STOCK_IDS:
        crawler_finmind.apply_async(kwargs={"stock_id": stock_id}, queue="twse")
        print(f"已發送 {stock_id} 爬蟲任務")


default_args = {
    "owner": "data-team",
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(hours=1),
}

with DAG(
    dag_id="stock_bigquery_etl_dag",
    default_args=default_args,
    description="台股每日資料線 - 觸發爬蟲雙寫並重算 BigQuery 分析層",
    schedule_interval="0 20 * * 1-5",
    catchup=False,
    max_active_runs=1,
    tags=["stock", "bigquery", "etl", "analytics"],
) as dag:

    start_task = BashOperator(
        task_id="start_daily_pipeline",
        bash_command='echo "開始執行台股每日資料線..."',
    )

    # ① 發爬蟲任務：worker 會把當日資料雙寫進 MySQL/Cloud SQL 與 BigQuery raw
    send_tasks = PythonOperator(
        task_id="send_crawler_tasks",
        python_callable=send_crawler_tasks,
    )

    # ② 等 worker 消化：發任務是非同步的, 給 worker 一段時間把整批做完
    #    教學版用固定等待；真實系統會改用 sensor 盯完成訊號（例如查表的最新日期）
    wait_for_workers = BashOperator(
        task_id="wait_for_workers",
        bash_command="sleep 90",
    )

    # ③ 重算 stage：view 定義冪等重建（raw 有新資料它自動反映）
    transform_stage = PythonOperator(
        task_id="create_stage_layer",
        python_callable=create_stage_layer,
    )

    # ④ 重算 app：實體表不會自己更新, 每日 CTAS 重算——排程存在的主因
    transform_app = PythonOperator(
        task_id="create_app_layer",
        python_callable=create_app_layer,
    )

    end_task = BashOperator(
        task_id="end_daily_pipeline",
        bash_command='echo "台股每日資料線執行完成"',
        trigger_rule="all_success",
    )

    start_task >> send_tasks >> wait_for_workers >> transform_stage >> transform_app >> end_task
