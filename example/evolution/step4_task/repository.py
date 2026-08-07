"""
Step 3 的資料儲存層（repository）: 只負責「怎麼把資料存下去」。

這個檔案的邊界:
    知道 CSV 要存哪個目錄、MySQL 的連線字串與資料表名稱。
    不知道資料是從 FinMind 來的, 也不知道資料被整理過什麼。

換儲存目標（CSV → MySQL → BigQuery）時, 只有這個檔案要改。
對應 Step 1 的 save() 函式, 差別是兩種儲存方式各自獨立成函式, 並由設定決定要用哪些。
"""
import os

import pandas as pd
from sqlalchemy import create_engine

from config import (
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


# 儲存目標名稱與實作的對照表。
# 要加第三種儲存方式（例如 BigQuery）, 就多寫一個函式再加進這張表。
SAVERS = {
    "csv": save_to_csv,
    "mysql": save_to_mysql,
}


def save(df: pd.DataFrame, stock_id: str):
    """依 config 的 STORAGE 設定, 依序寫入指定的儲存目標。

    STORAGE=csv        只寫 CSV
    STORAGE=mysql      只寫 MySQL
    STORAGE=csv,mysql  兩個都寫, 也就是課程正式版說的雙寫

    名稱不在對照表裡就直接丟例外, 不做略過處理。
    設定值打錯時要立刻知道, 不能安靜地什麼都沒存。
    """
    targets = [name.strip() for name in STORAGE.split(",") if name.strip()]

    if not targets:
        raise ValueError("STORAGE 不能是空值, 至少要指定一個儲存目標")

    for name in targets:
        if name not in SAVERS:
            raise ValueError(f"STORAGE 只接受 {list(SAVERS)}, 收到的值是: {name}")
        SAVERS[name](df, stock_id)
