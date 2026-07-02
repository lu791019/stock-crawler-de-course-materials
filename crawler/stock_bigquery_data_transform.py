"""
Stock BigQuery Data Transform
用於在 BigQuery 中建立台股股價相關的檢視表和實體表
"""
from crawler.bigquery import (
    create_view,
    create_table_from_view,
    PROJECT_ID,
    DATASET_ID,
)


def create_stock_price_daily_view_and_table():
    """在 BigQuery 中建立台股每日股價 View 和 Table"""
    view_sql = f"""
    SELECT
      t.stock_id,
      t.date AS trade_date,
      t.open,
      t.max,
      t.min,
      t.close,
      t.spread,
      t.Trading_Volume,
      t.Trading_turnover
    FROM (
      SELECT
        s.*,
        ROW_NUMBER() OVER (
          PARTITION BY s.stock_id, s.date
          ORDER BY s.Trading_Volume DESC
        ) AS rn
      FROM `{PROJECT_ID}.{DATASET_ID}.TaiwanStockPrice` s
    ) AS t
    WHERE t.rn = 1
    """
    create_view(view_name="vw_stock_price_daily", view_sql=view_sql)
    create_table_from_view(view_name="vw_stock_price_daily", table_name="stock_price_daily")
    print("BigQuery 台股每日股價 View 和 Table 建立完成")


def create_stock_trend_analysis_view_and_table():
    """建立台股趨勢分析 View 和 Table"""
    trend_sql = f"""
    SELECT
      stock_id,
      trade_date,
      open,
      close,
      Trading_Volume,
      LAG(close) OVER (PARTITION BY stock_id ORDER BY trade_date) AS prev_close,
      close - LAG(close) OVER (PARTITION BY stock_id ORDER BY trade_date) AS daily_change,
      AVG(close) OVER (
        PARTITION BY stock_id
        ORDER BY trade_date
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
      ) AS ma5,
      AVG(close) OVER (
        PARTITION BY stock_id
        ORDER BY trade_date
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
      ) AS ma20
    FROM `{PROJECT_ID}.{DATASET_ID}.vw_stock_price_daily`
    """
    create_view(view_name="vw_stock_trend_analysis", view_sql=trend_sql)
    create_table_from_view(view_name="vw_stock_trend_analysis", table_name="stock_trend_analysis")
    print("BigQuery 台股趨勢分析 View 和 Table 建立完成")


def create_daily_summary_view_and_table():
    """建立每日市場匯總 View 和 Table"""
    summary_sql = f"""
    SELECT
      trade_date,
      COUNT(DISTINCT stock_id) AS active_stocks,
      SUM(Trading_Volume) AS total_volume,
      AVG(close) AS avg_close,
      SUM(CASE WHEN daily_change > 0 THEN 1 ELSE 0 END) AS up_count,
      SUM(CASE WHEN daily_change < 0 THEN 1 ELSE 0 END) AS down_count,
      CURRENT_DATETIME() AS created_at
    FROM `{PROJECT_ID}.{DATASET_ID}.stock_trend_analysis`
    WHERE trade_date IS NOT NULL
    GROUP BY trade_date
    ORDER BY trade_date DESC
    """
    create_view(view_name="vw_market_daily_summary", view_sql=summary_sql)
    create_table_from_view(view_name="vw_market_daily_summary", table_name="market_daily_summary")
    print("BigQuery 每日市場匯總 View 和 Table 建立完成")


def main():
    print("開始執行 Stock BigQuery Data Transform...")
    create_stock_price_daily_view_and_table()
    create_stock_trend_analysis_view_and_table()
    create_daily_summary_view_and_table()
    print("Stock BigQuery Data Transform 完成！")


if __name__ == "__main__":
    main()
