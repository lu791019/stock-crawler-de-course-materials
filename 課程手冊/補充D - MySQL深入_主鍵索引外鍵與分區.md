# 補充 D：MySQL 深入 — 約束、索引、外鍵、交易與分區（含 phpMyAdmin 實戰）

> 第 5、6 章教會你「把資料寫進去、寫得不重複」。這份補充回答下一層的問題：**資料庫怎麼查得快（索引、分區）、怎麼保護資料的正確性（約束、外鍵、交易）、怎麼管得安全（權限）**。每一段都用我們的 `TaiwanStockPrice` 或 repo 裡現成的 SQL 檔實測，所有輸出都是 VM 真實跑出來的。

---

## 為什麼要學這些

第 5 章的 `to_sql` 把表交給 pandas「用猜的」建，沒主鍵、沒索引、沒約束——小資料看不出問題。但資料一變厚：查詢開始慢（沒索引）、髒資料塞得進去（沒約束）、多表對不上（沒外鍵）、改到一半出錯資料壞一半（沒交易）。這些工具就是 RDB 之所以叫「關聯式資料庫」而不是「很大的 CSV」的原因。

**先把資料填厚**（索引實驗需要資料量），在 phpMyAdmin 的 SQL 頁籤執行 `example/mock_stock_price_data.sql`，或：

```bash
docker exec -i mysql mysql -uroot -p1234 mydb < example/mock_stock_price_data.sql
docker exec mysql mysql -uroot -p1234 mydb -e "SELECT COUNT(*) FROM TaiwanStockPrice;"
# → 320（10 支股票 × 32 個交易日）
```

---

## 1. 索引 — 從「整本翻」到「查目錄」

**索引（index）是資料庫的目錄**。沒有目錄，查一個字要整本書翻過去（全表掃描）；有目錄，翻兩三頁就到。底層是 B+Tree——你可以先想成「排好序、可以二分搜尋的目錄樹」，細節等需要時再深究。

### 親眼看差異：EXPLAIN

`EXPLAIN` 放在任何 SELECT 前面，資料庫會告訴你「我打算怎麼查」。**建索引前**：

```sql
EXPLAIN SELECT * FROM TaiwanStockPrice WHERE stock_id = '2330';
```

```
type  possible_keys  key   rows  Extra
ALL   NULL           NULL  320   Using where     ← type=ALL：全表掃描，320 筆全翻
```

**建索引**（SQL 或 phpMyAdmin 二選一）：

```sql
-- CREATE INDEX 索引名 ON 表名 (欄位...)：在這些欄位上建一份「排好序的目錄」
-- 兩欄一起寫 = 複合索引：先按 stock_id 排、同股再按 date 排
CREATE INDEX idx_stock_date ON TaiwanStockPrice (stock_id, date);
```

> **phpMyAdmin 路徑**：選表 → Structure → 勾選 `stock_id`、`date` 兩欄 → 下方按 **Index**。建好後 Indexes 區塊會出現 `idx_stock_date`。

**建索引後**再 EXPLAIN 一次：

```
type  possible_keys   key             rows  Extra
ref   idx_stock_date  idx_stock_date  32    NULL   ← type=ref：走索引，只碰 32 筆
```

**320 → 32，掃描量變成 1/10**。這還只是 320 筆的玩具表；真實系統百萬筆時，就是「秒回 vs 卡死」的差別。

### 複合索引的最左前綴原則

`(stock_id, date)` 這個複合索引像「先按股票、再按日期排的目錄」：

```sql
EXPLAIN SELECT * FROM TaiwanStockPrice WHERE stock_id = '2330';          -- ✅ 用得到（最左欄）
EXPLAIN SELECT * FROM TaiwanStockPrice WHERE stock_id='2330' AND date='2025-06-13';  -- ✅ 全用上
EXPLAIN SELECT * FROM TaiwanStockPrice WHERE date = '2025-06-13';        -- ❌ 用不到！
```

