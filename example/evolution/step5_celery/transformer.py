"""
Step 5 的資料整理層（transformer）: 與 Step 3、Step 4 完全相同, 連 import 都沒有改。

這個檔案不需要 import config, 所以不受 Celery 載入方式影響。
用 diff 比對三個步驟的 transformer.py 會沒有任何輸出。

這個檔案的邊界:
    知道 API 回傳哪些欄位、資料庫要哪些欄位、型別要怎麼轉。
    不知道資料是怎麼抓來的, 也不知道整理完會被存到哪裡。

改欄位、改型別、改去重規則時, 只有這個檔案要改。
"""
import pandas as pd

# 整理階段要保留的欄位與順序
COLUMNS = [
    "date",
    "stock_id",
    "Trading_Volume",
    "Trading_money",
    "open",
    "max",
    "min",
    "close",
    "spread",
    "Trading_turnover",
]


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """把 API 原始資料整理成要存的樣子, 回傳新的 DataFrame。

    做三件事:
        1. 去掉完全重複的列。
        2. 把 date 從字串轉成日期型別。
        3. 挑出需要的欄位並固定順序。

    這個函式不修改傳進來的 df, 而是回傳一份新的,
    原始資料保持不動, 要對照整理前後的差異隨時可以比對。
    """
    if df.empty:
        return df

    # drop_duplicates 回傳新的 DataFrame, 不動原本那份
    cleaned = df.drop_duplicates()
    # assign 也是回傳新的 DataFrame; date 從字串轉成日期型別
    cleaned = cleaned.assign(date=pd.to_datetime(cleaned["date"]).dt.date)
    # 挑欄位並固定順序, 讓每次寫出去的結構都一樣
    return cleaned[COLUMNS]
