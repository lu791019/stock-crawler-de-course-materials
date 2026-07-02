# Metabase

視覺化 BI 工具，用來查詢和呈現 MySQL 裡的台股股價資料。

## 快速啟動

```bash
# 1. 建立外部網路（如果還沒建過）
docker network create my_network

# 2. 確保 MySQL 已啟動（compose-advanced/mysql.yml 或 docker-compose-local.yml）

# 3. 啟動 Metabase
docker compose -f metabase/docker-compose-metabase.yml up -d
```

Metabase 啟動較慢（JVM），約需 30-60 秒。

啟動後：http://localhost:3000

## 首次設定

1. 開啟 http://localhost:3000，依照導覽建立管理員帳號
2. 設定 → 資料庫 → 新增資料庫
3. 填寫 MySQL 連線資訊：
   - 類型：MySQL
   - Host：`mysql`（Docker 網路內的 hostname）
   - Port：`3306`
   - 資料庫名稱：`mydb`
   - 帳號：`root`
   - 密碼：`1234`
4. 儲存後即可在 Metabase 裡查詢 TaiwanStockPrice 等資料表

## 架構說明

Metabase 使用內建 H2 資料庫存放自己的設定（帳號、dashboard、查詢紀錄等），
不依賴外部 MySQL。MySQL 只作為「資料來源」在 Web UI 設定。

資料持久化透過 Docker volume `metabase-data`，重啟容器不會遺失設定。

## 停止

```bash
docker compose -f metabase/docker-compose-metabase.yml down
```

加 `-v` 會刪除 volume（清除所有 Metabase 設定）：
```bash
docker compose -f metabase/docker-compose-metabase.yml down -v
```
