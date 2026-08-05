"""
Step 4 的任務層: 與 Step 3 的 task.py 相比, 函式主體一行都沒有改。

三處差異全部與爬蟲邏輯無關:
    1. 多 import 了 worker 裡的 app。
    2. 函式上方多了一行 @app.task 裝飾器, 作用是把這個函式註冊成可派送的任務。
    3. import client 與 repository 改用完整套件路徑（原因見 client.py 的說明）。

裝飾器不改變函式的行為: crawl(...) 直接呼叫時仍然是同步執行的普通函式,
crawl.delay(...) 才是把任務送進 RabbitMQ 交給 worker 執行。
這代表 Celery 換掉的是「誰來執行、在哪裡執行」, 不是「執行什麼」。
"""
from example.evolution.step4_celery import client, repository
from example.evolution.step4_celery.worker import app


@app.task()
def crawl(stock_id: str, start_date: str, end_date: str):
    """處理一顆任務: 抓一支股票在一段期間的資料, 存到 repository 決定的目標。

    函式主體與 Step 3 完全相同。
    參數必須是可以被序列化的型別（字串、數字、list、dict）,
    因為任務會被轉成訊息送進 RabbitMQ, DataFrame 或連線物件無法這樣傳遞。
    """
    df = client.fetch_stock_price(stock_id, start_date, end_date)

    if df.empty:
        print(f"{stock_id} 沒有資料, 不進行儲存")
        return

    print(f"{stock_id} 取得 {len(df)} 筆")
    repository.save(df, stock_id)