最後一句實測回 `type=ALL`——因為目錄是「先股票再日期」排的，只知道日期等於從目錄中間開始找，沒用。**口訣：複合索引像電話簿（姓、名），只知道名字查不了電話簿。** 常按日期查的話，就再建一個以 `date` 開頭的索引。

### 索引的代價（為什麼不每欄都建）

- **寫入變慢**：每 INSERT 一筆，所有索引都要跟著更新——爬蟲這種寫入密集的 workload，索引越多寫越慢
- **佔空間**：每個索引都是一份額外的目錄
- 原則：**照你的 WHERE 建**。常查什麼建什麼，不查的不建。主鍵自帶一個索引，不用重複建。

---

## 2. 約束家族 — 資料庫的「入場檢查」

約束（constraint）是你寫在表定義上的規則，**資料庫在寫入的瞬間強制檢查**，不合格直接拒收。這比「在 Python 裡自己檢查」可靠——因為不管誰來寫（爬蟲、手動、別的程式），檢查永遠在。

| 約束 | 意思 | 股價表的例子 |
|------|------|-------------|
| `NOT NULL` | 這欄不准空 | `date DATE NOT NULL`——沒有日期的股價沒有意義 |
| `DEFAULT` | 沒給值就用預設 | `created_at DATETIME DEFAULT CURRENT_TIMESTAMP` |
| `UNIQUE` | 這欄不准重複 | email、身分證字號這類「天然唯一」的欄位 |
| `PRIMARY KEY` | 唯一 + 不准空 + 一張表只有一個 | `(stock_id, date)`——第 6 章的複合主鍵 |
| `AUTO_INCREMENT` | 整數自動遞增 | `id INT AUTO_INCREMENT`——人工代理鍵 |
| `FOREIGN KEY` | 值必須存在於另一張表 | 見第 3 節 |

> 這三種「入場檢查」被違反時長什麼樣，第 3 節載入電商資料後，用同一張會員表一次實測給你看。

### 主鍵的兩派選擇：自然鍵 vs 代理鍵

- **自然鍵**：用資料**天生的身分**當主鍵。「2330 在 6/13 的股價」本來就只該有一筆，所以 `(stock_id, date)` 這個組合天然就是它的身分證。
- **代理鍵**：另外發一張**號碼牌**——加一欄 `id INT AUTO_INCREMENT`，資料進來就 1、2、3… 自動編下去。號碼跟資料內容一點關係都沒有，像戶政事務所的抽號機。現成的例子就在第 3 節要載入的 `example/ecommerce.sql`：`users` 表的 `user_id`（1、2、3…）就是號碼牌——Alice 叫什麼名字、換什麼 email 都與它無關。

號碼牌的好處是單欄、短、永不變動；但**號碼牌防不了重複排隊**——同一筆「2330、6/13」塞兩次，會各拿到 id=5 和 id=6，資料庫覺得沒問題（號碼不同嘛），業務上卻重複了。我們選自然鍵，因為「同股同日只能有一筆」正是業務規則本身——這也是第 6 章 upsert 能防重複的根基。

> 進階：實務常混搭——代理鍵當主鍵、自然鍵另設 `UNIQUE`，兩個好處都拿到。為什麼需要它？第 3 節的「改名實驗」會用會員改名的完整劇本演給你看。

> **phpMyAdmin 哪裡看**：選表 → **Structure** 頁籤。主鍵欄位會有金色鑰匙 🔑；下方 Indexes 區塊列出所有鍵。第 5 章 `to_sql` 自動建的表在這裡會看到「**沒有任何鍵**」——這就是第 6 章要拿回控制權的原因。

---

## 3. 外鍵 FOREIGN KEY — 表與表之間的「掛鉤」

股價表是單表世界，看不出外鍵的用途。用 repo 的 `example/ecommerce.sql`（三張表：users、products、orders）：

```bash
docker exec -i mysql mysql -uroot -p1234 < example/ecommerce.sql
```

### 先用 users 表把第 2 節的約束落地

`users` 原本沒什麼約束，用 `ALTER`（DDL）補上三種，然後故意違規給你看（VM 實測）：

