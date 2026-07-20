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

### REST 的動作語彙：HTTP 動詞

REST 的一句請求由兩部分組成：**動詞**（對資源做什麼）＋**路徑**（哪個資源）。常用動詞五個：

| 動詞 | 語意 | 對應資料操作 | 範例（假想的完整股價服務）|
|------|------|:---:|--------------------------|
| **GET** | 查詢，不改變資料 | Read | `GET /stocks/2330/prices` 查 2330 的股價 |
| **POST** | 新增一筆資源 | Create | `POST /stocks` 新增一支股票 |
| **PUT** | 整筆覆蓋更新 | Update | `PUT /stocks/2330` 用整包新資料取代 2330 |
| **PATCH** | 部分欄位更新 | Update | `PATCH /stocks/2330` 只改其中幾個欄位 |
| **DELETE** | 刪除資源 | Delete | `DELETE /stocks/2330` 刪掉 2330 |

兩個設計慣例值得記：

- **GET 是「安全」的**：只讀不寫，打幾次都不會改變伺服器上的資料——所以瀏覽器網址列、搜尋引擎爬蟲都只發 GET。
- **冪等在 HTTP 層重演**（手冊06 的概念）：GET / PUT / DELETE 重複執行結果不變（刪掉的東西再刪一次，狀態還是「已刪除」）；**POST 不冪等**——重送一次就多建一筆。這就是付款頁警告「請勿重複點擊送出」的原因。

本篇的 API 只開 **GET**：這個服務定位是「資料的查詢出口」，寫入由爬蟲 pipeline 負責（第 5、6 章），不開放外界寫入——**開放哪些動詞本身就是權限設計**。

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

> ⚠️ 兩個前提：①本課環境**沒有安裝 Django**（`uv sync` 不會裝）；②這兩段程式碼**不能存成兩個散檔直接跑**——必須放進 `django-admin startproject` 產生的專案結構裡。這正是表格說的「全功能框架」的代價：連開一支最簡單的 API 都要先有專案骨架。

想自己完整跑一次的話，照下面四步（找一個**課程專案以外**的資料夾做）：

```bash
# ① 開一個獨立的 uv 專案裝 Django（跟本課同一套工具，但不要裝進課程專案）
mkdir django-demo && cd django-demo
uv init          # 生成 pyproject.toml（附帶的 main.py、README.md 這裡用不到，可忽略）
uv add django    # 跟本課裝套件同一套做法：寫進 pyproject.toml 並裝進 .venv

# ② 生成專案骨架
uv run django-admin startproject demo
```

`startproject` 會生出這個結構——兩段範例程式碼要搬去的位置標了 ★：

```
demo/
├── manage.py            ← 指令入口：runserver、migrate 都靠它
└── demo/                ← 專案套件（跟外層資料夾同名，第一次看容易搞混）
    ├── __init__.py
    ├── settings.py      ← 全專案設定：資料庫、時區、掛了哪些 app
    ├── urls.py          ← ★ 用上面的 urls.py 範例「整檔取代」
    ├── views.py         ← ★ 新建這個檔，內容就是上面的 views.py 範例
    ├── asgi.py          ← 部署用入口（ASGI 伺服器）
    └── wsgi.py          ← 部署用入口（WSGI 伺服器）
```

```bash
# ③ 搬程式碼：在 demo/demo/ 裡新建 views.py、整檔取代 urls.py

# ④ 啟動，另開終端機打打看
cd demo
uv run python manage.py runserver   # uv run 會自動往上找到 django-demo 的環境
curl http://127.0.0.1:8000/stocks   # runserver 預設開在 8000
# → {"stocks": ["2330", "2317", "2454"]}
```

`runserver` 啟動的是 **Django 內建的開發用 WSGI 伺服器**——角色等同 Flask 的 `flask run`、FastAPI 的 `uvicorn --reload`：只供開發（改檔自動重載）。上線不用它，而是把 `wsgi.py` 或 `asgi.py` 入口交給 gunicorn / uvicorn 這類正式伺服器（兩種入口的差別見「想再深入一點」的「WSGI 與 ASGI」節）。

