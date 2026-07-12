# 第 8 章：把資料變成看得到的圖表 — Metabase BI 視覺化

> 這是 Phase B 的第一章。前面各章寫進 MySQL 的股價資料，在這一章轉成可互動的圖表與儀表板。

---

## 做完這一章，你會做到

1. 啟動 Metabase 並連上你的 MySQL。
2. 做出三種圖表：走勢折線圖、成交量長條圖、最新收盤價數字卡片。
3. 把多張圖組合成一個 Dashboard。
4. 用 SQL 模式下自訂查詢，並把 MySQL 的 VIEW 拿來做圖。
5. 分得清「Metabase 自己的設定」和「它查詢的資料來源」是兩個不同的資料庫。

---

## 先搞懂：資料的「出口」

前面的章節都在解決「怎麼把資料可靠地生出來、存起來」。但存進資料庫的資料，目前只有會寫 SQL 的人查得到。**BI（Business Intelligence，商業智慧）工具就是資料的出口**——讓不會寫 SQL 的人也能拉圖表、看趨勢、做決策。

**BI / Dashboard 工具在做什麼？六件核心的事**：

1. **連資料源**：接上資料庫/倉儲，不搬資料、即時查
2. **查詢**：不會 SQL 的人拖拉點選（query builder），會 SQL 的人直接寫
3. **視覺化**：查詢結果變成折線、長條、圓餅、數字卡…
4. **Dashboard 組裝**：多張圖拼成一面儀表板，加全域篩選器
5. **分享與權限**：誰能看哪個庫、哪張表、哪面板
6. **排程與告警**：定時寄報表、指標超標自動通知

**常見 BI 工具一覽**：

| 工具 | 定位 | 特點 | 費用 |
|------|------|------|------|
| **Metabase** | 開源自架、輕量 | 上手最快、query builder 對非工程師友善、Docker 一行起 | 開源免費（另有付費雲）|
| **Power BI** | 微軟企業級 | 功能深（DAX）、Office/Excel 整合強 | 個人免費、團隊付費 |
| **Tableau** | 視覺化旗艦 | 拖拉分析成熟、圖表類型與客製化選項最多，大型企業普遍採用 | 貴 |
| **Redash** | 開源、SQL-first | 每張圖就是一句 SQL，開發者取向 | 開源（近年維護趨緩）|
| **Superset** | Apache 開源 | 功能最全的開源選項，架設與學習較重 | 免費 |
| **Looker Studio** | Google 免費雲端 | 接 GA、BigQuery 特別順 | 免費 |
| **Grafana** | 監控/時序起家 | 主要用於系統監控指標（metrics）儀表板，非業務報表 | 開源 |

選型參考：教學與中小團隊自架 → Metabase；企業微軟生態 → Power BI；純 SQL 人 → Redash / Superset；看系統監控 → Grafana。本課選 Metabase：開源、單一容器即可啟動、query builder 入門成本最低。

**Metabase 是什麼**：

- 開源的商業智慧（BI）平台
- 能將資料庫裡的資料快速轉換成圖表、儀表板與報表
- 簡單易用、安裝快速，適合中小型團隊、教育場合，或作為企業內部的輕量 BI 工具

**為什麼排在這裡？** 因為到第 6 章為止，資料已經能穩定寫入 MySQL（含去重與冪等）。資料管線的下一步是輸出：把表裡的數據轉成圖表與儀表板。

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `metabase/docker-compose-metabase.yml` | 部署 | 啟動 Metabase 容器（設定庫指向 MySQL）|
| `metabase/init-metabase-appdb.sql` | 初始化 | 建立設定庫 `metabasedb`（第 13 章 all 版自動執行）|
| `metabase/README.md` | 說明 | 連線設定與操作步驟 |
| `example/mock_stock_price_data.sql` | 模擬資料 | MySQL 沒資料時快速補一批 |
| `example/vw_stock_price_daily.sql` | VIEW 範例 | 每日去重的股價 VIEW（進階段落用）|

---

## 先懂一個容易混淆的觀念：Metabase 碰到兩個資料庫

Metabase 本身也需要一個資料庫。帳號、做好的 Question 與 Dashboard、查詢紀錄——這些「Metabase 自己的狀態」都要存在某個地方，存放它們的資料庫稱為**設定庫（application database）**。設定庫和「被查詢的資料」是兩回事，所以本章會出現兩個 database，角色完全不同：

