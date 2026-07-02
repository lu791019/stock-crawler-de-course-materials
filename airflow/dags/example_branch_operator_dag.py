"""
範例 Airflow DAG - BranchOperator 簡化示範
展示如何使用 BranchPythonOperator 實現條件分支
學習重點：條件分支邏輯和任務路由
"""
from datetime import datetime
from airflow import DAG
from airflow.operators.python_operator import BranchPythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator


# 預設參數
default_args = {
    'owner': 'data-team',
    'start_date': datetime(2024, 1, 1),
}


# ===== Python Functions =====

def decide_morning_or_afternoon(**context):
    """
    簡單的分支邏輯：根據時間決定路徑
    """
    print("🕐 檢查當前時間...")
    
    from datetime import datetime
    current_hour = datetime.now().hour
    
    print(f"當前時間：{current_hour}:00")
    
    if current_hour < 12:
        print("🌅 現在是上午，執行上午任務")
        return 'morning_task'
    else:
        print("🌆 現在是下午，執行下午任務")
        return 'afternoon_task'

# ===== DAG Definition =====

with DAG(
    dag_id='example_branch_operator_dag',
    default_args=default_args,
    description='分支操作示範 - BranchPythonOperator 的使用',
    schedule_interval=None,  # 手動觸發
    catchup=False,
    tags=['example', 'branch', 'simple'],
) as dag:

    # ===== Tasks Definition =====
    
    # 開始任務
    start_task = DummyOperator(
        task_id='start',
    )
    
    # 分支決策 1：根據時間分支
    time_branch = BranchPythonOperator(
        task_id='decide_time_path',
        python_callable=decide_morning_or_afternoon,
    )
    
    # 時間分支路徑
    morning_task = BashOperator(
        task_id='morning_task',
        bash_command='echo "🌅 執行上午任務..." && echo "☕ 準備咖啡，開始工作！"',
    )
    
    afternoon_task = BashOperator(
        task_id='afternoon_task',
        bash_command='echo "🌆 執行下午任務..." && echo "🍵 喝茶休息，繼續努力！"',
    )

    # ===== Task Dependencies =====
    
    # 時間分支流程
    start_task >> time_branch >> [morning_task, afternoon_task]
    
