# 補充 C：讓程式自己證明自己是對的 — Unit Test 與整合測試

> 前面每一章的「驗證」都是你用眼睛看：看 log、看 phpMyAdmin、看 Flower。這一篇把驗證變成**程式**——寫一次、隨時重跑、幾秒出結果。改了程式碼不確定有沒有弄壞東西？跑一下測試就知道。

---

## 做完這一篇，你會做到

1. 用 pytest 跑通專案的測試套件（5 個單元測試 + 2 個整合測試）。
2. 看懂三種測試的分工：測設定（config）、測邏輯（mock 隔離網路）、測資料庫行為（整合）。
3. 會用 mock 把「打真實 API」換成假物件——測試不吃網路、不吃 API 額度。
4. 用測試**證明**第 6 章的冪等主張：同一批資料寫兩次，筆數不變。

---

## 先搞懂：為什麼需要自動化測試

你已經有一套手動驗證流程（第 13 章的七步驟）。它很好，但有兩個限制：

1. **貴**：每次改完程式碼都要人工跑一輪，十分鐘起跳。
2. **測不準邏輯細節**：「API 回 402 時有沒有走到錯誤處理？」手動很難製造這個情境。

自動化測試把驗證變成程式：**幾秒跑完、每次改碼都跑、邊界情境隨你製造**。手動驗證和自動測試不是二選一——手動驗證「系統整體會動」，自動測試「每塊邏輯是對的」。

### 測試金字塔（這一篇的地圖）

| 層 | 測什麼 | 速度 | 需要外部服務？ | 本篇對應 |
|----|--------|------|--------------|---------|
| 單元測試 | 一個函式的邏輯 | 毫秒 | ❌ | `test_config.py`、`test_crawler_parsing.py` |
| 整合測試 | 程式和真實服務的互動 | 秒 | ✅（MySQL）| `test_upsert_integration.py` |
| 端到端 | 整個系統 | 分鐘 | ✅ 全部 | 第 13 章的七步驟（人工/腳本）|

原則：**下層多寫、上層少寫**。邏輯錯誤盡量在毫秒級的單元測試就抓到。

---

## 這一篇會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `tests/test_config.py` | 單元測試 | 驗證環境變數覆蓋機制（第 1、7 章的觀念）|
| `tests/test_crawler_parsing.py` | 單元測試 | mock 掉 requests，測爬蟲的成功/失敗路徑 |
| `tests/test_upsert_integration.py` | 整合測試 | 真連 MySQL，證明 upsert 冪等（第 6 章）|
| `pyproject.toml` | 設定 | pytest 的 testpaths 和 marker 定義 |

pytest 已在 dev 依賴裡，`uv sync` 就有。

---

## 一步一步跟著做（先跑起來，再讀懂）

### Step 1：跑單元測試（不需要任何服務）

```bash
uv run pytest -m "not integration" -v
```

✅ **預期**：

```
tests/test_config.py::test_default_values PASSED
tests/test_config.py::test_env_override PASSED
tests/test_crawler_parsing.py::test_success_prints_dataframe PASSED
tests/test_crawler_parsing.py::test_api_error_prints_msg PASSED
tests/test_crawler_parsing.py::test_no_real_network_call PASSED
5 passed, 2 deselected
```

**注意速度：不到一秒。** 而且你沒開 Docker、沒有網路請求——這就是單元測試的價值。

### Step 2：跑整合測試（需要 MySQL）

```bash
docker compose -f docker-compose-local.yml up -d mysql
# 等 MySQL healthy（20-30 秒）
uv run pytest -m integration -v
```

✅ **預期**：

```
tests/test_upsert_integration.py::test_upsert_is_idempotent PASSED
tests/test_upsert_integration.py::test_upsert_updates_value PASSED
2 passed, 5 deselected
```

> 💡 沒開 MySQL 直接跑會怎樣？**自動 skip**，不會紅掉——測試檔開頭就先探測連線，連不到就 `pytest.skip`。這是整合測試的好習慣：缺依賴時明說「跳過」，而不是誤報「失敗」。

### Step 3：全部一起跑

```bash
uv run pytest -v
```

✅ **預期**：`7 passed`。

---

## 一行一行讀懂三個測試檔

### ① `test_config.py` — 測「設定」

