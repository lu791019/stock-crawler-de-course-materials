# 第 8 章：把資料變成看得到的圖表 — Metabase BI 視覺化

> 這是 Phase B 的第一章，也是整套課的「回報時刻」。你前面辛苦爬下來、寫進 MySQL 的股價，到這裡第一次變成一張你點得動的走勢圖。

---

## 做完這一章，你會做到

1. 啟動 Metabase 並連上你的 MySQL。
2. 做出三種圖表：走勢折線圖、成交量長條圖、最新收盤價數字卡片。
3. 把多張圖組合成一個 Dashboard。
4. 用 SQL 模式下自訂查詢，並把 MySQL 的 VIEW 拿來做圖。
5. 分得清「Metabase 自己的設定」和「它查詢的資料來源」是兩個不同的資料庫。

---

## 先搞懂：資料的「出口」

前面的章節都在解決「怎麼把資料可靠地生出來、存起來」。但資料躺在資料庫裡沒人看，價值等於零。**BI（Business Intelligence，商業智慧）工具就是資料的出口**——讓不會寫 SQL 的人也能拉圖表、看趨勢、做決策。

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
| **Tableau** | 視覺化旗艦 | 拖拉分析與圖表表現力天花板、企業標配 | 貴 |
| **Redash** | 開源、SQL-first | 每張圖就是一句 SQL，開發者取向 | 開源（近年維護趨緩）|
| **Superset** | Apache 開源 | 功能最全的開源選項，架設與學習較重 | 免費 |
| **Looker Studio** | Google 免費雲端 | 接 GA、BigQuery 特別順 | 免費 |
| **Grafana** | 監控/時序起家 | DevOps 儀表板之王，看系統 metrics 不是業務報表 | 開源 |

選型口訣：教學與中小團隊自架 → Metabase；企業微軟生態 → Power BI；純 SQL 人 → Redash / Superset；看系統監控 → Grafana。本課選 Metabase：開源、Docker 一行起、十分鐘拉出第一張圖。

**Metabase 是什麼**：

- 開源的商業智慧（BI）平台
- 能將資料庫裡的資料快速轉換成圖表、儀表板與報表
- 簡單易用、安裝快速，適合中小型團隊、教育場合，或作為企業內部的輕量 BI 工具

**為什麼排在這裡？** 因為到第 4 章為止，你的資料已經穩定地在 MySQL 裡了。這時把它變成圖表，你會第一次「看到自己做的東西有用」——這種成就感是最好的學習動力。

---

## 這一章會用到的檔案

| 檔案 | 角色 | 說明 |
|------|------|------|
| `metabase/docker-compose-metabase.yml` | 部署 | 啟動 Metabase 容器 |
| `metabase/README.md` | 說明 | 連線設定與操作步驟 |
| `example/mock_stock_price_data.sql` | 模擬資料 | MySQL 沒資料時快速補一批 |
| `example/vw_stock_price_daily.sql` | VIEW 範例 | 每日去重的股價 VIEW（進階段落用）|

---

## 先懂一個容易混淆的觀念：Metabase 碰到兩個資料庫

用之前一定要分清楚，不然你會被「為什麼要設定兩次資料庫」搞糊塗：

1. **Metabase 自己的設定庫**：你的帳號、做好的 Dashboard、查詢紀錄，存在 Metabase **內建的 H2 資料庫**裡，透過 Docker volume `metabase-data` 保存。**它跟你的 MySQL 沒關係。**
   > 有些教學會要你先在 phpMyAdmin 建一個 `metabasedb` 資料庫和專用帳號給 Metabase 存設定——那是「設定庫放 MySQL」的做法；本課用內建 H2，這整組步驟都**不需要**。Google 到那種教學時別混淆。
2. **資料來源**：也就是你的 MySQL（`mydb`）。Metabase 只是「連過去查」，你要在它的網頁設定裡手動加這個連線。

一句話：**MySQL 是「被查的對象」，Metabase 的設定另外存在 H2。** 因為有 volume，重啟容器你的 Dashboard 不會不見。

---

## Metabase 功能地圖（每一項都實測過）

做圖之前先認識整個介面有什麼。下表的「實測範例」都是在本課的股價資料上真實跑過的：

