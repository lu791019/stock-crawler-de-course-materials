"""
整合測試：upsert 的冪等性（需要真實 MySQL）

先啟動 MySQL 再跑：
    docker compose -f docker-compose-local.yml up -d mysql
    uv run pytest -m integration -v

沒開 MySQL 時會自動 skip，不會讓整個測試suite 紅掉。
驗證第 5 章的核心主張：同一批資料寫幾次，資料庫筆數都不變。
"""
import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from crawler.config import MYSQL_ACCOUNT, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT
from crawler.tasks_crawler_finmind_duplicate import upload_data_to_mysql_duplicate

pytestmark = pytest.mark.integration

TEST_STOCK = "TEST999"   # 專用假代碼，不會撞到真實資料

SAMPLE = pd.DataFrame(
    [
        {"date": "2025-01-02", "stock_id": TEST_STOCK, "Trading_Volume": 100,
         "Trading_money": 1000, "open": 10.0, "max": 11.0, "min": 9.0,
         "close": 10.5, "spread": 0.5, "Trading_turnover": 10},
        {"date": "2025-01-03", "stock_id": TEST_STOCK, "Trading_Volume": 200,
         "Trading_money": 2000, "open": 10.5, "max": 12.0, "min": 10.0,
         "close": 11.0, "spread": 0.5, "Trading_turnover": 20},
    ]
)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/mydb"
    )
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("MySQL 未啟動 —— 先 docker compose -f docker-compose-local.yml up -d mysql")

    # 確保表存在（用 0 列的 DataFrame 觸發 create_all），再清掉舊的測試資料
    upload_data_to_mysql_duplicate(SAMPLE.head(0))
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM TaiwanStockPrice_duplicate WHERE stock_id = :s"),
                     {"s": TEST_STOCK})
    yield eng
    # 測完清乾淨，不留垃圾
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM TaiwanStockPrice_duplicate WHERE stock_id = :s"),
                     {"s": TEST_STOCK})


def _count(engine):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT COUNT(*) FROM TaiwanStockPrice_duplicate WHERE stock_id = :s"),
            {"s": TEST_STOCK},
        ).scalar()


def test_upsert_is_idempotent(engine):
    """寫兩次同一批資料，筆數不變 —— 冪等的直接證明"""
    upload_data_to_mysql_duplicate(SAMPLE)
    first = _count(engine)
    upload_data_to_mysql_duplicate(SAMPLE)   # 故意重跑
    second = _count(engine)
    assert first == second == 2


def test_upsert_updates_value(engine):
    """主鍵相同、值不同 → 應該是更新，不是報錯也不是多一筆"""
    modified = SAMPLE.copy()
    modified.loc[0, "close"] = 999.0
    upload_data_to_mysql_duplicate(modified)

    with engine.connect() as conn:
        close = conn.execute(
            text("SELECT close FROM TaiwanStockPrice_duplicate "
                 "WHERE stock_id = :s AND date = '2025-01-02'"),
            {"s": TEST_STOCK},
        ).scalar()
    assert close == 999.0
    assert _count(engine) == 2               # 筆數還是 2，沒有變 3
