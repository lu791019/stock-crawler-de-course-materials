# 補充 F：ACID 與 CAP — 從 MySQL 到 MongoDB

> 手冊05 的大局觀比過 RDBMS vs NoSQL，那張表裡有兩個沒展開的縮寫：**ACID** 和 **CAP**。這份補充說明這兩個概念，然後動手跑一個真的 NoSQL——用跟 MySQL 版完全同款的 Celery 爬蟲，把股價寫進 **MongoDB**，比較兩個世界的差異。

---

## 1. ACID — 交易的四條保證

交易（補充D 第 5 節操作過的 `START TRANSACTION` / `ROLLBACK`）背後就是這四個字母：

| 字母 | 名稱 | 白話 | 課程對應 |
|------|------|------|---------|
| **A** | Atomicity 原子性 | 一組操作要嘛全做完、要嘛全沒發生 | 補充D 第 5 節交易實驗：改成 0 → ROLLBACK → 變回 1000.65 |
| **C** | Consistency 一致性 | 交易前後，資料都符合所有規則（主鍵、外鍵、約束）| 補充D 第 2、3 節：NOT NULL 缺值（1048）、主鍵重複（1062）、外鍵指向不存在的資料（1452），都會被拒收 |
| **I** | Isolation 隔離性 | 多人同時操作，彼此不互相干擾（像各自在隔間工作）| 多 worker 同時寫入時由 MySQL 處理衝突 |
| **D** | Durability 持久性 | COMMIT 成功的資料，斷電也不會消失（已落盤）| volume 掛載 + MySQL 的交易日誌 |

**ACID 是資料庫對「交易」的保證：資料正確、不遺失。** 它本身跟單機或分散式無關，但在單機上最容易完整實現——MySQL、PostgreSQL 這類 RDBMS 都完整支援。一旦資料分散到多台機器，要維持同樣的保證就必須跨機器協調、成本大增——這正是下一節 CAP 要處理的問題。

## 2. CAP — 多機器資料庫的「三選二」

資料一多，一台機器放不下，要多台——這時有一個取捨定理。三個目標：

- **C**onsistency 一致性：任何時刻、問任何一台，答案都一樣
- **A**vailability 可用性：任何時刻都有人回答你（不會「服務暫停」）
- **P**artition tolerance 分區容忍：機器之間**斷線時**系統還能運作

**CAP 定理：三個最多同時滿足兩個。** 其中 P 沒有商量餘地——機器之間的網路無法保證永不中斷，系統必須在斷線時仍能運作。所以實際的選擇是：**斷線的當下，要 C 還是 A？**

注意：CAP 講的是**分散式系統**，不是 NoSQL 專屬——MySQL 做主從複寫或集群時同樣受 CAP 約束；單機一台 MySQL 沒有「機器之間斷線」的問題，所以不在 CAP 討論範圍。只是多數 NoSQL 天生為分散式設計，才更常跟 CAP 一起被提起。

用連鎖餐廳想像：台北、高雄兩家分店共用會員點數，兩店之間網路斷了，這時客人來扣點——

- **選 C（一致優先）**：「系統連不上總部，暫停服務」——寧可不做生意，也不能讓兩邊點數對不上（MySQL 集群、金融系統的選擇）
- **選 A（可用優先）**：「先扣，等連線恢復再對帳」——生意照做，允許短暫的不一致，事後同步（很多 NoSQL 的預設，稱**最終一致性**）

三種組合各舉實例：

| 組合 | 意思 | 系統例子 | 商業情境 |
|------|------|---------|---------|
| **CA** | 不面對分區——只有一台機器，沒有「機器之間斷線」的問題 | 單機 MySQL（本課的 mydb 就是）| 單一門市的 POS、公司內部 ERP |
| **CP** | 斷線時保一致、犧牲可用：連不上多數節點的那一邊停止服務 | etcd（Kubernetes 存設定用）、HBase | 銀行轉帳、演唱會票券庫存——寧可暫停交易，也不能同一張票賣兩次 |
| **AP** | 斷線時保可用、事後補同步（最終一致） | Cassandra、DynamoDB | 社群按讚、購物車、會員點數——先讓用戶操作成功，恢復後再對帳 |

