"""
Step 2：同一支檔案內，把「處理一支股票的完整流程」抽成一顆任務函式。

跟 Step 1 相比，檔案還是一支、三個階段函式（fetch/transform/save）一行都沒改，
唯一的變化：main() 迴圈裡「抓 → 整理 → 存」那段流程，抽成了 crawl(stock_id, start_date, end_date)。

這一步是整條演進線的樞紐——「任務」在這裡誕生：
    1. 所有輸入都由參數帶進來, 函式內部沒有寫死的清單。
    2. 不依賴其他任務的執行結果, 單獨呼叫就能完成。
    3. 不回傳資料給呼叫端, 結果直接寫進儲存層。
滿足這三個條件的函式才能被切分給多台機器執行。此時完全沒有 Celery——
任務的定義與傳遞任務的工具是兩回事。

執行方式:
    uv run python example/evolution/step2_task_function.py

執行結果:
    與 Step 1 相同。
"""
import pandas as pd
import requests
from sqlalchemy import create_engine

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
STOCK_IDS = ["2330", "0050", "2317", "0056", "00713"]
START_DATE = "2025-01-02"
END_DATE = "2025-06-17"

WRITE_MYSQL = False
MYSQL_ADDRESS = "mysql+pymysql://root:1234@127.0.0.1:3306/mydb"
TABLE_NAME = "TaiwanStockPrice"

COLUMNS = [
    "date", "stock_id", "Trading_Volume", "Trading_money",
    "open", "max", "min", "close", "spread", "Trading_turnover",
]


def fetch_stock_price(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """階段一: 抓資料。與 Step 1 完全相同。"""
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    resp = requests.get(FINMIND_URL, params=parameter)
    data = resp.json()
    if resp.status_code != 200:
        print(f"{stock_id} 抓取失敗: {data.get('msg')}")
        return pd.DataFrame()
    return pd.DataFrame(data["data"])


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """階段二: 整理資料。與 Step 1 完全相同。"""
    if df.empty:
        return df
    cleaned = df.drop_duplicates()
    cleaned = cleaned.assign(date=pd.to_datetime(cleaned["date"]).dt.date)
    return cleaned[COLUMNS]


def save(df: pd.DataFrame, stock_id: str):
    """階段三: 存資料。與 Step 1 完全相同。"""
    path = f"output/{TABLE_NAME}_{stock_id}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"已寫入 {path}")
    if WRITE_MYSQL:
        engine = create_engine(MYSQL_ADDRESS)
        df.to_sql(TABLE_NAME, con=engine, if_exists="append", index=False)
        print(f"已寫入 MySQL {TABLE_NAME}（{stock_id}）")


def crawl(stock_id: str, start_date: str, end_date: str):
    """一顆任務: 抓一支股票在一段期間的資料, 整理後存下去。

    Step 1 的 main() 把這段流程寫在迴圈裡; 抽成函式之後,
    「處理一支股票」有了明確的邊界——輸入是參數、輸出是一次完成的工作。
    之後不管是誰來呼叫（迴圈、排程器、別台機器上的 worker）, 做的事都一樣。
    """
    raw_df = fetch_stock_price(stock_id, start_date, end_date)
    if raw_df.empty:
        print(f"{stock_id} 沒有資料, 不進行整理與儲存")
        return
    clean_df = transform(raw_df)
    print(f"{stock_id} 取得 {len(clean_df)} 筆")
    save(clean_df, stock_id)


def main():
    """迴圈只剩一件事: 決定要處理哪些股票, 逐顆呼叫任務。"""
    for stock_id in STOCK_IDS:
        crawl(stock_id, START_DATE, END_DATE)


if __name__ == "__main__":
    main()
