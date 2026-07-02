"""
範例 Airflow DAG - 包含多個 Dummy Tasks
展示複雜的工作流程和任務依賴關係
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator


# 預設參數
default_args = {
    'owner': 'data-team',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

def hello_world():
    """簡單的 Python function"""
    print("Hello from Airflow!")


# 使用 with DAG 語法
with DAG(
    dag_id='example_dummy_tasks_dag',
    default_args=default_args,
    description='A DAG example with multiple dummy tasks',
    schedule_interval=None,  # 不定期執行
    start_date=datetime(2024, 1, 1),  # 從2024年1月1日開始生效
    catchup=False,  # 不執行歷史任務
    tags=['example'],
) as dag:

    # 起始任務
    start_task = PythonOperator(
        task_id='start',
        python_callable=hello_world,
    )

    # 資料準備任務（並行）
    prepare_data_1 = DummyOperator(
        task_id='prepare_data_1',
    )
    
    prepare_data_2 = DummyOperator(
        task_id='prepare_data_2',
    )
    
    # 資料驗證任務
    validate_data = DummyOperator(
        task_id='validate_data',
    )
    
    # 資料處理任務（並行）
    process_data_1 = DummyOperator(
        task_id='process_data_1',
    )
    
    process_data_2 = DummyOperator(
        task_id='process_data_2',
    )
    
    # 合併結果任務
    merge_results = DummyOperator(
        task_id='merge_results',
    )

    # 結束任務
    end_task = BashOperator(
        task_id='end',
        bash_command='echo "Hello from Airflow! Success"',
    )

    # 設定依賴關係：
    # start -> [prepare_data_1, prepare_data_2] -> validate_data -> [process_data_1, process_data_2] -> merge_results -> end
    start_task >> [prepare_data_1, prepare_data_2] >> validate_data
    validate_data >> [process_data_1, process_data_2] >> merge_results >> end_task