## 3. 所以 SQL 和 NoSQL 是這樣分工的

| | MySQL（RDBMS 代表）| MongoDB（NoSQL 代表）|
|---|---|---|
| 資料模型 | 表格＋固定 schema | 文件（document）＝ dict，欄位自由 |
| 一致性 | ACID 強一致 | 預設偏可用性、最終一致（可調）|
| 擴展 | 垂直為主，水平擴展成本高 | 天生為水平擴展設計 |
| 適合 | 交易系統、需要 JOIN 與強約束 | 結構多變、量大、高流量寫入 |
| 課程對應 | 手冊05-06 的股價落地 | 本補充的動手段 |

（手冊05 大局觀那張 RDBMS vs NoSQL 表的「ACID」「最終一致性」，對應的就是上面兩節。）

---

## 4. 認識 MongoDB — 動手前先知道它是什麼

### MongoDB 是什麼

MongoDB 是目前使用最廣的**文件式（Document）資料庫**：資料以「文件」為單位儲存，一份文件就是一個 JSON 格式的物件（內部以 BSON 二進位格式存放，額外支援日期、二進位等型別）——對 Python 來說，就是一個 dict。這跟爬蟲的資料形態直接對應：FinMind API 回來的就是 dict 的 list，寫入 MongoDB 不需要先定義表格結構，dict 進去就是一份文件。

名詞跟 MySQL 一一對應：

| MySQL | MongoDB | 說明 |
|-------|---------|------|
| database 資料庫 | database 資料庫 | 名稱相同，都是最上層容器 |
| table 表 | collection 集合 | 一群文件的容器，不用先定義欄位 |
| row 列 | document 文件 | 一筆資料；每份文件的欄位可以不同 |
| column 欄位 | field 欄位 | 不用預先宣告，寫入時自帶 |
| primary key 主鍵 | `_id` | 每份文件都有 `_id`，不給就自動產生 |
| index 索引 | index 索引 | 概念相同，也支援 unique |

查詢與擴展的機制：

- **查詢**用 JSON 條件描述，例如 `find({stock_id: "2330"})`；聚合分析用 aggregation pipeline（`$match`、`$group`，對應 SQL 的 WHERE、GROUP BY）——動手段和 `example/pymongo.ipynb` 都會操作到
- **擴展**靠兩個內建機制：replica set（複本集，多台存同一份資料，提供容錯與讀取分流）和 sharding（分片，資料切段分散到多台）。第 3 節說 MongoDB「天生為水平擴展設計」，指的就是這兩個機制；本課用單機一台，不涉及這部分

### NoSQL 不是只有 MongoDB — 四大類型

手冊05 大局觀那張表的 NoSQL 欄位列了四個名字，各代表一類：

| 類型 | 資料長相 | 代表系統 | 適合場景 | 課程對應 |
|------|----------|---------|---------|---------|
| 文件式 Document | JSON 文件（dict）| **MongoDB**、CouchDB | 結構多變的半結構化資料：爬蟲結果、商品目錄、log | 本補充的動手段 |
| 鍵值式 Key-Value | key → value，整個資料庫像一個大 dict | **Redis**、DynamoDB | 快取、session、排行榜——用 key 直取最快，但只能用 key 查 | 手冊10 CeleryExecutor 部署用 Redis 當 Celery broker |
| 寬欄式 Wide-Column | 表格外形，但每列欄位可不同、按欄儲存 | **Cassandra**、HBase | 寫入量極大的時序資料：IoT 感測、訊息紀錄 | 第 2 節 CAP 表的 CP（HBase）/ AP（Cassandra）例子 |
| 圖形式 Graph | 節點＋邊，關係本身就是資料 | **Neo4j** | 關係查詢：社群網絡、推薦系統、金流追蹤 | （本課未使用）|

四類的共同點：各自放棄「固定 schema + JOIN + 強約束」的一部分，換取特定場景的擴展性或速度。選型時先問「資料長什麼樣、怎麼查」，再對表挑類型——不是「NoSQL 比較新所以比較好」。

本課的動手段選 MongoDB：文件式跟爬蟲回來的 dict 直接對應、不用轉換，最能呈現「同一份資料、兩種落地」的差異。

