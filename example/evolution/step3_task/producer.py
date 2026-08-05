"""
Step 3 的派工層（producer）: 只負責「決定要做哪些任務」, 不負責執行細節。

這個檔案回答一個問題: 這一輪要處理哪些參數組合。
它不知道抓資料要呼叫哪個 API, 也不知道資料會被存到哪裡。

此時 producer 用一般的函式呼叫來執行任務, 整批仍在同一支程式裡循序跑完。
Step 4 只會改這裡的一行——把 task.crawl(...) 換成 task.crawl.delay(...)。

執行方式:
    uv run python example/evolution/step3_task/producer.py

執行結果:
    與 Step 2 完全相同, 差別只在任務清單與任務執行已經分開在兩個檔案。
"""
import task
from config import END_DATE, START_DATE, STOCK_IDS


def build_jobs():
    """產生這一輪的任務清單, 每個元素是一顆任務要用的參數。

    任務顆粒度在這裡決定: 目前是「一支股票一顆任務」。
    要改成「一支股票 × 一天一顆任務」, 只需要改這個函式, task.py 不用動。
    """
    return [
        {"stock_id": stock_id, "start_date": START_DATE, "end_date": END_DATE}
        for stock_id in STOCK_IDS
    ]


def main():
    """把清單裡的每一顆任務送出去執行。

    這裡是直接呼叫函式, 所以是循序執行: 前一支抓完才輪到下一支。
    """
    for job in build_jobs():
        print(f"送出任務: {job['stock_id']}")
        task.crawl(**job)


if __name__ == "__main__":
    main()
