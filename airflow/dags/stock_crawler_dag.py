"""
Stock Crawler DAG
使用 FinMind API 爬取台股股價數據，並上傳至 MySQL 資料庫
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator

from crawler.tasks_crawler_finmind import crawler_finmind

STOCK_IDS = [
    "2330", "2317", "2454", "2308", "2382",
    "0050", "0056", "00713", "00878", "006208",
]

default_args = {
    "owner": "data-team",
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(hours=1),
}

with DAG(
    dag_id="stock_crawler_dag",
    default_args=default_args,
    description="台股股價爬取 DAG - 使用 FinMind API 爬取股價並寫入 MySQL",
    schedule_interval="0 18 * * 1-5",
    catchup=False,
    max_active_runs=1,
    tags=["stock", "crawler", "finmind"],
) as dag:

    start_task = BashOperator(
        task_id="start_crawler",
        bash_command="echo 開始執行台股爬蟲任務...",
    )

    stock_branch = DummyOperator(task_id="stock_branch")

    stock_tasks = []
    for stock_id in STOCK_IDS:
        task = PythonOperator(
            task_id=f"crawl_stock_{stock_id}",
            python_callable=crawler_finmind,
            op_args=[stock_id],
        )
        stock_tasks.append(task)

    end_task = BashOperator(
        task_id="end_crawler",
        bash_command="echo 台股爬蟲任務執行完成！",
        trigger_rule="all_success",
    )

    start_task >> stock_branch >> stock_tasks >> end_task
