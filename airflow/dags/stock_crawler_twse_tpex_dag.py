"""
台股上市/上櫃分組爬蟲 DAG（串法一延伸：字典分組 + 雙層迴圈）。

對應課程：股票爬蟲章節的「分組爬取（串法一延伸）」主題。
教學目的：說明如何用字典把股票分組，再用雙層迴圈為每一組自動生出分組節點與爬取 task。

核心概念：
- 這支 DAG 的形狀是：start → 兩個分組節點 → 各組平行爬取 → 匯合 end。
- 用字典（dict）把股票分成 twse / tpex 兩組，外層迴圈跑「每個市場」，內層迴圈跑「組內每支股票」。
- 外層每個市場生一個 DummyOperator 當分組節點，它不做事，只負責把該組的圖形整理清楚。
- 之後若要新增第三組，只要在 STOCK_GROUPS 字典多加一個 key 即可，迴圈會自動處理，DAG 結構不用改。

觸發方式：
    airflow dags unpause stock_crawler_twse_tpex_dag
    airflow dags trigger stock_crawler_twse_tpex_dag
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator

# crawler_finmind 是實際的爬蟲函式，業務邏輯放在 crawler 套件裡。
from crawler.tasks_crawler_finmind import crawler_finmind

# 用字典把股票分成兩組：key 是市場別，value 是該市場的股票代號清單。
# 這裡的分組概念與第 3 章多佇列分流（twse / tpex queue）相同，只是這裡分的是 task 圖形。
STOCK_GROUPS = {
    "twse": ["2330", "2317", "2454"],  # 上市（TWSE）
    "tpex": ["6488", "3105", "8069"],  # 上櫃（TPEX）
}

default_args = {
    "owner": "data-team",                      # 負責團隊
    "start_date": datetime(2024, 1, 1),        # 排程起算日
    "retries": 1,                               # task 失敗時重試 1 次
    "retry_delay": timedelta(minutes=1),        # 每次重試間隔 1 分鐘
    "execution_timeout": timedelta(hours=1),    # 單一 task 執行超過 1 小時視為逾時失敗
}

with DAG(
    dag_id="stock_crawler_twse_tpex_dag",
    default_args=default_args,
    description="台股上市/上櫃分組爬蟲 DAG - 兩組平行爬取後匯合",
    schedule_interval=None,  # 教學用手動觸發；正式排程可改成 cron
    catchup=False,           # 不補跑歷史排程區間
    max_active_runs=1,       # 同一時間最多一個 DAG run
    tags=["stock", "crawler", "finmind", "branch"],
) as dag:

    # 起始任務：整批爬取的共同起點。
    start_task = BashOperator(
        task_id="start_crawler",
        bash_command="echo 開始執行上市/上櫃分組爬蟲任務...",
    )

    # 結束任務：兩組全部爬完後的共同匯合點。
    end_task = BashOperator(
        task_id="end_crawler",
        bash_command="echo 上市/上櫃分組爬蟲任務全部完成！",
        trigger_rule="all_success",  # 只有當全部上游 task 都成功時才執行
    )

    # 外層迴圈：逐一處理每個市場（twse、tpex）。
    for market, stock_ids in STOCK_GROUPS.items():
        # 每個市場生一個分組節點（DummyOperator 不做事，純粹整理圖形）。
        branch = DummyOperator(task_id=f"{market}_branch")

        # 內層迴圈：為該市場組內的每支股票生一個爬取 task。
        crawl_tasks = []
        for stock_id in stock_ids:
            task = PythonOperator(
                task_id=f"crawl_{market}_{stock_id}",  # 用市場別加股票代號組出唯一 task_id
                python_callable=crawler_finmind,
                op_args=[stock_id],                    # 呼叫時帶入的參數
            )
            crawl_tasks.append(task)

        # 依賴關係：起始 → 該組分組節點 → 組內平行爬取（list）→ 匯合 end。
        # 每個市場都連到同一個 end_task，所以兩組會在 end 匯合。
        start_task >> branch >> crawl_tasks >> end_task
