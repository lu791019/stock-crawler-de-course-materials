# 這個檔案集中管理所有環境變數設定
# 統一從這裡 import, 不要在各處直接用 os.environ, 方便日後統一維護
import os

# os.environ.get(key, default):
# 如果系統有設定環境變數就用環境變數, 沒有就用預設值
# 這樣開發時用預設值, 部署到正式環境再透過環境變數覆蓋, 不用改程式碼

# RabbitMQ (訊息佇列) 登入帳密
WORKER_ACCOUNT = os.environ.get("WORKER_ACCOUNT", "worker")
WORKER_PASSWORD = os.environ.get("WORKER_PASSWORD", "worker")

# RabbitMQ 主機位址與通訊埠
# 127.0.0.1 代表本機, 若 RabbitMQ 跑在 docker 內, 要改成對應的 host
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "127.0.0.1")
# int() 轉型是因為環境變數讀出來都是字串, 後續連線需要數字型別
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))

# MySQL 資料庫連線設定
MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_ACCOUNT = os.environ.get("MYSQL_ACCOUNT", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "1234")

# MongoDB 連線設定（補充F 用）
# 跟 MySQL 一樣的哲學: 本機用預設值 127.0.0.1, 容器內由 compose 的 environment 覆蓋成服務名 mongodb
MONGO_HOST = os.environ.get("MONGO_HOST", "127.0.0.1")
MONGO_PORT = int(os.environ.get("MONGO_PORT", 27017))
MONGO_ACCOUNT = os.environ.get("MONGO_ACCOUNT", "root")
MONGO_PASSWORD = os.environ.get("MONGO_PASSWORD", "1234")

# GCP 設定（使用 BigQuery 時取消註解）
# GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-project-id")
