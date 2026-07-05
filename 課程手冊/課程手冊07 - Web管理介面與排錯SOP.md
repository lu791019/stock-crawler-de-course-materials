# 第 7 章：看清系統的每一層 — Web 管理介面與排錯 SOP

> 第 1~6 章你已經零散用過 RabbitMQ UI、Flower、phpMyAdmin。這一章把它們做個總整理：每個介面到底負責看什麼、出事的時候先看哪一個。這一章不長，但這套「排錯順序」你之後每次系統出問題都會用到。

---

## 做完這一章，你會做到

1. 講得出三大介面的分工：RabbitMQ 看**訊息**、Flower 看**任務**、phpMyAdmin 看**資料**。
2. 看懂 RabbitMQ 佇列的三個關鍵數字：Ready / Unacked / Total。
3. （選做）架起 Portainer，用 Web 介面管理所有容器。
4. 建立一套「出事了先看哪裡」的排錯 SOP。

---

## 先搞懂：每個介面各看系統的哪一段

```
Producer → [RabbitMQ] → Worker → [MySQL]
              ↑            ↑          ↑
         管理介面      Flower      phpMyAdmin
         (15672)      (5555)       (8080)
              全部容器：Portainer (9000，選做)
```

| 服務 | 網址 | 帳密 | 它回答的問題 |
|------|------|------|-------------|
| RabbitMQ 管理介面 | http://localhost:15672 | worker / worker | 訊息有沒有進佇列？堆積了嗎？ |
| Flower | http://localhost:5555 | （無） | 任務成功還失敗？跑多久？ |
| phpMyAdmin | http://localhost:8080 | root / 1234 | 資料真的寫進 DB 了嗎？ |
| Portainer（選做） | http://localhost:9000 | 自設 | 容器都活著嗎？log 說什麼？ |

---

## 一步一步跟著做

### Step 1：把 infra 起好

```bash
docker compose -f docker-compose-local.yml up -d rabbitmq flower mysql phpmyadmin

curl -o /dev/null -s -w "RabbitMQ:   %{http_code}\n" http://localhost:15672
curl -o /dev/null -s -w "Flower:     %{http_code}\n" http://localhost:5555
curl -o /dev/null -s -w "phpMyAdmin: %{http_code}\n" http://localhost:8080
```

> ✅ 三個都回 200 就過關。

### Step 2：RabbitMQ 管理介面 — 看「訊息」

開 http://localhost:15672（worker / worker）。重點只有兩個地方：

| 頁籤 | 看什麼 |
|------|--------|
| **Overview** | 訊息總量、傳輸速率、節點健康 |
| **Queues and Streams** | 每條佇列的訊息數（**最重要**）|

點進 **Queues and Streams**，每條佇列有三個數字，這三個一定要會讀：

| 欄位 | 意思 | 健康狀態 |
|------|------|---------|
| **Ready** | 排隊中、還沒被 worker 取走 | 應該很快歸 0 |
| **Unacked** | worker 取走了、還沒回報完成 | 短暫出現後消失 |
| **Total** | Ready + Unacked | — |

- Ready 一直堆高不降 → 沒有 worker 在消費（沒開、掛了、或 `-Q` 訂錯佇列）——第 3 章的對照實驗你已經親眼看過。
- Unacked 卡住不動 → worker 拿了任務但卡住沒做完——第 4 章的 requeue 實驗你也看過它跳動。

### Step 3：Flower — 看「任務」

開 http://localhost:5555 ：

| 頁籤 | 看什麼 |
|------|--------|
| **Dashboard** | worker 清單、Online 狀態、各自處理了幾個任務 |
| **Tasks** | 每個任務的狀態（SUCCESS / FAILURE / RETRY）、耗時、參數、回傳值 |
| **Workers** | 點進單一 worker 看它訂閱哪些佇列、concurrency |

**RabbitMQ UI 和 Flower 的分工**，一句話記住：

