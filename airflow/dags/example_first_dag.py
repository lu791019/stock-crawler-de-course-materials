"""
第一支 Airflow DAG 範例。

對應課程：Airflow 入門章節的「第一支 DAG」主題。
教學目的：用最少的元件說明 DAG、Operator、依賴關係這三個核心概念。

核心概念：
- DAG 是一個工作流的容器，本身不執行工作，只負責把多個步驟組織起來。
- Operator 代表工作流裡的一個步驟，每一種 Operator 是「做某類事情的方法」；
  PythonOperator 用來呼叫 Python 函式，BashOperator 用來執行 shell 指令。
- `>>` 用來定義步驟之間的先後順序，a >> b 表示 a 成功後才會執行 b。

觸發方式（先解除暫停，再手動觸發一次）：
    airflow dags unpause example_first_dag
    airflow dags trigger example_first_dag
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator


# default_args 是這支 DAG 裡所有 task 共用的預設參數，
# 個別 task 若沒有特別指定，就會套用這裡的設定。
default_args = {
    'owner': 'data-team',              # 這支 DAG 的負責團隊，會顯示在 Airflow 介面上
    'retries': 1,                       # task 失敗時自動重試的次數，這裡設為重試 1 次
    'retry_delay': timedelta(minutes=1),  # 兩次重試之間要等待多久，這裡設為 1 分鐘
}
# 用 with DAG(...) as dag 的寫法，可以讓區塊內建立的 task 自動歸屬到這支 DAG。
with DAG(
    dag_id='example_first_dag',         # DAG 的唯一識別名稱，Airflow 介面上以此顯示
    default_args=default_args,          # 套用上面定義的共用預設參數
    description='A simple example DAG',  # 這支 DAG 的簡短說明
    schedule_interval='0 * * * *',      # cron 排程：每個整點（每小時）自動執行一次
    start_date=datetime(2024, 1, 1),    # 排程的起算日，Airflow 從這個日期之後才計算執行時間
    catchup=False,  # 設為 False 表示不補跑；若為 True，會把 start_date 到現在漏掉的每個排程區間全部補跑一遍
    tags=['example'],                   # 標籤，方便在 Airflow 介面上分類與篩選 DAG
) as dag:

    def hello_world():
        """簡單的 Python function，被 start_task 呼叫時會印出訊息。"""
        print("Hello from Airflow!")

    # 起始任務：用 PythonOperator 呼叫上面的 hello_world 函式。
    start_task = PythonOperator(
        task_id='start',                # task 在這支 DAG 內的唯一識別名稱
        python_callable=hello_world,    # 指定要執行的函式（只給函式名稱，不加括號）
    )

    # 結束任務：用 BashOperator 執行一行 shell 指令。
    end_task = BashOperator(
        task_id='end',
        bash_command='echo "Hello from Airflow! Success"',  # 實際要執行的 shell 指令
    )

    # 設定依賴關係：start_task 成功後才執行 end_task。
    start_task >> end_task
