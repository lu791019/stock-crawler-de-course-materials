# 爬蟲概念與 stock-crawler 入門 實作手冊

> 對象：已裝好 Docker、Git、uv 的學員
> 涵蓋：Docker 操作複習 → Clone stock-crawler → 認識專案結構 → 跑第一個 FinMind 爬蟲 → 看懂程式碼
> 實作專案：https://github.com/lu791019/stock-crawler-de-course-materials

---

## 使用前提

先確認三個工具都可用：

```bash
docker --version          # Docker version 29.x.x
docker compose version    # Docker Compose version v2+
git --version             # git version 2.x.x
uv --version              # uv 0.x.x
```

✅ **預期**：四個指令都印出版本號。若有任一項失敗，回前面的環境建置手冊補起來。

---

## 目錄

- [第四部分：Clone stock-crawler](#第四部分clone-stock-crawler)
- [第五部分：認識專案結構](#第五部分認識專案結構)
- [第六部分：跑第一個 FinMind 爬蟲](#第六部分跑第一個-finmind-爬蟲)
- [第七部分：看懂程式碼](#第七部分看懂程式碼)

---

## 第一部分：Clone stock-crawler

### Step 1：Clone 專案

```bash
cd ~
git clone https://github.com/lu791019/stock-crawler-de-course-materials.git stock-crawler
cd stock-crawler
```

✅ **驗證**：

```bash
ls
```

✅ **預期**：看到 `crawler/`、`Dockerfile`、`docker-compose-local.yml`、`compose-advanced/`、`pyproject.toml`、`uv.lock`、`README.md` 等。

### Step 2：用 VS Code 開啟

```bash
code .
```

在 VS Code 裡瀏覽檔案結構，對照下面的專案結構說明。

---

## 第二部分：認識專案結構

```
stock-crawler/
├── crawler/                              ← Python Package（所有程式碼）
│   ├── config.py                         ← 環境變數管理
│   ├── worker.py                         ← Celery app 定義
│   ├── worker_demo.py                    ← 失敗處理教學專用 app
│   ├── tasks.py                          ← 簡單範例 task（print）
│   ├── tasks_crawler_finmind.py          ← 真實爬蟲 task（FinMind API + 寫 DB）
│   ├── tasks_demo_fail.py                ← 4 個失敗情境 task
│   ├── producer.py                       ← 最簡單發任務（for 迴圈 100 次）
│   ├── producer_crawler_finmind_print.py ← 批次發爬蟲（print 版，不寫 DB）
│   ├── producer_crawler_finmind.py       ← 批次發爬蟲（寫 DB 版）
│   ├── producer_multi_queue.py           ← 多 queue 分流（寫 DB）
│   ├── producer_multi_queue_print.py     ← 多 queue 分流（print 版）
│   ├── producer_demo_fail.py             ← 發失敗情境 task
│   └── scheduler.py                      ← 定時排程（APScheduler）
├── docker-compose-local.yml              ← 整合版（一鍵啟動所有服務）
├── compose-advanced/                     ← 進階：分開版 + 多 worker 網路版
│   ├── rabbitmq-network.yml
│   ├── mysql.yml
│   ├── docker-compose-worker-network.yml
│   └── docker-compose-producer-network.yml
├── Dockerfile                            ← 容器化（Ubuntu + uv）
├── pyproject.toml + uv.lock              ← Python 依賴管理
└── README.md                            ← 學習順序
```

### 漸進式設計說明

stock-crawler 的設計哲學是「每個概念都有簡化版先跑通，再進階到正式版」：

| 概念 | 簡化版（先跑通） | 正式版（再深入） |
|------|----------------|----------------|
| Task | `tasks.py`（只 print） | `tasks_crawler_finmind.py`（真的爬 API + 寫 DB） |
| Producer | `producer.py`（發一批） | `producer_crawler_finmind.py`（批次爬蟲） |
| 不寫 DB → 寫 DB | `crawler_finmind_print`（只印出） | `crawler_finmind`（寫 MySQL + CSV） |
| Queue | 預設單一 queue | `producer_multi_queue.py`（twse/tpex 分流） |
| 失敗處理 | 一般 task | `tasks_demo_fail.py`（retry / requeue / reject） |
| 排程 | 手動執行 producer | `scheduler.py`（APScheduler 定時） |

> 這種設計讓你每次只多學一個新概念，不會一次被複雜度淹沒。

---

## 第三部分：跑第一個 FinMind 爬蟲

### Step 1：安裝 Python 套件

```bash
cd ~/stock-crawler
uv sync
```

✅ **預期**：uv 依 `pyproject.toml` / `uv.lock` 安裝 celery、requests、pandas、loguru、sqlalchemy、pymysql 等套件，建立 `.venv`。

### Step 2：直接呼叫 FinMind API（不用啟動 Docker）

先確認 FinMind API 能通，用 inline python 直接抓台積電（2330）：

```bash
uv run python -c "
import requests
import pandas as pd

url = 'https://api.finmindtrade.com/api/v4/data'
parameter = {
    'dataset': 'TaiwanStockPrice',
    'data_id': '2330',
    'start_date': '2025-01-01',
    'end_date': '2025-06-17',
}
resp = requests.get(url, params=parameter)
data = resp.json()
if resp.status_code == 200:
    df = pd.DataFrame(data['data'])
    print(f'抓到 {len(df)} 筆資料')
    print(df.head())
else:
    print(data['msg'])
"
```

✅ **預期**：

```
抓到 XXX 筆資料
         date stock_id  Trading_Volume  ...   close  spread  Trading_turnover
0  2025-01-02     2330        34587892  ...  1040.0    15.0       35810803350
1  2025-01-03     2330        28374881  ...  1050.0    10.0       29720832960
...
```

看到台積電股價 DataFrame = FinMind API 能通、pandas 正常。

### Step 3：看懂回傳欄位

| 欄位 | 說明 |
|------|------|
| `date` | 日期 |
| `stock_id` | 股票代碼 |
| `Trading_Volume` | 成交量（股） |
| `open` | 開盤價 |
| `max` / `min` | 最高價 / 最低價 |
| `close` | 收盤價 |
| `spread` | 漲跌 |
| `Trading_turnover` | 成交金額 |

### Step 4：換一支股票試試

```bash
uv run python -c "
import requests, pandas as pd
resp = requests.get('https://api.finmindtrade.com/api/v4/data',
    params={'dataset':'TaiwanStockPrice','data_id':'0050',
            'start_date':'2025-06-01','end_date':'2025-06-17'})
df = pd.DataFrame(resp.json()['data'])
print(f'0050: {len(df)} 筆')
print(df[['date','close']].tail())
"
```

✅ **預期**：看到 0050（元大台灣50）的收盤價資料。

---

## 第四部分：看懂程式碼

### config.py — 環境變數管理

```bash
cat crawler/config.py
```

重點：用 `os.environ.get(key, default)` 讀環境變數。開發時用預設值，Docker 裡用 environment 覆蓋，不用改程式碼。

| 變數 | 預設值 | Docker 裡改成 |
|------|--------|--------------|
| `WORKER_ACCOUNT` | `worker` | （不變） |
| `WORKER_PASSWORD` | `worker` | （不變） |
| `RABBITMQ_HOST` | `127.0.0.1` | `rabbitmq` |
| `MYSQL_HOST` | `127.0.0.1` | `mysql` |

### worker.py — Celery App 定義

```bash
cat crawler/worker.py
```

三個重點：
1. **`include`**：告訴 Celery 去哪些模組找 task（`crawler.tasks`、`crawler.tasks_crawler_finmind`）
2. **`broker`**：連到 RabbitMQ 的 URL，格式 `pyamqp://worker:worker@127.0.0.1:5672/`
3. **`logger.info()`**：啟動時印出設定，方便確認環境變數有沒有讀對

### tasks.py — 最簡單的 Task

```bash
cat crawler/tasks.py
```

```python
@app.task()
def crawler(x):
    print("crawler")
    print(f"execute task: {x}...")
    time.sleep(random.randint(1, 10))
    return x
```

`@app.task()` 裝飾器讓普通函式變成「可派送的任務」。沒有裝飾的函式只能本地呼叫，無法透過 RabbitMQ 派送。

### producer.py — 發任務

```bash
cat crawler/producer.py
```

```python
from crawler.tasks import crawler

for i in range(100):
    crawler.delay(x=f"task{i}")
```

`crawler.delay(...)` = 把任務丟進 RabbitMQ，立刻回傳，不等 Worker 做完。這就是「非同步派送」。

---

## 本集完成清單

- [ ] Docker 單一容器操作：`docker run` 跑 Nginx → curl 驗證 → stop
- [ ] Docker Compose 操作：clone nginx-demo → `docker compose up` → 驗證 → down
- [ ] 理解 docker run vs docker compose 差異
- [ ] Clone stock-crawler 到本地
- [ ] `uv sync` 安裝套件
- [ ] 直接呼叫 FinMind API，看到台積電股價 DataFrame
- [ ] 看懂 config.py / worker.py / tasks.py / producer.py

---

## 下集預告

下一集會把這些元件用 Celery **真正串起來**：啟動 RabbitMQ + Flower、啟動 Celery Worker、執行 Producer 發任務、在 Worker log 看到結果、用 Flower 監控。
