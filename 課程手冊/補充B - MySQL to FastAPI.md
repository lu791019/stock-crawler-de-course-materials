# 補充 B：把資料開成 API — MySQL to FastAPI

> 到第 9、10 章為止，資料有兩個出口：Metabase（給**人**看圖表）、BigQuery（給**分析**用）。這一篇補上第三個、也是工程上最常見的出口：**REST API，給程式用**。別的系統（網頁前端、App、其他服務）不會登入你的 MySQL，它們透過 API 拿資料。

---

## 做完這一篇，你會做到

1. 說得出 API 是什麼、常見的 Web API 風格差在哪，以及 Django / Flask / FastAPI 怎麼選。
2. 用 FastAPI 把 MySQL 裡的股價開成三支 REST API。
3. 用瀏覽器打開自動生成的互動式 API 文件（Swagger UI），直接在網頁上試打 API。
4. 看懂參數化查詢為什麼能防 SQL Injection。
5. 分得清資料的三種出口：BI（人）、倉儲（分析）、API（程式）。

---

## 先搞懂：API 是什麼

API（Application Programming Interface，應用程式介面）是**程式與程式之間約定好的溝通方式**：定義「怎麼呼叫、要給什麼參數、會回什麼結果」，呼叫方不需要知道內部怎麼實作。

其實你從第 2 章就一直在用 API——爬蟲打的 FinMind 就是：約定是「GET 這個網址、帶 `dataset` 和 `stock_id` 參數，回 JSON 格式的股價」。FinMind 內部用什麼資料庫、怎麼撈的，你不知道也不需要知道——這就是介面的意義：**只約定輸入輸出，不暴露內部**。

「API」一詞的範圍很廣——pandas 的 `read_sql()` 也是一種 API（函式庫的介面）。本篇講的是 **Web API**：走 HTTP 協定、跨網路呼叫的那種。前面的章節你是「呼叫別人的 API」（消費方），本篇換到另一邊：「把自己的資料開成 API」（提供方）。

## 常見的 Web API 風格

Web API 有很多種風格，差別主要在**資料怎麼傳送**：誰發起、走什麼格式、連線是一次性還是持續的。先看八種常見風格：

| 風格 | 傳送方式 | 特點 | 常見場景 |
|------|---------|------|---------|
| **REST** | 客戶端發 HTTP 請求 → 伺服器回應（一問一答）；HTTP 動詞（GET/POST/PUT/DELETE）＋路徑表達資源，多用 JSON | 最普及、工具鏈最全，瀏覽器和 curl 都能直接打 | 絕大多數公開 API——FinMind 就是 REST |
| **SOAP** | 一問一答；訊息包在 XML 信封（Envelope）裡，規格由 WSDL 文件嚴格定義 | 規範完整（安全、交易、重試都有標準），但笨重、開發慢 | 銀行、金流、保險等老牌企業系統 |
| **GraphQL** | 一問一答；單一端點，客戶端用查詢語言指定要哪些欄位 | 一次拿齊、不多不少；伺服器端實作較複雜 | 前端需求多變的產品（GitHub API v4）|
| **gRPC** | 一問一答為主，也支援雙向串流；HTTP/2 ＋ Protobuf 二進位格式 | 效能高、強型別；瀏覽器不能直接打 | 微服務之間的內部通訊 |
| **WebSocket** | 先 HTTP 握手，之後升級成**持續的雙向通道**，雙方隨時可傳 | 伺服器可主動推送，延遲低；連線管理成本高 | 即時場景：聊天室、即時股價報價 |
| **SSE**（Server-Sent Events） | 一條 HTTP 連線保持開著，**伺服器單向持續推送** | 比 WebSocket 簡單，瀏覽器原生支援自動重連；只能伺服器→客戶端 | 即時通知、看板更新、LLM 逐字輸出（ChatGPT 的打字效果就是 SSE）|
| **Webhook** | 方向反過來：你留一個網址給對方，**事件發生時對方主動 POST 給你**（回呼） | 不用一直輪詢問「有沒有新資料」；你得開一個能被打到的端點 | 付款完成通知、GitHub push 觸發 CI |
| **MQTT** | 發布/訂閱：發送方把訊息交給 **broker**，訂閱方從 broker 收——雙方互不認識 | 極輕量、省電省頻寬；需要多架一個 broker | IoT 感測器、車聯網（和第 1 章的 RabbitMQ 同屬訊息佇列家族）|