---

## 5. 動手：同一支爬蟲，落地改 MongoDB

### 啟動（跟其他服務完全同款的管理方式）

```bash
docker compose -f docker-compose-local.yml up -d mongodb mongo-express
```

| 服務 | 是什麼 | 入口 |
|------|--------|------|
| `mongodb` | MongoDB 本體（帳密 root / 1234，跟 MySQL 同慣例）| port 27017 |
| `mongo-express` | **Web 管理介面**——MongoDB 界的 phpMyAdmin | http://localhost:8082（root / 1234）|

> ✅ 8082 不帶帳密回 401、帶 root/1234 回 200。port 用 8082 避開 phpMyAdmin(8080) 和 Airflow(8081)。

### 對照組程式碼：跟 MySQL 版差在哪

`crawler/tasks_crawler_finmind_mongo.py`——前半段（打 FinMind API）跟 MySQL 版一模一樣，只換落地：

```python
def upload_data_to_mongo(data: list):
    client = MongoClient(host=MONGO_HOST, port=MONGO_PORT,
                         username=MONGO_ACCOUNT, password=MONGO_PASSWORD)
    collection = client["mydb"]["TaiwanStockPrice"]   # 資料庫和集合不存在時，第一次寫入自動建立
    for doc in data:
        collection.update_one(
            {"stock_id": doc["stock_id"], "date": doc["date"]},  # 同股同日 = 同一份文件
            {"$set": doc},
            upsert=True,        # 存在就更新、不存在就新增 —— Mongo 版的冪等寫入
        )
```

| | MySQL 版（手冊05/06）| MongoDB 版（本補充）|
|---|---|---|
| 寫入前要做什麼 | 建表、定欄位型別、設主鍵 | 不需要——dict 直接寫入 |
| 資料單位 | 一列（row，欄位固定）| 一份文件（dict，欄位自由）|
| 防重複 | 複合主鍵 + `on_duplicate_key_update` | `update_one(filter, $set, upsert=True)` |
| 型別 | DB 層強制（DECIMAL/BIGINT…）| 寫進去是什麼就是什麼 |
| 任務派送 | `.delay()`（同手冊06 的單一 worker 方式）| **完全同款**（worker 是同一批）|

### 跑起來

另開一個終端機，啟動本機 worker——不帶 `-Q`、收預設佇列，跟手冊06 同一個方式（pymongo 已在 uv 環境裡，`uv sync` 會裝）：

```bash
uv run celery -A crawler.worker worker --loglevel=info
```

派送 5 支股票（`.delay()` 不指定佇列，單一 worker 逐一執行）：

```bash
uv run crawler/producer_crawler_finmind_mongo_single.py
```

> 想搭配第 3 章的多佇列分流跑，用 `producer_crawler_finmind_mongo.py`；那條路的 worker 在 docker 裡，要先 `up -d --build worker_twse worker_tpex` 重建 image 才有 pymongo。

執行結果：

```bash
docker exec mongodb mongosh -u root -p 1234 --quiet --eval \
  'db.getSiblingDB("mydb").TaiwanStockPrice.countDocuments()'
# → 回傳文件總數（5 支股票的歷史日線資料）

# 查看其中一份文件——就是 FinMind 回來的 dict 原樣：
# { stock_id: '2330', date: '2024-01-02', Trading_Volume: 27997826, ... }
```

**再跑一次 producer**，countDocuments 的數字不變——重跑不重複，`upsert=True` 就是 Mongo 版的冪等（跟手冊06 同一個觀念、不同語法）。

### 用 mongo-express 看資料

http://localhost:8082 → 資料庫 `mydb` → collection `TaiwanStockPrice` → 直接瀏覽文件、可以搜尋 `{"stock_id": "2330"}`——跟 phpMyAdmin 看表是同一件事。

### mongosh 基本操作（SQL 對照）

Web 介面的角色由 mongo-express 擔任，命令列的角色則是 **mongosh**。進入方式：

```bash
docker exec -it mongodb mongosh -u root -p 1234
```

