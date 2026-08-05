"""
Step 1：同一支檔案內拆成三個函式。

跟 Step 0 相比, 檔案還是一支、執行結果也完全相同, 只有一個差別:
原本一個函式裡的三個職責, 現在是三個各自獨立的函式。

三個函式分別對應三個會為了不同理由改變的東西:
    build_jobs()        要抓什麼——改股票清單、改日期範圍只動這裡
    fetch_stock_price() 怎麼拿——FinMind 改欄位、換資料集只動這裡
    save_to_csv()       怎麼存——換儲存目標只動這裡
main() 只負責把三者串起來, 本身不含任何 API 細節與儲存細節。

執行方式:
    uv run python example/evolution/step1_functions.py

執行結果:
    與 Step 0 完全相同, 在 output/ 產生 5 個 CSV 檔。
"""
import requests
import pandas as pd

# 設定值從函式內部搬到模組最上方, 一眼看得到全部可調整的東西
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
STOCK_IDS = ["2330", "0050", "2317", "0056", "00713"]
START_DATE = "2025-01-02"
END_DATE = "2025-06-17"


def build_jobs():
    """職責一: 決定要抓什麼。

    回傳一份工作清單, 每個元素是一組「一次要抓的參數」。
    這個函式不呼叫 API, 也不碰資料庫, 它只是產生清單。
    """
    return [
        {"stock_id": stock_id, "start_date": START_DATE, "end_date": END_DATE}
        for stock_id in STOCK_IDS
    ]


def fetch_stock_price(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """職責二: 決定怎麼拿。

    輸入股票代碼與日期範圍, 回傳 DataFrame。
    這個函式只跟 FinMind API 打交道, 不知道資料之後會被存到哪裡。
    抓不到資料時回傳空的 DataFrame, 由呼叫端決定要不要往下走。
    """
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


def save_to_csv(df: pd.DataFrame, stock_id: str):
    """職責三: 決定怎麼存。

    輸入一份 DataFrame, 存成 CSV。
    這個函式不知道資料從哪裡來, 換成 MySQL 或 BigQuery 時只有這裡要改。
    """
    df.to_csv(
        f"output/TaiwanStockPrice_{stock_id}.csv",
        index=False,
        encoding="utf-8-sig",
    )


def main():
    """把三個職責串起來: 產生清單 → 逐一抓取 → 逐一儲存。"""
    for job in build_jobs():
        df = fetch_stock_price(
            stock_id=job["stock_id"],
            start_date=job["start_date"],
            end_date=job["end_date"],
        )
        if df.empty:
            # 空的 DataFrame 代表這一支沒抓到, 跳過儲存
            continue
        print(f"{job['stock_id']} 取得 {len(df)} 筆")
        save_to_csv(df, job["stock_id"])


if __name__ == "__main__":
    main()
