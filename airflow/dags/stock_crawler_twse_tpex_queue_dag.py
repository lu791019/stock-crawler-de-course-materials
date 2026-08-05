"""
台股上市/上櫃分組爬蟲 DAG（串法二版本：分支選組 + 發任務到對應佇列）。

對應課程：股票爬蟲章節的「分組爬取」主題，串法二寫法。
教學目的：與 stock_crawler_twse_tpex_dag 對照——DAG 的形狀完全相同，
差別只在每個 task 是「自己執行爬蟲」還是「把任務發到佇列」。

跟 stock_crawler_twse_tpex_dag 的差異只有一處：
- 那一支用 python_callable=crawler_finmind 直接呼叫爬蟲函式，
  爬蟲在 airflow-scheduler 容器裡執行，不經過 RabbitMQ。
- 這一支用 crawler_finmind.apply_async(queue=市場別) 把任務丟進佇列，
  由 crawler_twse / crawler_tpex 兩個 worker 取走執行。

兩個因此而來的行為差異，觸發前要先知道：
1. task 綠燈的意義變了。這裡的綠燈只代表「任務發出去了」，
   爬蟲的成敗要看 Flower 與 worker 的 log，不在 DAG 畫面上。
2. 分組直接對應佇列。twse 組的任務進 twse 佇列、tpex 組進 tpex 佇列，
   兩個 worker 會同時有事做——這是第 3 章多佇列分流在 Airflow 上的樣子。

多機架構下的差別（第 16 章之後會遇到）：
- 直接執行的版本要由 airflow-scheduler 自己連資料庫，
  而 compose 檔給 Airflow 容器的 MYSQL_HOST 是容器名 mysql。
  第 16 章把資料庫換成 Cloud SQL、VM1 不再啟動 mysql 容器之後，那支 DAG 就連不到資料庫。
- 這一支不碰資料庫，只把任務送進 RabbitMQ；真正寫入的是 VM2 上的 worker，
  它的 .env 指向 Cloud SQL。所以拆成多台機器之後，這個寫法仍然可用。

觸發方式：
    airflow dags unpause stock_crawler_twse_tpex_queue_dag
    airflow dags trigger stock_crawler_twse_tpex_queue_dag                              # 兩組都發
    airflow dags trigger stock_crawler_twse_tpex_queue_dag --conf '{"market": "twse"}'  # 只發上市
    airflow dags trigger stock_crawler_twse_tpex_queue_dag --conf '{"market": "tpex"}'  # 只發上櫃
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import BranchPythonOperator, PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator

# 匯入的是同一個 Celery task。差別在呼叫方式：
# 直接呼叫 crawler_finmind(stock_id) 是當場執行，
# 呼叫 crawler_finmind.apply_async(...) 是把任務送進佇列。
from crawler.tasks_crawler_finmind import crawler_finmind

# 分組定義與 stock_crawler_twse_tpex_dag 相同。
# 這裡的 key 有雙重身分：既是分組名稱，也是 Celery 佇列名稱。
STOCK_GROUPS = {
    "twse": ["2330", "2317", "2454"],  # 上市（TWSE）→ 發到 twse 佇列
    "tpex": ["6488", "3105", "8069"],  # 上櫃（TPEX）→ 發到 tpex 佇列
}


def send_to_queue(stock_id, market):
    """把單一支股票的爬取任務發到該市場對應的佇列。

    用 apply_async 而不是 .delay()，理由與 stock_crawler_producer_dag 相同：
    .delay() 只會把任務送進預設佇列 celery，
    而 compose 檔裡的兩個 worker 分別只監聽 twse 與 tpex，
    送進預設佇列的任務沒有人取走，會一直留在 RabbitMQ 裡。
    apply_async 的 queue 參數才能指定要進哪一個佇列。

    這裡的 market 直接當佇列名稱用，所以分組與佇列是一對一的。

    函式只負責發送，不等待結果。發送成功就返回，
    task 在 Airflow 上顯示綠燈——這個綠燈不代表爬蟲已經完成。
    """
    result = crawler_finmind.apply_async(kwargs={"stock_id": stock_id}, queue=market)
    print(f"已發送 {stock_id} 到 {market} 佇列，task_id={result.id}")


def choose_market(**context):
    """分支決策函式：依觸發時的 conf 參數決定要發哪個市場分組。

    邏輯與 stock_crawler_twse_tpex_dag 完全相同，這一段沒有任何改動：
    回傳一個 task_id 就只走那條分支；回傳 list 則列出的分支都會執行。
    沒被回傳的分支會被標成 skipped，它的下游跟著連鎖跳過。
    """
    market = (context["dag_run"].conf or {}).get("market", "all")

    if market in STOCK_GROUPS:
        print(f"conf 指定 market={market}，只發 {market} 這一組")
        return f"{market}_branch"          # 回傳單一 task_id：只走一條分支

    print("未指定 market（或值不在分組內），兩組都發")
    return [f"{m}_branch" for m in STOCK_GROUPS]  # 回傳 list：兩條分支都走


default_args = {
    "owner": "data-team",                      # 負責團隊
    "start_date": datetime(2024, 1, 1),        # 排程起算日
    "retries": 1,                               # task 失敗時重試 1 次
    "retry_delay": timedelta(minutes=1),        # 每次重試間隔 1 分鐘
    "execution_timeout": timedelta(hours=1),    # 單一 task 執行超過 1 小時視為逾時失敗
}

with DAG(
    dag_id="stock_crawler_twse_tpex_queue_dag",
    default_args=default_args,
    description="台股上市/上櫃分組爬蟲 DAG - 分支選組後發任務到對應佇列（串法二）",
    schedule_interval=None,  # 教學用手動觸發；正式排程可改成 cron
    catchup=False,           # 不補跑歷史排程區間
    max_active_runs=1,       # 同一時間最多一個 DAG run
    tags=["stock", "crawler", "finmind", "branch", "queue"],
) as dag:

    # 起始任務：整批發送的共同起點。
    start_task = BashOperator(
        task_id="start_producer",
        bash_command="echo 開始發送上市/上櫃分組爬蟲任務...",
    )

    # 分支決策：依 conf 的 market 參數回傳要走的分組節點 task_id。
    market_branch = BranchPythonOperator(
        task_id="choose_market",
        python_callable=choose_market,
    )

    # 結束任務：被選中的分組全部發完後的共同匯合點。
    # trigger_rule 用 none_failed_min_one_success，理由與分組爬蟲版相同：
    # skipped 的那組不會擋住 end。
    end_task = BashOperator(
        task_id="end_producer",
        bash_command="echo 任務已全部發送，執行狀況請看 Flower 與 worker log",
        trigger_rule="none_failed_min_one_success",
    )

    # 外層迴圈：逐一處理每個市場（twse、tpex）。
    for market, stock_ids in STOCK_GROUPS.items():
        # 每個市場一個分組節點：分支決策的落點，task_id 要跟決策函式回傳的對上。
        branch = DummyOperator(task_id=f"{market}_branch")

        # 內層迴圈：為該市場組內的每支股票生一個發送 task。
        send_tasks = []
        for stock_id in stock_ids:
            task = PythonOperator(
                task_id=f"send_{market}_{stock_id}",   # 命名用 send 而不是 crawl，反映它做的事
                python_callable=send_to_queue,
                op_args=[stock_id, market],            # 第二個參數決定要進哪個佇列
            )
            send_tasks.append(task)

        # 依賴關係與分組爬蟲版完全相同：
        # 起始 → 分支決策 → 該組分組節點 → 組內平行發送（list）→ 匯合 end。
        start_task >> market_branch >> branch >> send_tasks >> end_task