補充：正式的 Django 專案不會把 `views.py` 直接放在專案套件裡，而是 `python manage.py startapp stocks` 建獨立的 app 再掛進 `settings.py`——那套結構屬於 Django 的課程範圍，這裡只走到「同一支 API 實際跑起來」為止。

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

FastAPI 這段有三個常被跳過的名詞，先說清楚：

- **uvicorn 是什麼？** FastAPI 只負責「定義 API」（哪些路徑、收什麼參數、怎麼處理），它自己**不會聽網路連線**。實際開 port、接收 HTTP 請求、把請求交給 app 處理的是 **uvicorn**——一個 ASGI 伺服器（ASGI 是什麼？「想再深入一點」有「WSGI 與 ASGI」專節）。Django 和 Flask 都內建了開發伺服器（`manage.py runserver`、`flask run`），FastAPI 把伺服器拆出去獨立，所以啟動指令是 `uvicorn` 開頭。
  - `uvicorn app:app` 的讀法是「**檔名:變數名**」——去 `app.py` 裡找那個叫 `app` 的 FastAPI 物件。本課主線的 `uvicorn api.main:app` 同理：`api/main.py` 裡的 `app`
  - `--reload`：開發模式，存檔自動重啟；上線不開
- **`/docs` 是什麼？** FastAPI 從路由和型別註記自動生成 OpenAPI 規格，再用 Swagger UI 渲染成可互動試打的網頁。兩個名詞的關係和試打操作，在後面 Step 4 有完整說明
- **撈資料一定要 ORM 嗎？** 不用。FastAPI 不綁定資料層（表格裡「ORM 等自選」的意思）：本篇主線手寫 SQL（`api/main.py`），文末「附錄一」有同一組端點的 ORM 版（`api/main_orm.py`），兩種寫法的差異對照也在那裡

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

**路徑參數 vs 查詢參數，怎麼選？** 這支端點同時用了兩種，差異值得停下來看清楚：

| | 路徑參數 `{stock_id}` | 查詢參數 `?limit=5` |
|---|---|---|
| 放什麼 | 資源的**身分**——你在指名「哪一個」 | 對結果的**修飾**——篩選、排序、分頁 |
| 少了它會怎樣 | 網址不成立（`/stocks//prices` 沒有意義）| 有預設值，不給也能跑（`limit` 預設 30）|
| 在這支端點 | `/stocks/2330/prices`——2330 是主角 | `?start_date=...&limit=5`——只是查詢條件 |

判斷口訣：**指名資源用路徑，過濾結果用查詢字串**。對照一下：FinMind 把股票代碼放查詢參數（`?data_id=2330`）也能運作——這是設計風格的差異，REST 慣例偏好把資源身分放進路徑，讓網址讀起來像一句話：「2330 這支股票的 prices」。

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

# 參數超出範圍 → 422（limit 上限是 1000，一行驗證邏輯都沒寫，FastAPI 自動擋）
curl "http://localhost:8000/stocks/2330/prices?limit=5000"
# → {"detail":[{"type":"less_than_equal","loc":["query","limit"],
#      "msg":"Input should be less than or equal to 1000","input":"5000","ctx":{"le":1000}}]}
```

最後那個 422 值得多看一眼：錯誤訊息精確指出**哪個參數**（`["query","limit"]`）、**什麼規則沒過**（≤1000）、**你給了什麼**（5000）——這是 `Query(30, ge=1, le=1000)` 那行型別註記自動換來的。

### 看懂 API 回的狀態碼

上面幾發 curl 已經蒐集到三種狀態碼了。狀態碼是 HTTP 的通用語言，第一位數字就分好了陣營：

| 狀態碼 | 意思 | 本篇哪裡遇到 | 誰的責任 |
|--------|------|------------|---------|
| **200** OK | 成功 | 每次查詢成功 | — |
| **404** Not Found | 資源不存在 | 查 9999——我們自己 `raise HTTPException(404)` | 呼叫方（查了不存在的東西）|
| **422** Unprocessable Entity | 參數驗證不過 | `limit=5000`——FastAPI 自動回 | 呼叫方（參數不合規則）|
| **500** Internal Server Error | 伺服器內部錯誤 | 程式有 bug、或 DB 掛了沒處理到 | 提供方（我們的鍋）|

記法：**2xx 成功；4xx 呼叫方的錯**（改請求再試）；**5xx 提供方的錯**（呼叫方等修就好）。再注意一個分層：**404 是我們設計的**（業務邏輯：查無此股票）、**422 是框架送的**（機械規則：參數不合法）——好的 API 讓兩層錯誤各司其職。

> 想看一次 HTTP 往返的完整報文（request/response 的 headers、狀態列），加 `-v`：`curl -v http://localhost:8000/`。報文結構屬於網路基礎課的範圍，這裡知道「curl -v 看得到」就夠。

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

