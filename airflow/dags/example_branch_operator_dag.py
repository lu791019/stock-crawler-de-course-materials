"""
分支流程 Airflow DAG 範例。

對應課程：Airflow 章節的「條件分支（BranchPythonOperator）」主題。
教學目的：說明如何依條件決定工作流要走哪一條分支路徑。

核心概念：
- BranchPythonOperator 掛的函式必須回傳一個「task_id 字串」，
  Airflow 會依這個回傳值決定接下來要執行哪一個下游 task。
- 沒有被選中的那條分支會被標成 skipped（跳過），在分支語意下這是正常結果，不是失敗。
- 這裡用 datetime.now() 判斷時間，取到的是容器的時區時間；本課程的映像檔已設定為
  Asia/Taipei，所以判斷結果符合台灣當地時間。

觸發方式：
    airflow dags unpause example_branch_operator_dag
    airflow dags trigger example_branch_operator_dag
"""
from datetime import datetime
from airflow import DAG
from airflow.operators.python_operator import BranchPythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator


# 這支 DAG 的共用預設參數。
default_args = {
    'owner': 'data-team',              # 負責團隊
    'start_date': datetime(2024, 1, 1),  # 排程起算日
}


# ===== Python Functions =====

def decide_morning_or_afternoon(**context):
    """
    分支決策函式：依當前小時決定要走上午或下午路徑。

    這個函式的回傳值是一個 task_id 字串，Airflow 會依它挑出要執行的下游 task。
    `**context` 是 Airflow 在執行時注入的執行環境資訊，這裡沒有用到，但保留參數
    以符合 Airflow 呼叫 callable 時會帶入 context 的慣例。
    """
    print("🕐 檢查當前時間...")

    from datetime import datetime
    current_hour = datetime.now().hour  # 取容器時區（Asia/Taipei）的當前小時

    print(f"當前時間：{current_hour}:00")

    # 回傳的字串必須剛好等於某個下游 task 的 task_id，Airflow 才知道要走哪條分支。
    if current_hour < 12:
        print("🌅 現在是上午，執行上午任務")
        return 'morning_task'    # 回傳上午分支的 task_id
    else:
        print("🌆 現在是下午，執行下午任務")
        return 'afternoon_task'  # 回傳下午分支的 task_id

# ===== DAG Definition =====

with DAG(
    dag_id='example_branch_operator_dag',
    default_args=default_args,
    description='分支操作示範 - BranchPythonOperator 的使用',
    schedule_interval=None,  # 設為 None 表示不自動排程，只能手動觸發
    catchup=False,           # 不補跑歷史排程區間
    tags=['example', 'branch', 'simple'],
) as dag:

    # ===== Tasks Definition =====

    # 開始任務：用 DummyOperator 當作流程的起點，本身不做任何事。
    start_task = DummyOperator(
        task_id='start',
    )

    # 分支決策 task：執行 decide_morning_or_afternoon，依其回傳的 task_id 選擇下游分支。
    time_branch = BranchPythonOperator(
        task_id='decide_time_path',
        python_callable=decide_morning_or_afternoon,
    )

    # 上午分支：只有當決策函式回傳 'morning_task' 時才會執行，否則被標成 skipped。
    morning_task = BashOperator(
        task_id='morning_task',
        bash_command='echo "🌅 執行上午任務..." && echo "☕ 準備咖啡，開始工作！"',
    )

    # 下午分支：只有當決策函式回傳 'afternoon_task' 時才會執行，否則被標成 skipped。
    afternoon_task = BashOperator(
        task_id='afternoon_task',
        bash_command='echo "🌆 執行下午任務..." && echo "🍵 喝茶休息，繼續努力！"',
    )

    # ===== Task Dependencies =====

    # 依賴關係：start_task 之後進入分支決策，決策後接上兩條候選分支，
    # 實際只會執行其中被回傳選中的一條，另一條會被跳過。
    start_task >> time_branch >> [morning_task, afternoon_task]
