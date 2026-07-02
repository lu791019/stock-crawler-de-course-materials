"""
Docker Operator DAG 範例
這個範例展示如何在 Airflow 中使用 Docker Operator 來執行容器化的任務
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.operators.python_operator import PythonOperator


# 預設參數
default_args = {
    'owner': 'data-team',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
    'start_date': datetime(2024, 1, 1),
}

def start_pipeline():
    """啟動 pipeline 的 Python function"""
    print("Pipeline started - preparing to run Docker containers")


def end_pipeline():
    """結束 pipeline 的 Python function"""
    print("Pipeline completed successfully!")


# 使用 with DAG 語法
with DAG(
    dag_id='example_docker_operator_dag',
    default_args=default_args,
    description='A Docker Operator example DAG',
    schedule_interval=None,
    catchup=False,
    tags=['example', 'docker'],
) as dag:

    # 起始任務
    start_task = PythonOperator(
        task_id='start_pipeline',
        python_callable=start_pipeline,
    )

    # Docker 任務 1: 執行 Python 腳本
    python_docker_task = DockerOperator(
        task_id='run_python_script',
        image='python:3.9-slim',
        command='python -c "print(\'Hello from Python Docker container!\'); import time; time.sleep(5)"',
        auto_remove=True,  # 執行完畢後自動刪除容器
    )

    # Docker 任務 2: 執行資料處理
    data_processing_task = DockerOperator(
        task_id='data_processing',
        image='alpine:latest',
        command=['sh', '-c', 'echo "Processing data..." && sleep 3 && echo "Data processing completed"'],
        auto_remove=True,
    )

    # Docker 任務 3: 執行 Ubuntu 容器中的 bash 命令
    bash_docker_task = DockerOperator(
        task_id='run_bash_commands',
        image='ubuntu:20.04',
        command=['bash', '-c', 'echo "Running in Ubuntu container" && ls -la && whoami'],
        auto_remove=True,
    )

    # 結束任務
    end_task = PythonOperator(
        task_id='end_pipeline',
        python_callable=end_pipeline,
    )

    # 設定依賴關係
    # start -> [python_docker, data_processing, bash_docker] -> end
    start_task >> [python_docker_task, data_processing_task, bash_docker_task] >> end_task
