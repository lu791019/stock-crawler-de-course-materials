"""
Step 2 的進入點: 把三層串起來, 本身不含任何 API 細節與儲存細節。

檔案分工:
    config.py     設定值
    client.py     怎麼拿
    repository.py 怎麼存
    main.py       要抓什麼 + 串接順序

執行方式（在專案根目錄執行, 檔案內的 import 用同目錄的模組名稱）:
    uv run python example/evolution/step2_modules/main.py

換儲存目標到 MySQL（需要先啟動 MySQL 容器）:
    STORAGE=mysql uv run python example/evolution/step2_modules/main.py

第二個指令是這一步的驗收: client.py 一行都沒改, 資料就從 CSV 換成進了資料庫。
"""
import repository
from client import fetch_stock_price
from config import END_DATE, START_DATE, STOCK_IDS


def build_jobs():
    """決定要抓什麼: 把設定展開成一份工作清單。"""
    return [
        {"stock_id": stock_id, "start_date": START_DATE, "end_date": END_DATE}
        for stock_id in STOCK_IDS
    ]


def main():
    """逐一處理清單裡的每一組參數: 抓資料 → 存資料。"""
    for job in build_jobs():
        df = fetch_stock_price(
            stock_id=job["stock_id"],
            start_date=job["start_date"],
            end_date=job["end_date"],
        )
        if df.empty:
            continue
        print(f"{job['stock_id']} 取得 {len(df)} 筆")
        # 呼叫 repository.save, 存到哪裡由 config 的 STORAGE 決定
        repository.save(df, job["stock_id"])


if __name__ == "__main__":
    main()
