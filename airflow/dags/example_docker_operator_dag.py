"""
DockerOperator Airflow DAG 範例。

對應課程：Airflow 章節的「在 DAG 裡執行容器化任務（DockerOperator）」主題。
教學目的：說明如何用 DockerOperator 在 task 裡臨時起一個容器來執行工作。

核心概念：
- DockerOperator 會為這個 task 臨時起一個容器來執行指定指令，任務結束後把容器刪掉
  （由 auto_remove=True 控制），適合需要獨立環境或特定映像檔的任務。
- 能這樣運作的前提是 docker compose 已經把 /var/run/docker.sock 掛進 Airflow 容器，
  Airflow 才有權限指揮宿主機的 Docker 去起新容器。
- 這個範例用三個不同映像檔（python、alpine、ubuntu）示範同一支 DAG 可以混用多種容器環境。

觸發方式：
    airflow dags unpause example_docker_operator_dag
    airflow dags trigger example_docker_operator_dag
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.operators.python_operator import PythonOperator


# 這支 DAG 的共用預設參數。
default_args = {
    'owner': 'data-team',              # 負責團隊
    'retries': 1,                       # task 失敗時重試 1 次
    'retry_delay': timedelta(minutes=1),  # 每次重試間隔 1 分鐘
    'start_date': datetime(2024, 1, 1),  # 排程起算日
}

def start_pipeline():
    """起始任務呼叫的函式，只印出開始訊息。"""
    print("Pipeline started - preparing to run Docker containers")


def end_pipeline():
    """結束任務呼叫的函式，只印出完成訊息。"""
    print("Pipeline completed successfully!")


# 用 with DAG(...) as dag 建立 DAG。
with DAG(
    dag_id='example_docker_operator_dag',
    default_args=default_args,
    description='A Docker Operator example DAG',
    schedule_interval=None,  # 不自動排程，只能手動觸發
    catchup=False,           # 不補跑歷史排程區間
    tags=['example', 'docker'],
) as dag:

    # 起始任務：用 PythonOperator 印出開始訊息。
    start_task = PythonOperator(
        task_id='start_pipeline',
        python_callable=start_pipeline,
    )

    # Docker 任務 1：用 python:3.9-slim 映像檔臨時起容器執行一段 Python。
    python_docker_task = DockerOperator(
        task_id='run_python_script',
        image='python:3.9-slim',  # 這個 task 要使用的容器映像檔
        command='python -c "print(\'Hello from Python Docker container!\'); import time; time.sleep(5)"',  # 在容器內執行的指令
        auto_remove=True,  # 執行完畢後自動刪除臨時容器，避免殘留
    )

    # Docker 任務 2：用 alpine:latest 映像檔執行一段 shell 模擬資料處理。
    data_processing_task = DockerOperator(
        task_id='data_processing',
        image='alpine:latest',
        command=['sh', '-c', 'echo "Processing data..." && sleep 3 && echo "Data processing completed"'],  # command 用 list 形式指定指令與參數
        auto_remove=True,
    )

    # Docker 任務 3：用 ubuntu:20.04 映像檔執行 bash 指令。
    bash_docker_task = DockerOperator(
        task_id='run_bash_commands',
        image='ubuntu:20.04',
        command=['bash', '-c', 'echo "Running in Ubuntu container" && ls -la && whoami'],
        auto_remove=True,
    )

    # 結束任務：用 PythonOperator 印出完成訊息。
    end_task = PythonOperator(
        task_id='end_pipeline',
        python_callable=end_pipeline,
    )

    # 設定依賴關係：起始任務之後，三個 Docker 任務平行執行，全部完成才進入結束任務。
    # start -> [python_docker, data_processing, bash_docker] -> end
    start_task >> [python_docker_task, data_processing_task, bash_docker_task] >> end_task
