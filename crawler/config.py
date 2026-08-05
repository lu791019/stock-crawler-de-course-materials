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

# GCP 專案 ID（雙寫用, 手冊15 詳細介紹）
# 沒設定就是空字串, worker 會印「BQ 未設定，略過雲端寫入」只寫 MySQL
# 部署到 GCP 時由 compose 的 environment 注入實際專案 ID
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")

# Cloud Spanner 體驗用（手冊16 Spanner 節）
# 設了 SPANNER_INSTANCE 爬蟲才會把資料多寫一份到 Spanner, 平常不設、不影響主線
# compose 的插值會把沒設的變數注入成空字串, 用 or 讓空字串也回退到 GCP_PROJECT_ID
SPANNER_PROJECT_ID = os.environ.get("SPANNER_PROJECT_ID") or GCP_PROJECT_ID
SPANNER_INSTANCE = os.environ.get("SPANNER_INSTANCE", "")
SPANNER_DATABASE = os.environ.get("SPANNER_DATABASE", "stockdb")

# Secret Manager 執行時讀取（參考用, 課程不啟用）
# 課程做法是「部署時注入」: up 指令用 $(gcloud secrets versions access ...) 把密碼塞進環境變數,
# 程式只讀環境變數（上面第 23 行）, 不裝 SDK。下面是另一種做法——程式執行時自己讀 secret,
# 代價是要裝 google-cloud-secret-manager, 且失敗時靜默退回預設值不報錯（見手冊16 B-4 補充）
# def _password_from_secret_manager():
#     """讀 Secret Manager 的 mysql-password; 任何原因失敗回 None, 讓呼叫端退回原值"""
#     try:
#         from google.cloud import secretmanager
#         client = secretmanager.SecretManagerServiceClient()
#         name = f"projects/{GCP_PROJECT_ID}/secrets/mysql-password/versions/latest"
#         return client.access_secret_version(name=name).payload.data.decode()
#     except Exception:
#         # 沒裝套件、沒憑證、沒授權、還沒建 secret——都走這裡, 程式不會因此掛掉
#         return None
#
# MYSQL_PASSWORD = _password_from_secret_manager() or MYSQL_PASSWORD
