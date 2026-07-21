"""
平行任務 Airflow DAG 範例。

對應課程：Airflow 章節的「平行任務編排」主題。
教學目的：說明在依賴關係中用中括號 `[]` 把多個 task 包起來，就是要求它們平行執行。

核心概念：
- 把多個 task 放進一個 list（例如 [task1, task2, ...]），Airflow 會讓它們同時排入執行，
  彼此沒有先後順序，這就是「平行」。
- 這與第 1 章「一批任務被 worker 併發消化」是同一個概念，差別只在於這裡是把併發搬到
  Airflow 的編排層來表達，實際同時能跑幾個仍受 worker 數量與並行度設定影響。

觸發方式：
    airflow dags unpause example_parallel_dag
    airflow dags trigger example_parallel_dag
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator


# 這支 DAG 裡所有 task 共用的預設參數。
default_args = {
    'owner': 'data-team',              # 負責團隊
    'retries': 1,                       # task 失敗時重試 1 次
    'retry_delay': timedelta(minutes=1),  # 每次重試間隔 1 分鐘
}

def hello_world():
    """簡單的 Python function，由起始任務呼叫。"""
    print("Hello from Airflow!")

def parallel_task(task_name):
    """模擬一個需要花時間的平行任務，用隨機睡眠代表工作耗時。"""
    import time
    import random
    print(f"Task {task_name} 開始執行...")
    time.sleep(random.randint(1, 10))  # 用隨機秒數的睡眠模擬工作負載，讓平行效果較明顯
    print(f"Task {task_name} 執行完成！")

# 用 with DAG(...) as dag 建立 DAG，區塊內的 task 會自動歸屬到這支 DAG。
with DAG(
    dag_id='example_parallel_dag',
    default_args=default_args,
    description='A simple example DAG with parallel tasks',
    schedule_interval='0 * * * *',      # cron 排程：每個整點（每小時）執行一次
    start_date=datetime(2024, 1, 1),    # 排程起算日
    catchup=False,  # 不補跑 start_date 到現在漏掉的歷史排程區間
    tags=['example'],
) as dag:

    # 起始任務：所有平行任務的共同上游。
    start_task = PythonOperator(
        task_id='start',
        python_callable=hello_world,
    )

    # 結束任務：所有平行任務的共同下游，等它們全部完成才執行。
    end_task = BashOperator(
        task_id='end',
        bash_command='echo "所有平行任務執行完成！"',
    )

    # 以下建立 10 個結構相同的平行任務，差別只在傳入的 task 名稱。
    # op_args 是呼叫 python_callable 時要帶入的位置參數清單，
    # 例如 op_args=['task1'] 等同於呼叫 parallel_task('task1')。
    task1 = PythonOperator(
        task_id='task1',
        python_callable=parallel_task,
        op_args=['task1'],              # 傳給 parallel_task 的參數
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

    # 設定依賴關係：start_task 之後接一個包含 10 個 task 的 list，
    # 這個 list 裡的 task 會平行執行，全部完成後才進入 end_task。
    start_task >> [task1, task2, task3, task4, task5, task6, task7, task8, task9, task10] >> end_task

    # 下面被註解掉的寫法效果相同，改用 for 迴圈自動產生 10 個平行任務，
    # 當任務數量多時可避免手動一個個列出，是後面章節「迴圈生 task」的預習。
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
