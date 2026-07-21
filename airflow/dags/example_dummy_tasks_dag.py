"""
DummyOperator 組合流程的 Airflow DAG 範例。

對應課程：Airflow 章節的「用 DummyOperator 組織工作流形狀」主題。
教學目的：說明如何用不做事的 DummyOperator 當作集合點，把較複雜的依賴結構表達清楚。

核心概念：
- DummyOperator 不執行任何實際工作，只在流程圖上當作一個節點（集合點或分界點）。
- 用它可以把「準備（平行）→ 驗證（匯合）→ 處理（平行）→ 合併」這種先分散再收攏的
  依賴結構表達得清楚易讀，而不必把真實工作硬塞進這些節點。

觸發方式：
    airflow dags unpause example_dummy_tasks_dag
    airflow dags trigger example_dummy_tasks_dag
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator


# 這支 DAG 的共用預設參數。
default_args = {
    'owner': 'data-team',              # 負責團隊
    'retries': 1,                       # task 失敗時重試 1 次
    'retry_delay': timedelta(minutes=1),  # 每次重試間隔 1 分鐘
}

def hello_world():
    """起始任務呼叫的函式。"""
    print("Hello from Airflow!")


# 用 with DAG(...) as dag 建立 DAG。
with DAG(
    dag_id='example_dummy_tasks_dag',
    default_args=default_args,
    description='A DAG example with multiple dummy tasks',
    schedule_interval=None,  # 不自動排程，只能手動觸發
    start_date=datetime(2024, 1, 1),  # 排程起算日
    catchup=False,  # 不補跑 start_date 到現在漏掉的歷史排程區間
    tags=['example'],
) as dag:

    # 起始任務：流程起點，實際會執行 hello_world。
    start_task = PythonOperator(
        task_id='start',
        python_callable=hello_world,
    )

    # 資料準備任務（兩個平行的集合點，代表兩份可同時準備的資料）。
    prepare_data_1 = DummyOperator(
        task_id='prepare_data_1',
    )

    prepare_data_2 = DummyOperator(
        task_id='prepare_data_2',
    )

    # 資料驗證任務：匯合點，等兩份準備工作都完成後才進行。
    validate_data = DummyOperator(
        task_id='validate_data',
    )

    # 資料處理任務（驗證通過後，兩個平行的處理集合點）。
    process_data_1 = DummyOperator(
        task_id='process_data_1',
    )

    process_data_2 = DummyOperator(
        task_id='process_data_2',
    )

    # 合併結果任務：匯合點，等兩份處理工作都完成後才進行。
    merge_results = DummyOperator(
        task_id='merge_results',
    )

    # 結束任務：流程終點，執行一行 echo。
    end_task = BashOperator(
        task_id='end',
        bash_command='echo "Hello from Airflow! Success"',
    )

    # 設定依賴關係，形成「平行 → 匯合 → 平行 → 匯合」的結構：
    # start -> [prepare_data_1, prepare_data_2] -> validate_data -> [process_data_1, process_data_2] -> merge_results -> end
    start_task >> [prepare_data_1, prepare_data_2] >> validate_data
    validate_data >> [process_data_1, process_data_2] >> merge_results >> end_task
