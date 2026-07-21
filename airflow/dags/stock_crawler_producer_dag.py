"""
台股爬蟲 Producer DAG（串法二：Airflow 只發任務、由 Celery worker 爬）。

對應課程：股票爬蟲章節的「用 Airflow 發任務到佇列（串法二）」主題。
教學目的：說明如何讓 Airflow 只負責把任務發送到 RabbitMQ，實際爬取交給 Celery worker 完成。

核心概念：
- 這裡的 task 只負責「發任務」，發完就結束，不會等爬蟲跑完，這與串法一「Airflow 直接爬」不同。
- 因此 Airflow 介面上 task 全綠，只代表任務發送成功；爬蟲真正的成敗要看 Flower 或 worker log。
- 發任務時用 apply_async(queue="twse") 指定佇列，而不是用 .delay()。原因見下方函式說明。

觸發方式：
    airflow dags unpause stock_crawler_producer_dag
    airflow dags trigger stock_crawler_producer_dag
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator

# crawler_finmind 是 Celery task，這裡不是直接呼叫它，而是把它發送到佇列。
from crawler.tasks_crawler_finmind import crawler_finmind

# 要發送爬蟲任務的股票代號清單，清單內都是上市標的，所以統一發到 twse 佇列。
STOCK_IDS = [
    "2330", "2317", "2454", "2308", "2382",
    "0050", "0056", "00713", "00878", "006208",
]


def trigger_stock_crawler(stock_id):
    """把單支股票的爬蟲任務發送到 RabbitMQ 的 twse 佇列。

    這裡用 apply_async(queue="twse") 而不是 .delay()，原因是：
    第 3 章的 worker 池是分流版，只監聽 twse / tpex 這兩個佇列；
    .delay() 會把任務發到預設佇列（celery），那個佇列沒有 worker 消費，
    任務就會一直卡在 RabbitMQ 裡不會被執行。
    所以必須用 apply_async 明確指定 queue，任務才會被對應的 worker 取走。
    """
    crawler_finmind.apply_async(kwargs={"stock_id": stock_id}, queue="twse")


default_args = {
    "owner": "data-team",                      # 負責團隊
    "start_date": datetime(2024, 1, 1),        # 排程起算日
    "retries": 1,                               # task 失敗時重試 1 次
    "retry_delay": timedelta(minutes=1),        # 每次重試間隔 1 分鐘
    "execution_timeout": timedelta(hours=1),    # 單一 task 執行超過 1 小時視為逾時失敗
}

with DAG(
    dag_id="stock_crawler_producer_dag",
    default_args=default_args,
    description="台股爬蟲 Producer DAG - 透過 Celery 發送爬蟲任務",
    schedule_interval=None,  # 不自動排程，只能手動觸發
    catchup=False,           # 不補跑歷史排程區間
    max_active_runs=1,       # 同一時間最多一個 DAG run
    tags=["stock", "crawler", "producer"],
) as dag:

    # 起始任務：整批發送的起點。
    start_task = BashOperator(
        task_id="start_crawler",
        bash_command="echo 開始發送台股爬蟲任務...",
    )

    # 分組節點：DummyOperator 不做事，當作 start 之後的集合點。
    stock_branch = DummyOperator(task_id="stock_branch")

    # 依股票清單生出平行的「發任務」task，每個 task 只負責把一支股票發到佇列。
    stock_tasks = []
    for stock_id in STOCK_IDS:
        task = PythonOperator(
            task_id=f"crawl_stock_{stock_id}",
            python_callable=trigger_stock_crawler,  # 掛的是發任務的函式，不是爬蟲本身
            op_args=[stock_id],                     # 呼叫時帶入的股票代號
        )
        stock_tasks.append(task)

    # 結束任務：等所有「發任務」都成功後才印出訊息。
    # 注意這只代表任務都發送成功，不代表爬蟲都已跑完。
    end_task = BashOperator(
        task_id="end_crawler",
        bash_command="echo 台股爬蟲任務發送完成！",
        trigger_rule="all_success",  # 只有當全部上游 task 都成功時才執行
    )

    # 依賴關係：起始 → 分組節點 → 平行發任務（list）→ 結束。
    start_task >> stock_branch >> stock_tasks >> end_task
