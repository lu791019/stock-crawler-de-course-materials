"""
MySQL 工具模組
提供 MySQL 的 View 建立、資料查詢等操作功能
"""
import pandas as pd
from sqlalchemy import create_engine, text

from crawler.config import MYSQL_ACCOUNT, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT

MYSQL_DATABASE = "mydb"


def _get_engine():
    address = f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    return create_engine(address)


def upload_data_to_mysql(table_name: str, df: pd.DataFrame, mode: str = "replace"):
    """上傳 DataFrame 到 MySQL"""
    engine = _get_engine()
    with engine.connect() as connection:
        df.to_sql(table_name, con=connection, if_exists=mode, index=False)
    print(f"資料已上傳到表 '{table_name}'，共 {len(df)} 筆記錄")


def create_view(view_name: str, view_sql: str):
    """在 MySQL 中建立或替換 View"""
    engine = _get_engine()
    with engine.begin() as connection:
        connection.execute(text(view_sql))
    print(f"View '{view_name}' 建立成功")


def create_table_from_view(view_name: str, table_name: str):
    """從 View 建立實體 Table（先刪後建）"""
    engine = _get_engine()
    with engine.begin() as connection:
        connection.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        connection.execute(text(f"CREATE TABLE {table_name} AS SELECT * FROM {view_name}"))
        result = connection.execute(text(f"SELECT COUNT(*) as count FROM {table_name}"))
        count = result.fetchone()[0]
    print(f"成功建立 Table '{table_name}'，共 {count} 筆記錄")


def query_to_dataframe(sql: str) -> pd.DataFrame:
    """執行 SQL 查詢並返回 DataFrame"""
    engine = _get_engine()
    df = pd.read_sql(sql, engine)
    print(f"查詢執行成功，返回 DataFrame，共 {len(df)} 筆記錄")
    return df


def execute_query(sql: str):
    """執行 SQL 查詢並返回字典列表"""
    engine = _get_engine()
    with engine.connect() as connection:
        result = connection.execute(text(sql))
        columns = list(result.keys())
        rows = [{columns[i]: v for i, v in enumerate(row)} for row in result.fetchall()]
    print(f"查詢執行成功，返回 {len(rows)} 筆記錄")
    return rows
