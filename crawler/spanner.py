"""
Cloud Spanner 工具模組（手冊16 Spanner 節體驗用）
把爬蟲抓到的股價寫進 Spanner 的 TaiwanStockPrice 表——
用 insert_or_update（主鍵 upsert）, 同一筆資料重跑不會疊重複列,
正好與 MySQL 的 upsert（第 6 章）同陣營、與 BigQuery raw 的 append 對照。
使用前須設定環境變數 SPANNER_INSTANCE（沒設時呼叫端應略過）
"""
import pandas as pd
from google.cloud import spanner

from crawler.config import SPANNER_DATABASE, SPANNER_INSTANCE, SPANNER_PROJECT_ID

COLUMNS = [
    "stock_id", "date", "Trading_Volume", "Trading_money",
    "open", "max", "min", "close", "spread", "Trading_turnover",
]


def upload_data_to_spanner(df: pd.DataFrame, table_name: str = "TaiwanStockPrice"):
    """把 DataFrame upsert 進 Spanner（主鍵 stock_id+date, 重跑冪等）"""
    client = spanner.Client(project=SPANNER_PROJECT_ID)
    database = client.instance(SPANNER_INSTANCE).database(SPANNER_DATABASE)

    rows = df[COLUMNS].copy()
    # 日期欄轉成 date 型別, 數值欄轉原生 int/float（Spanner client 不吃 numpy 型別）
    rows["date"] = pd.to_datetime(rows["date"]).dt.date
    values = [
        [
            str(r.stock_id), r.date,
            int(r.Trading_Volume), int(r.Trading_money),
            float(r.open), float(r.max), float(r.min), float(r.close),
            float(r.spread), int(r.Trading_turnover),
        ]
        for r in rows.itertuples()
    ]

    # mutation 一批上限受限, 分批送（每批 500 列在課程資料量下綽綽有餘）
    with database.batch() as batch:
        for i in range(0, len(values), 500):
            batch.insert_or_update(table=table_name, columns=COLUMNS, values=values[i:i + 500])
    print(f"資料已 upsert 到 Spanner 表 '{table_name}'，共 {len(values)} 筆記錄")
