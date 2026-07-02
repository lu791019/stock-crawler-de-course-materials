CREATE OR REPLACE VIEW vw_stock_price_daily AS
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
  FROM TaiwanStockPrice s
) AS t
WHERE t.rn = 1;
