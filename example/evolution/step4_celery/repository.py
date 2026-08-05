"""
Step 4 的資料儲存層（repository）: 函式內容與 Step 2、Step 3 完全相同, 只有 import 那一行不同。

import 改寫的原因與 client.py 相同: Celery 以模組路徑載入程式, 要用完整套件路徑。

這個檔案的邊界:
    知道 CSV 要存哪個目錄、MySQL 的連線字串與資料表名稱。
    不知道資料是從 FinMind 來的, 也不知道是誰決定要存這一份。

換儲存目標（CSV → MySQL → BigQuery）時, 只有這個檔案要改。
兩個實作對外的函式簽名相同, 都是 save(df, stock_id), 所以呼叫端換一個字就能換目標。
"""
import os

import pandas as pd
from sqlalchemy import create_engine

from example.evolution.step4_celery.config import (
    CSV_OUTPUT_DIR,
    MYSQL_ACCOUNT,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    STORAGE,
)

# 資料表名稱與課程正式版一致
TABLE_NAME = "TaiwanStockPrice"


def save_to_csv(df: pd.DataFrame, stock_id: str):
    """把 DataFrame 存成 CSV。目錄不存在時先建立。"""
    os.makedirs(CSV_OUTPUT_DIR, exist_ok=True)
    path = f"{CSV_OUTPUT_DIR}/{TABLE_NAME}_{stock_id}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"已寫入 {path}")


def save_to_mysql(df: pd.DataFrame, stock_id: str):
    """把 DataFrame 追加寫入 MySQL 的 TaiwanStockPrice 資料表。

    連線字串格式: mysql+pymysql://帳號:密碼@主機:埠號/資料庫
    if_exists="append" 代表資料表已存在就往後追加, 不存在就先建表。
    """
    address = (
        f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    )
    engine = create_engine(address)
    df.to_sql(TABLE_NAME, con=engine, if_exists="append", index=False)
    print(f"已寫入 MySQL {MYSQL_DATABASE}.{TABLE_NAME}（{stock_id}）")


def save(df: pd.DataFrame, stock_id: str):
    """依 config 的 STORAGE 設定選擇儲存目標。

    STORAGE=csv   走 save_to_csv
    STORAGE=mysql 走 save_to_mysql
    值不認得就直接丟例外, 不做靜默略過——設錯值要立刻知道, 不能安靜地什麼都沒存。
    """
    if STORAGE == "csv":
        save_to_csv(df, stock_id)
    elif STORAGE == "mysql":
        save_to_mysql(df, stock_id)
    else:
        raise ValueError(f"STORAGE 只接受 csv 或 mysql, 目前的值是: {STORAGE}")
