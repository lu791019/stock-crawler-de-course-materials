"""
Step 2 的設定層: 集中管理所有「會因環境而變」的值。

Step 0 把設定寫死在函式裡, Step 1 搬到模組最上方, 這裡再往前一步——
改用 os.environ.get() 讀環境變數, 讀不到才用預設值。
這樣同一份程式在本機、在容器、在雲端都不用改任何一行, 只換環境變數。

這個檔案的寫法與課程正式版 crawler/config.py 相同。
"""
import os

# 要抓什麼: 股票清單與日期範圍
STOCK_IDS = ["2330", "0050", "2317", "0056", "00713"]
START_DATE = os.environ.get("START_DATE", "2025-01-02")
END_DATE = os.environ.get("END_DATE", "2025-06-17")

# 怎麼拿: FinMind API 位址與資料集名稱
FINMIND_URL = os.environ.get("FINMIND_URL", "https://api.finmindtrade.com/api/v4/data")
FINMIND_DATASET = os.environ.get("FINMIND_DATASET", "TaiwanStockPrice")

# 怎麼存: STORAGE 決定要用哪些 repository 實作, 可用值是 csv 與 mysql
# 用逗號分隔可以同時寫多個目標, 例如 STORAGE=csv,mysql
# 這個開關是 Step 2 的驗收重點——換值不用改 client 與 transformer 的任何一行
STORAGE = os.environ.get("STORAGE", "csv")

# CSV 的輸出目錄
CSV_OUTPUT_DIR = os.environ.get("CSV_OUTPUT_DIR", "output")

# MySQL 連線資訊, 預設值對應課程的本機 MySQL 容器
MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_ACCOUNT = os.environ.get("MYSQL_ACCOUNT", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "1234")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "mydb")