```sql
ALTER TABLE users MODIFY name VARCHAR(50) NOT NULL;                     -- 名字不准空
ALTER TABLE users ADD UNIQUE (email);                                  -- email 不准重複
ALTER TABLE users ADD COLUMN joined_at DATETIME DEFAULT CURRENT_TIMESTAMP;  -- 沒給就自動補
```

```sql
INSERT INTO users (user_id, name, email) VALUES (4, NULL, 'dave@example.com');
-- ERROR 1048: Column 'name' cannot be null                ← NOT NULL 擋下

INSERT INTO users (user_id, name, email) VALUES (4, 'Dave', 'alice@example.com');
-- ERROR 1062: Duplicate entry 'alice@example.com'          ← UNIQUE 擋下

INSERT INTO users (user_id, name, email, created_at) VALUES (4, 'Dave', 'dave@example.com', '2024-04-10');
SELECT user_id, name, joined_at FROM users WHERE user_id = 4;
-- 4  Dave  2026-07-08 14:25:17                             ← 沒給 joined_at，DEFAULT 自動補 ✅
```

兩次拒收、一次自動補——「入場檢查」不再是名詞。（Dave 進來了，等下 CASCADE 實驗還會用到他。）

`orders` 表的定義裡有兩個外鍵：

```sql
CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    user_id INT,
    product_id INT,
    ...
    FOREIGN KEY (user_id) REFERENCES users(user_id),      -- 訂單的 user_id 必須存在於 users 表
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
```

意思：**訂單不能掛在不存在的使用者或商品上**。實測兩個方向的保護：

```sql
-- ① 擋進：塞一筆「孤兒訂單」（user_id=99，users 表沒有 99 號）
INSERT INTO orders VALUES (9999, 99, 101, '2024-05-01', 1, 100);
```
```
ERROR 1452 (23000): Cannot add or update a child row: a foreign key constraint fails
```

```sql
-- ② 擋刪：刪掉 Alice（user_id=1），但她名下還有訂單掛著
DELETE FROM users WHERE user_id = 1;
```
```
ERROR 1451 (23000): Cannot delete or update a parent row: a foreign key constraint fails
```

白話記法：**1452＝擋進（不准建立孤兒訂單）、1451＝擋刪（不准丟下孤兒就跑）**。一個管進、一個管刪，合起來保證訂單永遠找得到主人——這就是「參照完整性」。（進階：`ON DELETE CASCADE` 可以改成「刪父連子一起刪」，預設是擋下來。）

### 同一個實驗，改用 phpMyAdmin 介面做

不想打 SQL 的話，圖形介面照樣能踩到這兩道保護——phpMyAdmin 只是幫你送出同一句 SQL，紅色錯誤框裡的代碼一模一樣：

**擋進（#1452）**：
1. 左側選 `test_ecommerce` → 點 `orders` 表 → 上方 **Insert（新增）** 頁籤
2. 填 order_id `9999`、user_id `99`（故意填不存在的）、product_id `101`、其餘隨意 → **Go**
3. 頁面跳出紅色錯誤：`#1452 - Cannot add or update a child row...`——資料沒進去

**擋刪（#1451）**：
1. 點 `users` 表 → **Browse（瀏覽）** 頁籤
2. 找到 user_id=1（Alice）那一列 → 按該列的 **Delete** → 確認
3. 紅色錯誤：`#1451 - Cannot delete or update a parent row...`——Alice 還有訂單，刪不掉

### 有了關聯，JOIN 才有意義

```sql
SELECT o.order_id, u.name, p.name AS product, o.total_amount   -- AS：幫欄位取別名，避免兩個 name 撞名
FROM orders o                                   -- o / u / p 是「表別名」，讓下面寫起來短
JOIN users u    ON o.user_id = u.user_id        -- ON：兩表用什麼條件對起來（訂單的 user_id = 會員的 user_id）
JOIN products p ON o.product_id = p.product_id; -- 再接第二張表，一樣用鍵對應
```
```
order_id  name   product      total_amount
1001      Alice  iPhone 15    32900
1002      Alice  AirPods Pro  7500
1003      Bob    AirPods Pro  7500
```

