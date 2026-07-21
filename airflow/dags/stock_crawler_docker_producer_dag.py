"""
台股爬蟲 Docker Producer DAG（串法三：用臨時容器執行多佇列 producer）。

對應課程：股票爬蟲章節的「用 DockerOperator 執行 producer（串法三）」主題。
教學目的：說明如何用 DockerOperator 臨時起一個容器，執行第 3 章的多佇列 producer 程式。

核心概念：
- DockerOperator 會臨時起一個容器來執行 producer，跑完自動刪除（auto_remove=True）。
- 這個臨時容器不是由 docker compose 啟動的，所以它不會讀 compose 的 .env，
  連線資訊必須在 environment 參數裡明確給；漏了 RABBITMQ_HOST，程式會預設連 127.0.0.1
  （容器自己），導致 Connection refused。
- network_mode 必須指定成與其他服務相同的網路（my_network），容器才解析得到 rabbitmq、mysql
  這些服務名稱；不指定就無法用名稱連到那些服務。

觸發方式：
    airflow dags unpause stock_crawler_docker_producer_dag
    airflow dags trigger stock_crawler_docker_producer_dag
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.operators.bash_operator import BashOperator

default_args = {
    "owner": "data-team",                      # 負責團隊
    "start_date": datetime(2024, 1, 1),        # 排程起算日
    "retries": 1,                               # task 失敗時重試 1 次
    "retry_delay": timedelta(minutes=1),        # 每次重試間隔 1 分鐘
    "execution_timeout": timedelta(hours=1),    # 單一 task 執行超過 1 小時視為逾時失敗
}

with DAG(
    dag_id="stock_crawler_docker_producer_dag",
    default_args=default_args,
    description="台股爬蟲 Docker DAG - 用 Docker 容器執行爬蟲",
    schedule_interval=None,  # 不自動排程，只能手動觸發
    catchup=False,           # 不補跑歷史排程區間
    max_active_runs=1,       # 同一時間最多一個 DAG run
    tags=["stock", "crawler", "docker"],
) as dag:

    # 起始任務：印出開始訊息。
    start_task = BashOperator(
        task_id="start_crawler",
        bash_command="echo 開始執行台股爬蟲任務...",
    )

    DOCKER_IMAGE = "stock-crawler:latest"  # 臨時容器要使用的映像檔
    # 容器內要執行的指令：跑第 3 章的多佇列 producer。
    # 該 producer 用 apply_async(queue=...) 把任務分流到 twse / tpex 佇列；
    # 因為 worker 池是 -Q twse / -Q tpex 的分流版，發到預設佇列的任務不會被消費。
    DOCKER_COMMAND = "uv run python -m crawler.producer_multi_queue"
    DOCKER_NETWORK = "my_network"  # 與其他服務共用的 Docker 網路名稱

    docker_crawler_task = DockerOperator(
        task_id="docker_stock_crawler",
        image=DOCKER_IMAGE,
        command=DOCKER_COMMAND,
        network_mode=DOCKER_NETWORK,  # 指定網路，容器才解析得到 rabbitmq / mysql 這些服務名稱
        # 臨時容器不會讀 compose 的 .env，連線資訊要在這裡明確給。
        # RABBITMQ_HOST 不設的話會預設連 127.0.0.1（容器自己），造成 Connection refused。
        environment={
            "TZ": "Asia/Taipei",        # 容器時區設為台灣，避免時間判斷偏差
            "RABBITMQ_HOST": "rabbitmq",  # RabbitMQ 服務名稱，靠共用網路解析
            "MYSQL_HOST": "mysql",        # MySQL 服務名稱，靠共用網路解析
        },
        auto_remove=True,  # 執行完畢後自動刪除臨時容器
    )

    # 結束任務：等 producer 容器成功執行後才印出訊息。
    end_task = BashOperator(
        task_id="end_crawler",
        bash_command="echo 台股爬蟲任務發送完成！",
        trigger_rule="all_success",  # 只有當全部上游 task 都成功時才執行
    )

    # 依賴關係：起始 → Docker producer → 結束。
    start_task >> docker_crawler_task >> end_task
