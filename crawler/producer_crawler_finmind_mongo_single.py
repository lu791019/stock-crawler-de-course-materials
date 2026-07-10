# 「寫入 MongoDB 版」producer 的單一 worker 版——補充F 示範用
# 不指定佇列：.delay() 把任務送進預設佇列，由「不帶 -Q 啟動」的本機 worker 消費
# （跟手冊06 的示範同一套方式；補充F 只看 MongoDB 落地，一次只看一件事）
# 多佇列分流版見 producer_crawler_finmind_mongo.py（第 3 章的路由設計）
from crawler.tasks_crawler_finmind_mongo import crawler_finmind_mongo

# 一次派送 5 支股票，worker 會逐一執行
for stock_id in ["2330", "2317", "0050", "0056", "00713"]:
    print(f"sent {stock_id}")
    crawler_finmind_mongo.delay(stock_id=stock_id)
