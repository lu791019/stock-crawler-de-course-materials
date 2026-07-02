"""
Stock Crawler ETL DAG
爬取台股股價數據，寫入 MySQL，並建立分析 View
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator

from crawler.tasks_crawler_finmind import crawler_finmind
from crawler.mysql import create_view, create_table_from_view

STOCK_IDS = [
    "2330", "2317", "2454", "2308", "2382",
    "0050", "0056", "00713", "00878", "006208",
]

default_args = {
    "owner": "data-team",
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(hours=1),
}


def create_stock_price_daily_view():
    """建立台股每日股價 View（每支股票每天只取一筆）"""
    view_sql = """
    CREATE OR REPLACE VIEW vw_stock_price_daily AS
    SELECT
      t.stock_id,
      t.date AS trade_date,
      t.open,
      t.max,
      t.min,
      t.close,
      t.spread,
      t.Trading_Volume,
      t.Trading_turnover
    FROM (
      SELECT
        s.*,
        ROW_NUMBER() OVER (
          PARTITION BY s.stock_id, s.date
          ORDER BY s.Trading_Volume DESC
        ) AS rn
      FROM TaiwanStockPrice s
    ) AS t
    WHERE t.rn = 1;
    """
    create_view(view_name="vw_stock_price_daily", view_sql=view_sql)
    print("台股每日股價 View 建立完成")


def replace_stock_price_daily_table():
    """從 View 建立實體 Table"""
    create_table_from_view(
        view_name="vw_stock_price_daily",
        table_name="stock_price_daily",
    )
    print("台股每日股價 Table 建立完成")


with DAG(
    dag_id="stock_crawler_etl_dag",
    default_args=default_args,
    description="台股爬蟲 ETL DAG - 爬取股價 + MySQL View 建立",
    schedule_interval="0 18 * * 1-5",
    catchup=False,
    max_active_runs=1,
    tags=["stock", "crawler", "etl"],
) as dag:

    start_task = BashOperator(
        task_id="start_crawler",
        bash_command='echo "開始執行台股 ETL 任務..."',
    )

    stock_branch = DummyOperator(task_id="stock_branch")

    stock_tasks = []
    for stock_id in STOCK_IDS:
        task = PythonOperator(
            task_id=f"crawl_stock_{stock_id}",
            python_callable=crawler_finmind,
            op_args=[stock_id],
        )
        stock_tasks.append(task)

    etl_task = DummyOperator(task_id="etl_task")

    create_view_task = PythonOperator(
        task_id="create_stock_price_daily_view",
        python_callable=create_stock_price_daily_view,
    )

    create_table_task = PythonOperator(
        task_id="replace_stock_price_daily_table",
        python_callable=replace_stock_price_daily_table,
    )

    end_task = BashOperator(
        task_id="end_crawler",
        bash_command='echo "台股 ETL 任務執行完成"',
        trigger_rule="all_success",
    )

    start_task >> stock_branch >> stock_tasks >> etl_task
    etl_task >> create_view_task >> create_table_task >> end_task
