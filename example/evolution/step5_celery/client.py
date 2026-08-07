"""
Step 5 的資料來源層（client）: 函式內容與 Step 3、Step 4 完全相同, 只有 import 那一行不同。

import 改寫的原因與爬蟲邏輯無關:
    Step 3、Step 4 是用 python 直接執行檔案, Python 會把「檔案所在目錄」加進搜尋路徑,
    所以寫 from config import ... 找得到同目錄的 config.py。
    Step 5 是用 celery -A example.evolution.step5_celery.worker 啟動,
    Celery 以「模組路徑」載入程式, 搜尋路徑是專案根目錄, 同目錄那種寫法就找不到檔案。
    因此這裡改用完整套件路徑, 並在每一層資料夾放一個空的 __init__.py。

這個檔案的邊界:
    知道 FinMind 的網址、參數名稱、回傳格式。
    不知道資料會被存到 CSV 還是 MySQL, 也不知道誰會呼叫它。
"""
import pandas as pd
import requests

from example.evolution.step5_celery.config import FINMIND_DATASET, FINMIND_URL


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
