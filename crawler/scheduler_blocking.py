"""
定時排程器（阻塞版）：用 BlockingScheduler 做為 scheduler.py 的對照組。

跟 scheduler.py（Background 版）的差別只有一個：
BlockingScheduler 的 scheduler.start() 會「卡住」主執行緒——
程式停在那一行，只執行排程工作，start() 之後的程式碼不會被執行。
因此這一版不需要檔案結尾的 while True 保活迴圈。
適合「這支程式就是專門跑排程」的情況，例如放進一個容器單獨執行。

啟動方式：
    uv run crawler/scheduler_blocking.py
"""
# 匯入 APScheduler 的「阻塞式」排程器。
# Blocking 的意思是：scheduler.start() 會卡住主執行緒、程式停在該行專心當排程器。
# 對照 BackgroundScheduler（見 scheduler.py）：那一版 start() 之後程式會繼續往下走。
from apscheduler.schedulers.blocking import BlockingScheduler

# 匯入 loguru 進行 log 紀錄
from loguru import logger

# 匯入 Celery 任務。注意匯入的是「任務物件」，
# 下面呼叫 .delay() 時只是把訊息發進佇列，函式本體是在 worker 那邊執行。
from crawler.tasks_crawler_finmind import crawler_finmind


# 教學觀察用任務：每 5 秒印一行字。
# 目的是讓你啟動排程器後馬上看得到「排程真的在動」，不用等 12 小時。
def hello_world():
    logger.info("========================hello_world=====================")


# 正式任務：發送一批股票的爬蟲任務。
# 內容跟你前面章節手動執行的 producer 完全相同——
# 差別只是「誰來呼叫它」：以前是你在終端機打指令，現在是排程器到點自動呼叫。
def send_crawler_stock_price_task():
    # 逐一發送每支股票的爬蟲任務，實際執行交給 Celery worker
    for stock_id in ["2330", "0050", "2317", "0056", "00713"]:
        logger.info(stock_id)  # 印出目前發送的股票代碼，方便對照 log
        crawler_finmind.delay(
            stock_id=stock_id
        )  # .delay() 只是把任務訊息丟進 RabbitMQ，發完立刻返回、不等爬完


def main():
    # 建立阻塞式排程器。timezone 一定要明寫：
    # 不寫的話會用系統時區，容器和雲端主機常常是 UTC，跟台北差 8 小時，
    # 排 18:00 的工作會在台北時間凌晨 2 點才跑。
    scheduler = BlockingScheduler(
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
        # day_of_week="1-5",  # 改成這樣就是只有週一到週五執行
        # day_of_week="0,1,3,5",  # 改成這樣就是只有週日、週一、週三、週五執行
        second="*/5",  # 秒數每 5 秒符合一次——APScheduler 比系統 crontab 多這個秒欄位
        coalesce=True,  # 程式中斷錯過多次排程時，恢復後只補跑一次，不會把錯過的每一次都補跑
    )
    # 註冊工作 B：正式的爬蟲發送任務，每 12 小時的整點執行一次
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
    # 啟動排程器。Blocking 版的 start() 會卡住主執行緒——
    # 程式停在這一行專心跑排程，這行之後的任何程式碼都不會被執行，
    # 所以這一版不需要 while True 保活迴圈。
    scheduler.start()


if __name__ == "__main__":
    main()
