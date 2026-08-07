"""
Step 4 的任務層: 一次呼叫只處理「一顆任務」。

Step 3 的 main() 裡有一個 for 迴圈, 一次跑完整批。
Step 4 把迴圈搬到 producer.py, 這個檔案只留下「處理一組參數」的邏輯。

三個階段的串接順序與 Step 3 的 main() 完全相同, 抓資料 → 整理資料 → 存資料,
client.py、transformer.py、repository.py 三支檔案一行都沒有改。

這一步是整條演進線的樞紐, 理由:
    任務要能被丟進佇列, 前提是它有明確的邊界——輸入是一組參數, 輸出是一次完成的工作。
    參數還寫在函式內部時, 任務沒有邊界, 無法被切分給多個 worker。

這個檔案此時還沒有任何 Celery 的痕跡, 它就是一個普通的 Python 函式,
可以直接 import 進來單機呼叫。Step 5 會在這個函式上加一行 @app.task。
"""
import client
import repository
import transformer


def crawl(stock_id: str, start_date: str, end_date: str):
    """處理一顆任務: 抓一支股票在一段期間的資料, 整理後存到 repository 決定的目標。

    參數:
        stock_id: 股票代碼
        start_date: 起始日期
        end_date: 結束日期

    這個函式的三個特徵決定了它可以被分散執行:
        1. 所有輸入都由參數帶進來, 函式內部沒有任何寫死的清單。
        2. 不依賴其他任務的執行結果, 單獨呼叫就能完成。
        3. 不回傳資料給呼叫端, 結果直接寫進儲存層。
    """
    raw_df = client.fetch_stock_price(stock_id, start_date, end_date)

    if raw_df.empty:
        print(f"{stock_id} 沒有資料, 不進行整理與儲存")
        return

    clean_df = transformer.transform(raw_df)
    print(f"{stock_id} 取得 {len(clean_df)} 筆")
    repository.save(clean_df, stock_id)
