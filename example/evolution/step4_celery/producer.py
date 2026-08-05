"""
Step 4 的派工層: 與 Step 3 的 producer.py 相比, 只有一行不同。

    Step 3: task.crawl(**job)          直接呼叫函式, 當場執行, 執行完才輪到下一顆
    Step 4: task.crawl.delay(**job)    把任務送進 RabbitMQ, 送完立刻返回, 由 worker 執行

build_jobs() 一行都沒改, 因為「要做哪些任務」與「任務由誰執行」是兩件事。

執行方式（在專案根目錄執行, 用 -m 以模組路徑啟動）:
    uv run python -m example.evolution.step4_celery.producer

執行前提:
    1. RabbitMQ 已啟動。
    2. worker 已啟動: uv run celery -A example.evolution.step4_celery.worker worker --loglevel=info
"""
from example.evolution.step4_celery import task
from example.evolution.step4_celery.config import END_DATE, START_DATE, STOCK_IDS


def build_jobs():
    """產生這一輪的任務清單, 內容與 Step 3 相同。"""
    return [
        {"stock_id": stock_id, "start_date": START_DATE, "end_date": END_DATE}
        for stock_id in STOCK_IDS
    ]


def main():
    """把清單裡的每一顆任務發送到 RabbitMQ。

    .delay() 送完就返回, 不等待任務執行結果,
    所以這支程式會很快結束, 抓資料的過程要看 worker 的 log 或 Flower。
    """
    for job in build_jobs():
        print(f"發送任務: {job['stock_id']}")
        task.crawl.delay(**job)


if __name__ == "__main__":
    main()