> 不想用 `docker exec`？下面「同樣的操作」兩節用 **pymongo（Python）** 和 **mongo-express（網頁）** 做一模一樣的事，配套 notebook `example/pymongo.ipynb` 可以直接跑。

| 你想做 | SQL（MySQL）| MongoDB（mongosh）|
|--------|-------------|-------------------|
| 切換資料庫 | `USE mydb` | `use mydb` |
| 查前幾筆 | `SELECT * FROM t LIMIT 5` | `db.t.find().limit(5)` |
| 條件查詢 | `WHERE stock_id='2330'` | `.find({stock_id: "2330"})` |
| 只挑欄位 | `SELECT date, close` | `.find({...}, {_id: 0, date: 1, close: 1})` |
| 排序 | `ORDER BY date DESC` | `.sort({date: -1})` |
| 計數 | `SELECT COUNT(*)` | `.countDocuments()` |
| 不重複值 | `SELECT DISTINCT stock_id` | `.distinct("stock_id")` |
| 範圍條件 | `WHERE close > 1000` | `.find({close: {$gt: 1000}})` |
| 更新一筆 | `UPDATE ... WHERE ...` | `.updateOne(filter, {$set: {...}})` |
| 刪除一筆 | `DELETE ... WHERE ...` | `.deleteOne(filter)` |
| 分組統計 | `GROUP BY` | `.aggregate([{$group: ...}])` |

逐條操作（都在 `use mydb` 之後執行）：

```javascript
// 2330 最近三天的收盤價：條件 + 挑欄位 + 排序 + 限量
db.TaiwanStockPrice.find({stock_id: "2330"}, {_id: 0, date: 1, close: 1}).sort({date: -1}).limit(3)
// [{date: '2026-07-09', close: 2415}, {date: '2026-07-08', close: 2465}, ...]

// 集合裡有哪些股票
db.TaiwanStockPrice.distinct("stock_id")
// ['0050', '0056', '00713', '2317', '2330']

// 條件計數：2330 收盤價超過 1000 的天數（$gt = greater than；同族還有 $gte / $lt / $lte / $ne）
db.TaiwanStockPrice.countDocuments({stock_id: "2330", close: {$gt: 1000}})

// 分組統計：每支股票的平均收盤價與筆數（SQL 的 GROUP BY + AVG + COUNT）
db.TaiwanStockPrice.aggregate([
  {$group: {_id: "$stock_id", avg_close: {$avg: "$close"}, days: {$sum: 1}}},
  {$sort: {_id: 1}}
])
// {_id: '0050', avg_close: 130.55, days: 603}
// {_id: '2330', avg_close: 1234.27, days: 608} ...
```

`$gt`、`$set`、`$group`、`$avg` 這些帶 `$` 的都是 MongoDB 的**運算子**——條件用巢狀 dict 組出來，這是它和 SQL 語法差異最大的地方。

### schema-free 的另一面：寫入一份欄位完全不同的文件

```javascript
db.TaiwanStockPrice.insertOne({stock_id: "TEST", note: "欄位跟股價完全不同", anything: [1, 2, 3]})
// { acknowledged: true, insertedId: ObjectId('...') }   ← 照樣收下，沒有任何檢查

db.TaiwanStockPrice.find({stock_id: "TEST"}, {_id: 0})
// {stock_id: 'TEST', note: '欄位跟股價完全不同', anything: [1, 2, 3]}

db.TaiwanStockPrice.deleteOne({stock_id: "TEST"})   // 清掉實驗文件
```

同一張表這樣寫，MySQL 會報 1054（欄位不存在）直接拒絕；MongoDB 照單全收——同一個集合裡可以放結構完全不同的文件。方便，但髒資料的檢查責任全部落到程式碼層（想一想 Q3 的取捨）。

順帶認識 `_id`：每份文件都有一個自動產生的 `ObjectId`，這是 MongoDB 內建的代理鍵（補充D「自然鍵 vs 代理鍵」的 Mongo 版）。

### MongoDB 怎麼防重複：unique index

MySQL 用主鍵擋重複；MongoDB 對應的機制是**唯一索引**：

