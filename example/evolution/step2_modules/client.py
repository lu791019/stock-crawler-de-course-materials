"""
Step 2 的資料來源層（client）: 只負責「怎麼跟外部系統拿資料」。

這個檔案的邊界很清楚:
    知道 FinMind 的網址、參數名稱、回傳格式。
    不知道資料會被存到 CSV 還是 MySQL, 也不知道誰會呼叫它。

FinMind 改欄位、改參數、換 API 版本時, 只有這個檔案要改。
"""
import pandas as pd
import requests

from config import FINMIND_DATASET, FINMIND_URL


def fetch_stock_price(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """向 FinMind 取得單一股票在指定期間的日線資料。

    參數:
        stock_id: 股票代碼, ex: 2330
        start_date: 起始日期, 格式 YYYY-MM-DD
        end_date: 結束日期, 格式 YYYY-MM-DD

    回傳:
        DataFrame。API 回傳非 200 時回傳空的 DataFrame, 由呼叫端判斷。
    """
    parameter = {
        "dataset": FINMIND_DATASET,
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