三張表靠鍵接回一張完整報表——「關聯式」資料庫的招牌動作。

### 改名實驗：為什麼主鍵要用「不會變的」

第 2 節說代理鍵是號碼牌，這裡用「會員改名」演完整劇本。先看一件事：**`ecommerce.sql` 一開始就是混搭設計**——`user_id`（代理鍵）當主鍵、orders 掛的是 id 不是名字。所以：

**第一幕：混搭設計下，改名毫髮無傷**

```sql
UPDATE users SET name = 'Alice Wang' WHERE user_id = 1;    -- Alice 改名
SELECT o.order_id, u.name FROM orders o JOIN users u ON o.user_id = u.user_id
WHERE u.user_id = 1;
-- 1001  Alice Wang
-- 1002  Alice Wang     ← 三筆訂單全部無恙，JOIN 照樣對得回來
-- 1004  Alice Wang        因為訂單掛的是 user_id=1，不是名字
```

**第二幕：反例——如果當初拿 username 當主鍵**

```sql
CREATE TABLE users_nat (username VARCHAR(50) PRIMARY KEY);   -- 反例組：拿會變動的 username 直接當主鍵
INSERT INTO users_nat VALUES ('alice123');                    -- Alice 用帳號名報到
CREATE TABLE orders_nat (order_id INT PRIMARY KEY, username VARCHAR(50),
                         FOREIGN KEY (username) REFERENCES users_nat(username));  -- 訂單外鍵直接掛 username
INSERT INTO orders_nat VALUES (1, 'alice123');                -- 一筆掛在她名下的訂單

UPDATE users_nat SET username = 'alice_wang' WHERE username = 'alice123';
-- ERROR 1451: Cannot delete or update a parent row    ← 想改名？外鍵擋下，動不了
```

**那……訂單不要掛 username 不就好了？** 好問題，只有三條路：

1. **掛 username**——就是第二幕：改名被卡死
2. **掛別的欄位**——外鍵只能指向主鍵或 UNIQUE 欄位，所以你需要「另一個唯一、且永不變動的欄位」……一個不變的唯一流水號——**你剛剛自己發明了代理鍵**，這就是混搭方案
3. **乾脆不設外鍵，訂單自己存一份 username**——第三幕演給你看：

**第三幕：不設外鍵，改名後「默默斷鏈」**

```sql
CREATE TABLE users_nofk (username VARCHAR(50) PRIMARY KEY);
INSERT INTO users_nofk VALUES ('alice123');
CREATE TABLE orders_nofk (order_id INT PRIMARY KEY, username VARCHAR(50));   -- 訂單自己存名字，「沒有」外鍵約束
INSERT INTO orders_nofk VALUES (1, 'alice123');

UPDATE users_nofk SET username = 'alice_wang';             -- 改名：成功，沒人擋（因為沒有 FK 保護）
SELECT COUNT(*) FROM orders_nofk o                          -- 用名字把訂單 JOIN 回會員
JOIN users_nofk u ON o.username = u.username;
-- 0        ← 訂單裡躺著舊名字，JOIN 對不回任何人——沒有報錯，資料默默壞掉
```

第三幕最可怕：**它不會報錯**。第二幕至少大聲擋你，第三幕是幾個月後報表對不上才發現。結論：問題的根源是「username 既當身分、又會變動」——解法是給一個永不變的身分（代理鍵 id）供人引用，會變的欄位退居 `UNIQUE` 防重複。

### 順手補：ON DELETE CASCADE 長什麼樣

前面說預設是「擋刪」（1451），也可以改成「刪父連子一起刪」。用約束實驗留下的 Dave 來演：

```sql
CREATE TABLE reviews_demo (review_id INT PRIMARY KEY, user_id INT, comment VARCHAR(100),
                           FOREIGN KEY (user_id) REFERENCES users(user_id)
                           ON DELETE CASCADE);   -- ← 關鍵：刪父列時「連鎖刪除」子列（預設是擋下 1451）
INSERT INTO reviews_demo VALUES (1, 4, '出貨快'), (2, 4, '品質好');   -- Dave（user_id=4）的兩則評論

DELETE FROM users WHERE user_id = 4;      -- 刪 Dave（他沒有訂單，不會被 orders 的預設外鍵擋）
SELECT COUNT(*) FROM reviews_demo;        -- 0  ← 兩則評論被 CASCADE 自動刪掉
SELECT COUNT(*) FROM orders;              -- 6  ← 別人的訂單原封不動
```