```javascript
db.TaiwanStockPrice.createIndex({stock_id: 1, date: 1}, {unique: true})
// 'stock_id_1_date_1'

db.TaiwanStockPrice.getIndexes()
// [{key: {_id: 1}}, {key: {stock_id: 1, date: 1}, unique: true}]

// 之後 insert 同股同日的第二份文件會被擋下：
db.TaiwanStockPrice.insertOne({stock_id: "2330", date: "2024-01-02", close: 1})
// E11000 duplicate key error ... dup key: { stock_id: "2330", date: "2024-01-02" }
```

E11000 就是 MongoDB 版的 1062。我們的任務用 `update_one(upsert=True)`，本來就不會製造重複；unique index 的價值是**保底**——即使有程式用 insert 亂寫，資料庫層也擋得住。對應補充D 的原則：規則放在資料庫層，任何程式來寫都會被管到。

### 同樣的操作①：pymongo（不用 docker exec）

我們的爬蟲任務（`tasks_crawler_finmind_mongo.py`）用的就是 pymongo——所以你已經用過它的 `update_one(upsert=True)`。連線方式也一樣：

```python
from pymongo import MongoClient

client = MongoClient(host="127.0.0.1", port=27017, username="root", password="1234")
col = client["mydb"]["TaiwanStockPrice"]
```

三欄對照——同一件事的兩種寫法：

| 你想做 | mongosh（上面）| pymongo |
|--------|-----------------|---------|
| 計數 | `.countDocuments()` | `col.count_documents({})` |
| 條件查詢 | `.find({stock_id: "2330"})` | `col.find({"stock_id": "2330"})` |
| 只挑欄位 | `.find({...}, {_id: 0, close: 1})` | `col.find({...}, {"_id": 0, "close": 1})` |
| 排序 | `.sort({date: -1})` | `.sort("date", -1)` |
| 不重複值 | `.distinct("stock_id")` | `col.distinct("stock_id")` |
| 範圍條件 | `{close: {$gt: 1000}}` | `{"close": {"$gt": 1000}}` |
| 分組統計 | `.aggregate([...])` | `col.aggregate([...])` |
| 寫入一筆 | `.insertOne({...})` | `col.insert_one({...})` |
| 刪除一筆 | `.deleteOne({...})` | `col.delete_one({...})` |
| 建唯一索引 | `.createIndex({...}, {unique: true})` | `col.create_index([("stock_id", 1), ("date", 1)], unique=True)` |

三個規律看完就會轉換：

1. **dict 的 key 要加引號**——mongosh 是 JavaScript（`{stock_id: ...}`），Python 的 dict key 必須是字串（`{"stock_id": ...}`）
2. **方法名從駝峰變蛇形**——`countDocuments` → `count_documents`、`insertOne` → `insert_one`
3. **運算子完全相同**——`$gt`、`$set`、`$group`、`$avg` 原封不動，只是包在字串裡

動手跑（跟 `pandas.ipynb` 同一個開法）：

```bash
uv run --with jupyter jupyter lab
# 開 example/pymongo.ipynb，由上往下執行
```

notebook 內容依序是：連線與計數 → 查詢（條件/挑欄位/排序/範圍/分組統計）→ 寫入與刪除（schema-free 驗證）→ unique index 防重複（含撞 `DuplicateKeyError` 的驗證）→ 收尾還原，每段都對照 SQL 和 mongosh 的等價寫法。

### 同樣的操作②：mongo-express（不寫程式）

http://localhost:8082 → 資料庫 `mydb` → 集合 `TaiwanStockPrice`。介面做得到的事：

| 操作 | 在哪裡做 |
|------|---------|
| 瀏覽文件、分頁 | 集合頁面主畫面，上方顯示文件總數 |
| 條件查詢 | 上方查詢框：**Simple** 分頁填 key/value；**Advanced** 分頁直接填 JSON，例如 `{"stock_id": "2330"}` |
| 挑欄位、排序 | **Advanced** 分頁的 **Projection** 欄（`{"_id": 0, "date": 1, "close": 1}`）與 **Sort** 欄（`{"date": -1}`）|
| 分組統計 | **Advanced** 分頁勾選 **Aggregate query**，查詢框改填管線陣列：`[{"$group": {"_id": "$stock_id", "avg_close": {"$avg": "$close"}}}]` |
| 新增文件 | **New Document** 按鈕，直接編輯 JSON |
| 編輯／刪除單筆 | 每份文件旁的編輯／刪除圖示 |
| 看索引、刪索引、建一般索引 | 集合頁面下方 **Indexes** 區塊（**Add Indexes** 填索引鍵 JSON：`{"stock_id": 1, "date": 1}`）|