八種看似複雜，按**傳送方式**分只有三類：

1. **一問一答**（REST / SOAP / GraphQL / gRPC）——客戶端問一次、伺服器答一次，答完連線就結束。差別只在訊息格式和查詢彈性。
2. **持續連線推送**（WebSocket / SSE / MQTT）——連線建好後一直開著，伺服器有新資料就推過來，不用客戶端反覆問。
3. **反向回呼**（Webhook）——平常沒有連線，事件發生時**對方**才發起請求打到你留的網址。

**想看動圖比較？** 這幾份視覺化資源把上面的傳送方式畫成了動畫和圖解：

- [Top 6 Most Popular API Architecture Styles（ByteByteGo，YouTube 動畫）](https://www.youtube.com/watch?v=4vLxWqE94l4)——SOAP/REST/GraphQL/gRPC/WebSocket/Webhook 六種風格的動畫比較，6 分鐘
- [API Architectural Styles 圖解（ByteByteGo blog）](https://blog.bytebytego.com/p/ep49-api-architectural-styles)——同主題的靜態總覽圖
- [API 風格比較 cheatsheet（ByteByteGo）](https://bytebytego.com/guides/a-cheatsheet-on-comparing-api-architectural-styles/)——一張表比完各風格的格式、效能、適用場景
- [Polling vs Long Polling vs SSE vs WebSockets vs Webhooks（AlgoMaster）](https://blog.algomaster.io/p/polling-vs-long-polling-vs-sse-vs-websockets-webhooks)——「持續連線推送」三兄弟＋Webhook 的逐格圖解
- [短輪詢/長輪詢/SSE/WebSocket 圖解（ByteByteGo）](https://bytebytego.com/guides/shortlong-polling-sse-websocket/)——四種即時傳送方式的時序圖
- [MQTT Pub/Sub 架構圖解（HiveMQ MQTT Essentials Part 2）](https://www.hivemq.com/blog/mqtt-essentials-part2-publish-subscribe/)——發布/訂閱模式的官方圖解系列

本篇做的是 **REST**——跟你打了十幾章的 FinMind 同一種風格，只是角色從呼叫方變成提供方。

## 為什麼我們的系統需要 API 這個出口

想像你做了一個「台股看盤網頁」。網頁的 JavaScript 要拿股價，選項有：

- ❌ **直接連 MySQL**：等於把資料庫帳密放進前端程式碼，任何人打開開發者工具就拿到你的 root 密碼。
- ✅ **透過 API**：前端只能呼叫你**開放的那幾個查詢**，資料庫躲在 API 後面，帳密不外洩、查詢範圍你控制。

這就是 API 在資料系統裡的角色：**資料庫的守門員**。外界不碰資料庫本體，只能走你開的門。

## Python 用什麼寫 API：Django vs Flask vs FastAPI

Python 生態最常見的三個 Web 框架：

| | **Django**（2005）| **Flask**（2010）| **FastAPI**（2018）|
|---|---|---|---|
| 定位 | 全功能框架（batteries included）| 微框架，核心極小 | 現代 API 框架 |
| 內建 | ORM、後台管理、認證、模板引擎全包 | 只有路由與請求處理，其餘自己拼裝 | 型別驗證、自動文件；ORM 等自選 |
| 寫 API | 要加 Django REST Framework | 要加 flask-restful 等擴充 | 原生就是為 API 設計 |
| 非同步 | 3.0 起支援 ASGI | 原生同步（WSGI）| 原生 ASGI，async 是一等公民 |
| 適合 | 完整網站：內容管理、會員系統、後台 | 小型服務、高自由度組裝 | 純 API 服務、微服務、ML model serving |

選型參考：要做「整個網站」→ Django；要極簡自由拼裝 → Flask；要做「資料 API 服務」→ FastAPI。本課的需求是把 MySQL 資料開成查詢端點——標準的 FastAPI 場景。

### 同一支 API，三個框架分別怎麼寫

光看表格感受不深，拿最簡單的需求當比較基準：開一支 `GET /stocks`，回傳股票清單 JSON。

> **這一段用看的就好，不用跟做。** 本篇的動手實作只有 FastAPI 版（後面的 `api/main.py`）。Django 和 Flask 的範例是給你對照寫法用的——本篇不會帶你建這兩個框架的環境，想自己試的話照各段最後的說明。

**Django** —— 要先 `django-admin startproject` 建專案結構，至少動兩個檔案：`views.py` 寫處理函式、`urls.py` 註冊路徑：

```python
# views.py
from django.http import JsonResponse

def list_stocks(request):
    return JsonResponse({"stocks": ["2330", "2317", "2454"]})
```

```python
# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("stocks", views.list_stocks),
]
```

啟動：`python manage.py runserver`。函式和路徑分在兩個檔案，是 Django 專案結構的約定；要做完整 REST API（序列化、權限、分頁）通常還要再裝 Django REST Framework。

> ⚠️ 注意兩件事：①本課環境**沒有安裝 Django**（`uv sync` 不會裝）；②這兩段程式碼**不能存成兩個散檔直接跑**——`views.py` 和 `urls.py` 必須放在 `django-admin startproject` 產生的專案結構裡才有效。這正是表格說的「全功能框架」的代價：連開一支最簡單的 API 都要先有專案骨架。想自己試的話：`pip install django` → `django-admin startproject demo` → 把兩段程式碼放進對應檔案。

**Flask** —— 單一檔案就能跑，路徑用裝飾器直接綁在函式上：

```python
# app.py
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/stocks")
def list_stocks():
    return jsonify({"stocks": ["2330", "2317", "2454"]})
```

啟動：`flask --app app run`（預設開在 http://localhost:5000 ）。沒有專案結構的負擔，但參數驗證、API 文件都要自己處理（或另裝擴充套件）。

> 想自己試的話：flask 已包含在本課依賴裡（`uv sync` 會裝），找個空資料夾把上面存成 `app.py` 就能跑。但本篇不會帶做——實作留給 FastAPI 版。

**FastAPI** —— 寫法跟 Flask 幾乎一樣，但多送三樣東西：自動文件（`/docs`）、型別驗證、原生 async：

```python
# app.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/stocks")
def list_stocks():
    return {"stocks": ["2330", "2317", "2454"]}
```

啟動：`uvicorn app:app --reload`。回傳 dict 自動轉 JSON；打開 `http://localhost:8000/docs` 就有互動式文件，一行文件都不用寫。

三段程式碼放在一起看：**核心模式相同**——一個函式處理請求、一條路徑對到一個函式，差別在框架幫你做多少事。這也是為什麼會了其中一個，換另一個的學習成本不高。

## FastAPI 是什麼

2018 年發布，架在兩個成熟套件之上：**Starlette**（處理 HTTP 的 ASGI 框架）＋ **Pydantic**（用型別註記做資料驗證）。三個招牌能力，後面的程式碼全會用到：

1. **型別註記＝自動驗證**：參數宣告成 `limit: int = Query(30, ge=1, le=1000)`，解析、轉型、範圍檢查框架全做，驗證邏輯一行都不用寫
2. **自動生成互動式文件**：從型別註記生成 OpenAPI 規格，`/docs` 直接開出 Swagger UI（Step 4 會看到）
3. **原生 async**：需要高併發時把函式改成 `async def` 即可（本篇教學版用同步寫法就夠）

FastAPI 本身只負責「定義」API，實際跑起來需要 ASGI 伺服器 **uvicorn**——這就是 Step 2 指令 `uv run uvicorn api.main:app` 的由來。

---

## 這一篇會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `api/main.py` | API 定義 | 三支端點：股票清單、歷史價格、最新價格 |
| `crawler/config.py` | 設定 | 沿用同一套 MySQL 連線設定（複用第 1 章的設定中心）|

依賴（`fastapi`、`uvicorn`）已在 `pyproject.toml` 裡，`uv sync` 就會裝好。

---

## 一行一行讀懂 `api/main.py`

### ① 建立 app 與資料庫引擎

```python
from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import create_engine, text
from crawler.config import MYSQL_ACCOUNT, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT

app = FastAPI(
    title="Stock Price API",
    description="台股股價查詢 API — stock-crawler 教學專案的資料出口",
    version="0.1.0",
)

engine = create_engine(
    f"mysql+pymysql://{MYSQL_ACCOUNT}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/mydb"
)
```

- `FastAPI(...)` 建立整個 API 應用，`title` / `description` 會直接出現在自動生成的文件頁上。
- `create_engine` 放在**模組層級**（不在函式裡）——app 存活期間共用同一個連線池（第 5 章講過 engine 是連線池管理者）。
- 注意 import 的是 `crawler.config`——**API 和爬蟲共用同一個設定中心**。第 1 章的設計在這裡又賺到一次。

### ② 健康檢查端點

```python
@app.get("/")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "database": f"error: {e}"}
```

- `@app.get("/")` 是 FastAPI 的路由裝飾器：「GET 方法打 `/` 這個路徑時，執行這個函式」。**像不像 `@app.task`？** 同一個模式——裝飾器把普通函式註冊進框架。
- 函式 return dict，FastAPI 自動轉成 JSON 回給呼叫者。
- 健康檢查是每個正式服務的標配（第 13 章 compose 的 healthcheck 打的就是這種端點）。

### ③ 股票清單

```python
@app.get("/stocks")
def list_stocks():
    sql = """
        SELECT stock_id, COUNT(*) AS records,
               MIN(date) AS first_date, MAX(date) AS last_date
        FROM TaiwanStockPrice
        GROUP BY stock_id
        ORDER BY stock_id
    """
    df = pd.read_sql(sql, engine)
    return df.to_dict(orient="records")
```

- `pd.read_sql` 第 5 章用過（查詢 → DataFrame）；`to_dict(orient="records")` 把 DataFrame 變成 list of dict，FastAPI 再變成 JSON。
- 一條熟悉的路：**SQL → DataFrame → JSON**。

### ④ 歷史價格（重點：參數化查詢）

```python
@app.get("/stocks/{stock_id}/prices")
def get_prices(
    stock_id: str,
    start_date: str | None = Query(None, description="起始日 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="結束日 YYYY-MM-DD"),
    limit: int = Query(30, ge=1, le=1000, description="最多回傳幾筆"),
):
    sql = "SELECT ... FROM TaiwanStockPrice WHERE stock_id = :stock_id"
    params = {"stock_id": stock_id}
    if start_date:
        sql += " AND date >= :start_date"
        params["start_date"] = start_date
    ...
    df = pd.read_sql(text(sql), engine, params=params)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"找不到 {stock_id} 的資料")
    return df.to_dict(orient="records")
```

三個關鍵：

- **路徑參數 + 查詢參數**：`{stock_id}` 從網址路徑來；`start_date` / `limit` 從 `?start_date=...&limit=...` 來。FastAPI 靠**型別註記**自動解析、驗證（`limit` 給了 `ge=1, le=1000`，傳 5000 會直接被擋，你一行驗證邏輯都沒寫）。
- **參數化查詢（最重要）**：SQL 裡寫 `:stock_id` 佔位符、值放在 `params` dict——**絕不把使用者輸入用 f-string 拼進 SQL**。如果拼字串，有人傳 `stock_id = "2330' OR '1'='1"` 就能改寫你的查詢（SQL Injection）。參數化讓輸入永遠只是「值」，不可能變成 SQL 語法。
- **`HTTPException(404)`**：查無資料回標準的 404 + 錯誤訊息，呼叫端好處理。API 的錯誤也要是「設計過的」。

### ⑤ 最新一筆

```python
@app.get("/stocks/{stock_id}/latest")
def get_latest(stock_id: str):
    # ORDER BY date DESC LIMIT 1 —— 跟第 8 章 Metabase 數字卡片同一招
```

---

## 一步一步跟著做

### Step 1：確認 MySQL 有資料

```bash
docker compose -f docker-compose-local.yml up -d mysql
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) FROM TaiwanStockPrice GROUP BY stock_id" 2>/dev/null
```

沒資料就載 mock：

```bash
docker exec -i mysql mysql -uroot -p1234 mydb < example/mock_stock_price_data.sql
```

### Step 2：啟動 API

```bash
uv run uvicorn api.main:app --reload --port 8000
```

- `uvicorn` 是 ASGI 伺服器（FastAPI 需要它來跑）；`api.main:app` = 「`api/main.py` 裡那個叫 `app` 的物件」——跟 `celery -A crawler.worker` 指定 app 是同一個邏輯。
- `--reload`：改程式碼自動重啟，開發時好用。

> ✅ 看到 `Uvicorn running on http://127.0.0.1:8000` 就過關。

### Step 3：打 API

另開終端機（或用瀏覽器直接開網址）：

```bash
# 健康檢查
curl http://localhost:8000/
# → {"status":"ok","database":"connected"}

# 股票清單
curl http://localhost:8000/stocks

# 台積電最新收盤
curl http://localhost:8000/stocks/2330/latest

# 歷史價格（限 3 筆）
curl "http://localhost:8000/stocks/2330/prices?limit=3"

# 指定日期範圍
curl "http://localhost:8000/stocks/2330/prices?start_date=2025-06-01&end_date=2025-06-13"

# 查不存在的股票 → 404
curl http://localhost:8000/stocks/9999/latest
# → {"detail":"找不到 9999 的資料"}
```

### Step 4：打開自動生成的互動式文件（FastAPI 的招牌）

瀏覽器開 **http://localhost:8000/docs** 。

**先搞清楚兩個名詞**，很多人把它們混在一起：

- **OpenAPI**：一種描述 REST API 的**標準格式**（JSON）——這個服務有哪些端點、每個端點收什麼參數、參數什麼型別、回應長什麼樣。它只是一份規格文件，不是網頁。這個標準的前身就叫 Swagger，所以兩個詞常混用。
- **Swagger UI**：把 OpenAPI 規格**渲染成互動網頁**的工具——讓你用點的看文件、用填的試打 API。

FastAPI 的生成鏈是三層，你可以逐一打開驗證：

```
你的程式碼（路由 + 型別註記）
    ↓ FastAPI 自動生成
http://localhost:8000/openapi.json   ← OpenAPI 規格本體（一大包 JSON）
    ↓ 用兩種介面渲染
http://localhost:8000/docs     ← Swagger UI（可互動試打）
http://localhost:8000/redoc    ← ReDoc（純閱讀版，不能試打）
```

**在 /docs 上試打一支 API 的操作**：

1. 點開 `GET /stocks/{stock_id}/prices` 這一列展開
2. 按右上角 **Try it out**——參數欄位變成可輸入
3. 填 `stock_id` = `2330`、`limit` = `5`
4. 按 **Execute**
5. 往下看結果區：Swagger UI 幫你組好的 **curl 指令**、實際打的 **Request URL**、以及**回應的 JSON**——跟你 Step 3 手打 curl 是同一件事，只是變成點按

這份文件你一行都沒寫——FastAPI 從路由和型別註記自動生成。這帶來一個重要性質：**文件永遠跟程式碼同步**。傳統手寫 API 文件最大的問題是「程式改了、文件忘了改」，自動生成把這個問題整個消掉。實務上 /docs 也是前後端協作的介面契約：後端把 /docs 網址丟給前端，前端就知道每支 API 怎麼呼叫、會回什麼。

> ✅ 在 /docs 頁面成功試打一次 `/stocks/{stock_id}/prices`，這一篇就完成了。

### Step 5：收工

```bash
# API：Ctrl+C
docker compose -f docker-compose-local.yml down
```

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | `/` 回 `database: connected` | API 與 DB 連通 |
| 2 | `/stocks` 回股票清單 JSON | SQL → DataFrame → JSON 的路通了 |
| 3 | `limit=5000` 被自動擋下（422）| 型別註記就是驗證 |
| 4 | 查不存在的股票回 404 | 錯誤處理是設計過的 |
| 5 | /docs 能互動試打 | 自動文件生成 |

---

## 想再深入一點

- **三個出口的分工，現在完整了**：Metabase 給人看（第 8 章）、BigQuery 給大規模分析（第 14 章）、API 給程式呼叫（本篇）。三者都只是「讀取 MySQL 的不同姿勢」——上游的爬蟲 pipeline 一行都不用改。這就是分層架構的威力。
- **為什麼 API 不直接讓外界下任意 SQL？** 因為 API 的價值就在「限制」：只開放安全的、設計過的查詢。權限控制、流量限制、輸入驗證都在這層做。
- **正式部署還缺什麼？** 本篇是教學版。上線前至少還要：認證（API key / OAuth）、rate limiting、CORS 設定、用 gunicorn+uvicorn workers 跑多行程。這些是後端工程的下一步。

---

## 想一想（確認你懂了）

**Q1：前端網頁為什麼不能直接連 MySQL，一定要繞 API？**

直接連要把資料庫帳密交給前端，等於公開；而且資料庫沒辦法限制「只能做哪幾種查詢」。API 是守門員：帳密留在伺服器端，外界只能走你開的那幾扇門，每扇門的輸入都經過驗證。

**Q2：參數化查詢防的是什麼攻擊？原理是什麼？**

防 SQL Injection。原理：把 SQL 語句和「值」分開送給資料庫——`:stock_id` 佔位符的位置永遠只會被當成**值**處理，就算使用者輸入了 `' OR '1'='1` 這種字串，它也只是一個奇怪的股票代碼，不可能變成 SQL 語法的一部分。

**Q3：`@app.get(...)` 和 `@app.task()`，模式上像在哪？**

都是「裝飾器把普通函式註冊進框架」：`@app.task()` 把函式登記成 Celery 可派送的任務；`@app.get()` 把函式登記成 FastAPI 某路徑的處理者。框架收到對應的觸發（訊息 / HTTP 請求）時，就知道該呼叫哪個函式。

---

## 換你試試看

**練習 1：加一支「總覽」端點**

新增 `GET /summary`：回傳總股票數、總筆數、資料最早和最晚日期（一條 SQL 就夠）。加完存檔，`--reload` 會自動重啟，直接在 /docs 試打。

**練習 2：故意試 SQL Injection**

用 curl 打 `http://localhost:8000/stocks/2330%27%20OR%20%271%27=%271/latest`（URL 編碼的注入字串）。你會得到 404 而不是整張表——參數化查詢把它當成一個不存在的股票代碼。這確認了防線有效。

**練習 3：讓 API 查 VIEW**

把 `/stocks/{stock_id}/prices` 的表名換成第 8 章建的 `vw_stock_price_daily`（欄位名要對應調整）。這讓你體會：API 查「清理過的 VIEW」而不是原始表，是實務上常見的組合——髒資料在 DB 層就擋掉了。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| `ModuleNotFoundError: fastapi` | 依賴沒裝 | 根目錄 `uv sync` |
| `/` 回 `degraded` | MySQL 沒起來或連不到 | `docker compose -f docker-compose-local.yml up -d mysql` |
| `/stocks` 回 500 | `mydb` 沒有 TaiwanStockPrice 表 | 載 mock 資料（Step 1）|
| 8000 被占用 | 別的程式在用 | 換 port：`--port 8001` |
| 改了程式沒生效 | 沒加 `--reload` | 重啟或加上 `--reload` |

---

## 附錄：同一組 API 的 ORM 版（選讀）

> 本篇主線用「手寫 SQL」撈資料。這個附錄提供另一條路線的完整對照：**ORM**。用看的就好，想動手的話 repo 裡有完整可跑的檔案。

### 先分清楚：我們主線用了 SQLAlchemy，但沒用它的 ORM

SQLAlchemy 這個套件分兩層：

| 層 | 主線有沒有用 | 用來做什麼 |
|----|:---:|-----------|
| **Core**（`create_engine`、`text()`）| ✅ 有 | 管連線池、安全執行你手寫的 SQL |
| **ORM**（`Session`、Model class）| ❌ 沒有 | 把 table 變成 Python class，讓你不寫 SQL |

ORM（Object-Relational Mapping）把 **table 映射成 class、每一列映射成物件**：查詢用 Python 方法鏈寫，SQL 由框架生成；拿回來的不是 DataFrame，是有屬性的 Python 物件（`row.close` 而不是 `df["close"]`）。

### repo 附了完整可跑的 ORM 版：`api/main_orm.py`

四支端點跟主線的 `api/main.py` **一模一樣**（含 Swagger 上可填的 `stock_id`、`start_date`、`end_date`、`limit` 參數），只是撈資料的寫法全部換成 ORM。可以跟 SQL 版**同時開、互不干擾**：

```bash
# 視窗 1：SQL 版（主線）
uv run uvicorn api.main:app --reload --port 8000

# 視窗 2：ORM 版（附錄）
uv run uvicorn api.main_orm:app --reload --port 8001
```

開兩個瀏覽器分頁：http://localhost:8000/docs 和 http://localhost:8001/docs ，
對同一支 API 填同樣的參數按 Execute——**回應完全相同**，差的只是伺服器內部怎麼組查詢。

### 兩版的關鍵差異（對著兩個檔案看）

| | SQL 版 `api/main.py` | ORM 版 `api/main_orm.py` |
|---|---|---|
| 前置成本 | 零——會 SQL 就能動 | 要先定義 `StockPrice` Model class，欄位跟表一一對應 |
| 動態加條件 | 拼 SQL 字串 + params dict | `.where()` 一路往上疊 |
| 拿回的東西 | DataFrame，一行 `to_dict` 轉 JSON | `StockPrice` 物件，要自己轉 dict |
| 防注入 | `:佔位符` 參數化 | 生成的 SQL 本來就參數化——**兩邊都安全** |
| 聚合查詢（/stocks）| `GROUP BY` 直接寫 | `func.count()` / `func.min()` 組出同一句 SQL |

一個 ORM 特有的細節：ORM 規定 Model 一定要宣告主鍵，但 mock 表沒設主鍵——沒關係，主鍵宣告在 Model 上就好（`date` + `stock_id` 一天一股一筆，天然唯一）。

### 什麼時候會選 ORM？

主線選手寫 SQL 的理由：本課一路都是 SQL（第 5 章、Metabase、BigQuery），查詢型態是「讀取＋聚合」，`pd.read_sql` 直通 DataFrame。反過來，**CRUD 為主的業務系統**（會員、訂單）、物件關聯多、團隊不想維護 SQL 字串時，ORM 是主流選擇——Django 內建的就是一套 ORM，Django 世界幾乎不手寫 SQL。

---

## 這一篇你學到了

- API 是程式之間約定好的介面；Web API 風格按傳送方式分三類——一問一答（REST/SOAP/GraphQL/gRPC）、持續連線推送（WebSocket/SSE/MQTT）、反向回呼（Webhook）。其中 REST 最普及——呼叫 FinMind 和本篇提供的服務都是 REST。
- API 是資料的第三個出口：給程式用、資料庫的守門員。
- Python 三大框架分工：Django 做完整網站、Flask 極簡拼裝、FastAPI 專攻 API 服務。
- FastAPI 三件套：路由裝飾器、型別註記（自動驗證）、自動文件。
- 參數化查詢是防 SQL Injection 的鐵律。
- SQL → DataFrame → JSON，全是你已經會的積木。