| 頁面 / 功能 | 在哪 | 做什麼 | 實測範例 |
|------------|------|--------|---------|
| **Browse data** | 左側 Databases | 點開資料庫直接看每張表 | 連上後看到 4 張表（含 VIEW）|
| **Question 查詢產生器** | + New → Question | 免 SQL：選表→篩選→彙總→分組 | 「各股平均收盤價」長條圖：11 支股票一次畫出 |
| **SQL 模式 + 變數** | + New → SQL query | 寫 SQL，`{{變數}}` 做互動篩選 | `WHERE stock_id = {{sid}}`，切 2454 立刻重畫 32 天走勢 |
| **視覺化切換** | 結果頁左下 Visualization | 同一份結果切折線/長條/數字卡… | 上面兩例分別存成 bar 和 line |
| **Dashboard** | + New → Dashboard | 卡片拼裝＋全域篩選器＋自動刷新 | 「台股戰情室」：兩張卡並排組裝完成 |
| **Collections** | 左側收藏集 | 資料夾式管理 Question/Dashboard，可設權限 | 建「股價分析」收藏集歸檔 |
| **X-ray 一鍵分析** | 表格頁的黃色閃電 | Metabase 自動掃資料生一組圖 | 對 TaiwanStockPrice 按下去：**自動生出 9 張圖** |
| **訂閱與警示** | Dashboard / Question 內 | 定時寄報表、數字達標告警 | 功能在 UI 裡；寄送需先設 SMTP（管理員→設定→Email），課堂不設 |
| **Admin → Databases** | 齒輪 → 管理員 | 資料源管理、同步 schema | Step 10 的 VIEW 同步就在這 |
| **Admin → People / Permissions** | 同上 | 使用者、群組、誰能看哪個資料庫 | 見下方「權限有兩層」|

> **權限有兩層**：MySQL 的 `metabase_ro` 管「Metabase 整體拿得到什麼」（DB 層）；Metabase 的 Permissions 管「哪個使用者看得到什麼」（BI 層）。兩層各守一關。

---

## 一步一步跟著做

### Step 1：確認 MySQL 裡有資料

先確保前面幾章已經把股價寫進 `mydb`（第 5 章跑過 producer；注意第 6 章寫的是另一張表 `TaiwanStockPrice_duplicate`，不算數）。

```bash
docker compose -f docker-compose-local.yml up -d mysql phpmyadmin

docker exec mysql mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice GROUP BY stock_id"
```

> ✅ 有幾支股票、各有幾百筆，就過關。
>
> 💡 **沒資料（或想要更多支股票）？** 用專案附的模擬資料一鍵補齊——10 支股票、各約 32 個交易日：
>
> ```bash
> docker exec -i mysql mysql -uroot -p1234 mydb < example/mock_stock_price_data.sql
> ```
>
> 再跑一次上面的查詢，就會看到 2330、0050、2317 等 10 支股票的資料。

### Step 2：啟動 Metabase

```bash
# 如果這個 compose 用到外部網路，先建一次（建過就跳過）
docker network create my_network

docker compose -f metabase/docker-compose-metabase.yml up -d
```

> ⏳ Metabase 是 Java（JVM）應用，**啟動比較慢，大約要等 30~60 秒**。可以用這段等它就緒：
>
> ```bash
> until curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/api/health | grep -q 200; do
>   echo "等待 Metabase 啟動中..."
>   sleep 10
> done
> echo "Metabase 已就緒！"
> ```

**把 MySQL 接上 my_network**（關鍵一步）：Metabase 掛在 `my_network` 上，但 `docker-compose-local.yml` 起的 mysql 不在那個網路——不接起來，等一下 Metabase 會連不到 MySQL：

```bash
docker network connect my_network mysql
```

> 已經接過會顯示 `already exists`，無妨。想一次到位的話，`docker-compose-all.yml`（第 13 章）把所有服務放在同一網路，就不需要這一步。

### Step 3：首次設定，建立管理員帳號

打開 http://localhost:3000 ，跟著導覽建立一個管理員帳號（這個帳號是存在 Metabase 的 H2 裡，跟 MySQL 無關）。語言可選繁體中文。

### Step 3.5：幫 Metabase 建一個「唯讀」資料庫帳號

Metabase 對 MySQL 只需要「讀」——正式做法是給它一個只有 SELECT 的專用帳號（最小權限原則，補充D 第 6 節的實戰應用）：

```sql
CREATE USER 'metabase_ro'@'%' IDENTIFIED BY 'metabase';   -- _ro = read-only 的慣用命名
GRANT SELECT ON mydb.* TO 'metabase_ro'@'%';              -- 只給查詢，不給寫
```

> **phpMyAdmin 版**（同一件事的圖形操作）：root 登入 → 首頁 **User accounts** → **Add user account** → 使用者名稱 `metabase_ro`、主機名稱選「任何主機（%）」、設密碼 → 「資料庫的權限」選 `mydb` → 只勾 **SELECT** → 執行。

✅ VM 實測：這個帳號透過 Metabase 查資料一切正常；想 `DELETE` 會被 MySQL 直接擋下（`DELETE command denied to user 'metabase_ro'`）——BI 只該讀、不該寫，權限層幫你守住。

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
> 💡 用 `root / 1234` 也連得上，但正式做法是最小權限——就算 Metabase 被玩壞或帳號外洩，也動不了你的資料。
>
> ⚠️ 最常卡在 Host：在 Docker 網路裡，容器之間要用**服務名**（`mysql`）互相找，不能用 `127.0.0.1`（那會指向 Metabase 容器自己）。前提是兩個容器在同一個網路（`my_network`）。