介面做不到、要靠 pymongo 或 mongosh 的兩件事：**`distinct`**（沒有對應介面）、**unique 索引**（Add Indexes 只能填索引鍵，沒有 unique 選項）。

跟 phpMyAdmin 的對位：

| | phpMyAdmin（MySQL）| mongo-express（MongoDB）|
|---|---|---|
| 瀏覽資料 | Browse 頁籤 | 集合頁面 |
| 下查詢 | SQL 頁籤寫 SQL | Advanced 分頁填 JSON |
| 改資料 | 列上的編輯/刪除 | 文件上的編輯/刪除 |
| 管索引 | Structure → Indexes | Indexes 區塊 |

### 三條路怎麼選

| 情境 | 用哪條 |
|------|--------|
| 看一眼資料長怎樣、改一兩筆 | mongo-express（零門檻）|
| 分析、批次處理、要進 pipeline | pymongo（能跟 pandas、Celery 銜接）|
| 臨時管理操作、跟著官方文件做事 | mongosh（官方工具，文件範例都用它）|

### 收工

```bash
docker compose -f docker-compose-local.yml down    # mongodb volume 保留資料；要清掉加 -v
```

---

## 6. 什麼時候選誰

| 情境 | 選 | 原因 |
|------|-----|------|
| 交易、金流、庫存 | MySQL | 錢的事沒有「最終一致」，要 ACID |
| 欄位固定、要 JOIN 分析 | MySQL | 關聯與約束是它的主場 |
| 資料結構常變（每支爬蟲欄位都不同）| MongoDB | 免 schema，改欄位不用 ALTER |
| 超高流量寫入、要水平擴展 | MongoDB | 天生分散式 |
| 我們的股價表 | MySQL 為主 | 欄位固定、要給 Metabase/BigQuery 做關聯查詢 |

## 想一想（確認你懂了）

**Q1：ACID 的 A 和手冊06 的「冪等」是同一件事嗎？**

不是。A（原子性）保證「一組操作全做或全不做」；冪等保證「同一個操作重做幾次結果一樣」。to_sql 一批寫入靠交易保 A，但重跑會翻倍（不冪等）——兩個都要有才安全。

**Q2：為什麼說 CAP 的 P 不是選項？**

因為網路斷線是物理現實，不是你能拒絕的。所以設計分散式系統時，真正要決定的是「斷線的當下選一致還是選可用」。

**Q3：MongoDB 免建表很方便，代價是什麼？**

沒有 DB 層的入場檢查——欄位打錯字、型別不對它照收（補充D 的 1048/1062 都不會發生），檢查責任全部落到程式碼層。方便和保護是一組取捨。

## 速查

| 我想… | 指令 |
|-------|------|
| 起 MongoDB + 介面 | `docker compose -f docker-compose-local.yml up -d mongodb mongo-express` |
| 進 mongo shell | `docker exec -it mongodb mongosh -u root -p 1234` |
| 用 Python 做同樣操作 | `uv run --with jupyter jupyter lab` → 開 `example/pymongo.ipynb` |
| 數文件 | `db.getSiblingDB("mydb").TaiwanStockPrice.countDocuments()` |
| 條件查詢 | `db.TaiwanStockPrice.find({stock_id: "2330"})`（先 `use mydb`）|
| 防重複保底（唯一索引）| `db.TaiwanStockPrice.createIndex({stock_id: 1, date: 1}, {unique: true})` |
| 派送 mongo 版爬蟲（單一 worker）| `uv run crawler/producer_crawler_finmind_mongo_single.py` |
| 派送 mongo 版爬蟲（多佇列分流）| `uv run crawler/producer_crawler_finmind_mongo.py` |
| Web 介面 | http://localhost:8082（root / 1234）|
