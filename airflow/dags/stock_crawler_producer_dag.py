"""
台股爬蟲 Producer DAG（串法二：Airflow 只發任務、由 Celery worker 爬）。

對應課程：股票爬蟲章節的「用 Airflow 發任務到佇列（串法二）」主題。
教學目的：說明如何讓 Airflow 只負責把任務發送到 RabbitMQ，實際爬取交給 Celery worker 完成；
並用 BranchPythonOperator 在發任務前做「交易日守門」——平日才發、週末整批跳過。

核心概念：
- 這裡的 task 只負責「發任務」，發完就結束，不會等爬蟲跑完，這與串法一「Airflow 直接爬」不同。
- 因此 Airflow 介面上 task 全綠，只代表任務發送成功；爬蟲真正的成敗要看 Flower 或 worker log。
- 發任務時用 apply_async(queue="twse") 指定佇列，而不是用 .delay()。原因見下方函式說明。
- 發任務前先過一個 BranchPythonOperator：判斷今天是不是交易日（教學版只看平日/週末），
  平日走 send_tasks 這條路、週末走 skip_no_trading——沒被選中的那條會被標成 skipped。
  這是分支的「守門」用法：條件不成立時讓整批下游優雅跳過，而不是失敗。
- 有分支就有 skipped 的可能，end 的 trigger_rule 要用 none_failed_min_one_success
 （沿用 all_success 的話，週末那次 run 的 end 會跟著被跳過，看不到收尾訊息）。

觸發方式：
    airflow dags unpause stock_crawler_producer_dag
    airflow dags trigger stock_crawler_producer_dag
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import BranchPythonOperator, PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator

# crawler_finmind 是 Celery task，這裡不是直接呼叫它，而是把它發送到佇列。
from crawler.tasks_crawler_finmind import crawler_finmind

# 要發送爬蟲任務的股票代號清單，清單內都是上市標的，所以統一發到 twse 佇列。
STOCK_IDS = [
    "2330", "2317", "2454", "2308", "2382",
    "0050", "0056", "00713", "00878", "006208",
]


def check_trading_day(**context):
    """分支決策函式：判斷今天是不是交易日，決定要發任務還是整批跳過。

    回傳的字串必須等於某個下游 task 的 task_id：
    平日回傳 'send_tasks'（發任務那條路）、週末回傳 'skip_no_trading'（跳過那條路）。
    沒被選中的那條分支會被標成 skipped——在分支語意下這是正常結果，不是失敗。

    教學版只用「平日/週末」判斷（weekday() 回傳 0~6，0 是週一、5 之後是週末）；
    真實系統還要對國定假日行事曆（例如春節），做法是把休市日清單存成表再查表。
    datetime.now() 取到容器時區的時間，課程映像檔已設定 Asia/Taipei。
    """
    weekday = datetime.now().weekday()

    if weekday < 5:
        print(f"今天 weekday={weekday}（平日），發送爬蟲任務")
        return "send_tasks"

    print(f"今天 weekday={weekday}（週末休市），整批跳過")
    return "skip_no_trading"


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
    description="台股爬蟲 Producer DAG - 交易日守門後透過 Celery 發送爬蟲任務",
    schedule_interval=None,  # 不自動排程，只能手動觸發
    catchup=False,           # 不補跑歷史排程區間
    max_active_runs=1,       # 同一時間最多一個 DAG run
    tags=["stock", "crawler", "producer", "branch"],
) as dag:

    # 起始任務：整批發送的起點。
    start_task = BashOperator(
        task_id="start_crawler",
        bash_command="echo 開始發送台股爬蟲任務...",
    )

    # 分支決策：平日走 send_tasks、週末走 skip_no_trading。
    trading_day_branch = BranchPythonOperator(
        task_id="check_trading_day",
        python_callable=check_trading_day,
    )

    # 發任務那條路的落點：DummyOperator 不做事，
    # 當作「分支選中發任務」的集合點，後面接整批平行的發任務 task。
    send_tasks = DummyOperator(task_id="send_tasks")

    # 跳過那條路的落點：週末被選中時只印一行訊息，整批發任務 task 都不會跑。
    skip_no_trading = BashOperator(
        task_id="skip_no_trading",
        bash_command="echo 今天休市，不發送爬蟲任務",
    )

    # 依股票清單生出平行的「發任務」task，每個 task 只負責把一支股票發到佇列。
    stock_tasks = []
    for stock_id in STOCK_IDS:
        task = PythonOperator(
            task_id=f"crawl_stock_{stock_id}",
            python_callable=trigger_stock_crawler,  # 掛的是發任務的函式，不是爬蟲本身
            op_args=[stock_id],                     # 呼叫時帶入的股票代號
        )
        stock_tasks.append(task)

    # 結束任務：發任務那條路全部成功、或走了跳過那條路，都會收尾。
    # trigger_rule 用 none_failed_min_one_success：沒有上游失敗、至少一個上游成功就執行
    # ——skipped 的那條路不會把 end 一起拖成 skipped。
    # 注意 end 變綠只代表「發送階段」結束，不代表爬蟲都已跑完。
    end_task = BashOperator(
        task_id="end_crawler",
        bash_command="echo 台股爬蟲任務發送完成！",
        trigger_rule="none_failed_min_one_success",
    )

    # 依賴關係：起始 → 交易日分支 → 發任務路（集合點 → 平行發任務）→ 結束，
    #                        └──── 跳過路 ────────────────────────┘
    start_task >> trading_day_branch >> send_tasks >> stock_tasks >> end_task
    trading_day_branch >> skip_no_trading >> end_task
