"""
DAG 觸發 DAG 的 Airflow 範例。

對應課程：Airflow 章節的「一個 DAG 觸發另一個 DAG（TriggerDagRunOperator）」主題。
教學目的：說明如何讓一支 DAG 在流程中觸發另一支 DAG，並等它跑完才繼續。

核心概念：
- 這一個檔案裡定義了兩支 DAG：一支是主要 DAG，一支是被觸發的資料處理 DAG。
- TriggerDagRunOperator 讓主要 DAG 在流程中間去觸發另一支 DAG。
- wait_for_completion=True 表示主要 DAG 會等被觸發的 DAG 跑完，才繼續執行後面的 task。
- 被觸發的那支 DAG 也必須先 unpause，否則觸發後不會實際執行。

觸發方式（兩支 DAG 都要先解除暫停，再觸發主要 DAG）：
    airflow dags unpause example_triggered_data_processing_dag
    airflow dags unpause example_trigger_main_dag
    airflow dags trigger example_trigger_main_dag
"""
from datetime import datetime
from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.dummy_operator import DummyOperator


# 兩支 DAG 共用的預設參數。
default_args = {
    'owner': 'data-team',              # 負責團隊
    'start_date': datetime(2024, 1, 1),  # 排程起算日
}


# ===== 主要 DAG =====

with DAG(
    dag_id='example_trigger_main_dag',
    default_args=default_args,
    description='主要 DAG - 示範 TriggerDagOperator 的使用',
    schedule_interval=None,  # 不自動排程，只能手動觸發
    catchup=False,           # 不補跑歷史排程區間
    tags=['example', 'trigger', 'main'],
) as dag:

    # 開始任務：流程起點，本身不做事。
    start_task = DummyOperator(
        task_id='start',
    )

    # 執行主要工作：這裡用 echo 模擬主要 DAG 自己要做的事。
    main_work_task = BashOperator(
        task_id='execute_main_work',
        bash_command='echo "🚀 執行主要工作..." && echo "✅ 主要工作完成！"',
    )

    # 觸發另一支 DAG：由 trigger_dag_id 指定要觸發的目標 DAG。
    trigger_data_processing = TriggerDagRunOperator(
        task_id='trigger_data_processing_dag',
        trigger_dag_id='example_triggered_data_processing_dag',  # 要觸發的目標 DAG 的 dag_id
        wait_for_completion=True,  # 等被觸發的 DAG 整支跑完，才繼續往下走
    )

    # 結束任務：流程終點，本身不做事。
    end_task = DummyOperator(
        task_id='end',
    )

    # ===== Task Dependencies =====
    # 依序執行：開始 → 主要工作 → 觸發並等待另一支 DAG → 結束。
    start_task >> main_work_task >> trigger_data_processing  >> end_task


# ===== 被觸發的 DAG - 資料處理 =====

with DAG(
    dag_id='example_triggered_data_processing_dag',
    default_args=default_args,
    description='被觸發的資料處理 DAG',
    schedule_interval=None,  # 設為 None，代表這支 DAG 只會被別的 DAG 觸發，不會自動排程執行
    catchup=False,           # 不補跑歷史排程區間
    tags=['example', 'trigger', 'data'],
) as triggered_dag1:

    # 資料處理流程的起點，本身不做事。
    start_processing = DummyOperator(
        task_id='start_processing',
    )

    # 處理資料：這裡用 sleep 模擬一段需要花時間的處理工作。
    process_data = BashOperator(
        task_id='process_data',
        bash_command='echo "📊 開始處理資料..." && sleep 30 && echo "✅ 資料處理完成"',
    )

    # 儲存結果：用 echo 模擬把處理結果存起來。
    save_results = BashOperator(
        task_id='save_results',
        bash_command='echo "💾 儲存處理結果..." && echo "✅ 結果已儲存"',
    )

    # 資料處理流程的終點，本身不做事。
    end_processing = DummyOperator(
        task_id='end_processing',
    )

    # 依序執行：開始 → 處理資料 → 儲存結果 → 結束。
    start_processing >> process_data >> save_results >> end_processing
