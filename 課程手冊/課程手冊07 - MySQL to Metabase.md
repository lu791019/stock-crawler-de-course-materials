# MySQL to Metabase 實作手冊

> 對象：已完成課程手冊06（MySQL 裡有 TaiwanStockPrice 資料）的學員
> 涵蓋：啟動 Metabase → 連接 MySQL → 建立圖表 → 建立 Dashboard → SQL 模式 → VIEW 應用
> 所有指令在 WSL Ubuntu 環境實測

---

## 這集要做什麼？

前面把股價存進了 MySQL，但「看資料」還是要手動下 SQL。這一集用 **Metabase**（開源 BI 工具）把 MySQL 的資料變成**互動式圖表和儀表板**，不寫程式也能看趨勢。

完成後你會有：
- 台積電收盤價折線圖
- 多支股票成交量長條圖
- 最新收盤價數字卡片
- 一個組合以上圖表的 Dashboard

---

## 目錄

- [第一部分：準備資料](#第一部分準備資料)
- [第二部分：啟動 Metabase](#第二部分啟動-metabase)
- [第三部分：首次設定與連接 MySQL](#第三部分首次設定與連接-mysql)
- [第四部分：第一個查詢](#第四部分第一個查詢)
- [第五部分：建立圖表](#第五部分建立圖表)
- [第六部分：建立 Dashboard](#第六部分建立-dashboard)
- [第七部分：SQL 模式與 VIEW 應用](#第七部分sql-模式與-view-應用)

---

## 第一部分：準備資料

確保 MySQL 裡有足夠的股價資料。如果前面已經跑過爬蟲，可以跳過這步。

### Step 1：啟動 MySQL

```bash
cd ~/stock-crawler
docker network create my_network 2>/dev/null
docker compose -f compose-advanced/mysql.yml up -d
```

等 20-30 秒讓 MySQL 初始化完成。

### Step 2：確認現有資料

```bash
docker exec -i compose-advanced-mysql-1 mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) as cnt FROM TaiwanStockPrice GROUP BY stock_id ORDER BY stock_id"
```

如果有資料（至少 2-3 支股票各幾十筆以上），直接跳到第二部分。

### Step 3：沒資料的話，載入模擬資料

```bash
docker exec -i compose-advanced-mysql-1 mysql -uroot -p1234 mydb < example/mock_stock_price_data.sql
```

✅ **預期**：10 支股票各約 32 筆資料。

```bash
docker exec -i compose-advanced-mysql-1 mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) as cnt FROM TaiwanStockPrice GROUP BY stock_id"
```

---

## 第二部分：啟動 Metabase

```bash
docker compose -f metabase/docker-compose-metabase.yml up -d
```

Metabase 啟動較慢（JVM 需要 30-60 秒），可以用以下指令等待：

```bash
# 等到 Metabase 回應 200
until curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/api/health | grep -q 200; do
  echo "等待 Metabase 啟動中..."
  sleep 10
done
echo "Metabase 已就緒！"
```

✅ **預期**：開啟瀏覽器 http://localhost:3000 看到 Metabase 歡迎畫面。

> Metabase 使用內建 H2 資料庫存自己的設定（帳號、Dashboard 等），不依賴外部 MySQL。
> MySQL 只作為「資料來源」，在下一步設定。

---

## 第三部分：首次設定與連接 MySQL

### Step 1：建立管理員帳號

開啟 http://localhost:3000，依照歡迎導覽：

1. 選擇語言（繁體中文或 English）
2. 填寫管理員資訊（名稱、Email、密碼）
3. 問「你想怎麼使用 Metabase？」選自用即可

### Step 2：新增 MySQL 資料來源

導覽會問「新增資料庫」，或從 設定（齒輪圖示）→ 管理員 → 資料庫 → 新增資料庫：

| 欄位 | 填入值 |
|------|--------|
| 資料庫類型 | MySQL |
| 顯示名稱 | Stock MySQL（自訂即可） |
| Host | `mysql` |
| Port | `3306` |
| 資料庫名稱 | `mydb` |
| 使用者名稱 | `root` |
| 密碼 | `1234` |

> Host 填 `mysql` 是因為 Metabase 和 MySQL 在同一個 Docker 網路（my_network）裡，
> Docker 會自動把容器名稱解析成 IP。

點「儲存」後，Metabase 會自動掃描你的資料表。

✅ **預期**：看到 `TaiwanStockPrice` 出現在可用資料表列表。

---

## 第四部分：第一個查詢

### Step 1：新增問題

點右上角「+ 新增」→「問題」→ 選擇「Stock MySQL」→ 選擇 `TaiwanStockPrice` 表。

### Step 2：簡單查詢

Metabase 會顯示資料預覽（類似 SELECT * LIMIT）。你可以：

- 點欄位名稱排序
- 用「篩選」只看特定股票（例：stock_id = 2330）
- 用「彙總」看統計（例：計算筆數）

### Step 3：篩選台積電資料

1. 點「篩選」
2. 選 `stock_id` → 等於 → 輸入 `2330`
3. 點「套用篩選」

✅ **預期**：只顯示台積電的股價資料。

---

## 第五部分：建立圖表

### 圖表 1：台積電收盤價折線圖

1. 點「+ 新增」→「問題」→ 選 `TaiwanStockPrice`
2. 篩選：`stock_id` = `2330`
3. 彙總：選「average of close」
4. 群組依據：選 `date`（按日）
5. 點「視覺化」→ 選「折線圖」

✅ **預期**：看到台積電收盤價的時間趨勢折線圖。

6. 點「儲存」→ 命名「台積電收盤價走勢」

### 圖表 2：多支股票成交量長條圖

1. 「+ 新增」→「問題」→ 選 `TaiwanStockPrice`
2. 彙總：選「Sum of Trading_Volume」
3. 群組依據：選 `stock_id`
4. 點「視覺化」→ 選「長條圖」

✅ **預期**：看到各股票的總成交量比較。

5. 儲存為「各股成交量比較」

### 圖表 3：最新收盤價數字卡片

1. 「+ 新增」→「問題」→ 選 `TaiwanStockPrice`
2. 篩選：`stock_id` = `2330`
3. 排序：`date` 降序
4. 限制：1 筆
5. 選擇只看 `close` 欄位
6. 視覺化 →「數字」

✅ **預期**：看到一個大數字顯示台積電最新收盤價。

7. 儲存為「台積電最新收盤價」

---

## 第六部分：建立 Dashboard

Dashboard 把多個圖表組合在一個頁面上。

### Step 1：建立 Dashboard

1. 點「+ 新增」→「Dashboard」
2. 命名：「台股股價儀表板」

### Step 2：加入圖表

1. 點右上角「鉛筆圖示」進入編輯模式
2. 點「+」→ 選擇剛才建立的圖表：
   - 台積電收盤價走勢（折線圖）
   - 各股成交量比較（長條圖）
   - 台積電最新收盤價（數字卡片）
3. 拖拉調整每個圖表的大小和位置

### Step 3：儲存 Dashboard

點「儲存」。

✅ **預期**：一個頁面看到三個圖表，互動式呈現股價資料。

---

## 第七部分：SQL 模式與 VIEW 應用

Metabase 除了點選式查詢，也支援直接寫 SQL。

### Step 1：用 SQL 查詢

1. 點「+ 新增」→「SQL 查詢」
2. 選擇資料庫「Stock MySQL」
3. 輸入：

```sql
SELECT stock_id, date, close, Trading_Volume
FROM TaiwanStockPrice
WHERE stock_id = '2330'
ORDER BY date DESC
LIMIT 10;
```

4. 點「執行」（或 Ctrl+Enter）

✅ **預期**：看到台積電最近 10 筆交易資料。

### Step 2：建立 VIEW（在 MySQL 中）

VIEW 是「儲存的查詢」，可以像表一樣使用。回到終端機：

```bash
docker exec -i compose-advanced-mysql-1 mysql -uroot -p1234 mydb < example/vw_stock_price_daily.sql
```

這會建立 `vw_stock_price_daily` VIEW，對每支股票每天只保留一筆資料（去重）。

### Step 3：在 Metabase 同步新 VIEW

1. 設定（齒輪）→ 管理員 → 資料庫 → Stock MySQL
2. 點「同步資料庫 schema」
3. 等待幾秒後，`vw_stock_price_daily` 會出現在可用表列表

### Step 4：用 VIEW 建圖表

1. 「+ 新增」→「SQL 查詢」
2. 輸入：

```sql
SELECT stock_id,
       trade_date,
       close,
       Trading_Volume
FROM vw_stock_price_daily
WHERE stock_id IN ('2330', '0050', '2317')
ORDER BY trade_date;
```

3. 執行後，點「視覺化」→ 選「折線圖」
4. X 軸選 `trade_date`，Y 軸選 `close`，系列選 `stock_id`

✅ **預期**：看到三支股票的收盤價走勢在同一張圖上比較。

5. 儲存為「多股收盤價比較」，可以加入 Dashboard。

---

## 本集完成清單

- [ ] 啟動 MySQL + Metabase
- [ ] Metabase 首次設定 + 連接 MySQL
- [ ] 台積電收盤價折線圖
- [ ] 各股成交量長條圖
- [ ] 最新收盤價數字卡片
- [ ] 建立 Dashboard（組合三個圖表）
- [ ] SQL 模式查詢
- [ ] 建立 VIEW 並在 Metabase 使用
- [ ] 多股收盤價比較折線圖

---

## 停止服務

```bash
docker compose -f metabase/docker-compose-metabase.yml down
docker compose -f compose-advanced/mysql.yml down
```

> Metabase 的設定（帳號、Dashboard）存在 Docker volume 裡，下次 `up` 還在。
> 加 `-v` 參數才會清除：`docker compose -f metabase/docker-compose-metabase.yml down -v`

---

## 下集預告

下一集進入 **Airflow**，用 DAG 把爬蟲任務排程自動化，不用再手動跑 Producer。
