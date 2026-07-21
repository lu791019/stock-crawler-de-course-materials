"""
台股爬蟲 ETL DAG（爬取 + 建立分析 View 與實體 Table）。

對應課程：股票爬蟲章節的「爬取後接 ETL（建立 View 與 Table）」主題。
教學目的：說明如何把「爬取」與「後續 ETL」串成一條流程，並用匯合點確保爬取全部成功才進 ETL。

核心概念：
- 流程分兩段：前段是 10 支股票的平行爬取，後段是 ETL（建立 View、再從 View 建實體 Table）。
- etl_task 是 DummyOperator 匯合點，只有當 10 支爬取全部成功後，流程才會進入 ETL 段。
- create_view 與 replace_table 兩個 PythonOperator 掛的函式，最終呼叫的是 crawler/mysql.py 裡的
  函式；DAG 檔本身不放 SQL 與業務邏輯。要改 VIEW 定義時改 mysql.py，DAG 不用動。

觸發方式：
    airflow dags unpause stock_crawler_etl_dag
    airflow dags trigger stock_crawler_etl_dag
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator

# crawler_finmind 是爬蟲函式；create_view / create_table_from_view 是 MySQL 操作函式，
# 兩者的實作都放在 crawler 套件裡，DAG 只負責把它們串成流程。
from crawler.tasks_crawler_finmind import crawler_finmind
from crawler.mysql import create_view, create_table_from_view

# 要爬取的股票代號清單。
STOCK_IDS = [
    "2330", "2317", "2454", "2308", "2382",
    "0050", "0056", "00713", "00878", "006208",
]

default_args = {
    "owner": "data-team",                      # 負責團隊
    "start_date": datetime(2024, 1, 1),        # 排程起算日
    "retries": 1,                               # task 失敗時重試 1 次
    "retry_delay": timedelta(minutes=1),        # 每次重試間隔 1 分鐘
    "execution_timeout": timedelta(hours=1),    # 單一 task 執行超過 1 小時視為逾時失敗
}


def create_stock_price_daily_view():
    """建立台股每日股價 View（每支股票每天只保留一筆）。

    SQL 寫在這裡是為了教學上把 View 定義看清楚；實際的建立動作交給 crawler/mysql.py
    的 create_view 執行。View 用視窗函式 ROW_NUMBER 依成交量取每支股票每天的第一筆，
    達成每檔每日去重的效果。
    """
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
    """把 View 的查詢結果落地成一張實體 Table。

    View 每次查詢都即時運算，實體化成 Table 後，下游查詢可以直接讀取結果。
    實際動作交給 crawler/mysql.py 的 create_table_from_view 執行。
    """
    create_table_from_view(
        view_name="vw_stock_price_daily",
        table_name="stock_price_daily",
    )
    print("台股每日股價 Table 建立完成")


with DAG(
    dag_id="stock_crawler_etl_dag",
    default_args=default_args,
    description="台股爬蟲 ETL DAG - 爬取股價 + MySQL View 建立",
    schedule_interval="0 18 * * 1-5",  # cron：週一到週五每天 18:00 執行，對應台股收盤後
    catchup=False,                      # 不補跑歷史排程區間
    max_active_runs=1,                  # 同一時間最多一個 DAG run
    tags=["stock", "crawler", "etl"],
) as dag:

    # 起始任務：整條流程的起點。
    start_task = BashOperator(
        task_id="start_crawler",
        bash_command='echo "開始執行台股 ETL 任務..."',
    )

    # 分組節點：start 之後、各爬取 task 之前的集合點。
    stock_branch = DummyOperator(task_id="stock_branch")

    # 依股票清單生出平行的爬取 task。
    stock_tasks = []
    for stock_id in STOCK_IDS:
        task = PythonOperator(
            task_id=f"crawl_stock_{stock_id}",
            python_callable=crawler_finmind,
            op_args=[stock_id],
        )
        stock_tasks.append(task)

    # ETL 匯合點：DummyOperator，等 10 支爬取全部成功後，流程才進入 ETL 段。
    etl_task = DummyOperator(task_id="etl_task")

    # 建立 View：呼叫上面的 create_stock_price_daily_view。
    create_view_task = PythonOperator(
        task_id="create_stock_price_daily_view",
        python_callable=create_stock_price_daily_view,
    )

    # 從 View 建實體 Table：呼叫上面的 replace_stock_price_daily_table。
    create_table_task = PythonOperator(
        task_id="replace_stock_price_daily_table",
        python_callable=replace_stock_price_daily_table,
    )

    # 結束任務：整條流程成功後印出訊息。
    end_task = BashOperator(
        task_id="end_crawler",
        bash_command='echo "台股 ETL 任務執行完成"',
        trigger_rule="all_success",  # 只有當全部上游 task 都成功時才執行
    )

    # 依賴關係分兩段：
    # 前段：起始 → 分組節點 → 平行爬取（list）→ ETL 匯合點。
    start_task >> stock_branch >> stock_tasks >> etl_task
    # 後段：ETL 匯合點 → 建立 View → 建實體 Table → 結束。
    etl_task >> create_view_task >> create_table_task >> end_task
