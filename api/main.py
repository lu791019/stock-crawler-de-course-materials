"""
Stock Price API — 用 FastAPI 把 MySQL 裡的股價開成 REST API

啟動方式（專案根目錄）：
    uv run uvicorn api.main:app --reload --port 8000

互動式文件（Swagger UI）：
    http://localhost:8000/docs
"""
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import create_engine, text

from crawler.config import MYSQL_ACCOUNT, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT

MYSQL_DATABASE = "mydb"

app = FastAPI(
    title="Stock Price API",
    description="台股股價查詢 API — stock-crawler 教學專案的資料出口",
    version="0.1.0",
)

# create_engine 建的是「連線池管理者」（第 5 章講過），app 存活期間重複使用
engine = create_engine(
    f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
)


@app.get("/")
def health():
    """健康檢查：確認 API 活著、資料庫連得上"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "database": f"error: {e}"}


@app.get("/stocks")
def list_stocks():
    """列出資料庫裡有哪些股票、各有幾筆資料"""
    sql = """
        SELECT stock_id, COUNT(*) AS records,
               MIN(date) AS first_date, MAX(date) AS last_date
        FROM TaiwanStockPrice
        GROUP BY stock_id
        ORDER BY stock_id
    """
    df = pd.read_sql(sql, engine)
    return df.to_dict(orient="records")


@app.get("/stocks/{stock_id}/prices")
def get_prices(
    stock_id: str,
    start_date: str | None = Query(None, description="起始日 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="結束日 YYYY-MM-DD"),
    limit: int = Query(30, ge=1, le=1000, description="最多回傳幾筆"),
):
    """查某支股票的歷史股價（可指定日期範圍）"""
    # 一律用參數化查詢（:stock_id），絕不把使用者輸入拼進 SQL 字串 —— 防 SQL Injection
    sql = "SELECT date, stock_id, open, max, min, close, spread, Trading_Volume FROM TaiwanStockPrice WHERE stock_id = :stock_id"
    params = {"stock_id": stock_id}
    if start_date:
        sql += " AND date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        sql += " AND date <= :end_date"
        params["end_date"] = end_date
    sql += " ORDER BY date DESC LIMIT :limit"
    params["limit"] = limit

    df = pd.read_sql(text(sql), engine, params=params)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"找不到 {stock_id} 的資料")
    return df.to_dict(orient="records")


@app.get("/stocks/{stock_id}/latest")
def get_latest(stock_id: str):
    """查某支股票的最新一筆收盤資料"""
    sql = text(
        "SELECT date, stock_id, close, spread, Trading_Volume "
        "FROM TaiwanStockPrice WHERE stock_id = :stock_id "
        "ORDER BY date DESC LIMIT 1"
    )
    df = pd.read_sql(sql, engine, params={"stock_id": stock_id})
    if df.empty:
        raise HTTPException(status_code=404, detail=f"找不到 {stock_id} 的資料")
    return df.to_dict(orient="records")[0]
