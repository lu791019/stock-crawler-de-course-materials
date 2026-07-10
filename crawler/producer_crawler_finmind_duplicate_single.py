# 「去重複版本」producer 的單一 worker 版——手冊06 示範用
# 不指定佇列：.delay() 會把任務送進預設佇列，由「不帶 -Q 啟動」的 worker 消費
# 本章只觀察「去重與冪等」，一次只看一件事；多佇列分流見第 3 章與 producer_crawler_finmind_duplicate.py
from crawler.tasks_crawler_finmind_duplicate import crawler_finmind_duplicate

crawler_finmind_duplicate.delay(stock_id="2330")
print("send task_2330 task")

crawler_finmind_duplicate.delay(stock_id="00679B")  # 美債
print("send task_00679b task")