| | 設定庫 `metabasedb` | 資料來源 `mydb` |
|---|---|---|
| 存什麼 | Metabase 的帳號、Dashboard 定義、查詢紀錄 | 股價資料（TaiwanStockPrice）|
| 誰在讀寫 | Metabase 程式本身（啟動時自動建表）| Metabase 代替使用者執行查詢 |
| 用什麼帳號連 | `metabase_app`（完整讀寫，Step 2 建）| `metabase_ro`（唯讀，Step 3.5 建）|
| 在哪裡設定 | compose 的環境變數（啟動前就要就緒）| Metabase 網頁介面手動新增（Step 4）|
| 內容消失會怎樣 | Dashboard、帳號全部消失 | 圖表查不到數據，但 Dashboard 定義還在 |

本課把兩個 database 放在**同一台 MySQL**（`docker-compose-local.yml` 起的那台）。Metabase 啟動後，可以在 phpMyAdmin 左側同時看到 `metabasedb` 和 `mydb`——點開 `metabasedb`，裡面是 Metabase 自動建立的幾十張表，Dashboard 的定義就存在其中。設定庫不是抽象概念，是一個看得到內容的 database。

**跟預設做法的差異**：不設任何 `MB_DB_*` 環境變數時，Metabase 會用**內建的 H2 資料庫**當設定庫——H2 是內嵌在 Metabase 程式裡的單檔資料庫，免安裝、免帳密，官方定位是試用場景；正式環境官方建議把設定庫放到外部資料庫（PostgreSQL 或 MySQL）。網路教學兩種做法都有：看到「先建 `metabasedb` 和專用帳號」的是設定庫放 MySQL（本課做法）；看到「直接啟動、掛 volume 保設定」的是 H2 做法。分辨的關鍵是設定庫放在哪。

本章共出現三組帳號，各管一件事：

| 帳號 | 用在哪 | 權限範圍 |
|------|--------|---------|
| Metabase 管理員（Step 3 建）| 登入 http://localhost:3000 的網頁帳號 | Metabase 介面內的最高權限；本身存在 `metabasedb` 裡 |
| `metabase_app`（Step 2 建）| Metabase 連**設定庫**用的 MySQL 帳號 | `metabasedb` 完整讀寫（Metabase 要自己建表）|
| `metabase_ro`（Step 3.5 建）| Metabase 連**資料來源**用的 MySQL 帳號 | `mydb` 唯讀 |

一句話：**`mydb` 是「被查的對象」，Metabase 自己的設定存在 `metabasedb`。** 設定跟著 MySQL 的 volume 持久化，Metabase 容器刪除重建都不影響 Dashboard。

---

## Metabase 功能地圖

做圖之前先認識整個介面有什麼。下表的範例都以本課的股價資料示範：

| 頁面 / 功能 | 在哪 | 做什麼 | 範例 |
|------------|------|--------|---------|
| **Browse data** | 左側 Databases | 點開資料庫直接看每張表 | 連上後列出 `mydb` 的資料表（含 VIEW）|
| **Question 查詢產生器** | + New → Question | 免 SQL：選表→篩選→彙總→分組 | 「各股平均收盤價」長條圖：所有股票一次畫出 |
| **SQL 模式 + 變數** | + New → SQL query | 寫 SQL，`{{變數}}` 做互動篩選 | `WHERE stock_id = {{sid}}`，換股票代號即重畫走勢 |
| **視覺化切換** | 結果頁左下 Visualization | 同一份結果切折線/長條/數字卡… | 上面兩例分別存成 bar 和 line |
| **Dashboard** | + New → Dashboard | 卡片拼裝＋全域篩選器＋自動刷新 | 「台股股價儀表板」：多張卡片組裝＋篩選器 |
| **Collections** | 左側收藏集 | 資料夾式管理 Question/Dashboard，可設權限 | 建「股價分析」收藏集歸檔 |
| **X-ray 一鍵分析** | 表格頁的黃色閃電 | Metabase 自動掃資料生一組圖 | 對 TaiwanStockPrice 執行：自動產生一組摘要圖表 |
| **訂閱與警示** | Dashboard / Question 內 | 定時寄報表、數字達標告警 | 功能在 UI 裡；寄送需先設 SMTP（管理員→設定→Email），課堂不設 |
| **Admin → Databases** | 齒輪 → 管理員 | 資料源管理、同步 schema | Step 10 的 VIEW 同步就在這 |
| **Admin → People / Permissions** | 同上 | 使用者、群組、誰能看哪個資料庫 | 見下方「權限有兩層」|