```python
def test_env_override(monkeypatch):
    monkeypatch.setenv("RABBITMQ_HOST", "rabbitmq")
    monkeypatch.setenv("RABBITMQ_PORT", "9999")
    config = _reload_config()
    assert config.RABBITMQ_HOST == "rabbitmq"
    assert config.RABBITMQ_PORT == 9999          # 不是字串 "9999"
    assert isinstance(config.RABBITMQ_PORT, int)
```

- **`monkeypatch`** 是 pytest 內建 fixture：临时改環境變數，**測試結束自動還原**——不會污染你的 shell 或其他測試。
- **為什麼要 `importlib.reload`？** config 的值在 import 那一刻就讀定了，之後改環境變數不會生效，reload 強迫它重讀。這其實逼你搞懂了 Python 的 import 機制。
- 第三個 assert 驗的是 `int()` 轉型——還記得第 1 章說「環境變數讀出來都是字串」嗎？這行測試就是那句話的自動化版本。
- 這正是第 4 章熱身實驗的**自動化版**：當時你手動跑兩條指令對照，現在程式自己驗。

### ② `test_crawler_parsing.py` — 測「邏輯」，用 mock 隔離網路

```python
@patch("crawler.tasks_crawler_finmind.requests.get")
def test_success_prints_dataframe(mock_get, capsys):
    mock_get.return_value = _fake_response(
        200, data=[{"date": "2025-01-02", "stock_id": "2330", "close": 1000.0}]
    )
    crawler_finmind_print("2330")          # 直接呼叫 = 本地同步執行

    out = capsys.readouterr().out
    assert "2330" in out

    _, kwargs = mock_get.call_args
    assert kwargs["params"]["dataset"] == "TaiwanStockPrice"
```

四個關鍵：

- **`@patch("crawler.tasks_crawler_finmind.requests.get")`**：把「那個模組裡的 `requests.get`」換成假物件。注意 patch 的路徑是**使用方**（tasks_crawler_finmind 裡的 requests），不是 requests 本尊——這是 mock 新手最常踩的坑。
- **假回應**：`_fake_response()` 做一個「長得像 requests 回應」的 MagicMock，`status_code` 和 `.json()` 都由你控制。想測 402 限流？一行就製造出來——真實世界你還得真的打爆 API 才遇得到。
- **`crawler_finmind_print("2330")` 直接呼叫**：第 1 章 Q1 講過，task 物件直接呼叫 = 本地同步執行、不經 RabbitMQ。**單元測試就是靠這個性質測 Celery 任務的**——不用起 broker、不用起 worker。
- **`capsys`**：pytest 內建 fixture，捕捉 print 輸出讓你 assert。

### ③ `test_upsert_integration.py` — 測「資料庫行為」

```python
def test_upsert_is_idempotent(engine):
    upload_data_to_mysql_duplicate(SAMPLE)
    first = _count(engine)
    upload_data_to_mysql_duplicate(SAMPLE)   # 故意重跑
    second = _count(engine)
    assert first == second == 2
```

- 這條測試就是**第 6 章整章的主張，壓縮成三行斷言**：寫兩次、筆數不變。
- 為什麼不能 mock？因為要驗的正是 `on_duplicate_key_update` 在**真實 MySQL** 上的行為——mock 掉資料庫就什麼都沒驗到。這就是「該用整合測試」的判斷標準：**你要驗的東西就在外部服務那一側**。
- 幾個整合測試的好習慣，都在檔案裡示範了：
  - 用專屬假代碼 `TEST999`，不污染真實資料
  - fixture 開頭探測連線、連不到就 skip
  - 測完 `DELETE` 清理，不留垃圾
  - 用參數化查詢（`:s`）——跟補充 B 同一條鐵律

---

## pytest 常用指令速查

| 指令 | 用途 |
|------|------|
| `uv run pytest` | 跑全部 |
| `uv run pytest -v` | 顯示每條測試名稱 |
| `uv run pytest -m "not integration"` | 只跑單元測試（快）|
| `uv run pytest -m integration` | 只跑整合測試 |
| `uv run pytest tests/test_config.py` | 只跑一個檔案 |
| `uv run pytest -k idempotent` | 只跑名稱含關鍵字的測試 |
| `uv run pytest -x` | 第一個失敗就停 |

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | 單元測試 5 passed、不到一秒 | 不依賴外部服務的測試跑得飛快 |
| 2 | 沒開 MySQL 時整合測試 skip 而非 fail | 缺依賴要明說，不誤報 |
| 3 | 開了 MySQL 後 7 passed | 冪等主張被程式證明了 |
| 4 | mock 測試沒有真的打 FinMind | 網路被完全隔離 |

