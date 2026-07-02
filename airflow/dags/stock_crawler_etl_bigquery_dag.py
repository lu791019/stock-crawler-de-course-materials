"""
Stock BigQuery ETL DAG
從 MySQL 同步台股股價資料到 BigQuery 並進行 ETL 處理
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator

from crawler.stock_sync_mysql_to_bigquery import sync_mysql_to_bigquery
from crawler.stock_bigquery_data_transform import (
    create_stock_price_daily_view_and_table,
    create_stock_trend_analysis_view_and_table,
    create_daily_summary_view_and_table,
)

default_args = {
    "owner": "data-team",
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(hours=1),
}

with DAG(
    dag_id="stock_bigquery_etl_dag",
    default_args=default_args,
    description="台股 BigQuery ETL DAG - 從 MySQL 同步資料到 BigQuery 並進行分析",
    schedule_interval="0 20 * * 1-5",
    catchup=False,
    max_active_runs=1,
    tags=["stock", "bigquery", "etl", "analytics"],
) as dag:

    start_task = BashOperator(
        task_id="start_bigquery_etl",
        bash_command='echo "開始執行台股 BigQuery ETL 任務..."',
    )

    sync_to_bigquery_task = PythonOperator(
        task_id="sync_mysql_to_bigquery",
        python_callable=sync_mysql_to_bigquery,
    )

    create_price_daily_task = PythonOperator(
        task_id="create_stock_price_daily_view_and_table",
        python_callable=create_stock_price_daily_view_and_table,
    )

    create_trend_task = PythonOperator(
        task_id="create_stock_trend_analysis_view_and_table",
        python_callable=create_stock_trend_analysis_view_and_table,
    )

    create_summary_task = PythonOperator(
        task_id="create_daily_summary_view_and_table",
        python_callable=create_daily_summary_view_and_table,
    )

    end_task = BashOperator(
        task_id="end_bigquery_etl",
        bash_command='echo "台股 BigQuery ETL 任務執行完成"',
        trigger_rule="all_success",
    )

    start_task >> sync_to_bigquery_task >> create_price_daily_task >> create_trend_task >> create_summary_task >> end_task