CASCADE 方便但危險——刪一列可能連鎖刪掉一片，正式系統用之前要想清楚。

### 那為什麼我們的股價表「不用」外鍵？

誠實說：因為它是**單表、寫入密集的分析型資料**。外鍵每次寫入都要去父表查一次存在性，爬蟲大批寫入時是額外成本；而且股價表沒有「父表」可掛。**交易系統（訂單、會員）用外鍵保護正確性；資料工程的落地表常常不設外鍵、把驗證放在 pipeline 裡**——兩種都是對的，看場景。

---

## 4. VIEW 檢視表 — 存起來的查詢

VIEW 是一段「存了名字的 SELECT」——本身不存資料，每次查它就重新執行底下的查詢。repo 現成的例子 `example/vw_stock_price_daily.sql`：

```sql
CREATE OR REPLACE VIEW vw_stock_price_daily AS
SELECT t.stock_id, t.date AS trade_date, t.open, t.max, t.min, t.close, ...
FROM (
  SELECT s.*, ROW_NUMBER() OVER (PARTITION BY s.stock_id, s.date
                                 ORDER BY s.Trading_Volume DESC) AS rn
  FROM TaiwanStockPrice s
) AS t
WHERE t.rn = 1;      -- 同股同日若有重複，只取成交量最大的那筆
```

它把「去重後的乾淨日線」包成一張虛擬表，之後想要乾淨資料就：

```sql
SELECT stock_id, trade_date, close FROM vw_stock_price_daily   -- 查 VIEW 跟查表寫法一模一樣
WHERE stock_id = '2330' ORDER BY trade_date DESC LIMIT 3;      -- 背後其實是重新執行了上面那段 SELECT
```

**用途**：把複雜查詢包起來給下游用——第 8 章 Metabase 接的就是這個 VIEW，BI 工具永遠拿到乾淨資料，而不用每張圖表都重寫一次去重邏輯。這是「**在資料庫層做一層介面**」的思維。

> phpMyAdmin：VIEW 會出現在左側表清單（Structure 頁 Table_type 標示 VIEW），點開能看資料但不能直接改——因為它沒有自己的資料。

---

## 5. 交易 Transaction — 要嘛全做完，要嘛當沒發生

大局觀講過 ACID，這裡親手摸 A（原子性）。**交易**把多個操作包成一個單位：全部成功才算數（COMMIT），中間出錯全部撤銷（ROLLBACK）。實測：

```sql
SELECT close FROM TaiwanStockPrice WHERE stock_id='2330' AND date='2025-06-13';  -- 1000.65
START TRANSACTION;       -- 開一個交易：從這裡開始的修改都先「記帳」，不真正定案
UPDATE TaiwanStockPrice SET close = 0 WHERE stock_id='2330' AND date='2025-06-13';
SELECT close FROM ...;   -- 0.00   ← 交易內看得到自己的修改
ROLLBACK;                -- 撤銷：把這筆帳整個劃掉（反之 COMMIT 是定案生效）
SELECT close FROM ...;   -- 1000.65 ← 像沒發生過一樣
```

實測輸出：`1000.65 → 0.00 → ROLLBACK → 1000.65`。

**跟課程的關聯**：經典場景是轉帳（扣款+入帳必須同生共死）；在資料工程裡，「一批資料要嘛全進要嘛全不進」也是交易——第 5 章 `to_sql` 底層每個 chunk 就包在交易裡，這也是為什麼寫到一半失敗不會留半批髒資料。平常 mysql 客戶端 `autocommit=ON`（每句自動 COMMIT），所以你之前的操作都「立即生效」；要手動控制才寫 `START TRANSACTION`。

---

