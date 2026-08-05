"""
Step 5: 用 Airflow 取代手動執行 producer。

這一步只換掉一件事——誰來呼叫 producer。
    Step 4: 人在終端機下指令發任務。
    Step 5: Airflow 到排定的時間自動發任務。

DAG 裡的每個 task 只做一件事: 呼叫 crawl.delay() 把任務送進 RabbitMQ, 送完就結束。
抓資料與寫資料庫仍然由 Celery worker 執行, DAG 內不搬運任何資料。
因此 Airflow 介面上 task 變綠只代表「任務已送出」, 爬蟲的成敗要看 worker log 或 Flower。

這樣分工的理由:
    Airflow 負責排程與相依關係, 它的 scheduler 不適合承擔長時間的爬取工作。
    爬取工作放在 worker, 要加快只需要增加 worker 數量, 不必更動 Airflow。

部署方式:
    把這個檔案複製到 airflow/dags/ 目錄, Airflow 會自動載入。
    課程正式版的對照檔案是 airflow/dags/stock_crawler_producer_dag.py,
    那一支多了交易日分支判斷與指定佇列, 本示範保持最小結構。
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python_operator import PythonOperator

# 匯入 Step 4 註冊好的 Celery 任務。
# 這裡匯入的是任務物件, 呼叫 .delay() 只是發送訊息, 函式本體在 worker 執行。
from example.evolution.step4_celery.task import crawl
from example.evolution.step4_celery.config import END_DATE, START_DATE, STOCK_IDS

default_args = {
    "owner": "data-team",                   # 負責團隊
    "start_date": datetime(2024, 1, 1),     # 排程起算日
    "retries": 1,                            # task 失敗時重試 1 次
    "retry_delay": timedelta(minutes=1),     # 重試間隔
}


def send_one_task(stock_id: str):
    """把單支股票的爬蟲任務發送到 RabbitMQ。

    這個函式是 DAG 與 Celery 之間的唯一接點, 內容與 Step 4 producer 的迴圈主體相同。
    """
    crawl.delay(stock_id=stock_id, start_date=START_DATE, end_date=END_DATE)


with DAG(
    dag_id="evolution_producer_dag",
    default_args=default_args,
    description="六步拆解示範: Airflow 只發任務, 由 Celery worker 執行爬蟲",
    schedule_interval="0 18 * * 1-5",  # 週一到週五 18:00 發送, 語法為「分 時 日 月 星期」
    catchup=False,                      # 不補跑歷史區間
    max_active_runs=1,                  # 同一時間最多一個 DAG run
    tags=["evolution", "producer"],
) as dag:

    # 依股票清單產生平行的發任務 task, 每個 task 只負責送出一顆任務。
    for stock_id in STOCK_IDS:
        PythonOperator(
            task_id=f"send_{stock_id}",
            python_callable=send_one_task,  # 掛的是發任務的函式, 不是爬蟲本身
            op_args=[stock_id],
        )
