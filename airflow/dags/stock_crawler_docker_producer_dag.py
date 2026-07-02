"""
Stock Crawler Docker Producer DAG
使用 Docker 容器執行台股爬蟲任務
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.operators.bash_operator import BashOperator

default_args = {
    "owner": "data-team",
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(hours=1),
}

with DAG(
    dag_id="stock_crawler_docker_producer_dag",
    default_args=default_args,
    description="台股爬蟲 Docker DAG - 用 Docker 容器執行爬蟲",
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    tags=["stock", "crawler", "docker"],
) as dag:

    start_task = BashOperator(
        task_id="start_crawler",
        bash_command="echo 開始執行台股爬蟲任務...",
    )

    DOCKER_IMAGE = "stock-crawler:latest"
    DOCKER_COMMAND = "uv run python -m crawler.producer_crawler_finmind"
    DOCKER_NETWORK = "my_network"

    docker_crawler_task = DockerOperator(
        task_id="docker_stock_crawler",
        image=DOCKER_IMAGE,
        command=DOCKER_COMMAND,
        network_mode=DOCKER_NETWORK,
        environment={"TZ": "Asia/Taipei"},
        auto_remove=True,
    )

    end_task = BashOperator(
        task_id="end_crawler",
        bash_command="echo 台股爬蟲任務發送完成！",
        trigger_rule="all_success",
    )

    start_task >> docker_crawler_task >> end_task
