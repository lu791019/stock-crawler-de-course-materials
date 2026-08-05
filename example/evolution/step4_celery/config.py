"""
Step 4 的設定層: 與 Step 2、Step 3 的 config.py 內容相同, 只多了 RabbitMQ 那一段。

多出來的四個變數是給 Celery 連 broker 用的, 與爬蟲邏輯無關。
預設值對應課程的本機 RabbitMQ 容器（rabbitmq-network.yml 啟動的那一組）。
"""
import os

# 要抓什麼: 股票清單與日期範圍
STOCK_IDS = ["2330", "0050", "2317", "0056", "00713"]
START_DATE = os.environ.get("START_DATE", "2025-01-02")
END_DATE = os.environ.get("END_DATE", "2025-06-17")

# 怎麼拿: FinMind API 位址與資料集名稱
FINMIND_URL = os.environ.get("FINMIND_URL", "https://api.finmindtrade.com/api/v4/data")
FINMIND_DATASET = os.environ.get("FINMIND_DATASET", "TaiwanStockPrice")

# 怎麼存: STORAGE 決定要用哪一個 repository 實作, 值是 csv 或 mysql
STORAGE = os.environ.get("STORAGE", "csv")

# CSV 的輸出目錄
CSV_OUTPUT_DIR = os.environ.get("CSV_OUTPUT_DIR", "output")

# MySQL 連線資訊, 預設值對應課程的本機 MySQL 容器
MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_ACCOUNT = os.environ.get("MYSQL_ACCOUNT", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "1234")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "mydb")

# Step 4 新增: RabbitMQ 連線資訊, 給 Celery 當 broker 用
# 這四個變數與爬蟲邏輯無關, 是「任務怎麼傳遞」的設定
WORKER_ACCOUNT = os.environ.get("WORKER_ACCOUNT", "worker")
WORKER_PASSWORD = os.environ.get("WORKER_PASSWORD", "worker")
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "127.0.0.1")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))
