# 「去重複版本」producer 的單一佇列版——手冊06 示範用
# 兩個任務都送 twse 佇列、由同一個 worker 處理：
# 這一章只觀察「去重與冪等」的效果，一次只看一件事
# （多佇列分流的版本見 producer_crawler_finmind_duplicate.py，分流本身在第 3 章教）
from crawler.tasks_crawler_finmind_duplicate import crawler_finmind_duplicate

task_2330 = crawler_finmind_duplicate.s(stock_id="2330")
task_2330.apply_async(queue="twse")
print("send task_2330 task")

task_00679b = crawler_finmind_duplicate.s(stock_id="00679B")  # 美債
task_00679b.apply_async(queue="twse")
print("send task_00679b task")