**試打 API 的工具不只 curl 和 /docs**，實務上依場景選：

| 工具 | 形態 | 適合場景 |
|------|------|---------|
| **curl** | 指令列 | 快速一次性測試、寫進文件和腳本 |
| **Swagger UI**（/docs）| 內建網頁 | 開發中自測、丟給前端當契約 |
| **[Postman](https://www.postman.com/)** | 桌面 App | 把請求存成集合、團隊共用、寫自動化測試——業界最普及 |
| **[HTTPie](https://httpie.io/)** | 指令列 | 語法比 curl 直覺（`http :8000/stocks`），輸出自動上色 |

工作流程通常是：開發時用 /docs 自測 → 要重複測、跨團隊共用時進 Postman → 寫進 CI 或文件時用 curl。

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

### 為什麼主線全用 `def`，不用 `async def`？

框架比較表寫 FastAPI「async 是一等公民」，但 `api/main.py` 四支端點全是普通 `def`——這不是偷懶，是正確選擇。理由值得完整講一次：

**async 解決什麼問題？** 傳統模型是「一個請求佔一個執行緒」，請求在等資料庫回覆時，執行緒就閒著空等。async 模型改成單執行緒**事件迴圈**：程式跑到「要等待 IO」的地方（`await`）就先放手，去服務別的請求，等 IO 好了再回來接著跑——高併發時不用開幾千個執行緒，就能同時掛著幾千個等待中的請求。

**關鍵規則：`async def` 裡只能放「不會卡住」的操作。** `pd.read_sql`、`time.sleep`、`requests.get` 這些**同步阻塞**呼叫，放進 `async def` 會把整個事件迴圈卡死——不是只有這個請求變慢，是**所有**請求一起排隊等你。這是 async 最常見的誤用。

**FastAPI 對 `def` 的處理很聰明**：你寫普通 `def`，它自動把函式丟到執行緒池（threadpool）裡跑，不佔事件迴圈。所以本篇的選擇是對的——`pd.read_sql` 是同步阻塞，配 `def` 讓 FastAPI 幫你隔離。

**什麼時候改用 `async def` 才划算？** 兩個條件要同時成立：①改用支援 async 的函式庫（HTTP 用 `httpx`、MySQL 用 `asyncmy`、SQLAlchemy 有 async engine）；②場景真的是高併發 IO 等待——例如一支端點要打三個外部 API 再彙整結果，async 版可以三個同時等，而不是排隊等。

一句話總結：**阻塞的程式碼配 `def`，有 `await` 的程式碼配 `async def`**——放錯邊才是災難。

### WSGI 與 ASGI：伺服器和 Python 程式之間的介面標準

前面出現過兩個沒展開的名詞：框架表寫 Flask「原生同步（WSGI）」、FastAPI「原生 ASGI」。這節把它們講完整。

**它們是什麼？** WSGI（**W**eb **S**erver **G**ateway **I**nterface）和 ASGI（**A**synchronous **S**erver **G**ateway **I**nterface）是「網頁伺服器」與「Python 應用程式」之間的**介面標準**：規定伺服器收到 HTTP 請求後用什麼格式交給 Python 程式、程式用什麼格式把回應交回去。

**為什麼需要這層標準？** 三個理由：

1. **翻譯**：網頁伺服器（Nginx、Apache）不懂 Python，兩邊需要一份約定好的溝通格式
2. **拆分關注點**：網路流量端（連線管理、HTTPS、靜態檔案）和應用邏輯端（你寫的端點）各管各的，各自專注自己的強項
3. **可替換**：只要符合同一標準，伺服器和框架可以自由組合——Flask 換成 Django，gunicorn 照跑不誤，不被特定組合綁死

**兩者的差別：同步 vs 非同步**（上一節事件迴圈的概念直接接上）

| | **WSGI** | **ASGI** |
|---|---|---|
| 處理模型 | 同步：一個請求佔住一個執行緒/行程，直到回應完成 | 非同步：事件迴圈，單執行緒掛著多個等待中的請求 |
| I/O 密集場景 | 等資料庫、等外部 API 時執行緒閒置空等，高併發時成為瓶頸 | 等待時先服務別的請求，空檔被填滿 |
| 連線形態 | 一來一往：請求→回應→結束 | 連線可持續存在、雙向傳輸——WebSocket / SSE 這些長連線靠的就是它 |
| 對應伺服器 | gunicorn、uWSGI | **uvicorn**、hypercorn |
| 代表框架 | Flask（原生）、Django（傳統路線）| FastAPI（原生）、Django 3.0+ |

**框架對號入座**（把前面的知識收攏）：

- **Flask**：原生 WSGI。2.0 之後「可以寫」`async def` view，但底層還是 WSGI，拿不到 ASGI 的併發好處
- **Django**：3.0 起**兩條都通**——還記得 Django 搬運步驟那棵目錄樹裡 `wsgi.py` 和 `asgi.py` **並存**嗎？那就是證據：要走哪條，就把哪個入口檔交給對應的伺服器
- **FastAPI**：原生 ASGI——這就是啟動指令是 `uvicorn` 開頭的根本原因
- 下一節上線清單的 `gunicorn -k uvicorn.workers.UvicornWorker`：gunicorn 當行程管理者、裡面每個 worker 是 uvicorn——兩派的混合部署法

**ASGI 的長連線怎麼運作？** WSGI 的模型裡「一問一答」就是全部；ASGI 的連線建立後持續存在，訊息隨時雙向流動。沒有「一問一答」的配對，雙方就得約定**事件格式**：每則訊息自帶「這是什麼事件、內容是什麼」（常用 JSON 描述），收到的一方按事件類型分派處理——這叫**事件驅動**架構，跟第 1 章 RabbitMQ 的「訊息帶著任務內容」是同一族思路。彈性很大，代價是事件格式要先設計好、有限度地規範，否則後續維護困難。

### 上線前還缺什麼？（概念版檢查清單）

本篇是教學版。下面每一項都是上線前的必修，這裡講清楚概念，實作屬於後端工程的下一步：

**CORS（跨來源資源共享）**——瀏覽器有「同源政策」：A 網域載入的網頁，預設**不准**用 JavaScript 去打 B 網域的 API。所以你的看盤網頁（`https://myapp.com`）打你的 API（`https://api.myapp.com`）會被瀏覽器擋下——注意是**瀏覽器**在擋，所以 curl 和 `requests` 從來不會遇到這問題（它們不是瀏覽器）。解法是 API 端明白宣告「我允許哪些網域的網頁來打」：

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myapp.com"],   # 白名單，不要偷懶寫 ["*"]
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

**分頁（pagination）**——`limit` 只是第一步。資料一多，呼叫方需要「翻頁」：
- **offset 分頁**：`?limit=30&offset=60` 拿第三頁。直覺，但翻到深頁時資料庫還是得掃過前面所有列，愈翻愈慢
- **cursor 分頁**：帶上一頁最後一筆的鍵值當起點（股價場景就是 `?after_date=2025-06-01`），資料庫直接從索引定位。大表的標準做法

**版本管理**——路徑加前綴：`/v1/stocks/...`。原因：API 一公開就有人依賴它，你改了回傳格式就是弄壞別人的程式。`/v1` `/v2` 並行，讓舊呼叫方有時間搬家再下線 v1。從第一天就加 `/v1`，成本最低。

**認證**（概念即可）——兩條主流路線：**API key**（呼叫方申請一把金鑰，每次請求放在 header 帶上來，簡單、適合服務對服務）；**OAuth 2.0**（交給授權伺服器發 token，複雜但標準，適合「代表使用者」的場景）。共同原則：金鑰放 header、走 HTTPS，絕不放網址（網址會進 log）。

**Rate limiting**——防止單一呼叫方把你打爆：限制「每個 key 每分鐘最多 N 次」，超過回 `429 Too Many Requests`。常見做法：`slowapi` 套件、或在反向代理（Nginx）層做。第 2 章你打 FinMind 被限流過——現在你是提供方，換你限別人了。

**那 POST 呢？**（概念即可）——本篇刻意不開寫入：寫入由爬蟲 pipeline 負責，動詞的取捨就是權限設計。真要開 POST 的話有三件事跟 GET 不同：資料放 **request body**（不是網址）、body 的格式用 Pydantic model 定義（跟 `Query` 同一套驗證體系）、成功回 **201 Created**——而且開放寫入的端點必定要配認證。

**多行程部署**——`uvicorn` 開發模式是單行程。上線用 `gunicorn` 管多個 uvicorn worker（`gunicorn -k uvicorn.workers.UvicornWorker -w 4`），吃滿多核心、單一 worker 掛了自動重啟。

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

**練習 4：用第 2 章的 requests 當呼叫方**

第 2 章你用 `requests` 打 FinMind（呼叫方），本篇你開了自己的 API（提供方）。現在讓兩個角色會合——用你早就會的呼叫方式，打自己開的服務：

```python
import requests

r = requests.get(
    "http://localhost:8000/stocks/2330/prices",
    params={"limit": 3},
    timeout=5,
)
print(r.status_code)   # 200
print(r.json())        # 跟 curl 拿到的一模一樣
```

跟第 2 章打 FinMind 的程式碼放在一起看：**同一個模式**——網址、params、拿 JSON。差別只有一個：這次網址後面的服務是你自己寫的。做完這題，「呼叫方」和「提供方」兩邊你都站過了。

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

## 附錄一：同一組 API 的 ORM 版（選讀）

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

## 附錄二：用 Streamlit 給 API 加一個看盤頁面（選讀）

> 「為什麼我們的系統需要 API 這個出口」那節畫了一個願景：台股看盤網頁。這個附錄用 Streamlit 把它做出來——repo 附完整可跑的 `example/stock_dashboard.py`。

### Streamlit 是什麼？跟前面三個框架有什麼不同？

**Streamlit 是「用純 Python 做資料網頁」的框架**：不寫 HTML、不寫 JavaScript、不寫 CSS，一支 Python 腳本就是一個網頁。它跟 Django / Flask / FastAPI **不在同一個賽道**：

| | Django / Flask / FastAPI | Streamlit |
|---|---|---|
| 做什麼 | **服務**：網站後端、API | **資料應用的前端頁面** |
| 使用者是誰 | 程式（API）或完整網站訪客 | 看數據的人：儀表板、內部工具、demo |
| 你要會 | 路由、請求處理，正式網站還要前端三件套 | 只要 Python |
| 典型場景 | 產品後端 | PoC、資料探索、專題展示 |

所以「專案用 Streamlit」跟「本篇教 FastAPI」不衝突——它們常常**一起出現**：Streamlit 當前端、FastAPI 當資料出口。

### 最重要的概念：整個腳本會重跑

Streamlit 的執行模型跟「伺服器等請求」完全不同：**使用者每做一次互動（換下拉選單、按按鈕），整支腳本就從第一行重新跑一次**。這讓你可以用「寫直述腳本」的思路做互動網頁，但也帶來一個代價：不加快取的話，每次互動都會重打一次 API / 重查一次資料庫。解法是 `@st.cache_data`——同參數的呼叫在 TTL 內直接回快取。

### 完整範例：`example/stock_dashboard.py`

```python
import pandas as pd
import requests
import streamlit as st

API = "http://localhost:8000"


# Streamlit 每次互動都「整個腳本從頭重跑」——用 cache 避免重複打 API
@st.cache_data(ttl=60)
def fetch_json(url: str, params: dict | None = None):
    r = requests.get(url, params=params, timeout=5)
    r.raise_for_status()  # 非 2xx 直接拋錯，不讓壞回應往下走
    return r.json()


st.title("台股看盤板")

# 跟第 2 章打 FinMind 同一套 requests——只是這次打的是自己開的 API
stocks = fetch_json(f"{API}/stocks")
stock_ids = [str(s["stock_id"]) for s in stocks]

stock_id = st.selectbox("選一支股票", stock_ids)

prices = fetch_json(f"{API}/stocks/{stock_id}/prices", params={"limit": 120})
df = pd.DataFrame(prices).sort_values("date")

latest = df.iloc[-1]
st.metric("最新收盤", f'{latest["close"]}', delta=float(latest["spread"]))
st.line_chart(df.set_index("date")["close"])
```

不到 30 行，逐個元件看它做了什麼：

| 程式碼 | 畫面上長什麼樣 |
|--------|--------------|
| `st.title(...)` | 頁面大標題 |
| `st.selectbox("選一支股票", stock_ids)` | 下拉選單；**選了新股票 → 整支腳本重跑 → 圖跟著換**，這就是互動的全部原理 |
| `st.metric(..., delta=...)` | 數字卡片，delta 自動紅綠標漲跌——第 8 章 Metabase 的數字卡片，這裡三行就有 |
| `st.line_chart(...)` | 收盤價走勢圖，直接吃 DataFrame |

### 怎麼跑

```bash
# streamlit 不在本課依賴裡，要先自行安裝
uv add streamlit          # 或 pip install streamlit

# 視窗 1：API 先跑著（Streamlit 是呼叫方，沒有 API 就沒有資料）
uv run uvicorn api.main:app --port 8000

# 視窗 2：起前端頁面
uv run streamlit run example/stock_dashboard.py
# 瀏覽器自動開 http://localhost:8501
```

### 一個架構提醒：Streamlit 也能直連 MySQL，但別這樣做

Streamlit 寫 `pd.read_sql` 直連資料庫**能動**，很多專題也真的這樣寫。但回頭看「為什麼我們的系統需要 API 這個出口」那節的論證：直連代表 DB 帳密進了前端專案、查詢範圍沒有守門。走 API 的版本才是完整的分層：

```
MySQL ← api/main.py（守門員）← stock_dashboard.py（呼叫方）← 瀏覽器裡的你
```

前端專案裡只有一個 API 網址，沒有任何資料庫帳密——這就是本篇從頭講到尾的架構，第一次完整閉環。

---

## 這一篇你學到了

- API 是程式之間約定好的介面；Web API 風格按傳送方式分三類——一問一答（REST/SOAP/GraphQL/gRPC）、持續連線推送（WebSocket/SSE/MQTT）、反向回呼（Webhook）。其中 REST 最普及——呼叫 FinMind 和本篇提供的服務都是 REST。
- REST 用「HTTP 動詞＋路徑」表達操作：GET 查、POST 增、PUT/PATCH 改、DELETE 刪；GET/PUT/DELETE 冪等、POST 不冪等。本篇只開 GET——開放哪些動詞就是權限設計。
- API 是資料的第三個出口：給程式用、資料庫的守門員。
- Python 三大框架分工：Django 做完整網站、Flask 極簡拼裝、FastAPI 專攻 API 服務。
- FastAPI 三件套：路由裝飾器、型別註記（自動驗證）、自動文件。
- 參數化查詢是防 SQL Injection 的鐵律。
- 狀態碼分陣營：2xx 成功、4xx 呼叫方的錯、5xx 提供方的錯；404 是我們設計的、422 是 FastAPI 自動驗證擋的。
- 路徑參數放資源身分、查詢參數放過濾條件；阻塞程式碼配 `def`、`await` 程式碼配 `async def`。
- SQL → DataFrame → JSON，全是你已經會的積木。