> **權限有兩層**：MySQL 的 `metabase_ro` 管「Metabase 整體拿得到什麼」（DB 層）；Metabase 的 Permissions 管「哪個使用者看得到什麼」（BI 層）。兩層各自獨立生效。

---

## 一步一步跟著做

### Step 1：確認 MySQL 裡有資料

先確保前面幾章已經把股價寫進 `mydb`（第 5 章跑過 producer；注意第 6 章寫的是另一張表 `TaiwanStockPrice_duplicate`，不算數）。

```bash
docker compose -f docker-compose-local.yml up -d mysql phpmyadmin

docker exec mysql mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice GROUP BY stock_id"
```

> ✅ 查詢列出各股票代號與筆數，代表 `mydb` 有資料。
>
> 💡 **沒資料（或想要更多支股票）？** 用專案附的模擬資料補入——10 支股票、各約 32 個交易日：
>
> ```bash
> docker exec -i mysql mysql -uroot -p1234 mydb < example/mock_stock_price_data.sql
> ```
>
> 再跑一次上面的查詢，就會看到 2330、0050、2317 等 10 支股票的資料。

### Step 2：把兩個 compose 檔串起來，啟動 Metabase

本章的服務分屬兩個 compose 檔：MySQL 在 `docker-compose-local.yml`（Step 1 已啟動），Metabase 在 `metabase/docker-compose-metabase.yml`。要讓 Metabase 成功連上 MySQL，得先解決兩件事：

**第一件事——網路：兩個 compose 檔預設是兩個隔離的網路。** 每個 compose 檔啟動時會建立自己的網路，容器只能跟**同一個網路**裡的容器互通。`docker-compose-local.yml` 的 mysql 在它自己的預設網路裡；Metabase 的 compose 則宣告使用外部網路 `my_network`。兩邊要通，就把 mysql 也接上 `my_network`——`docker network connect` 做的就是這件事（一個容器可以同時掛在多個網路上，接上新網路不影響原本的）：

```
docker-compose-local.yml 的預設網路        my_network（外部網路）
┌─────────────────────────┐         ┌──────────────────┐
│  mysql      phpmyadmin  │         │     metabase     │
└─────┬───────────────────┘         └────────┬─────────┘
      │                                      │
      └── docker network connect ──► 接上後 mysql 同時在兩個網路，
                                     metabase 才找得到它
```

**第二件事——設定庫：Metabase 只會自己建「表」，不會建 database 和帳號。** 上一節說過設定庫 `metabasedb` 放在 MySQL。Metabase 第一次啟動時會在裡面自動建立它需要的所有表，但 `metabasedb` 這個 database 本身、和連線用的帳號 `metabase_app`，MySQL 不會憑空生出來——要先用 root 跑一段 SQL 準備好。這就是啟動 Metabase 之前得先動 MySQL 的原因。

兩件事都處理完才能起 Metabase，所以順序固定：**MySQL 就緒（Step 1）→ 建設定庫與帳號 → 接網路 → 起 Metabase**。順序反了，Metabase 開機連不到設定庫，容器會直接結束。完整指令：

```bash
# 1. 建立設定庫與專用帳號（IF NOT EXISTS：重複執行沒有副作用）
docker exec mysql mysql -uroot -p1234 -e "
CREATE DATABASE IF NOT EXISTS metabasedb;
CREATE USER IF NOT EXISTS 'metabase_app'@'%' IDENTIFIED BY '1234';
GRANT ALL PRIVILEGES ON metabasedb.* TO 'metabase_app'@'%';"

# 2. 建立外部網路（建過就跳過）
docker network create my_network

# 3. 把 MySQL 接上 my_network —— Metabase 掛在 my_network 上，
#    不接的話它開機連不到設定庫（已接過會顯示 already exists，無妨）
docker network connect my_network mysql

# 4. 啟動 Metabase
docker compose -f metabase/docker-compose-metabase.yml up -d
```

