"""
Stock Crawler TWSE/TPEX DAG
上市（TWSE）/ 上櫃（TPEX）雙分組爬蟲 DAG：
start → 兩個分組節點 → 各組平行爬取 → 匯合 end
展示「清單分組 + 迴圈生 task + 匯合」的常見 DAG 形狀
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator

from crawler.tasks_crawler_finmind import crawler_finmind

# 上市（TWSE）與上櫃（TPEX）分組清單
# 分組概念與第 3 章多佇列分流（twse / tpex queue）相同
STOCK_GROUPS = {
    "twse": ["2330", "2317", "2454"],  # 上市：台積電、鴻海、聯發科
    "tpex": ["6488", "3105", "8069"],  # 上櫃：環球晶、穩懋、元太
}

default_args = {
    "owner": "data-team",
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(hours=1),
}

with DAG(
    dag_id="stock_crawler_twse_tpex_dag",
    default_args=default_args,
    description="台股上市/上櫃分組爬蟲 DAG - 兩組平行爬取後匯合",
    schedule_interval=None,  # 教學用手動觸發；正式排程可改 cron
    catchup=False,
    max_active_runs=1,
    tags=["stock", "crawler", "finmind", "branch"],
) as dag:

    start_task = BashOperator(
        task_id="start_crawler",
        bash_command="echo 開始執行上市/上櫃分組爬蟲任務...",
    )

    end_task = BashOperator(
        task_id="end_crawler",
        bash_command="echo 上市/上櫃分組爬蟲任務全部完成！",
        trigger_rule="all_success",
    )

    # 每個市場一個分組節點（DummyOperator 純粹整理圖形，不做事）
    # 組內用 for 迴圈生出平行的爬蟲 task，最後一起匯合到 end
    for market, stock_ids in STOCK_GROUPS.items():
        branch = DummyOperator(task_id=f"{market}_branch")

        crawl_tasks = []
        for stock_id in stock_ids:
            task = PythonOperator(
                task_id=f"crawl_{market}_{stock_id}",
                python_callable=crawler_finmind,
                op_args=[stock_id],
            )
            crawl_tasks.append(task)

        start_task >> branch >> crawl_tasks >> end_task
