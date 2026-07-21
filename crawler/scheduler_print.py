"""
定時排程器（print 版，教學觀察用）：定時發送「只印出、不寫資料庫」的爬蟲任務。

跟 scheduler.py（正式版）的結構完全相同，唯一差別是發送的任務換成
crawler_finmind_print——worker 收到後只把爬到的資料印在 log，不寫入 MySQL。
教學時先跑這一版，觀察「定時派送 → worker 收到 → 印出資料」的完整流程，
確認流程沒問題後，再切換到 scheduler.py。

啟動方式：
    uv run crawler/scheduler_print.py
"""
import time

# 匯入 APScheduler 的「背景執行」排程器。
# Background 的意思是：排程器跑在背景執行緒，scheduler.start() 之後
# 主程式可以繼續往下走——所以檔案結尾需要 while True 保持主程式存活。
from apscheduler.schedulers.background import BackgroundScheduler

# 匯入 loguru 進行 log 紀錄
from loguru import logger

# 匯入 print 版的 Celery 任務：worker 收到後只印出資料、不寫入資料庫。
# 確認流程 OK 後，再切換到 scheduler.py（發送會寫入資料庫的正式任務）。
from crawler.tasks_crawler_finmind import crawler_finmind_print


# 教學觀察用任務：每 5 秒印一行字。
# 目的是讓你啟動排程器後馬上看得到「排程真的在動」，不用等 12 小時。
def hello_world():
    logger.info("========================hello_world=====================")


# 發送一批股票的爬蟲任務（print 版：worker 只印出、不寫資料庫）。
# 內容跟你前面章節手動執行的 producer 完全相同——
# 差別只是「誰來呼叫它」：以前是你在終端機打指令，現在是排程器到點自動呼叫。
def send_crawler_stock_price_task():
    # 逐一發送每支股票的爬蟲任務，實際執行交給 Celery worker
    for stock_id in ["2330", "0050", "2317", "0056", "00713"]:
        logger.info(stock_id)  # 印出目前發送的股票代碼，方便對照 log
        crawler_finmind_print.delay(
            stock_id=stock_id
        )  # .delay() 只是把任務訊息丟進 RabbitMQ，發完立刻返回、不等爬完


def main():
    # 建立背景排程器。timezone 一定要明寫：
    # 不寫的話會用系統時區，容器和雲端主機常常是 UTC，跟台北差 8 小時，
    # 排 18:00 的工作會在台北時間凌晨 2 點才跑。
    scheduler = BackgroundScheduler(
        timezone="Asia/Taipei",
    )
    # 註冊工作 A：hello_world，每 5 秒執行一次（教學觀察用）
    scheduler.add_job(
        id="hello_world",  # 工作的唯一識別名稱，重複註冊同名工作會報錯
        func=hello_world,  # 到點要執行的函式（傳函式本身，不加括號）
        trigger="cron",  # 用 cron 風格指定時間；cron 的欄位語法見課程手冊 09
        hour="*",  # 每個小時都符合
        minute="*",  # 每分鐘都符合
        day_of_week="*",  # 每個星期幾都符合
        second="*/5",  # 秒數每 5 秒符合一次——APScheduler 比系統 crontab 多這個秒欄位
        coalesce=True,  # 程式中斷錯過多次排程時，恢復後只補跑一次，不會把錯過的每一次都補跑
    )
    # 註冊工作 B：爬蟲發送任務（print 版），每 12 小時的整點執行一次
    scheduler.add_job(
        id="send_crawler_stock_price_task",
        func=send_crawler_stock_price_task,
        trigger="cron",
        hour="*/12",  # 小時數每 12 小時符合一次（0 點和 12 點）
        minute="0",  # 分鐘必須是 0——搭配上面就是「整點」
        day_of_week="*",  # 每個星期幾都符合
        second="0",  # 秒數必須是 0
        coalesce=True,  # 同上：錯過多次只補跑一次
    )
    logger.info(
        "send_crawler_stock_price_task add scheduler"
    )  # 記錄排程已註冊完成
    scheduler.start()  # 啟動排程器；Background 版這一行不會卡住，會繼續往下執行


if __name__ == "__main__":
    main()
    # BackgroundScheduler 跑在背景執行緒——主程式一結束，背景排程器也跟著消失。
    # 所以用無限迴圈讓主程式一直活著，排程器才能持續運作。
    while True:
        time.sleep(600)  # 主程式每 10 分鐘醒一次，純粹為了保持存活
