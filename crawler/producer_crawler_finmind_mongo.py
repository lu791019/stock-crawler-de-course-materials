# Producer: 派送「寫入 MongoDB 版」的爬蟲任務（補充F）
# 跟 producer_crawler_finmind 完全同一個模式, 只是任務換成 mongo 版
from crawler.tasks_crawler_finmind_mongo import crawler_finmind_mongo

for stock_id in ["2330", "0050", "2317", "0056", "00713"]:
    print("sent", stock_id)
    crawler_finmind_mongo.delay(stock_id=stock_id)