| | RabbitMQ 管理介面 | Flower |
|---|---|---|
| 觀察對象 | **訊息**（佇列裡有幾則）| **任務**（每個 task 的執行結果）|
| 排錯時機 | 懷疑任務**沒發出去** | 懷疑任務**執行出錯** |

### Step 4：phpMyAdmin — 看「資料」

開 http://localhost:8080（root / 1234）→ 左側 `mydb` → `TaiwanStockPrice`（第 5 章寫進去的）→ Browse。

這是驗證「資料真的落地」的最後一關。任務 SUCCESS 不代表資料寫對了——最終還是要來這裡（或下 SQL）眼見為憑。

### Step 5（選做）：Portainer — 看「容器」

Portainer 是 Docker 的 Web 管理介面，不用背指令就能看容器狀態、讀 log、重啟服務：

```bash
docker volume create portainer_data

docker run -d \
  --name portainer \
  --restart=always \
  -p 9000:9000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

開 http://localhost:9000 ，首次進入設定 admin 密碼（至少 12 字元）→ Get Started → 管理 local 環境。

**Containers** 頁會列出所有容器，點進去可以直接看 log、restart——排錯時特別方便。

> 💡 `-v /var/run/docker.sock:...` 是讓 Portainer 能操作 Docker 的關鍵（掛載 Docker socket）。第 11 章 Airflow 的 DockerOperator 也用同一招。

### Step 6：發一批任務，四個介面同步觀察

開一個 worker（本機）＋發一批 print 版任務：

```bash
# T1
uv run python -m celery -A crawler.worker worker --loglevel=info
# T2
uv run crawler/producer_crawler_finmind_print.py
```

然後在每個介面看對應的變化：

| 介面 | 你會看到 |
|------|---------|
| **RabbitMQ (15672)** | Queues 頁：Ready 短暫升高 → 被 worker 消化後降回 0 |
| **Flower (5555)** | Tasks 頁：5 個任務 STARTED → SUCCESS |
| **phpMyAdmin (8080)** | 這批是 print 版不寫 DB，資料不變（符合預期）|
| **Portainer (9000)** | Containers 全部綠燈 running |

> ✅ 能把「一批任務流過系統」在四個介面上各自指認出來，這一章的目的就達到了。

---

## 排錯 SOP（這一章真正要你帶走的東西）

系統出問題時，**由外而內、由抽象到具體**，照這個順序查：

```
1. Flower       → 任務有沒有到？成功還失敗？
2. RabbitMQ     → 訊息有沒有進佇列？堆積了嗎？
3. Portainer    → 容器都還活著嗎？有沒有一直 restart？
4. phpMyAdmin   → 資料有沒有真的寫進 DB？
5. docker logs  → 上面都看不出來，直接讀原始 log
```

| 症狀 | 先看哪裡 | 可能原因 |
|------|---------|---------|
| 任務發了沒反應 | Flower（沒紀錄？）→ RabbitMQ Queues | Ready 堆積 = 沒 worker 消費（沒開 / `-Q` 訂錯）|
| 任務一直 RETRY / FAILURE | Flower Tasks | 點進去看錯誤訊息 |
| 容器一直重啟 | Portainer Containers | 看 log 找 crash 原因 |
| 任務 SUCCESS 但查不到資料 | phpMyAdmin | MYSQL_HOST 沒設對 / 寫錯表 |
| 以上都看不出來 | `docker logs <容器名>` | 讀最原始的錯誤 |

看原始 log 的指令：

```bash
docker compose -f docker-compose-local.yml logs rabbitmq
docker compose -f docker-compose-local.yml logs worker_twse
# 或單一容器
docker logs rabbitmq
```

---

## 檢查你是不是真的做到了

| # | 你應該做到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | 講出 Ready / Unacked 各代表什麼 | 你會讀佇列的健康狀態 |
| 2 | 講出 RabbitMQ UI vs Flower 的分工 | 你知道「看訊息」和「看任務」的差別 |
| 3 | 發一批任務、在各介面指認它的足跡 | 你能追蹤任務流過系統的全程 |
| 4 | 背出排錯 SOP 的順序 | 出事時不會亂槍打鳥 |

---

## 想一想（確認你懂了）

**Q1：任務發出去沒反應，你第一個看哪裡？為什麼不是先看 log？**

照 SOP 從 Flower 開始：任務根本沒進系統、還是有進但執行失敗，Flower 一眼可分；Flower 完全沒紀錄，再看 RabbitMQ 的 Queues 是否堆積。因為 Web 介面能在 10 秒內告訴你「訊息到底有沒有進佇列、有沒有人消費」，快速把問題定位到某一層；直接鑽 log 是最後手段——log 資訊最原始但也最花時間。由外而內，先定位層，再看細節。

**Q2：Flower 顯示任務 SUCCESS，但 phpMyAdmin 查不到資料，問題可能出在哪？**

任務「執行成功」只代表程式沒拋出例外，不代表資料寫對了地方。可能：寫到別的資料庫（MYSQL_HOST 指錯，例如本機/容器搞混）、寫到別張表、或任務本身是 print 版根本不寫 DB。這就是為什麼資料落地一定要到 DB 層親眼驗證。

**Q3：Ready 堆高和 Unacked 卡住，分別代表什麼問題？**

Ready 堆高 = 訊息在排隊但**沒人領**——worker 沒開、掛了、或訂閱的佇列不對。Unacked 卡住 = worker **領了但做不完**——任務卡死、跑太久、或 worker 失去回應。兩個數字指向兩種完全不同的故障，這就是它們分開顯示的價值。

---

## 這一章你學到了

- 三大介面分工：RabbitMQ 看訊息、Flower 看任務、phpMyAdmin 看資料；Portainer 看容器。
- Ready / Unacked 是佇列健康的兩個關鍵訊號。
- 排錯 SOP：Flower → RabbitMQ → Portainer → phpMyAdmin → docker logs，由外而內。

## Phase A 收尾：完整跑一次 Celery pipeline

第 1~7 章的 Celery 階段到此完成。收尾前，把所有服務一起跑、走一次完整正式流程，確認整條鏈是通的：

```bash
# 1. 全開（六個服務）
docker compose -f docker-compose-local.yml up -d --build rabbitmq flower mysql phpmyadmin worker_twse worker_tpex

