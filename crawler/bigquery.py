"""
BigQuery 工具模組
提供 BigQuery 的資料上傳、View 建立等操作功能
使用前須設定環境變數 GCP_PROJECT_ID（沒設定時呼叫端應先檢查、略過 BQ 操作）
"""
import os

import pandas as pd
from google.cloud import bigquery
from google.cloud.bigquery import SchemaField, LoadJobConfig, WriteDisposition

from crawler.config import GCP_PROJECT_ID as PROJECT_ID

# 同步落地的 dataset：手冊15 主線設 BQ_DATASET=raw（三層的入口）；
# 不設就用 stock（手冊17 排程 DAG 沿用）
DATASET_ID = os.environ.get("BQ_DATASET", "stock")


def get_bigquery_client():
    """建立 BigQuery 客戶端"""
    return bigquery.Client(project=PROJECT_ID)


def create_dataset_if_not_exists(dataset_id: str = DATASET_ID):
    """建立 BigQuery Dataset（如果不存在）"""
    client = get_bigquery_client()
    dataset_ref = client.dataset(dataset_id)
    try:
        client.get_dataset(dataset_ref)
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset)
        print(f"Created dataset {dataset_id}")


def taiwan_stock_price_bq_schema():
    """定義 TaiwanStockPrice 表的 BigQuery schema"""
    return [
        bigquery.SchemaField(name="date", field_type="DATE"),
        bigquery.SchemaField(name="stock_id", field_type="STRING"),
        bigquery.SchemaField(name="Trading_Volume", field_type="INTEGER"),
        bigquery.SchemaField(name="Trading_money", field_type="INTEGER"),
        bigquery.SchemaField(name="open", field_type="FLOAT"),
        bigquery.SchemaField(name="max", field_type="FLOAT"),
        bigquery.SchemaField(name="min", field_type="FLOAT"),
        bigquery.SchemaField(name="close", field_type="FLOAT"),
        bigquery.SchemaField(name="spread", field_type="FLOAT"),
        bigquery.SchemaField(name="Trading_turnover", field_type="INTEGER"),
    ]


def create_table(table_name: str, schema, dataset_id: str = DATASET_ID, partition_key: str = None):
    """建立 BigQuery 表格"""
    client = get_bigquery_client()
    table_id = f"{PROJECT_ID}.{dataset_id}.{table_name}"
    table = bigquery.Table(table_id, schema=schema)
    if partition_key:
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partition_key,
        )
    table = client.create_table(table)
    print(f"表格 {table_id} 建立成功")


def create_table_if_not_exists(table_name: str, schema, dataset_id: str = DATASET_ID, partition_key: str = None):
    """表格不存在才建立——雙寫的 append 需要先有帶分區的表, 已存在就不動它"""
    client = get_bigquery_client()
    table_id = f"{PROJECT_ID}.{dataset_id}.{table_name}"
    try:
        client.get_table(table_id)
    except Exception:
        create_table(table_name, schema, dataset_id, partition_key)


def upload_data_to_bigquery(table_name: str, df: pd.DataFrame, dataset_id: str = DATASET_ID, mode: str = "replace"):
    """上傳 DataFrame 到 BigQuery"""
    client = get_bigquery_client()
    table_id = f"{PROJECT_ID}.{dataset_id}.{table_name}"
    write_disp = WriteDisposition.WRITE_TRUNCATE if mode == "replace" else WriteDisposition.WRITE_APPEND
    job_config = LoadJobConfig(write_disposition=write_disp, autodetect=True)
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    print(f"資料已上傳到 BigQuery 表 '{table_name}'，共 {len(df)} 筆記錄")


def create_view(view_name: str, view_sql: str, dataset_id: str = DATASET_ID):
    """在 BigQuery 中建立或替換 View"""
    client = get_bigquery_client()
    view_id = f"{PROJECT_ID}.{dataset_id}.{view_name}"
    create_dataset_if_not_exists(dataset_id)
    view = bigquery.Table(view_id)
    view.view_query = view_sql
    try:
        client.update_table(view, ["view_query"])
        print(f"更新 BigQuery View '{view_name}' 成功")
    except Exception:
        view = client.create_table(view)
        print(f"建立 BigQuery View '{view_name}' 成功")


def create_table_from_view(view_name: str, table_name: str, dataset_id: str = DATASET_ID):
    """從 BigQuery View 建立實體 Table"""
    client = get_bigquery_client()
    source_view_id = f"{PROJECT_ID}.{dataset_id}.{view_name}"
    dest_table_id = f"{PROJECT_ID}.{dataset_id}.{table_name}"
    try:
        client.delete_table(dest_table_id)
    except Exception:
        pass
    sql = f"SELECT * FROM `{source_view_id}`"
    job_config = bigquery.QueryJobConfig(
        destination=dest_table_id,
        write_disposition=WriteDisposition.WRITE_TRUNCATE,
    )
    query_job = client.query(sql, job_config=job_config)
    query_job.result()
    count_result = client.query(f"SELECT COUNT(*) as count FROM `{dest_table_id}`").result()
    count = list(count_result)[0].count
    print(f"成功建立 BigQuery Table '{table_name}'，共 {count} 筆記錄")


def drop_table_if_exists(table_name: str, dataset_id: str = DATASET_ID):
    """刪除 BigQuery 表格（如果存在）"""
    client = get_bigquery_client()
    table_id = f"{PROJECT_ID}.{dataset_id}.{table_name}"
    try:
        client.delete_table(table_id)
        print(f"表格 {table_id} 已刪除")
    except Exception:
        pass
