"""
Step 2 的進入點: 把三個階段串起來, 本身不含 API 細節、整理細節與儲存細節。

檔案分工（三個階段各自一支檔案, 與 Step 1 的三個函式一一對應）:
    config.py       設定值
    client.py       抓資料      對應 Step 1 的 fetch_stock_price()
    transformer.py  整理資料    對應 Step 1 的 transform()
    repository.py   存資料      對應 Step 1 的 save()
    main.py         要抓什麼 + 串接順序

執行方式（在專案根目錄執行, 檔案內的 import 用同目錄的模組名稱）:
    uv run python example/evolution/step2_modules/main.py

換儲存目標（需要先啟動 MySQL 容器）:
    STORAGE=mysql uv run python example/evolution/step2_modules/main.py
    STORAGE=csv,mysql uv run python example/evolution/step2_modules/main.py

後兩個指令是這一步的驗收: client.py 與 transformer.py 一行都沒改,
資料就從 CSV 換成進了資料庫, 或是兩邊都寫。
"""
import repository
from client import fetch_stock_price
from config import END_DATE, START_DATE, STOCK_IDS
from transformer import transform


def main():
    """逐一處理每一支股票: 抓資料 → 整理資料 → 存資料。

    要抓哪些股票、抓哪一段期間, 此時仍然寫在這個迴圈裡。
    Step 3 會把這件事獨立成 producer。
    """
    for stock_id in STOCK_IDS:
        raw_df = fetch_stock_price(stock_id, START_DATE, END_DATE)
        if raw_df.empty:
            continue

        clean_df = transform(raw_df)
        print(f"{stock_id} 取得 {len(clean_df)} 筆")
        # 存到哪裡由 config 的 STORAGE 決定, 這一行不用改
        repository.save(clean_df, stock_id)


if __name__ == "__main__":
    main()