# 2. 三個 Web 介面都活著
curl -o /dev/null -s -w "RabbitMQ:   %{http_code}\n" http://localhost:15672
curl -o /dev/null -s -w "Flower:     %{http_code}\n" http://localhost:5555
curl -o /dev/null -s -w "phpMyAdmin: %{http_code}\n" http://localhost:8080

# 3. worker ready
docker compose -f docker-compose-local.yml logs worker_twse | grep ready
docker compose -f docker-compose-local.yml logs worker_tpex | grep ready

# 4. 發任務（multi_queue：2330 → twse、00679B → tpex）
docker compose -f docker-compose-local.yml up producer

# 5. 驗證閉環：worker 成功 + DB 有資料
docker compose -f docker-compose-local.yml logs worker_twse | grep succeeded
docker exec mysql mysql -uroot -p1234 mydb -e \
  "SELECT stock_id, COUNT(*) AS cnt FROM TaiwanStockPrice GROUP BY stock_id;"
```

✅ **預期**：六服務 Up、三個 200、worker succeeded、MySQL 有 2330 / 00679B 的資料，Flower Tasks 頁全 SUCCESS。

> 這五步就是之後第 13 章「完整系統整合」七步驟驗證的雛形——到時會再加上 Airflow 和 Metabase。

收工：

```bash
docker compose -f docker-compose-local.yml down     # 保留資料
```

## 下一章要做什麼

Phase A 的系統面收齊了。**下一章進入 Phase B：把 MySQL 裡的股價資料變成看得到的圖表——用 Metabase 做出你的第一個股價 Dashboard。**
