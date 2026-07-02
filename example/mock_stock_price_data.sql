-- 生成模擬台股歷史股價資料
-- 用途：當 TaiwanStockPrice 表已有最新資料時，往回填充歷史模擬資料
-- 使用方式：在 MySQL CLI 或 phpMyAdmin 中執行

-- 先建立 TaiwanStockPrice 表（如果不存在）
CREATE TABLE IF NOT EXISTS TaiwanStockPrice (
    date DATE,
    stock_id VARCHAR(10),
    Trading_Volume BIGINT,
    Trading_money BIGINT,
    open DECIMAL(10,2),
    max DECIMAL(10,2),
    min DECIMAL(10,2),
    close DECIMAL(10,2),
    spread DECIMAL(10,2),
    Trading_turnover BIGINT
);

-- 插入模擬資料：10 支股票 x 30 個交易日
-- 使用 RAND() 生成接近真實的股價波動
INSERT INTO TaiwanStockPrice (date, stock_id, Trading_Volume, Trading_money, open, max, min, close, spread, Trading_turnover)
WITH RECURSIVE dates AS (
    SELECT DATE("2025-05-01") AS trade_date
    UNION ALL
    SELECT DATE_ADD(trade_date, INTERVAL 1 DAY)
    FROM dates
    WHERE trade_date < DATE("2025-06-15")
),
stocks AS (
    SELECT "2330" AS stock_id, 1000.00 AS base_price UNION ALL
    SELECT "2317", 150.00 UNION ALL
    SELECT "2454", 1200.00 UNION ALL
    SELECT "0050", 180.00 UNION ALL
    SELECT "0056", 40.00 UNION ALL
    SELECT "00713", 55.00 UNION ALL
    SELECT "2308", 70.00 UNION ALL
    SELECT "2382", 400.00 UNION ALL
    SELECT "00878", 22.00 UNION ALL
    SELECT "006208", 90.00
),
trading_days AS (
    SELECT trade_date FROM dates
    WHERE DAYOFWEEK(trade_date) NOT IN (1, 7)
)
SELECT
    td.trade_date,
    s.stock_id,
    FLOOR(RAND() * 50000000 + 5000000) AS Trading_Volume,
    FLOOR(RAND() * 50000000000 + 1000000000) AS Trading_money,
    ROUND(s.base_price * (1 + (RAND() - 0.5) * 0.04), 2) AS open_price,
    ROUND(s.base_price * (1 + (RAND() - 0.3) * 0.04), 2) AS max_price,
    ROUND(s.base_price * (1 + (RAND() - 0.7) * 0.04), 2) AS min_price,
    ROUND(s.base_price * (1 + (RAND() - 0.5) * 0.04), 2) AS close_price,
    ROUND((RAND() - 0.5) * s.base_price * 0.04, 2) AS spread,
    FLOOR(RAND() * 100000 + 10000) AS Trading_turnover
FROM trading_days td
CROSS JOIN stocks s
WHERE NOT EXISTS (
    SELECT 1 FROM TaiwanStockPrice p
    WHERE p.stock_id = s.stock_id AND p.date = td.trade_date
);
