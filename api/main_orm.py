"""
Stock Price API（ORM 版）— 與 api/main.py 完全相同的四支端點，改用 SQLAlchemy ORM 查詢

這是手冊補充B「附錄一」的對照版本，不屬於教學主線：
    SQL 版（主線）：api/main.py     — 手寫 SQL 字串 + pd.read_sql
    ORM 版（本檔）：api/main_orm.py — Model class + select()，SQL 由 SQLAlchemy 生成

建議讀法：開兩個編輯器分頁，同一支端點左右對照著看——
「函式簽名（參數）完全一樣，差的只是撈資料那幾行」。

啟動方式（專案根目錄，可與 SQL 版同時開、互不干擾）：
    uv run uvicorn api.main_orm:app --reload --port 8001

互動式文件（Swagger UI）：
    http://localhost:8001/docs
"""
from datetime import date as date_type   # 跟欄位名 date 撞名，改個名字避開
from decimal import Decimal              # MySQL 的 DECIMAL 欄位對應 Python 的 Decimal

from fastapi import FastAPI, HTTPException, Query
# select / func：用 Python 語法「組」SQL 的積木；text 只在健康檢查用到
from sqlalchemy import BigInteger, Date, Numeric, String, create_engine, func, select, text
# ORM 的四個核心：
#   DeclarativeBase — 所有 Model class 的共同父類別
#   Mapped / mapped_column — 宣告「這個 class 屬性對應到表的哪個欄位、什麼型別」
#   Session — 一次資料庫「工作階段」：查詢透過它執行
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
# 寫完之後的回報：查詢不再寫 SQL 字串，拿回來的每一列都是「有屬性的物件」。
class Base(DeclarativeBase):
    pass


class StockPrice(Base):
    """對應 MySQL 的 TaiwanStockPrice 表——欄位名、型別要跟表一致

    讀法示範：
        Mapped[str]  → 這個屬性在 Python 端是 str
        mapped_column(String(10)) → 在 MySQL 端是 VARCHAR(10)
    一行宣告，同時講清楚兩個世界的型別——這就是「Mapping（映射）」的意思。
    """

    __tablename__ = "TaiwanStockPrice"   # 對應到資料庫裡的哪張表

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
    # select(...) 開始組一句查詢；func.count() 等對應 SQL 的聚合函數；
    # .label("records") 就是 SQL 的 AS records（幫欄位取別名）
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
    # Session：一次資料庫工作階段。with 寫法確保用完自動歸還連線
    with Session(engine) as session:
        # .mappings() 把每一列轉成「欄位名 → 值」的 dict 形式
        # （這支查的是聚合結果，不是完整的 StockPrice 物件，所以用 mappings 而不是 scalars）
        rows = session.execute(stmt).mappings().all()
    return [dict(r) for r in rows]


@app.get("/stocks/{stock_id}/prices")
def get_prices(
    # 函式簽名與 SQL 版一字不差——路徑參數、查詢參數、驗證規則都是 FastAPI 的事，
    # 跟你用哪種方式撈資料無關
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
    # select(StockPrice) → SELECT 整列；.where(...) → WHERE 條件
    # 注意 == 不是打錯：這裡是「組查詢條件」，不是比較大小
    stmt = select(StockPrice).where(StockPrice.stock_id == stock_id)
    # 選填參數有給才疊條件——對照 SQL 版的「sql += " AND ..."」
    if start_date:
        stmt = stmt.where(StockPrice.date >= start_date)
    if end_date:
        stmt = stmt.where(StockPrice.date <= end_date)
    stmt = stmt.order_by(StockPrice.date.desc()).limit(limit)

    with Session(engine) as session:
        # .scalars() 把每一列取成 StockPrice 物件（查整列時用它）
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
        # .first()：拿第一筆，沒有就回 None（對照 SQL 版檢查 df.empty）
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