> 💡 `metabase_app` 對 `metabasedb` 是完整讀寫權限（`GRANT ALL ... ON metabasedb.*`）——Metabase 要在裡面自己建表。它跟 Step 3.5 的唯讀帳號 `metabase_ro` 用途不同：一個管設定庫、一個管資料來源，權限範圍也互不重疊。
>
> 💡 `docker-compose-all.yml`（第 13 章）把所有服務放在同一網路，並在 MySQL volume 初始化時自動建 `metabasedb`，上面的步驟 1-3 都不需要。

> ⏳ Metabase 是 Java（JVM）應用，啟動需要一段時間。用這段指令等它就緒：
>
> ```bash
> until curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/api/health | grep -q 200; do
>   echo "等待 Metabase 啟動中..."
>   sleep 10
> done
> echo "Metabase 已就緒！"
> ```

✅ 就緒後到 phpMyAdmin 看一眼：左側多了 `metabasedb`，裡面有 Metabase 自動建立的表——上一節說的「設定庫」就是它。

### Step 3：首次設定，建立管理員帳號

打開 http://localhost:3000 ，跟著導覽建立一個管理員帳號（這是 Metabase 網頁的登入帳號，存在設定庫 `metabasedb` 裡；它不是 MySQL 的使用者帳號）。語言可選繁體中文。

### Step 3.5：幫 Metabase 建一個「唯讀」資料庫帳號

Metabase 對 MySQL 只需要「讀」——正式做法是給它一個只有 SELECT 的專用帳號（最小權限原則，補充D 第 6 節的實戰應用）：

```sql
CREATE USER 'metabase_ro'@'%' IDENTIFIED BY 'metabase';   -- _ro = read-only 的慣用命名
GRANT SELECT ON mydb.* TO 'metabase_ro'@'%';              -- 只給查詢，不給寫
```

> **phpMyAdmin 版**（同一件事的圖形操作）：root 登入 → 首頁 **User accounts** → **Add user account** → 使用者名稱 `metabase_ro`、主機名稱選「任何主機（%）」、設密碼 → 「資料庫的權限」選 `mydb` → 只勾 **SELECT** → 執行。

✅ 這個帳號透過 Metabase 查資料一切正常；執行 `DELETE` 會被 MySQL 拒絕（`DELETE command denied to user 'metabase_ro'`）——BI 只需要讀取，寫入操作在 DB 權限層即被擋下。

### Step 4：把 MySQL 加進來當資料來源

在 Metabase 裡：設定（齒輪）→ 管理員 → 資料庫 → 新增資料庫，填入：

| 欄位 | 填什麼 |
|------|--------|
| 類型 | MySQL |
| 顯示名稱 | Stock MySQL（自訂即可）|
| Host | `mysql`（**注意：是這個服務名，不是 127.0.0.1**）|
| Port | `3306` |
| 資料庫名稱 | `mydb` |
| 帳號 | `metabase_ro`（Step 3.5 建的唯讀帳號）|
| 密碼 | `metabase` |

> ✅ 儲存後沒報錯、能在 Metabase 裡看到 `TaiwanStockPrice` 這張表，就連通了（Metabase 在「儲存」當下就會實際連線驗證，帳密錯會直接報錯）。
>
> 💡 用 `root / 1234` 也連得上，但正式做法是最小權限——就算 Metabase 設定錯誤或帳號外洩，資料也不會被改動。
>
> ⚠️ 最常卡在 Host：在 Docker 網路裡，容器之間要用**服務名**（`mysql`）互相找，不能用 `127.0.0.1`（那會指向 Metabase 容器自己）。前提是兩個容器在同一個網路（`my_network`）。

### Step 4.5：先規劃，再動手 — Dashboard 藍圖

做圖前先確定五件事：

1. 每個 Question 就是一張圖
2. 每張圖用來呈現**什麼資訊**
3. Dashboard 要有**哪幾張圖**
4. 每張圖**怎麼排版**
5. 要有哪些 **Filter**、套用在哪些圖

本課的「台股股價儀表板」藍圖（Step 5-8 會做其中三張，其餘留在「換你試試看」）：

```
Filter: 日期區間                Filter: 股票代號
┌──────────┬──────────┬──────────┬──────────┐
│ 最新收盤價 │  總成交量  │ 追蹤股票數 │ 最新資料日期│   ← 數字卡 ×4
├──────────┴──────────┴──────────┴──────────┤
│            收盤價走勢（折線，可多股比較）            │
├─────────────────────┬──────────────────────┤
│  各股成交量比較（長條）  │   單股高低價區間（線/區域）  │
├─────────────────────┴──────────────────────┤
│              每日行情明細（表格卡）                 │
└─────────────────────────────────────────────┘
```

