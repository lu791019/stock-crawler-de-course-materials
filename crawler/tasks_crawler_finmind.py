from urllib.parse import quote_plus  # 密碼含 @ : % 等符號時要先做 URL 編碼才能進連線字串

import pandas as pd
import requests
from sqlalchemy import create_engine  # 建立資料庫連線的工具（SQLAlchemy）

from crawler.config import (
    GCP_PROJECT_ID,
    MYSQL_ACCOUNT,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    SPANNER_INSTANCE,
)
from crawler.worker import app


# 教學用: 最簡單版本, 只抓資料並印出, 不上傳資料庫
# 適合剛接觸 Celery 的人, 先確認「任務能被派送、worker 能收到、API 能呼叫」
# 之後再進階到 crawler_finmind (含資料庫寫入)
@app.task()
def crawler_finmind_print(stock_id):
    # FinMind API endpoint, 提供台股歷史股價等免費資料
    url = "https://api.finmindtrade.com/api/v4/data"
    # API 參數: 指定要抓哪個資料集、哪檔股票、日期範圍
    parameter = {
        "dataset": "TaiwanStockPrice",  # 台股日線資料
        "data_id": stock_id,  # 股票代碼, ex: 2330
        "start_date": "2024-01-01",
        "end_date": "2025-06-17",
    }
    # 發送 HTTP GET 請求, 把參數放在 query string
    resp = requests.get(url, params=parameter)
    # 將回傳的 JSON 轉成 Python dict
    data = resp.json()
    # HTTP 200 代表請求成功
    if resp.status_code == 200:
        # data["data"] 是 list of dict, 剛好可以直接轉成 DataFrame
        df = pd.DataFrame(data["data"])
        # 只印出資料, 不做後續處理
        print(df)
    else:
        # 若 API 失敗, 印出錯誤訊息方便排查
        print(data["msg"])


def upload_data_to_mysql(df: pd.DataFrame):
    # 定義資料庫連線字串（MySQL 資料庫）
    # 格式：mysql+pymysql://使用者:密碼@主機:port/資料庫名稱
    # 上傳到 mydb, 同學可切換成自己的 database
    # 密碼要先 quote_plus 做 URL 編碼：連線字串裡 @ 分隔「帳密」與「主機」、: 分隔「主機」與「port」,
    # 密碼本身含這些符號時（強密碼常見）會把字串切歪, 出現 invalid literal for int() 之類的解析錯誤
    address = f"mysql+pymysql://{MYSQL_ACCOUNT}:{quote_plus(MYSQL_PASSWORD)}@{MYSQL_HOST}:{MYSQL_PORT}/mydb"

    # 建立 SQLAlchemy 引擎物件
    engine = create_engine(address)

    # 多個 worker 同時首次寫入時，可能同時嘗試建表導致衝突
    # 第一次失敗後重試一次即可（表已被另一個 worker 建好）
    try:
        df.to_sql(
            "TaiwanStockPrice",
            con=engine,
            if_exists="append",
            index=False,
        )
    except Exception:
        df.to_sql(
            "TaiwanStockPrice",
            con=engine,
            if_exists="append",
            index=False,
        )


def upload_data_to_bigquery_raw(df: pd.DataFrame):
    # 雙寫的 BigQuery 半邊: 抓完的資料直接 append 進 raw 層（手冊15 詳細介紹）
    # 沒設 GCP_PROJECT_ID（本機環境）就明確略過, MySQL 那份不受影響
    if not GCP_PROJECT_ID:
        print("BQ 未設定，略過雲端寫入")
        return
    try:
        from crawler.bigquery import (
            create_dataset_if_not_exists,
            create_table_if_not_exists,
            taiwan_stock_price_bq_schema,
            upload_data_to_bigquery,
        )

        bq_df = df.copy()
        # to_sql 可以吃字串日期, BigQuery 的 DATE 欄位要先轉成 date 型別
        bq_df["date"] = pd.to_datetime(bq_df["date"]).dt.date
        # 第一次寫入前把 dataset 與帶日期分區的表準備好, 之後每次都只是 append
        create_dataset_if_not_exists("raw")
        create_table_if_not_exists(
            "TaiwanStockPrice", taiwan_stock_price_bq_schema(),
            dataset_id="raw", partition_key="date",
        )
        upload_data_to_bigquery("TaiwanStockPrice", bq_df, dataset_id="raw", mode="append")
    except Exception as e:
        # 分析副本寫入失敗不能擋住爬蟲主職（MySQL 已寫完）, 印明確錯誤方便排查
        print(f"BigQuery 寫入失敗（MySQL 不受影響）: {e}")


def upload_data_to_spanner_if_configured(df: pd.DataFrame):
    # 手冊16 Spanner 節的體驗開關: 設了 SPANNER_INSTANCE 才多寫一份到 Spanner
    # 平常（主線）不設定, 這個函式什麼都不做
    if not SPANNER_INSTANCE:
        return
    try:
        from crawler.spanner import upload_data_to_spanner

        upload_data_to_spanner(df)
    except Exception as e:
        # 跟 BigQuery 同一條紀律: 體驗副本失敗不擋爬蟲主職
        print(f"Spanner 寫入失敗（MySQL/BigQuery 不受影響）: {e}")


# 註冊 task, 有註冊的 task 才可以變成任務發送給 rabbitmq
@app.task()
def crawler_finmind(stock_id):
    # FinMind API endpoint, 提供台股歷史股價等免費資料
    url = "https://api.finmindtrade.com/api/v4/data"
    # API 參數: 指定要抓哪個資料集、哪檔股票、日期範圍
    parameter = {
        "dataset": "TaiwanStockPrice",  # 台股日線資料
        "data_id": stock_id,  # 股票代碼, ex: 2330
        "start_date": "2024-01-01",
        "end_date": "2025-06-17",
    }
    # 發送 HTTP GET 請求, 把參數放在 query string
    resp = requests.get(url, params=parameter)
    # 將回傳的 JSON 轉成 Python dict
    data = resp.json()
    # HTTP 200 代表請求成功
    if resp.status_code == 200:
        # data["data"] 是 list of dict, 剛好可以直接轉成 DataFrame
        df = pd.DataFrame(data["data"])
        print(df)
        # print("upload db")
        # 雙寫: 同一份資料寫 MySQL（營運用）＋ BigQuery raw 層（分析用）
        upload_data_to_mysql(df)
        upload_data_to_bigquery_raw(df)
        # 手冊16 Spanner 體驗: 有設 SPANNER_INSTANCE 才會多寫一份
        upload_data_to_spanner_if_configured(df)
        # 同時存一份 CSV
        df.to_csv(f"output/TaiwanStockPrice_{stock_id}.csv", index=False, encoding="utf-8-sig")
        print(f"TaiwanStockPrice_{stock_id}.csv saved.")
    else:
        # 若 API 失敗, 印出錯誤訊息方便排查
        print(data["msg"])
