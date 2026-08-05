"""
Step 1：同一支檔案內拆成三個函式。

跟 Step 0 相比, 檔案還是一支, 主要差別是原本一個函式裡的流程變成三個獨立的函式。
另外補上了 Step 0 沒有的整理階段: Step 0 把 API 原始資料抓進來就直接存,
這裡在存之前先去重、轉型別、挑欄位。真實系統一定有這一層,
因為 API 回傳的欄位與資料庫想要的欄位很少完全一致。

三個函式對應資料處理的三個階段, 也對應三種不同的改動理由:
    fetch_stock_price()  抓資料——FinMind 改參數、換 API 版本只動這裡
    transform()          整理資料——改欄位、改型別、改去重規則只動這裡
    save()               存資料——換儲存目標、加一種儲存方式只動這裡
main() 只負責把三者串起來, 本身不含 API 細節、整理細節與儲存細節。

三個函式之間不互相呼叫, 全部由 main() 串接。
這一點是拆解成不成立的關鍵: 如果 fetch 裡面直接呼叫了 save,
兩者仍然綁在一起, 換儲存方式還是得改到抓資料的函式。

執行方式:
    uv run python example/evolution/step1_functions.py

執行結果:
    與 Step 0 相同, 在 output/ 產生 CSV 檔; WRITE_MYSQL 為 True 時同時寫入 MySQL。
"""
import pandas as pd
import requests
from sqlalchemy import create_engine

# 設定值從函式內部搬到模組最上方, 一眼看得到全部可調整的東西
# 此時設定仍然寫在程式碼裡, Step 2 才會改成讀環境變數
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
STOCK_IDS = ["2330", "0050", "2317", "0056", "00713"]
START_DATE = "2025-01-02"
END_DATE = "2025-06-17"

# 儲存設定: 與 Step 0 相同, CSV 一定寫, MySQL 由開關決定
WRITE_MYSQL = False
MYSQL_ADDRESS = "mysql+pymysql://root:1234@127.0.0.1:3306/mydb"
TABLE_NAME = "TaiwanStockPrice"

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


def fetch_stock_price(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """階段一: 抓資料。

    輸入股票代碼與日期範圍, 回傳 API 原始資料轉成的 DataFrame。
    這個函式只跟 FinMind API 打交道, 不整理資料, 也不知道資料之後會被存到哪裡。
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


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """階段二: 整理資料。

    輸入原始 DataFrame, 回傳整理後的新 DataFrame。
    做三件事: 去掉完全重複的列、把 date 轉成日期型別、挑出需要的欄位並固定順序。

    這個函式不修改傳進來的 df, 而是回傳一份新的。
    原始資料保持不動, 之後要對照「整理前後差在哪」隨時可以比對。

    這一層在 Step 0 是不存在的——原始資料抓進來就直接存下去。
    真實系統一定會有這一層, 因為 API 的欄位與資料庫想要的欄位很少完全一致。
    """
    if df.empty:
        return df

    # drop_duplicates 回傳新的 DataFrame, 不動原本那份
    cleaned = df.drop_duplicates()
    # assign 也是回傳新的 DataFrame; date 從字串轉成日期型別
    cleaned = cleaned.assign(date=pd.to_datetime(cleaned["date"]).dt.date)
    # 挑欄位並固定順序, 讓每次寫出去的結構都一樣
    return cleaned[COLUMNS]


def save(df: pd.DataFrame, stock_id: str):
    """階段三: 存資料。

    輸入整理後的 DataFrame, 寫進儲存目標。
    CSV 一定寫, MySQL 由 WRITE_MYSQL 開關決定, 行為與 Step 0 相同。

    這個函式不知道資料從哪裡來, 也不知道資料被整理過什麼。
    換儲存目標、多加一種儲存目標, 只有這個函式要改。
    """
    path = f"output/{TABLE_NAME}_{stock_id}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"已寫入 {path}")

    if WRITE_MYSQL:
        # if_exists="append" 代表資料表存在就往後追加, 不存在就先建表
        engine = create_engine(MYSQL_ADDRESS)
        df.to_sql(TABLE_NAME, con=engine, if_exists="append", index=False)
        print(f"已寫入 MySQL {TABLE_NAME}（{stock_id}）")


def main():
    """把三個階段串起來: 抓資料 → 整理資料 → 存資料。

    要抓哪些股票、抓哪一段期間, 此時仍然寫在這個函式的迴圈裡。
    Step 3 會把這件事獨立成 producer。
    """
    for stock_id in STOCK_IDS:
        raw_df = fetch_stock_price(stock_id, START_DATE, END_DATE)
        if raw_df.empty:
            # 空的 DataFrame 代表這一支沒抓到, 跳過後面兩個階段
            continue

        clean_df = transform(raw_df)
        print(f"{stock_id} 取得 {len(clean_df)} 筆")
        save(clean_df, stock_id)


if __name__ == "__main__":
    main()
