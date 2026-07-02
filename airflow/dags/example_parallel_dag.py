"""
範例 Airflow DAG
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator


# 預設參數
default_args = {
    'owner': 'data-team',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

def hello_world():
    """簡單的 Python function"""
    print("Hello from Airflow!")

def parallel_task(task_name):
    """模擬平行執行的任務"""
    import time
    import random
    print(f"Task {task_name} 開始執行...")
    time.sleep(random.randint(1, 10))  # 模擬 10 秒的工作
    print(f"Task {task_name} 執行完成！")

# 使用 with DAG 語法
with DAG(
    dag_id='example_parallel_dag',
    default_args=default_args,
    description='A simple example DAG with parallel tasks',
    schedule_interval='0 * * * *',  # 每小時執行
    start_date=datetime(2024, 1, 1),  # 從2024年1月1日開始生效
    catchup=False,  # 不執行歷史任務
    tags=['example'],
) as dag:

    # 起始任務
    start_task = PythonOperator(
        task_id='start',
        python_callable=hello_world,
    )

    # 結束任務
    end_task = BashOperator(
        task_id='end',
        bash_command='echo "所有平行任務執行完成！"',
    )

    # 平行執行的任務們
    task1 = PythonOperator(
        task_id='task1',
        python_callable=parallel_task,
        op_args=['task1'],
    )
    task2 = PythonOperator(
        task_id='task2',
        python_callable=parallel_task,
        op_args=['task2'],
    )
    task3 = PythonOperator(
        task_id='task3',
        python_callable=parallel_task,
        op_args=['task3'],
    )
    task4 = PythonOperator(
        task_id='task4',
        python_callable=parallel_task,
        op_args=['task4'],
    )
    task5 = PythonOperator(
        task_id='task5',
        python_callable=parallel_task,
        op_args=['task5'],
    )
    task6 = PythonOperator(
        task_id='task6',
        python_callable=parallel_task,
        op_args=['task6'],
    )
    task7 = PythonOperator(
        task_id='task7',
        python_callable=parallel_task,
        op_args=['task7'],
    )
    task8 = PythonOperator(
        task_id='task8',
        python_callable=parallel_task,
        op_args=['task8'],
    )
    task9 = PythonOperator(
        task_id='task9',
        python_callable=parallel_task,
        op_args=['task9'],
    )
    task10 = PythonOperator(
        task_id='task10',
        python_callable=parallel_task,
        op_args=['task10'],
    )

    # 設定依賴關係：start -> 10個平行任務 -> end
    start_task >> [task1, task2, task3, task4, task5, task6, task7, task8, task9, task10] >> end_task

    # 使用 for 迴圈建立 10 個平行任務
    # parallel_tasks = []
    # for i in range(10):
    #     task = PythonOperator(
    #         task_id=f'task{i+1}',
    #         python_callable=parallel_task,
    #         op_args=[f'task{i+1}'],
    #     )
    #     parallel_tasks.append(task)

    # # 設定依賴關係：start -> 10個平行任務 -> end
    # start_task >> parallel_tasks >> end_task
