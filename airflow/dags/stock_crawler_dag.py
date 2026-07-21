"""
台股爬蟲 DAG（串法一：Airflow 直接呼叫爬蟲函式）。

對應課程：股票爬蟲章節的「用 Airflow 排程爬蟲（串法一）」主題。
教學目的：說明如何讓 Airflow 的 worker 直接呼叫爬蟲函式，把多支股票排成平行 task。

核心概念：
- python_callable 掛的是函式本身（只給函式名稱，不加括號、也不加 .delay），
  Airflow 的 worker 執行到這個 task 時會自己呼叫它；換句話說，爬蟲是在 Airflow 內完成的。
- op_args 是呼叫該函式時要帶入的位置參數清單，這裡把 stock_id 傳進 crawler_finmind。
- 用 for 迴圈依股票清單自動生出多個平行 task，數量多時不必手動一個個列。

觸發方式：
    airflow dags unpause stock_crawler_dag
    airflow dags trigger stock_crawler_dag
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator

# crawler_finmind 是實際的爬蟲函式，業務邏輯放在 crawler 套件裡，DAG 只負責排程。
from crawler.tasks_crawler_finmind import crawler_finmind

# 要爬取的股票代號清單，迴圈會依這份清單逐一生出爬取 task。
STOCK_IDS = [
    "2330", "2317", "2454", "2308", "2382",
    "0050", "0056", "00713", "00878", "006208",
]

default_args = {
    "owner": "data-team",                      # 負責團隊
    "start_date": datetime(2024, 1, 1),        # 排程起算日
    "retries": 1,                               # task 失敗時重試 1 次
    "retry_delay": timedelta(minutes=1),        # 每次重試間隔 1 分鐘
    "execution_timeout": timedelta(hours=1),    # 單一 task 執行超過 1 小時就視為逾時失敗，避免卡住
}

with DAG(
    dag_id="stock_crawler_dag",
    default_args=default_args,
    description="台股股價爬取 DAG - 使用 FinMind API 爬取股價並寫入 MySQL",
    schedule_interval="0 18 * * 1-5",  # cron：週一到週五每天 18:00 執行，對應台股收盤後的時間
    catchup=False,                      # 不補跑歷史排程區間
    max_active_runs=1,                  # 同一時間最多只允許一個 DAG run，避免上一輪還沒跑完下一輪又開始
    tags=["stock", "crawler", "finmind"],
) as dag:

    # 起始任務：印出開始訊息，當作整批爬取的起點。
    start_task = BashOperator(
        task_id="start_crawler",
        bash_command="echo 開始執行台股爬蟲任務...",
    )

    # 分組節點：DummyOperator 不做事，只當作 start 之後、各爬取 task 之前的集合點。
    stock_branch = DummyOperator(task_id="stock_branch")

    # 依股票清單用迴圈生出平行的爬取 task，全部掛在 stock_branch 之後。
    stock_tasks = []
    for stock_id in STOCK_IDS:
        task = PythonOperator(
            task_id=f"crawl_stock_{stock_id}",   # 用股票代號組出唯一 task_id
            python_callable=crawler_finmind,      # 掛函式本身，worker 執行時會呼叫它
            op_args=[stock_id],                   # 呼叫時帶入的參數，等同 crawler_finmind(stock_id)
        )
        stock_tasks.append(task)

    # 結束任務：等所有爬取 task 成功後才印出完成訊息。
    end_task = BashOperator(
        task_id="end_crawler",
        bash_command="echo 台股爬蟲任務執行完成！",
        trigger_rule="all_success",  # 只有當全部上游 task 都成功時才執行，任一失敗就不執行
    )

    # 依賴關係：起始 → 分組節點 → 平行爬取（list）→ 結束。
    start_task >> stock_branch >> stock_tasks >> end_task
