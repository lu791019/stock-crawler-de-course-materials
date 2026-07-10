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

| 組合 | 意思 | 例子 |
|------|------|------|
| **CA** | 不面對分區——只有一台機器，沒有「機器之間斷線」的問題 | 單機 MySQL（本課的 mydb 就是）|
| **CP** | 斷線時保一致、犧牲可用：連不上多數節點的那一邊停止服務 | etcd（Kubernetes 存設定用）、HBase |
| **AP** | 斷線時保可用、事後補同步（最終一致） | Cassandra、DynamoDB |

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

## 4. 動手：同一支爬蟲，落地改 MongoDB

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
| 佇列派送 | `.s().apply_async(queue=)` | **完全同款**（worker 是同一批）|

### 跑起來

```bash
# worker 要重建一次（image 裡要有 pymongo；pyproject 已收錄、uv sync 會裝）
docker compose -f docker-compose-local.yml up -d --build worker_twse worker_tpex

# 派送 5 支股票（跟 MySQL 版同款的分流路由）
uv run crawler/producer_crawler_finmind_mongo.py
```

執行結果：

```bash
docker exec mongodb mongosh -u root -p 1234 --quiet --eval \
  'db.getSiblingDB("mydb").TaiwanStockPrice.countDocuments()'
# → 3035          ← 5 支股票的歷史資料全部寫入

# 查看其中一份文件——就是 FinMind 回來的 dict 原樣：
# { stock_id: '2330', date: '2024-01-02', Trading_Volume: 27997826, ... }
```

**再跑一次 producer** → countDocuments 仍是 **3035**——重跑不重複，`upsert=True` 就是 Mongo 版的冪等（跟手冊06 同一個觀念、不同語法）。

### 用 mongo-express 看資料

http://localhost:8082 → 資料庫 `mydb` → collection `TaiwanStockPrice` → 直接瀏覽文件、可以搜尋 `{"stock_id": "2330"}`——跟 phpMyAdmin 看表是同一件事。

### 收工

```bash
docker compose -f docker-compose-local.yml down    # mongodb volume 保留資料；要清掉加 -v
```

---

## 5. 什麼時候選誰

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
| 數文件 | `db.getSiblingDB("mydb").TaiwanStockPrice.countDocuments()` |
| 派送 mongo 版爬蟲 | `uv run crawler/producer_crawler_finmind_mongo.py` |
| Web 介面 | http://localhost:8082（root / 1234）|