---

## 想再深入一點

- **mock 測試全綠 ≠ 系統能跑。** mock 隔離了依賴，所以它只證明「你的邏輯對」，不證明「依賴真的在、連得上、行為如你想像」。所以才需要整合測試和第 13 章的端到端驗證。三層各補各的盲區，缺一不可。
- **測試也是文件。** `test_upsert_is_idempotent` 這個名字 + 三行內容，比一段文字更精確地告訴讀者「這個函式保證什麼」。新人接手專案，讀 tests/ 常常比讀說明快。
- **什麼時候寫測試？** 理想是跟程式碼一起寫（甚至先寫——TDD）。務實的底線是：**修 bug 時先寫一條會重現那個 bug 的測試**，修完它變綠，這個 bug 就永遠不會悄悄回來。
- **CI 的入口。** 有了 `uv run pytest`，之後接 GitHub Actions 只要一行——每次 push 自動跑測試，紅了就擋 merge。這是團隊協作的標配，也是這套測試真正的歸宿。

---

## 想一想（確認你懂了）

**Q1：為什麼 mock 的 patch 路徑是 `crawler.tasks_crawler_finmind.requests.get`，而不是 `requests.get`？**

因為要攔的是「被測模組手上的那個名字」。`tasks_crawler_finmind.py` 裡 `import requests` 之後，它用的是自己命名空間裡的 `requests`。你 patch 全域的 `requests.get`，它手上那份參照可能早就綁定了。規則：**在哪裡用，就在哪裡 patch**。

**Q2：冪等測試為什麼一定要真的 MySQL，不能 mock？**

因為受測的核心是 `on_duplicate_key_update` 這個 **MySQL 行為**——主鍵撞到時更新而非新增。mock 掉資料庫，你只是在測「我的程式有呼叫某個函式」，完全沒碰到要驗的東西。要驗的邏輯在外部服務那一側時，就得用整合測試。

**Q3：單元測試全綠，就能保證第 13 章的端到端一定通嗎？**

不能。單元測試 mock 掉了 RabbitMQ、MySQL、網路——它們的版本、設定、網路連通性都沒被驗到。例如 `MYSQL_HOST` 在 compose 裡打錯字，單元測試照樣全綠，端到端立刻爆。所以金字塔三層都要有，只是數量比例不同。

---

## 換你試試看

**練習 1：寫一條會失敗的測試，看失敗長什麼樣**

在 `test_config.py` 加一條 `assert config.RABBITMQ_PORT == 1234`，跑 `uv run pytest -k default -v`。讀懂 pytest 的失敗輸出（它會告訴你期望值 vs 實際值），然後把它刪掉。會讀失�敗訊息，比會寫測試更重要。

**練習 2：幫 `crawler_finmind` 的另一條路徑補測試**

模仿 `test_api_error_prints_msg`，寫一條「data 是空 list」的測試：mock 回 200 但 `data=[]`，驗證程式不會爆炸（印出空的 DataFrame）。這是真實會發生的情境——股票代碼存在但該期間沒交易資料。

**練習 3：測補充 B 的 API**

FastAPI 有現成的測試工具：

```python
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_health():
    resp = client.get("/")
    assert resp.status_code == 200
```

放進 `tests/test_api.py` 跑跑看（需要 MySQL 在，或觀察 degraded 狀態）。TestClient 不用真的起 uvicorn——又是一個「隔離依賴」的例子。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| `pytest: command not found` | 沒裝 dev 依賴 | `uv sync`（會含 dev group）|
| 整合測試 skip | MySQL 沒開 | `docker compose -f docker-compose-local.yml up -d mysql` |
| mock 沒生效、真的打了 API | patch 路徑寫錯 | patch「使用方」的路徑（Q1）|
| `Unknown pytest.mark.integration` 警告 | marker 沒註冊 | 已在 pyproject.toml 註冊；自建專案要記得加 |
| 測試互相影響、單跑會過一起跑會爆 | 測試間共享了狀態 | 用 fixture/monkeypatch 管理，測完還原（test_config 的 teardown 就是示範）|

---

## 這一篇你學到了

- 測試金字塔：單元（多而快）→ 整合（少而準）→ 端到端（最少最貴）。
- mock 隔離依賴測邏輯；要驗外部服務行為時用整合測試。
- Celery task 直接呼叫 = 同步執行，這讓任務可以被單元測試。
- 冪等這種「主張」，可以被三行斷言永久釘住。