## 6. 使用者與權限 — 別什麼都用 root

到目前為止我們都用 `root / 1234`——教學方便，但正式環境是大忌：任何程式拿到的帳號都能 DROP 整個資料庫。正確做法是**給每個應用一個「只能做份內事」的帳號**：

```sql
CREATE USER 'app'@'%' IDENTIFIED BY 'app-pass-123';   -- 建帳號：'名字'@'可以從哪裡連'（% = 任何主機）
GRANT SELECT, INSERT ON mydb.* TO 'app'@'%';           -- 授權：只給「查、寫」，範圍限 mydb 的所有表（mydb.*）
```

實測：`app` 帳號 `SELECT COUNT(*)` 正常回 320，但想 DROP TABLE：

```
ERROR 1142 (42000): DROP command denied to user 'app'@'localhost' for table 'TaiwanStockPrice'
```

**爬蟲 worker 其實只需要 `SELECT, INSERT, UPDATE`**（upsert 要 UPDATE）。搭配前面教過的 `.env` 帶入帳密（`docker-compose-dotenv-demo.yml`），就是完整的正式環境做法：受限帳號 + 不進 git 的密碼。

> phpMyAdmin：用 root 登入 → 首頁 **User accounts** 頁籤，可以圖形化建帳號、勾權限——本質就是幫你下 CREATE USER / GRANT。

---

## 7. 分區 Partitioning — 大表切抽屜（進階）

表大到千萬筆時，連索引都吃力。**分區**把一張表按規則實體切成多個「抽屜」，查詢時只開有關的抽屜（分區剪枝 pruning）。時序資料最常見**按時間切**：

```sql
CREATE TABLE TaiwanStockPrice_part (
  date DATE NOT NULL,
  stock_id VARCHAR(10) NOT NULL,
  open DECIMAL(10,2), close DECIMAL(10,2), Trading_Volume BIGINT,
  PRIMARY KEY (stock_id, date)               -- ⚠️ 分區鍵(date)必須包含在主鍵裡
) PARTITION BY RANGE (YEAR(date)) (          -- 用「date 的年份」當切抽屜的規則
  PARTITION p2024 VALUES LESS THAN (2025),     -- 2025 年以前的資料放這格
  PARTITION p2025 VALUES LESS THAN (2026),     -- 2025 年的放這格
  PARTITION pmax  VALUES LESS THAN MAXVALUE    -- 其餘（未來）全部收這格，避免無處可放報錯
);
```

塞入資料後看剪枝是否生效——EXPLAIN 的 `partitions` 欄：

```sql
EXPLAIN SELECT * FROM TaiwanStockPrice_part WHERE date BETWEEN '2025-06-01' AND '2025-06-13';
```
```
table                  partitions  type  rows
TaiwanStockPrice_part  p2025       ALL   320    ← 只開 p2025 這個抽屜，p2024/pmax 完全沒碰
```

分區資訊也可以直接查：

```sql
SELECT PARTITION_NAME, TABLE_ROWS            -- information_schema：MySQL 的「系統目錄」，存放所有表的中繼資料
FROM information_schema.PARTITIONS
WHERE TABLE_NAME = 'TaiwanStockPrice_part';
-- p2024: 0 / p2025: 320 / pmax: 0
```

**兩個誠實提醒**：

1. **分區鍵必須包含在主鍵（或唯一鍵）裡**——這是 MySQL 的硬規定。我們的複合主鍵 `(stock_id, date)` 正好含 date，天生適合按年分區；如果當初用自增 id 當主鍵，這裡就要重新設計。設計 Data Model 時多想一步的價值在這裡兌現。
2. **什麼時候才需要**：GB 級、千萬筆以上才有感。我們 320 筆的教學表用分區是殺雞用牛刀——先會概念和語法，等表真的大了再拿出來。BigQuery（第 14 章）的日期分區是同一個概念的雲端版，到時會再遇到它。

---

## 一頁決策表：什麼問題用什麼工具

