"""
台股上市/上櫃分組爬蟲 DAG（串法一延伸：BranchPythonOperator 參數分支 + 分組扇出）。

對應課程：股票爬蟲章節的「分組爬取（串法一延伸）」主題。
教學目的：說明如何用 BranchPythonOperator 依觸發參數決定要爬哪個市場分組，
再用字典 + 雙層迴圈為每一組自動生出組內的爬取 task。

核心概念：
- 這支 DAG 的形狀是：start → 分支決策 → 兩個分組節點 → 各組平行爬取 → 匯合 end。
- 分支決策是 BranchPythonOperator：函式回傳 task_id 決定走哪條路。
  回傳一個字串走一條；回傳 list 可以同時走多條——這支 DAG 預設回傳兩個分組節點，
  也就是「不給參數時兩組都爬」，行為與沒有分支時相同。
- 觸發時用 conf 參數選市場：--conf '{"market": "twse"}' 只爬上市，
  沒被選中的那組會被標成 skipped（跳過），組內的爬取 task 跟著連鎖跳過。
- 有分支就有 skipped 的可能，end 的 trigger_rule 不能再用 all_success
 （上游有 skipped 時 all_success 的 end 也會被跳過），
  要改用 none_failed_min_one_success：沒人失敗、且至少一條路真的跑完，end 才執行。
- 之後若要新增第三組，只要在 STOCK_GROUPS 字典多加一個 key，
  分支函式與迴圈會自動處理，DAG 結構不用改。

觸發方式：
    airflow dags unpause stock_crawler_twse_tpex_dag
    airflow dags trigger stock_crawler_twse_tpex_dag                              # 兩組都爬
    airflow dags trigger stock_crawler_twse_tpex_dag --conf '{"market": "twse"}'  # 只爬上市
    airflow dags trigger stock_crawler_twse_tpex_dag --conf '{"market": "tpex"}'  # 只爬上櫃
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import BranchPythonOperator, PythonOperator
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


def choose_market(**context):
    """分支決策函式：依觸發時的 conf 參數決定要爬哪個市場分組。

    BranchPythonOperator 掛的函式必須回傳「task_id」：
    回傳一個字串就只走那條分支；回傳 list 則列出的分支都會執行。
    沒被回傳的分支會被標成 skipped，它的下游（該組爬取 task）跟著連鎖跳過。

    conf 是觸發 DAG 時帶的參數（dict）：
    UI 的 Trigger DAG w/ config、CLI 的 --conf 都能帶。
    手動觸發沒帶 conf 時 dag_run.conf 是 None，所以要用 `or {}` 墊一個空 dict。
    """
    market = (context["dag_run"].conf or {}).get("market", "all")

    if market in STOCK_GROUPS:
        print(f"conf 指定 market={market}，只爬 {market} 這一組")
        return f"{market}_branch"          # 回傳單一 task_id：只走一條分支

    print("未指定 market（或值不在分組內），兩組都爬")
    return [f"{m}_branch" for m in STOCK_GROUPS]  # 回傳 list：兩條分支都走


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
    description="台股上市/上櫃分組爬蟲 DAG - BranchPythonOperator 選組後平行爬取匯合",
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

    # 分支決策：依 conf 的 market 參數回傳要走的分組節點 task_id。
    market_branch = BranchPythonOperator(
        task_id="choose_market",
        python_callable=choose_market,
    )

    # 結束任務：被選中的分組全部爬完後的共同匯合點。
    # trigger_rule 用 none_failed_min_one_success：
    # 「沒有上游失敗、且至少一個上游成功」就執行——skipped 的那組不會擋住 end。
    end_task = BashOperator(
        task_id="end_crawler",
        bash_command="echo 上市/上櫃分組爬蟲任務全部完成！",
        trigger_rule="none_failed_min_one_success",
    )

    # 外層迴圈：逐一處理每個市場（twse、tpex）。
    for market, stock_ids in STOCK_GROUPS.items():
        # 每個市場一個分組節點：它是分支決策的「落點」（task_id 要跟決策函式回傳的對上），
        # 也順便把該組的圖形整理清楚。
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

        # 依賴關係：起始 → 分支決策 → 該組分組節點 → 組內平行爬取（list）→ 匯合 end。
        # 每個市場都連到同一個 end_task，所以被選中的組會在 end 匯合。
        start_task >> market_branch >> branch >> crawl_tasks >> end_task
