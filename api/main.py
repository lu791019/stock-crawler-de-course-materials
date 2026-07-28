"""
Stock Price API — 用 FastAPI 把 MySQL 裡的股價開成 REST API

這支檔案做的事：定義四支「查詢端點」，讓外部程式不用碰資料庫，
就能透過 HTTP 拿到股價資料（手冊補充B 的主線實作）。

啟動方式（專案根目錄）：
    uv run uvicorn api.main:app --reload --port 8000
    # uvicorn 是 ASGI 伺服器：FastAPI 只「定義」API，開 port、收請求的是 uvicorn
    # api.main:app 的讀法是「模組路徑:變數名」→ 去 api/main.py 裡找叫 app 的物件
    # --reload：開發模式，存檔自動重啟（上線不開）

互動式文件（Swagger UI）：
    http://localhost:8000/docs
"""
import os

import pandas as pd                                    # 查詢結果 → DataFrame → JSON
from fastapi import FastAPI, HTTPException, Query      # 框架本體、標準錯誤回應、查詢參數驗證
from sqlalchemy import create_engine, text             # 連線池 + 參數化 SQL（防注入的關鍵）

# 資料庫帳密從 crawler/config.py 來（它讀 .env）——絕不把帳密寫死在程式碼裡
from crawler.config import MYSQL_ACCOUNT, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT

MYSQL_DATABASE = "mydb"

# Cloud Run 部署時（第 17 章）由 --set-env-vars 提供；本機與 VM 都沒設這個變數, 走原本的 TCP 路
# Cloud Run 連 Cloud SQL 不走公網 IP: --add-cloudsql-instances 會把資料庫掛成
# /cloudsql/{連線名稱} 的 unix socket, 連線走 Google 內部通道, 不需要授權網路
MYSQL_UNIX_SOCKET = os.environ.get("MYSQL_UNIX_SOCKET")

# 建立 FastAPI 應用程式物件。title / description 會顯示在 /docs 頁面的最上方
app = FastAPI(
    title="Stock Price API",
    description="台股股價查詢 API — stock-crawler 教學專案的資料出口",
    version="0.1.0",
)

# create_engine 建的是「連線池管理者」（第 5 章講過），app 存活期間重複使用
# 注意：這裡「還沒有」真的連上資料庫——第一次執行查詢時才會建立連線
if MYSQL_UNIX_SOCKET:
    # Cloud Run: 走 unix socket, URL 的 host:port 留空、socket 路徑放 query string
    _db_url = (
        f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}@/{MYSQL_DATABASE}"
        f"?unix_socket={MYSQL_UNIX_SOCKET}"
    )
else:
    # 本機 / VM: 走 TCP, 跟第 5 章以來完全相同
    _db_url = f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

engine = create_engine(_db_url)


# @app.get("/") 是「路由裝飾器」：把下面的函式登記成「GET / 這個路徑的處理者」
# 模式跟 Celery 的 @app.task() 一樣——裝飾器把普通函式註冊進框架
@app.get("/")
def health():
    """健康檢查：確認 API 活著、資料庫連得上

    實務上每個服務都該有這支：監控系統定期打它，掛了馬上知道。
    """
    try:
        # 對資料庫丟一句最便宜的 SQL（SELECT 1），連得上就代表 DB 正常
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        # DB 連不上時 API 本身還是要活著回話——回報 degraded（部分失能）而不是整個炸掉，
        # 呼叫方看 status 欄位就知道該不該繼續打
        return {"status": "degraded", "database": f"error: {e}"}


@app.get("/stocks")
def list_stocks():
    """列出資料庫裡有哪些股票、各有幾筆資料"""
    # 純聚合查詢：每支股票一列，附筆數與資料起訖日
    sql = """
        SELECT stock_id, COUNT(*) AS records,
               MIN(date) AS first_date, MAX(date) AS last_date
        FROM TaiwanStockPrice
        GROUP BY stock_id
        ORDER BY stock_id
    """
    # pd.read_sql：執行 SQL、把結果直接裝進 DataFrame（第 6 章用過的老朋友）
    df = pd.read_sql(sql, engine)
    # to_dict(orient="records")：DataFrame → list of dict，
    # FastAPI 會自動把它序列化成 JSON 回給呼叫方
    return df.to_dict(orient="records")


# 路徑裡的 {stock_id} 是「路徑參數」：GET /stocks/2330/prices → stock_id = "2330"
# 函式簽名裡的其他參數（start_date / end_date / limit）是「查詢參數」：
#   GET /stocks/2330/prices?start_date=2025-01-01&limit=5
# 區分原則：資源的「身分」放路徑，對結果的「過濾」放查詢字串
@app.get("/stocks/{stock_id}/prices")
def get_prices(
    stock_id: str,
    # Query(None) → 選填參數，不給就是 None；description 會顯示在 /docs
    start_date: str | None = Query(None, description="起始日 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="結束日 YYYY-MM-DD"),
    # Query(30, ge=1, le=1000) → 預設 30、必須介於 1~1000
    # 這行型別註記就是驗證邏輯本體：傳 limit=5000 會被 FastAPI 自動擋下、回 422
    limit: int = Query(30, ge=1, le=1000, description="最多回傳幾筆"),
):
    """查某支股票的歷史股價（可指定日期範圍）"""
    # 一律用參數化查詢（:stock_id），絕不把使用者輸入拼進 SQL 字串 —— 防 SQL Injection
    # :stock_id 是「佔位符」：值走 params dict 另外送，資料庫永遠把它當「值」處理，
    # 就算有人傳 "2330' OR '1'='1" 也只是一個查不到的股票代碼，變不成 SQL 語法
    sql = "SELECT date, stock_id, open, max, min, close, spread, Trading_Volume FROM TaiwanStockPrice WHERE stock_id = :stock_id"
    params = {"stock_id": stock_id}
    # 選填參數有給才加進 WHERE——SQL 條件跟著參數動態長大，但佔位符規則不變
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
        # 查無資料回標準的 404（Not Found）＋看得懂的訊息，
        # 呼叫方能用狀態碼判斷，而不是收到空陣列還要猜是「沒資料」還是「打錯了」
        raise HTTPException(status_code=404, detail=f"找不到 {stock_id} 的資料")
    return df.to_dict(orient="records")


@app.get("/stocks/{stock_id}/latest")
def get_latest(stock_id: str):
    """查某支股票的最新一筆收盤資料"""
    # ORDER BY date DESC LIMIT 1 —— 跟第 8 章 Metabase 數字卡片同一招
    sql = text(
        "SELECT date, stock_id, close, spread, Trading_Volume "
        "FROM TaiwanStockPrice WHERE stock_id = :stock_id "
        "ORDER BY date DESC LIMIT 1"
    )
    df = pd.read_sql(sql, engine, params={"stock_id": stock_id})
    if df.empty:
        raise HTTPException(status_code=404, detail=f"找不到 {stock_id} 的資料")
    # 只有一筆，回單一物件（dict）而不是包一層陣列——呼叫方少拆一層
    return df.to_dict(orient="records")[0]
