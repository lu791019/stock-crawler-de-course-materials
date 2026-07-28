"""
Sync MySQL to BigQuery Script
用於將 MySQL 台股股價資料同步到 BigQuery
"""
import pandas as pd

from crawler.bigquery import (
    create_dataset_if_not_exists,
    create_table,
    upload_data_to_bigquery,
    drop_table_if_exists,
    taiwan_stock_price_bq_schema,
)
from crawler.mysql import query_to_dataframe

tables_config = [
    {
        "mysql_table": "TaiwanStockPrice",
        "bq_table": "TaiwanStockPrice",
        "schema_func": taiwan_stock_price_bq_schema,
        "partition_key": "date",
    },
]


def sync_mysql_to_bigquery():
    """將 MySQL 台股股價資料同步到 BigQuery"""
    create_dataset_if_not_exists()

    for config in tables_config:
        try:
            table_name = config["mysql_table"]
            print(f"開始同步 {table_name} 到 BigQuery...")
            drop_table_if_exists(table_name=config["bq_table"])
            schema = config["schema_func"]()
            create_table(
                table_name=config["bq_table"],
                schema=schema,
                partition_key=config["partition_key"],
            )
            sql = f"SELECT * FROM {table_name}"
            df = query_to_dataframe(sql=sql)
            # 分區欄一律轉成真正的日期型別再上傳。
            # 來源表若是 to_sql 自動建的, date 會是文字(text)欄位,
            # 而 BigQuery 的 DAY 分區只接受 DATE/DATETIME/TIMESTAMP——不轉會被 400 擋下
            pk = config["partition_key"]
            df[pk] = pd.to_datetime(df[pk]).dt.date
            upload_data_to_bigquery(table_name=config["bq_table"], df=df, mode="replace")
            print(f"{table_name} 同步完成")
        except Exception as e:
            table_name = config["mysql_table"]
            print(f"{table_name} 同步失敗: {e}")
            raise


def main():
    print("開始執行 MySQL 到 BigQuery 的同步...")
    sync_mysql_to_bigquery()
    print("MySQL 到 BigQuery 的同步完成")


if __name__ == "__main__":
    main()
