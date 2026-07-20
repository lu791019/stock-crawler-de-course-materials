"""
Stock Price API（ORM 版）— 與 api/main.py 完全相同的四支端點，改用 SQLAlchemy ORM 查詢

這是手冊補充B 附錄的對照版本，不屬於教學主線：
    SQL 版（主線）：api/main.py     — 手寫 SQL 字串 + pd.read_sql
    ORM 版（本檔）：api/main_orm.py — Model class + select()，SQL 由 SQLAlchemy 生成

啟動方式（專案根目錄，可與 SQL 版同時開、互不干擾）：
    uv run uvicorn api.main_orm:app --reload --port 8001

互動式文件（Swagger UI）：
    http://localhost:8001/docs
"""
from datetime import date as date_type
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import BigInteger, Date, Numeric, String, create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from crawler.config import MYSQL_ACCOUNT, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT

MYSQL_DATABASE = "mydb"

app = FastAPI(
    title="Stock Price API (ORM)",
    description="台股股價查詢 API — ORM 版，與 api/main.py（SQL 版）對照用",
    version="0.1.0",
)

# 連線池跟 SQL 版一模一樣 —— ORM 是疊在 engine 上面的一層，不是取代它
engine = create_engine(
    f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
)


# ── ORM 的第一步：把 table 描述成 Python class（叫 Model）──
# 這是 SQL 版完全沒有的前置成本：每張要查的表都要先寫一個 class。
class Base(DeclarativeBase):
    pass


class StockPrice(Base):
    """對應 MySQL 的 TaiwanStockPrice 表——欄位名、型別要跟表一致"""

    __tablename__ = "TaiwanStockPrice"

    # ORM 規定 Model 一定要宣告主鍵。TaiwanStockPrice 的 mock 表沒設主鍵，
    # 沒關係：主鍵宣告在 Model 上就好（date + stock_id 一天一股一筆，天然唯一）
    date: Mapped[date_type] = mapped_column(Date, primary_key=True)
    stock_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    Trading_Volume: Mapped[int] = mapped_column(BigInteger)
    Trading_money: Mapped[int] = mapped_column(BigInteger)
    open: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    max: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    min: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    close: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    spread: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    Trading_turnover: Mapped[int] = mapped_column(BigInteger)


@app.get("/")
def health():
    """健康檢查：跟 SQL 版一模一樣——連線測試不需要 ORM"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "database": f"error: {e}"}


@app.get("/stocks")
def list_stocks():
    """列出資料庫裡有哪些股票、各有幾筆資料

    SQL 版寫 GROUP BY 字串；ORM 版用 func.count / func.min / func.max 組出同一句 SQL。
    """
    stmt = (
        select(
            StockPrice.stock_id,
            func.count().label("records"),
            func.min(StockPrice.date).label("first_date"),
            func.max(StockPrice.date).label("last_date"),
        )
        .group_by(StockPrice.stock_id)
        .order_by(StockPrice.stock_id)
    )
    with Session(engine) as session:
        rows = session.execute(stmt).mappings().all()
    return [dict(r) for r in rows]


@app.get("/stocks/{stock_id}/prices")
def get_prices(
    stock_id: str,
    start_date: str | None = Query(None, description="起始日 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="結束日 YYYY-MM-DD"),
    limit: int = Query(30, ge=1, le=1000, description="最多回傳幾筆"),
):
    """查某支股票的歷史股價（可指定日期範圍）

    對照 SQL 版的重點：
    - SQL 版動態加條件是「拼字串 + params dict」；ORM 版是「.where() 一路疊上去」
    - 參數化自動發生：stock_id 的值永遠被當成「值」送進 SQL，防注入效果與 :佔位符相同
    """
    stmt = select(StockPrice).where(StockPrice.stock_id == stock_id)
    if start_date:
        stmt = stmt.where(StockPrice.date >= start_date)
    if end_date:
        stmt = stmt.where(StockPrice.date <= end_date)
    stmt = stmt.order_by(StockPrice.date.desc()).limit(limit)

    with Session(engine) as session:
        rows = session.scalars(stmt).all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"找不到 {stock_id} 的資料")
    # ORM 拿回的是 StockPrice 物件（rows[0].close 用屬性存取），要自己轉 dict 回 JSON；
    # SQL 版的 DataFrame 一行 to_dict 就好 —— 這是「物件 vs 表格」取向的差異
    return [
        {
            "date": r.date,
            "stock_id": r.stock_id,
            "open": r.open,
            "max": r.max,
            "min": r.min,
            "close": r.close,
            "spread": r.spread,
            "Trading_Volume": r.Trading_Volume,
        }
        for r in rows
    ]


@app.get("/stocks/{stock_id}/latest")
def get_latest(stock_id: str):
    """查某支股票的最新一筆收盤資料"""
    stmt = (
        select(StockPrice)
        .where(StockPrice.stock_id == stock_id)
        .order_by(StockPrice.date.desc())
        .limit(1)
    )
    with Session(engine) as session:
        row = session.scalars(stmt).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"找不到 {stock_id} 的資料")
    return {
        "date": row.date,
        "stock_id": row.stock_id,
        "close": row.close,
        "spread": row.spread,
        "Trading_Volume": row.Trading_Volume,
    }
