from crawler.tasks_demo_fail import task_might_fail, task_requeue, task_reject_no_requeue, task_slow

print("=" * 50)
print("模擬失敗情境 Producer")
print("=" * 50)

# 情境 1：50% 機率失敗（自動重試 3 次）
print("\n📤 情境 1：發送可能失敗的任務（自動重試）")
task_might_fail.delay(stock_id="2330")
print("  sent 2330")

# 情境 2：消費失敗，訊息放回 queue（會一直留在 MQ）
print("\n📤 情境 2：發送會 requeue 的任務（訊息留在 MQ）")
task_requeue.delay(stock_id="REQUEUE_TEST")
print("  sent REQUEUE_TEST")

# 情境 3：消費失敗，訊息丟棄
# print("\n📤 情境 3：發送會丟棄的任務")
# task_reject_no_requeue.delay(stock_id="REJECT_TEST")

# 情境 4：慢任務（開 worker 後 Ctrl+C 殺掉，觀察任務回到 queue）
# print("\n📤 情境 4：發送慢任務（30 秒）")
# task_slow.delay(stock_id="SLOW_TEST", seconds=30)

print("\n✅ 發送完畢")
print("👀 先去 RabbitMQ UI 看 Queue 的 Ready 數量")
print("👀 再開 Worker，觀察 REQUEUE_TEST 會一直重複消費、一直留在 queue")
