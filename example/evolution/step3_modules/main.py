"""
Step 3 的進入點: 三個階段各自搬進獨立檔案, crawl() 任務函式留在這裡。

檔案分工（Step 1 的三個函式與三支檔案一一對應）:
    config.py       設定值（改讀環境變數）
    client.py       抓資料      對應 fetch_stock_price()
    transformer.py  整理資料    對應 transform()
    repository.py   存資料      對應 save()
    main.py         crawl() 任務 + 要抓什麼 + 串接順序

crawl() 的內容與 Step 2 完全相同, 只是三個階段的實作換成 import 進來的模組。

執行方式（在專案根目錄執行）:
    uv run python example/evolution/step3_modules/main.py

換儲存目標（需要先啟動 MySQL 容器）:
    STORAGE=mysql uv run python example/evolution/step3_modules/main.py
    STORAGE=csv,mysql uv run python example/evolution/step3_modules/main.py

後兩個指令是這一步的驗收: client.py 與 transformer.py 一行都沒改,
資料就從 CSV 換成進了資料庫, 或是兩邊都寫。
"""
import repository
from client import fetch_stock_price
from config import END_DATE, START_DATE, STOCK_IDS
from transformer import transform


def crawl(stock_id: str, start_date: str, end_date: str):
    """一顆任務: 抓 → 整理 → 存。與 Step 2 的 crawl() 相同, 實作換成三個模組。"""
    raw_df = fetch_stock_price(stock_id, start_date, end_date)
    if raw_df.empty:
        print(f"{stock_id} 沒有資料, 不進行整理與儲存")
        return
    clean_df = transform(raw_df)
    print(f"{stock_id} 取得 {len(clean_df)} 筆")
    repository.save(clean_df, stock_id)


def main():
    """要抓哪些股票仍然寫在這裡, Step 4 才把它獨立成 producer。"""
    for stock_id in STOCK_IDS:
        crawl(stock_id, START_DATE, END_DATE)


if __name__ == "__main__":
    main()
