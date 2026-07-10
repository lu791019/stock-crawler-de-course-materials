# 這是「去重複版本」的 producer
# 差別在: 對應的 task 在寫入 MySQL 時會用 on_duplicate_key_update
# 避免同一筆資料重複 insert 造成主鍵衝突
from crawler.tasks_crawler_finmind_duplicate import crawler_finmind_duplicate

# 兩個任務都送同一個佇列（twse）——這一章只觀察「去重與冪等」的效果，
# 一次只看一件事；多佇列分流在第 3 章已經教過
task_2330 = crawler_finmind_duplicate.s(stock_id="2330")
task_2330.apply_async(queue="twse")
print("send task_2330 task")

task_00679b = crawler_finmind_duplicate.s(stock_id="00679B")  # 美債
task_00679b.apply_async(queue="twse")
print("send task_00679b task")