### Step 5：第一張圖 — 台積電收盤價折線圖

1. 點「+ 新增」→「問題」（Ask a question）→ 選 `TaiwanStockPrice` 這張表。
2. 篩選：`stock_id` = `2330`。
3. 彙總：選「Average of close」；群組依據：選 `date`（按日）。
4. 點「視覺化」→ 選折線圖。

> ✅ 出現台積電的收盤價走勢折線——MySQL 裡的股價資料完成第一次視覺化。

5. 點「儲存」，命名「台積電收盤價走勢」→ 位置選「股價分析」收藏集（沒有就先「+ 新增收藏集」）。存檔後會問「要加進 Dashboard 嗎？」——先按「稍後」，Step 8 再一起組。

認識結果頁的三個按鈕（都在圖表區周圍）：

- **左下「視覺化」**：同一份結果切換折線／長條／數字卡…
- **右下「表格⇄圖表」切換**：一鍵在「原始資料」和「圖」之間切換——檢查圖畫得對不對就靠它
- **右下「下載」（雲朵/箭頭圖示）**：把結果匯出 CSV / Excel / JSON

### Step 6：第二張圖 — 各股成交量長條圖

1. 「+ 新增」→「問題」→ 選 `TaiwanStockPrice`。
2. 彙總：選「Sum of Trading_Volume」；群組依據：選 `stock_id`。
3. 視覺化 → 長條圖。
4. 儲存為「各股成交量比較」。

### Step 7：第三張圖 — 最新收盤價數字卡片

1. 「+ 新增」→「問題」→ 選 `TaiwanStockPrice`。
2. 篩選：`stock_id` = `2330`；排序：`date` 降冪；限制 1 筆。
3. 只留 `close` 欄位。
4. 視覺化 →「數字」。
5. 儲存為「台積電最新收盤價」。

### Step 8：組一個 Dashboard（照 Step 4.5 的藍圖）

1. 點「+ 新增」→「Dashboard」，命名「台股股價儀表板」，位置一樣選「股價分析」。
2. 進入**編輯模式**（右上鉛筆圖示）→ 上方「＋」（加卡片）→ 把剛才三張圖加進來。
3. **拖拉排版**：抓卡片本體移動位置、抓右下角拉大小——照藍圖：數字卡放最上排、折線圖全寬。
4. **加篩選器**：上方**漏斗圖示** → 「時間」→ 套到折線圖的 `date` 欄位（點卡片上出現的下拉選欄位）；再加一個「文字」篩選器 → 套到 `stock_id`。之後在 Dashboard 上選日期區間或輸入股票代號，所有連結的圖會一起變。
5. **加文字卡片**：上方 **T 圖示**——放標題或說明文字，補充圖表的閱讀脈絡。
6. **分頁標籤**：Dashboard 上方「＋新增分頁」——圖太多時分成「總覽」「個股」兩頁。
7. 右上「儲存」離開編輯模式。
8. **定期刷新**：Dashboard 檢視模式右上**時鐘圖示** → 選自動刷新間隔（如 15 分鐘），Dashboard 會定時重新查詢資料。

> ✅ 一個頁面同時顯示走勢、成交量、最新價；篩選器改變條件時，所有連結的卡片一起更新。
>
> 💡 **公開分享**：管理員 → 設定 → 公開分享 開啟後，Question/Dashboard 的分享圖示能產生「不用登入就能看」的公開連結。方便，但任何人拿到連結都能看到資料——正式環境需評估後再啟用。（按鈕名稱以 Metabase v0.62 為準，新版可能微調。）

### Step 9：SQL 模式 — 直接下 SQL

Metabase 除了點選式查詢，也能直接寫 SQL：

1. 「+ 新增」→「SQL 查詢」→ 選「Stock MySQL」。
2. 貼上：

```sql
SELECT stock_id, date, close, Trading_Volume
FROM TaiwanStockPrice
WHERE stock_id = '2330'
ORDER BY date DESC
LIMIT 10;
```

3. 執行（Ctrl+Enter）。

