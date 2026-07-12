# Metabase

視覺化 BI 工具，用來查詢和呈現 MySQL 裡的台股股價資料。

## 架構說明

Metabase 會用到兩個 database，都放在同一台 MySQL：

| | 設定庫 `metabasedb` | 資料來源 `mydb` |
|---|---|---|
| 存什麼 | Metabase 帳號、Dashboard 定義、查詢紀錄 | 股價資料 |
| 連線帳號 | `metabase_app`（完整讀寫）| `metabase_ro`（唯讀）|
| 在哪設定 | compose 環境變數（`MB_DB_*`，啟動前就要就緒）| Metabase Web UI 手動新增 |

設定的持久化跟著 MySQL 的 volume 走；Metabase 容器本身無狀態，刪除重建不影響 Dashboard。

## 快速啟動（順序固定）

```bash
# 1. 確保 MySQL 已啟動（docker-compose-local.yml）
docker compose -f docker-compose-local.yml up -d mysql phpmyadmin

# 2. 建立設定庫與專用帳號（IF NOT EXISTS，重複執行無副作用）
docker exec mysql mysql -uroot -p1234 -e "
CREATE DATABASE IF NOT EXISTS metabasedb;
CREATE USER IF NOT EXISTS 'metabase_app'@'%' IDENTIFIED BY '1234';
GRANT ALL PRIVILEGES ON metabasedb.* TO 'metabase_app'@'%';"

# 3. 建立外部網路（建過就跳過），並把 MySQL 接上
docker network create my_network
docker network connect my_network mysql

# 4. 啟動 Metabase
docker compose -f metabase/docker-compose-metabase.yml up -d
```

Metabase 是 JVM 應用，啟動需要一段時間；用 health check 確認就緒：

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/api/health
```

回 200 後開啟：http://localhost:3000

## 首次設定

1. 開啟 http://localhost:3000，依照導覽建立管理員帳號（存在設定庫 `metabasedb`，不是 MySQL 使用者帳號）
2. 幫 Metabase 建唯讀的資料來源帳號（最小權限，詳見課程手冊08 Step 3.5）：
   ```sql
   CREATE USER 'metabase_ro'@'%' IDENTIFIED BY 'metabase';
   GRANT SELECT ON mydb.* TO 'metabase_ro'@'%';
   ```
3. 設定 → 資料庫 → 新增資料庫，填寫 MySQL 連線資訊：
   - 類型：MySQL
   - Host：`mysql`（Docker 網路內的服務名）
   - Port：`3306`
   - 資料庫名稱：`mydb`
   - 帳號：`metabase_ro`
   - 密碼：`metabase`
4. 儲存後即可在 Metabase 裡查詢 TaiwanStockPrice 等資料表

## 停止

```bash
docker compose -f metabase/docker-compose-metabase.yml down
```

設定都在 MySQL 的 `metabasedb`，容器移除不影響。注意：對 MySQL 的 compose 使用 `down -v` 會把股價資料與 Metabase 設定一起刪除。
