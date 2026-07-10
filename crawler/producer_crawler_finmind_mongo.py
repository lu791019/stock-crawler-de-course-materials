# Producer: 派送「寫入 MongoDB 版」的爬蟲任務（補充F）
# 用 .s() + apply_async(queue=) 指定佇列 —— 跟 producer_multi_queue 同一個模式,
# 因為 docker-compose 的 worker 是用 -Q twse / -Q tpex 分流監聽的
from crawler.tasks_crawler_finmind_mongo import crawler_finmind_mongo

# 上市股票 → twse 佇列; ETF/上櫃習慣丟 tpex 佇列（沿用第 3 章的分流設計）
for stock_id, queue in [
    ("2330", "twse"),
    ("2317", "twse"),
    ("0050", "tpex"),
    ("0056", "tpex"),
    ("00713", "tpex"),
]:
    print(f"sent {stock_id} -> {queue}")
    crawler_finmind_mongo.s(stock_id=stock_id).apply_async(queue=queue)
