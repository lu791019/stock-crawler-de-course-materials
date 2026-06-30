from crawler.worker_demo import app
from celery.exceptions import Reject
import random


@app.task(bind=True, acks_late=True, max_retries=3, default_retry_delay=5)
def task_might_fail(self, stock_id):
    """情境 1：失敗自動重試 3 次，最終成功或放棄"""
    print(f"開始處理 {stock_id}...（第 {self.request.retries + 1} 次嘗試）")
    if random.random() < 0.5:
        print(f"❌ {stock_id} 失敗！5 秒後重試（剩餘 {self.max_retries - self.request.retries} 次）")
        raise self.retry(exc=Exception(f"{stock_id} 模擬錯誤"))
    print(f"✅ {stock_id} 處理成功！")
    return f"{stock_id} done"


@app.task(bind=True, acks_late=True)
def task_requeue(self, stock_id):
    """情境 2：消費失敗，訊息放回 queue（requeue）
    訊息不會消失，會一直留在 MQ 等下一次消費
    去 RabbitMQ UI 看 Unacked → Ready 的變化"""
    print(f"開始處理 {stock_id}...")
    print(f"❌ {stock_id} 處理失敗！訊息放回 queue")
    raise Reject(reason=f"{stock_id} 處理失敗", requeue=True)


@app.task(bind=True, acks_late=True)
def task_reject_no_requeue(self, stock_id):
    """情境 3：消費失敗，訊息丟棄（不放回 queue）
    訊息直接消失，跟 acks_late=False 的效果一樣"""
    print(f"開始處理 {stock_id}...")
    print(f"❌ {stock_id} 處理失敗！訊息丟棄（不放回 queue）")
    raise Reject(reason=f"{stock_id} 處理失敗", requeue=False)


@app.task(acks_late=True)
def task_slow(stock_id, seconds=30):
    """情境 4：處理很久，中途關掉 Worker
    因為 acks_late=True，Worker 被殺時任務還沒 ack，訊息會回到 queue"""
    import time
    print(f"開始處理 {stock_id}，需要 {seconds} 秒...")
    for i in range(seconds):
        time.sleep(1)
        print(f"  {stock_id} 進度 {i+1}/{seconds}")
    print(f"✅ {stock_id} 處理完成！")
    return f"{stock_id} done"
