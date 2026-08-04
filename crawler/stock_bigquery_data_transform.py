"""
Stock BigQuery Data Transform
用於在 BigQuery 中建立台股股價相關的檢視表和實體表

兩組函式：
- create_stage_layer / create_app_layer：維護手冊15 的三層（raw→stage→app），
  雙寫落 raw 之後由手冊17 的排程 DAG 每日重算
- create_*_view_and_table 三支：舊版單一 dataset 的轉換（讀碼教材，保留）
"""
from crawler.bigquery import (
    create_dataset_if_not_exists,
    create_view,
    create_table_from_view,
    get_bigquery_client,
    PROJECT_ID,
    DATASET_ID,
)


def create_stage_layer():
    """重算 stage 層：從 raw 去重、統一欄名（手冊15 Step 3 的 SQL）

    stage 是 view——raw 進了新資料它自動跟上, 這裡的「重算」其實只是
    確保 view 定義存在（CREATE OR REPLACE 是冪等的, 重跑無害）
    """
    create_dataset_if_not_exists("stage")
    sql = f"""
    CREATE OR REPLACE VIEW `{PROJECT_ID}.stage.stock_price_daily` AS
    SELECT stock_id, date AS trade_date, open, max, min, close, spread,
           Trading_Volume AS volume, Trading_money AS amount
    FROM (
      SELECT s.*, ROW_NUMBER() OVER (PARTITION BY stock_id, date ORDER BY Trading_Volume DESC) AS rn
      FROM `{PROJECT_ID}.raw.TaiwanStockPrice` s
    ) WHERE rn = 1
    """
    get_bigquery_client().query(sql).result()
    print("stage.stock_price_daily view 已更新")


def create_app_layer():
    """重算 app 層：從 stage 算出兩張成品表（手冊15 Step 4 的 SQL）

    app 是實體表（CTAS）, 不會自動跟上新資料——這正是排程要每日重算它的原因
    """
    create_dataset_if_not_exists("app")
    client = get_bigquery_client()
    trend_sql = f"""
    CREATE OR REPLACE TABLE `{PROJECT_ID}.app.stock_trend_analysis` AS
    SELECT stock_id, trade_date, close, volume,
      LAG(close) OVER (PARTITION BY stock_id ORDER BY trade_date) AS prev_close,
      AVG(close) OVER (PARTITION BY stock_id ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS ma5,
      AVG(close) OVER (PARTITION BY stock_id ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20
    FROM `{PROJECT_ID}.stage.stock_price_daily`
    """
    client.query(trend_sql).result()
    summary_sql = f"""
    CREATE OR REPLACE TABLE `{PROJECT_ID}.app.market_daily_summary` AS
    SELECT trade_date,
      COUNT(DISTINCT stock_id) AS active_stocks,
      SUM(volume) AS total_volume,
      ROUND(AVG(close), 2) AS avg_close,
      COUNTIF(spread > 0) AS up_count,
      COUNTIF(spread < 0) AS down_count
    FROM `{PROJECT_ID}.stage.stock_price_daily`
    GROUP BY trade_date
    """
    client.query(summary_sql).result()
    print("app.stock_trend_analysis 與 app.market_daily_summary 已重算")


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
