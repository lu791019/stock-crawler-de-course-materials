# 補充 G：MongoDB 操作 — pymongo 與 mongo-express

> 補充F 的 mongosh 操作要先 `docker exec` 進容器，門檻較高。這份補充用兩條低門檻的路做**同樣的事**：寫 Python 的用 **pymongo**（配套 notebook `example/pymongo.ipynb` 可以直接跑），不寫程式的用 **mongo-express** 網頁介面。三條路的概念完全相同，選一條順手的就好。

---

## 前置

```bash
# 服務在跑
docker compose -f docker-compose-local.yml up -d mongodb mongo-express

# 集合裡有資料（補充F 的爬蟲；跑過就不用再跑）
uv run crawler/producer_crawler_finmind_mongo_single.py
```

---

## 1. pymongo — 用 Python 做完 mongosh 的每一件事

我們的爬蟲任務（`tasks_crawler_finmind_mongo.py`）用的就是 pymongo——所以你已經用過它的 `update_one(upsert=True)`。連線方式也一樣：

```python
from pymongo import MongoClient

client = MongoClient(host="127.0.0.1", port=27017, username="root", password="1234")
col = client["mydb"]["TaiwanStockPrice"]
```

### 三欄對照表：同一件事的三種寫法

| 你想做 | mongosh（補充F）| pymongo |
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

### 動手跑

打開配套 notebook（跟 `pandas.ipynb` 同一個開法）：

```bash
uv run --with jupyter jupyter lab
# 開 example/pymongo.ipynb，由上往下執行
```

內容依序是：連線與計數 → 查詢（條件/挑欄位/排序/範圍/分組統計）→ 寫入與刪除（schema-free 驗證）→ unique index 防重複（含撞 `DuplicateKeyError` 的驗證）→ 收尾還原。每一段都對照 SQL 和 mongosh 的等價寫法。

執行結果範例（分組統計那格）：

```python
{'_id': '0050', 'avg_close': 130.55, 'days': 603}
{'_id': '2330', 'avg_close': 1234.27, 'days': 608}
```

---

## 2. mongo-express — 不寫程式的網頁介面

http://localhost:8082（root / 1234）→ 點資料庫 `mydb` → 點集合 `TaiwanStockPrice`。

### 介面做得到的事

| 操作 | 在哪裡做 |
|------|---------|
| 瀏覽文件、分頁 | 集合頁面主畫面，上方顯示文件總數 |
| 條件查詢 | 上方查詢框：**Simple** 分頁填 key/value；**Advanced** 分頁直接填 JSON，例如 `{"stock_id": "2330"}` |
| 挑欄位、排序 | **Advanced** 分頁的 **Projection** 欄（`{"_id": 0, "date": 1, "close": 1}`）與 **Sort** 欄（`{"date": -1}`）|
| 分組統計 | **Advanced** 分頁勾選 **Aggregate query**，查詢框改填管線陣列：`[{"$group": {"_id": "$stock_id", "avg_close": {"$avg": "$close"}}}]` |
| 新增文件 | **New Document** 按鈕，直接編輯 JSON |
| 編輯／刪除單筆 | 每份文件旁的編輯（鉛筆）／刪除（垃圾桶）圖示 |
| 看索引、刪索引 | 集合頁面下方 **Indexes** 區塊 |
| 建一般索引 | Indexes 區塊的 **Add Indexes** 按鈕，填索引鍵 JSON：`{"stock_id": 1, "date": 1}` |

### 介面做不到、要靠 pymongo 或 mongosh 的事

- **`distinct`**（列出不重複值）——沒有對應介面
- **unique 索引**——Add Indexes 只能填索引鍵，沒有 unique 選項；防重複保底要用 `col.create_index([...], unique=True)`

### 跟 phpMyAdmin 的對位

| | phpMyAdmin（MySQL）| mongo-express（MongoDB）|
|---|---|---|
| 瀏覽資料 | Browse 頁籤 | 集合頁面 |
| 下查詢 | SQL 頁籤寫 SQL | Advanced 分頁填 JSON |
| 改資料 | 列上的編輯/刪除 | 文件上的編輯/刪除 |
| 管索引 | Structure → Indexes | Indexes 區塊 |

---

## 3. 三條路怎麼選

| 情境 | 用哪條 |
|------|--------|
| 看一眼資料長怎樣、改一兩筆 | mongo-express（零門檻）|
| 分析、批次處理、要進 pipeline | pymongo（能跟 pandas、Celery 銜接）|
| 臨時管理操作、跟著官方文件做事 | mongosh（官方工具，文件範例都用它）|

---

## 速查

| 我想… | 指令 |
|-------|------|
| 開 notebook 練 pymongo | `uv run --with jupyter jupyter lab` → `example/pymongo.ipynb` |
| Web 介面 | http://localhost:8082（root / 1234）|
| pymongo 連線 | `MongoClient(host="127.0.0.1", port=27017, username="root", password="1234")` |
| 唯一索引（介面做不到）| `col.create_index([("stock_id", 1), ("date", 1)], unique=True)` |
| 收工 | `docker compose -f docker-compose-local.yml stop mongodb mongo-express` |