### Step 5：第一張圖 — 台積電收盤價折線圖

1. 點「+ 新增」→「問題」（Ask a question）→ 選 `TaiwanStockPrice` 這張表。
2. 篩選：`stock_id` = `2330`。
3. 彙總：選「Average of close」；群組依據：選 `date`（按日）。
4. 點「視覺化」→ 選折線圖。

> ✅ 看到一條台積電的收盤價走勢線，這一章最重要的一步就成功了——你爬的資料，現在是一張圖了。

5. 點「儲存」，命名「台積電收盤價走勢」。

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

### Step 8：組一個 Dashboard

1. 點「+ 新增」→「Dashboard」，命名「台股股價儀表板」。
2. 進入編輯模式（鉛筆圖示）→「+」把剛才三張圖加進來。
3. 拖拉調整每張圖的大小和位置 → 儲存。

> ✅ 一個頁面同時看到走勢、成交量、最新價——這就是給老闆看的那一頁。

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
| 6 | 重啟 Metabase 容器後 Dashboard 還在 | volume 讓設定持久化 |

---

## 想再深入一點

- **BI 工具把「查詢能力」下放給非技術同事。** 有了 Metabase，原本要工程師寫 SQL 才做得到的「看某段期間某股走勢」，業務或主管自己拉一拉就有了。這在真實團隊很有價值——工程師不用當「人肉查詢機」。
- **Metabase 的圖表底下其實還是 SQL。** 你用滑鼠拉的每一個問題，Metabase 都會翻譯成一段 SQL 去查 MySQL。它也有「原生查詢」模式讓你直接寫 SQL。所以 BI 不是取代 SQL，而是幫你把常用查詢包成好點的介面。
- **為什麼用 volume 特別重要？** 因為 Metabase 的設定（帳號、Dashboard）存在容器內的 H2。如果沒掛 volume，容器一刪，你辛苦做的 Dashboard 就全沒了。`metabase-data` 這個 volume 就是把這些設定存到容器外，確保重啟不遺失。

---

## 想一想（確認你懂了）

**Q1：Metabase 存 Dashboard 的地方，跟它查詢的股價資料，是同一個資料庫嗎？**

不是。Dashboard、帳號這些「Metabase 自己的設定」存在它內建的 H2（靠 `metabase-data` volume 保存）；股價資料在你的 MySQL（`mydb`）。Metabase 只是連去 MySQL「查」，兩者是分開的。

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

做好一張 Dashboard 後，把 Metabase 容器停掉再重開（`docker compose -f metabase/docker-compose-metabase.yml restart`），重新登入看 Dashboard 還在不在。它應該還在——這讓你確認 volume 真的把設定保存下來了。

**練習 4：把 Dashboard 加上第四張圖**

用 SQL 模式寫一個「每日總成交量 Top 5」的查詢（提示：`GROUP BY date ORDER BY SUM(Trading_Volume) DESC LIMIT 5`），做成長條圖加進 Dashboard。這讓你練習「SQL 查詢 → 圖表 → Dashboard」的完整路徑。

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| 連 MySQL 一直失敗 | Host 填了 `127.0.0.1`，或兩容器不同網路 | 改填服務名 `mysql`；跑 `docker network connect my_network mysql` |
| http://localhost:3000 一片空白 | Metabase（JVM）還在啟動 | 等 30~60 秒再刷新，或用 Step 2 的等待迴圈 |
| 看不到任何資料表 | MySQL 裡 `mydb` 沒資料，或帳密錯 | 回 Step 1 載入 mock 資料；確認 metabase_ro/metabase |
| 新增資料庫時帳密被拒 | `metabase_ro` 還沒建，或密碼打錯 | 回 Step 3.5 建帳號；`SHOW GRANTS FOR 'metabase_ro'@'%'` 檢查 |
| 新建的 VIEW 在 Metabase 找不到 | schema 還沒同步 | 管理員 → 資料庫 → 同步資料庫 schema |
| 重啟後 Dashboard 不見 | volume 沒掛好 | 確認 compose 有掛 `metabase-data` volume，別用 `down -v` |

---

## 收工

```bash
docker compose -f metabase/docker-compose-metabase.yml down    # 設定保留在 volume
```

> 加 `-v` 會連 volume 一起刪（Dashboard、帳號全部消失），要重來才用。

---

## 這一章你學到了

- BI 工具是資料的出口，讓資料變成可讀的圖表與決策依據。
- 三種基本圖表 + Dashboard 組合 + SQL 模式 + VIEW，就能涵蓋大部分報表需求。
- Metabase 用內建 H2 存自己的設定，MySQL 只是資料來源。
- Docker 網路內容器互連要用服務名（`mysql`），不是 localhost。

## 下一章要做什麼

Dashboard 有了，但資料要新鮮，還得**有人**每天手動跑 producer。**下一章裝上「鬧鐘」——用 APScheduler 定時觸發爬蟲，讓整條 pipeline 自己動起來。**
