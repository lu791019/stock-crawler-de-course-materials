"""
Step 4 新增的檔案: Celery app 定義。

這個檔案回答兩個問題:
    任務要送到哪裡排隊——broker 指定 RabbitMQ 的位址。
    哪些模組裡的任務要被註冊——include 列出模組路徑。

它不含任何爬蟲邏輯, 也不知道 task 裡面在做什麼。
寫法與課程正式版 crawler/worker.py 相同, 差別只在 include 指到本示範的模組。

啟動 worker（在專案根目錄執行）:
    uv run celery -A example.evolution.step4_celery.worker worker --loglevel=info
"""
from celery import Celery

from example.evolution.step4_celery.config import (
    RABBITMQ_HOST,
    RABBITMQ_PORT,
    WORKER_ACCOUNT,
    WORKER_PASSWORD,
)

app = Celery(
    "evolution",
    # include: 只有列在這裡的模組, 裡面用 @app.task 裝飾的函式才會被註冊成可執行任務
    include=["example.evolution.step4_celery.task"],
    # broker: 任務排隊的地方, 格式為 pyamqp://帳號:密碼@主機:埠號/
    broker=f"pyamqp://{WORKER_ACCOUNT}:{WORKER_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/",
)