✅ **預期**：台積電最近 10 筆交易資料。點選式做不到的複雜查詢，都可以退回 SQL 模式解決。

### Step 10（進階）：用 VIEW 做圖

VIEW 是「存起來的查詢」，可以像表一樣用。專案附了一個每日去重的股價 VIEW：

```bash
docker exec -i mysql mysql -uroot -p1234 mydb < example/vw_stock_price_daily.sql
```

然後讓 Metabase 認識這個新 VIEW：設定 → 管理員 → 資料庫 → Stock MySQL → 「同步資料庫 schema」。

幾秒後，用 SQL 模式做一張多股比較圖：

```sql
SELECT stock_id, trade_date, close
FROM vw_stock_price_daily
WHERE stock_id IN ('2330', '0050', '2317')
ORDER BY trade_date;
```

視覺化 → 折線圖，X 軸 `trade_date`、Y 軸 `close`、分組 `stock_id`。

✅ **預期**：三支股票的收盤價走勢疊在同一張圖上。

> 💡 這個 VIEW 用 `ROW_NUMBER()` 對「同股票同日期」去重——如果你的表裡有第 5 章重跑造成的重複資料，VIEW 查出來的仍是乾淨的。這是「不動原始資料、用查詢層清理」的實務手法，第 14 章 BigQuery 會再用一次。

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | Metabase 能列出 `mydb` 的資料表 | 資料來源連線成功 |
| 2 | 三張圖各自做得出來 | 折線 / 長條 / 數字卡片三種基本圖 |
| 3 | Dashboard 同頁顯示三張圖 | 你能組報表，不只單圖 |
| 4 | SQL 模式查得到資料 | 點選式之外你還有 SQL 這條路 |
| 5 | VIEW 同步後能拿來做圖 | DB 端的查詢層可以被 BI 直接用 |
| 6 | 重啟 Metabase 容器後 Dashboard 還在 | 設定庫在 MySQL 裡，容器本身無狀態 |

---

## 想再深入一點

- **BI 工具把「查詢能力」下放給非技術同事。** 有了 Metabase，原本要工程師寫 SQL 才做得到的「看某段期間某股走勢」，業務或主管自己拉一拉就有了。工程師不必逐一處理這類查詢需求。
- **Metabase 的圖表底下其實還是 SQL。** 你用滑鼠拉的每一個問題，Metabase 都會翻譯成一段 SQL 去查 MySQL。它也有「原生查詢」模式讓你直接寫 SQL。所以 BI 不是取代 SQL，而是幫你把常用查詢包成好點的介面。
- **Metabase 容器是無狀態的。** 設定全部存在 MySQL 的 `metabasedb`，容器裡沒有任何需要保留的資料——刪掉 Metabase 容器再重建，只要 `MB_DB_*` 指回同一個設定庫，Dashboard 原封不動。反過來說，設定的存亡跟著 MySQL 的 volume：對 MySQL 用 `down -v`，股價資料和 Dashboard 會一起消失。「狀態集中到資料庫、應用程式本身無狀態」是伺服器應用的常見設計，方便隨時汰換或擴充應用容器。

---

## 想一想（確認你懂了）

**Q1：Metabase 存 Dashboard 的地方，跟它查詢的股價資料，是同一個資料庫嗎？**

在同一台 MySQL 伺服器上，但是兩個不同的 database：Dashboard、帳號這些「Metabase 自己的設定」存在 `metabasedb`（Metabase 用 `metabase_app` 讀寫）；股價資料在 `mydb`（Metabase 用 `metabase_ro` 唯讀查詢）。兩者各自獨立——清空 `mydb` 不會弄壞 Dashboard 定義，只是圖表查不到數據。

**Q2：為什麼連線 Host 要填 `mysql` 而不是 `127.0.0.1`？**

因為 Metabase 和 MySQL 是兩個 Docker 容器。在 Docker 網路裡，容器之間要用「服務名」互相找，`mysql` 這個名字會被解析到 MySQL 容器。如果填 `127.0.0.1`，那指的是 Metabase 容器自己，裡面根本沒有 MySQL，就連不到。

**Q3：有了 BI 工具，哪些原本要工程師做的事可以下放給別人？**

各種「看數據」的需求：某段期間的股價走勢、比較幾支股票、算平均、做月報表……這些原本要工程師寫 SQL 撈，現在非技術同事在 Metabase 上點一點就有，還能存成 Dashboard 重複看。工程師就能把時間留給更難的事。