| 你的問題 | 工具 | 一句話 |
|---------|------|--------|
| 同一筆資料不能重複 | 主鍵 / UNIQUE | 給資料一張身分證 |
| 髒資料塞得進來 | NOT NULL / DEFAULT / 約束 | 入場檢查 |
| 查詢越來越慢 | 索引（照 WHERE 建）| 幫資料建目錄 |
| 多表資料對不上 | 外鍵 | 表與表之間掛鉤 |
| 下游要乾淨資料 | VIEW | 存起來的查詢，DB 層的介面 |
| 多步驟要同生共死 | 交易 | 全做完或當沒發生 |
| 程式權限太大很危險 | CREATE USER / GRANT | 只給份內事 |
| 表大到索引都吃力 | 分區 | 切抽屜、只開有關的 |

---

## 想一想（確認你懂了）

**Q1：複合索引 `(stock_id, date)` 存在時，`WHERE date = '2025-06-13'` 為什麼用不到它？**

因為複合索引是「先按 stock_id、再按 date」排序的目錄——像電話簿先姓後名，只知道名字沒法用。要按日期查得快，得另建以 date 開頭的索引。

**Q2：外鍵那麼好，為什麼我們的股價表不設？**

外鍵每次寫入都要回父表驗證，寫入密集的爬蟲有額外成本；而且股價表是單表、沒有父表可掛。交易系統靠外鍵保正確性，資料工程的落地表常把驗證放 pipeline——場景不同，選擇不同。

**Q3：為什麼分區表的主鍵一定要包含分區鍵？**

MySQL 要能只憑主鍵判斷「這筆在哪個抽屜」。若主鍵不含 date，插入時無法確定分區、唯一性檢查也得開全部抽屜，分區就失去意義。

**Q4：worker 的資料庫帳號該給哪些權限？**

`SELECT, INSERT, UPDATE`（upsert 需要 UPDATE）。不給 DELETE、DROP、ALTER——爬蟲的份內事不包含刪表改結構，出 bug 或被入侵時損害也被限制住。

---

## 換你試試看

**練習 1：幫查詢配眼鏡**
對 `TaiwanStockPrice` 跑 `EXPLAIN SELECT * FROM TaiwanStockPrice WHERE close > 1000;`，看 type 是什麼。替 `close` 建索引再跑一次。想一想：什麼樣的查詢值得為它建索引？

**練習 2：體驗外鍵的保護**
在 `test_ecommerce` 加一張 `reviews` 表（review_id、user_id、product_id、rating），設兩個外鍵。試塞一筆 user_id=999 的評論，確認被擋下。

**練習 3：交易的「全或無」**
開交易、連續兩句 UPDATE 改兩支股票的 close、ROLLBACK，確認兩筆都回到原值——體會「包在一起」的意義。

**練習 4（進階）：用 `example/backup/employees.sql` 練 GROUP BY + 索引**
載入員工表，查各部門平均薪資；替 department 建索引前後各 EXPLAIN 一次比較。

---

## 收工（清掉實驗產物）

```sql
DROP TABLE IF EXISTS TaiwanStockPrice_part;      -- 刪分區實驗表（IF EXISTS：不存在也不報錯）
DROP INDEX idx_stock_date ON TaiwanStockPrice;   -- 拆掉實驗用的索引
DROP DATABASE IF EXISTS test_ecommerce;          -- 整個電商練習庫（含所有實驗表）一起收
DROP USER IF EXISTS 'app'@'%';                   -- 刪實驗帳號
```

---

## 這份補充你學到了

- 約束是資料庫層的入場檢查；主鍵有自然鍵/代理鍵兩派，股價表選自然鍵因為業務規則就是「同股同日一筆」
- 索引 = 目錄：EXPLAIN 親測 320→32；複合索引有最左前綴原則；索引的代價是寫入變慢
- 外鍵保護參照完整性（1452/1451 兩個方向）；資料工程落地表常不設外鍵，驗證放 pipeline
- VIEW 是 DB 層的介面，Metabase 接的就是它；交易讓多步驟同生共死
- 正式環境用受限帳號（GRANT）；分區是大表的抽屜術，分區鍵必須在主鍵裡
