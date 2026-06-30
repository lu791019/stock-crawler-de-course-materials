from celery import Celery
from loguru import logger
from crawler.config import (
    RABBITMQ_HOST,
    RABBITMQ_PORT,
    WORKER_ACCOUNT,
    WORKER_PASSWORD,
)

logger.info(f"""
    RABBITMQ_HOST: {RABBITMQ_HOST}
    RABBITMQ_PORT: {RABBITMQ_PORT}
    WORKER_ACCOUNT: {WORKER_ACCOUNT}
    WORKER_PASSWORD: {WORKER_PASSWORD}
""")

app = Celery(
    "task_demo",
    include=[
        "crawler.tasks_demo_fail",
    ],
    broker=f"pyamqp://{WORKER_ACCOUNT}:{WORKER_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/",
)

# acks_late 全域設定：做完才確認，失敗會重新排隊
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True