**Q4：什麼時候用點選式、什麼時候切到 SQL 模式？**

日常的篩選、彙總、分組，點選式就夠、而且做出來的問題別人容易改。遇到複雜邏輯（多表 JOIN、視窗函數、CASE WHEN）點選式做不出來，就切 SQL 模式。實務上兩者混用：SQL 高手寫好複雜查詢存起來，其他人拿去改篩選條件。

---

## 換你試試看

**練習 1：比較多支股票**

做一張圖，同時畫 2330 和 2317 的收盤價走勢（用 `stock_id` 當分組）。你會得到兩條線疊在一起，可以直觀比較兩支股票的走勢。這讓你熟悉 Metabase 的「分組」功能。

**練習 2：算一個彙總數字**

做一個問題：查某支股票在某個月的「平均收盤價」或「最高成交量」。這讓你體會 BI 不只畫線圖，也能做彙總統計（相當於 SQL 的 `AVG`、`MAX`、`GROUP BY`），而你完全不用寫 SQL。

**練習 3：驗證持久化**

做好一張 Dashboard 後，把 Metabase 容器整個刪掉再重建（`docker compose -f metabase/docker-compose-metabase.yml down` 再 `up -d`），重新登入看 Dashboard 還在不在。它應該還在——設定存在 MySQL 的 `metabasedb`，不在容器裡，所以連 `down` 都不會弄丟它。

**練習 4：把 Dashboard 加上第四張圖**

用 SQL 模式寫一個「每日總成交量 Top 5」的查詢（提示：`GROUP BY date ORDER BY SUM(Trading_Volume) DESC LIMIT 5`），做成長條圖加進 Dashboard。這讓你練習「SQL 查詢 → 圖表 → Dashboard」的完整路徑。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| Metabase 容器起不來（`Exited` 或反覆重啟）| 開機連不到設定庫：MySQL 沒啟動、沒接 `my_network`，或 `metabasedb`/`metabase_app` 沒建 | 照 Step 2 的順序重跑四個指令；`docker logs metabase` 看錯誤訊息 |
| 連 MySQL 一直失敗 | Host 填了 `127.0.0.1`，或兩容器不同網路 | 改填服務名 `mysql`；跑 `docker network connect my_network mysql` |
| http://localhost:3000 一片空白 | Metabase（JVM）還在啟動 | 等啟動完成再刷新，或用 Step 2 的等待迴圈 |
| 看不到任何資料表 | MySQL 裡 `mydb` 沒資料，或帳密錯 | 回 Step 1 載入 mock 資料；確認 metabase_ro/metabase |
| 新增資料庫時帳密被拒 | `metabase_ro` 還沒建，或密碼打錯 | 回 Step 3.5 建帳號；`SHOW GRANTS FOR 'metabase_ro'@'%'` 檢查 |
| 新建的 VIEW 在 Metabase 找不到 | schema 還沒同步 | 管理員 → 資料庫 → 同步資料庫 schema |
| 重啟後 Dashboard 不見 | 連到了別台 MySQL，或 `metabasedb` 被刪 | 確認 `MB_DB_*` 指向同一台 MySQL；別對 MySQL 的 compose 用 `down -v` |

---

## 收工

```bash
docker compose -f metabase/docker-compose-metabase.yml down    # 設定都在 MySQL 的 metabasedb，容器移除不影響
```

> 要注意的是 MySQL 那邊：對 `docker-compose-local.yml` 用 `down -v` 會把股價資料和 Metabase 設定一起刪掉，要整個重來才用。

---

## 這一章你學到了

- BI 工具是資料的出口，讓資料變成可讀的圖表與決策依據。
- 三種基本圖表 + Dashboard 組合 + SQL 模式 + VIEW，就能涵蓋大部分報表需求。
- Metabase 的設定庫（`metabasedb`）和資料來源（`mydb`）是同一台 MySQL 裡的兩個 database，連線帳號與權限各自獨立。
- Docker 網路內容器互連要用服務名（`mysql`），不是 localhost。

## 下一章要做什麼

Dashboard 有了，但資料更新目前仍靠手動跑 producer。**下一章用 APScheduler 定時觸發爬蟲，讓整條 pipeline 自動執行。**
