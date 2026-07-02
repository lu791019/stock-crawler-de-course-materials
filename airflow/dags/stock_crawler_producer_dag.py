"""
Stock Crawler Producer DAG
透過 Celery Producer 發送台股爬蟲任務到 RabbitMQ
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


def trigger_stock_crawler(stock_id):
    """觸發股票爬蟲任務"""
    crawler_finmind.delay(stock_id=stock_id)


default_args = {
    "owner": "data-team",
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(hours=1),
}

with DAG(
    dag_id="stock_crawler_producer_dag",
    default_args=default_args,
    description="台股爬蟲 Producer DAG - 透過 Celery 發送爬蟲任務",
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=["stock", "crawler", "producer"],
) as dag:

    start_task = BashOperator(
        task_id="start_crawler",
        bash_command="echo 開始發送台股爬蟲任務...",
    )

    stock_branch = DummyOperator(task_id="stock_branch")

    stock_tasks = []
    for stock_id in STOCK_IDS:
        task = PythonOperator(
            task_id=f"crawl_stock_{stock_id}",
            python_callable=trigger_stock_crawler,
            op_args=[stock_id],
        )
        stock_tasks.append(task)

    end_task = BashOperator(
        task_id="end_crawler",
        bash_command="echo 台股爬蟲任務發送完成！",
        trigger_rule="all_success",
    )

    start_task >> stock_branch >> stock_tasks >> end_task
