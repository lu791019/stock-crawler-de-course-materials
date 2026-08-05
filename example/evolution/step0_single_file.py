"""
Step 0：單體版爬蟲——一支程式從頭做到尾。

這支程式是拆解的起點, 也是多數人第一版會寫出來的樣子:
一個函式裡同時做了三件事——決定要抓哪些資料、呼叫 API 拿資料、把資料存下來。
它可以正常執行, 沒有任何錯誤, 但三件事綁在一起, 之後每一種改動都會動到同一個函式。

執行方式:
    uv run python example/evolution/step0_single_file.py

執行結果:
    在 output/ 產生 5 個 CSV 檔（每支股票一個）。
"""
import requests
import pandas as pd
from sqlalchemy import create_engine


def crawl_taiwan_stock_price():
    """抓 5 支股票的日線資料並存檔。三個職責全部寫在這一個函式裡。"""

    # 職責一: 決定「要抓什麼」——股票清單與日期範圍寫死在函式內部
    stock_ids = ["2330", "0050", "2317", "0056", "00713"]
    start_date = "2025-01-02"
    end_date = "2025-06-17"

    # 設定值也寫死在函式內部: API 位址、資料集名稱、資料庫連線資訊
    url = "https://api.finmindtrade.com/api/v4/data"
    write_mysql = False  # 改成 True 就會多寫一份到 MySQL, 需要先啟動 MySQL
    mysql_address = "mysql+pymysql://root:1234@127.0.0.1:3306/mydb"

    for stock_id in stock_ids:
        # 職責二: 決定「怎麼拿」——組參數、發 HTTP 請求、把 JSON 轉成 DataFrame
        parameter = {
            "dataset": "TaiwanStockPrice",  # 台股日線資料
            "data_id": stock_id,            # 股票代碼, ex: 2330
            "start_date": start_date,
            "end_date": end_date,
        }
        resp = requests.get(url, params=parameter)
        data = resp.json()

        if resp.status_code != 200:
            # API 失敗時印出訊息, 換下一支股票
            print(f"{stock_id} 抓取失敗: {data.get('msg')}")
            continue

        df = pd.DataFrame(data["data"])
        print(f"{stock_id} 取得 {len(df)} 筆")

        # 職責三: 決定「怎麼存」——存成 CSV, 需要時再多存一份到 MySQL
        df.to_csv(
            f"output/TaiwanStockPrice_{stock_id}.csv",
            index=False,
            encoding="utf-8-sig",
        )

        if write_mysql:
            # 資料庫寫入的細節（連線、資料表名稱、寫入模式）同樣寫在這個函式裡
            engine = create_engine(mysql_address)
            df.to_sql("TaiwanStockPrice", con=engine, if_exists="append", index=False)


if __name__ == "__main__":
    crawl_taiwan_stock_price()
