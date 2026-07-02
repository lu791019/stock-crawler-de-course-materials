"""
範例 Airflow DAG - TriggerDagOperator 簡化示範
展示如何使用 TriggerDagOperator 觸發其他 DAG
學習重點：DAG 之間的觸發關係
"""
from datetime import datetime
from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.dummy_operator import DummyOperator


# 預設參數
default_args = {
    'owner': 'data-team',
    'start_date': datetime(2024, 1, 1),
}


# ===== 主要 DAG =====

with DAG(
    dag_id='example_trigger_main_dag',
    default_args=default_args,
    description='主要 DAG - 示範 TriggerDagOperator 的使用',
    schedule_interval=None,  # 手動觸發
    catchup=False,
    tags=['example', 'trigger', 'main'],
) as dag:

    # 開始任務
    start_task = DummyOperator(
        task_id='start',
    )
    
    # 執行主要工作
    main_work_task = BashOperator(
        task_id='execute_main_work',
        bash_command='echo "🚀 執行主要工作..." && echo "✅ 主要工作完成！"',
    )
    
    # 觸發資料處理 DAG
    trigger_data_processing = TriggerDagRunOperator(
        task_id='trigger_data_processing_dag',
        trigger_dag_id='example_triggered_data_processing_dag',  # 要觸發的 DAG ID
        wait_for_completion=True,
    )
    
    # 結束任務
    end_task = DummyOperator(
        task_id='end',
    )

    # ===== Task Dependencies =====
    start_task >> main_work_task >> trigger_data_processing  >> end_task


# ===== 被觸發的 DAG - 資料處理 =====

with DAG(
    dag_id='example_triggered_data_processing_dag',
    default_args=default_args,
    description='被觸發的資料處理 DAG',
    schedule_interval=None,  # 只能被觸發，不自動執行
    catchup=False,
    tags=['example', 'trigger', 'data'],
) as triggered_dag1:

    start_processing = DummyOperator(
        task_id='start_processing',
    )
    
    process_data = BashOperator(
        task_id='process_data',
        bash_command='echo "📊 開始處理資料..." && sleep 30 && echo "✅ 資料處理完成"',
    )
    
    save_results = BashOperator(
        task_id='save_results',
        bash_command='echo "💾 儲存處理結果..." && echo "✅ 結果已儲存"',
    )
    
    end_processing = DummyOperator(
        task_id='end_processing',
    )
    
    start_processing >> process_data >> save_results >> end_processing

