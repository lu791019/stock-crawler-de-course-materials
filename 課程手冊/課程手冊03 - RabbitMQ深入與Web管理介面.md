# RabbitMQ 深入與 Web 管理介面 實作手冊

> 對象：已完成「Celery 基礎」的學員
> 涵蓋：啟動完整 infra → RabbitMQ 管理介面 → Flower 監控 → phpMyAdmin → Portainer → 四介面觀察 → 排錯 SOP
> 實作專案：https://github.com/lu791019/stock-crawler-de-course-materials

---

## 這一集在做什麼

前面只用 Worker log 觀察系統，這一集學會用**四個 Web 介面**看清整個分散式系統的每個環節：

```
Producer → [RabbitMQ] → Worker → [MySQL]
              ↑            ↑          ↑
         管理介面     Flower 監控  phpMyAdmin
         (15672)      (5555)      (8080)
              全部容器：Portainer (9000)
```

---

## 使用前提

```bash
cd ~/stock-crawler
docker --version
uv --version
```

✅ **預期**：Docker、uv 都可用。

---

## 目錄

- [第一部分：啟動完整 infra](#第一部分啟動完整-infra)
- [第二部分：RabbitMQ 管理介面](#第二部分rabbitmq-管理介面)
- [第三部分：Flower 監控](#第三部分flower-監控)
- [第四部分：phpMyAdmin](#第四部分phpmyadmin)
- [第五部分：Portainer 安裝與操作](#第五部分portainer-安裝與操作)
- [第六部分：發任務在四個介面觀察](#第六部分發任務在四個介面觀察)
- [第七部分：排錯 SOP](#第七部分排錯-sop)

---

## 第一部分：啟動完整 infra

一次起 RabbitMQ、Flower、MySQL、phpMyAdmin 四個基礎服務。

### Step 1：啟動

```bash
cd ~/stock-crawler
docker compose -f docker-compose-local.yml up -d rabbitmq flower mysql phpmyadmin
```

### Step 2：確認全部 Up

```bash
docker compose -f docker-compose-local.yml ps
```

✅ **預期**：`rabbitmq`、`flower`、`mysql`、`phpmyadmin` 四個都是 `Up`（等 20-30 秒讓 MySQL 完成初始化）。

### Step 3：curl 確認 Web 介面

```bash
curl -o /dev/null -w "RabbitMQ:   %{http_code}\n" http://localhost:15672
curl -o /dev/null -w "Flower:     %{http_code}\n" http://localhost:5555
curl -o /dev/null -w "phpMyAdmin: %{http_code}\n" http://localhost:8080
```

✅ **預期**：三個都回 `200`。

| 服務 | 網址 | 帳密 |
|------|------|------|
| RabbitMQ 管理 | http://localhost:15672 | worker / worker |
| Flower 監控 | http://localhost:5555 | （無） |
| phpMyAdmin | http://localhost:8080 | root / 1234 |

---

## 第二部分：RabbitMQ 管理介面

瀏覽器開 http://localhost:15672，帳密 `worker` / `worker`。

### 各頁籤重點

| 頁籤 | 看什麼 |
|------|--------|
| **Overview** | 訊息總量、傳輸速率、節點健康狀態 |
| **Connections** | 目前連上的連線（Worker、Producer）|
| **Channels** | 連線內的通道 |
| **Queues and Streams** | 每條 queue 的訊息數量（**最重要**）|

### Queue 三個關鍵數字

點進 **Queues and Streams**，每條 queue 有三個數字：

| 欄位 | 意思 |
|------|------|
| **Ready** | 排隊中、還沒被 Worker 取走的訊息 |
| **Unacked** | Worker 取走了、但還沒回報完成（ack）|
| **Total** | Ready + Unacked |

✅ **理解**：
- 正常運作時 Ready 應該很快降到 0（Worker 消化掉）
- Ready 一直堆高不降 → 沒有 Worker 在消費，或 Worker 掛了
- Unacked 卡住不動 → Worker 拿了任務但卡住沒做完

---

## 第三部分：Flower 監控

瀏覽器開 http://localhost:5555

### 各頁籤重點

| 頁籤 | 看什麼 |
|------|--------|
| **Dashboard** | Worker 清單、Online 狀態、各 worker 處理任務數 |
| **Tasks** | 每個任務的狀態（SUCCESS / FAILURE / RETRY）、耗時、參數、回傳值 |
| **Workers** | 點進去看 worker 監聽哪些 queue、concurrency |

### RabbitMQ 管理介面 vs Flower 的分工

| | RabbitMQ 管理介面 | Flower |
|---|---|---|
| 觀察對象 | **訊息**（queue 裡有幾則）| **任務**（每個 task 的執行結果）|
| 回答的問題 | 任務有沒有進 queue？堆積了嗎？ | 任務成功還是失敗？跑多久？ |
| 排錯時機 | 懷疑任務沒發出去 | 懷疑任務執行出錯 |

---

## 第四部分：phpMyAdmin

瀏覽器開 http://localhost:8080，帳密 `root` / `1234`。

### 操作重點

1. 左側點開 `mydb` 資料庫
2. 目前還沒發爬蟲任務寫 DB，所以 `mydb` 裡通常沒有資料表 —— 這是正常的
3. 上方 **SQL** 頁籤可以直接下 SQL 查詢

✅ **預期**：能登入、看到左側資料庫清單有 `mydb`。

> phpMyAdmin 是「資料庫的 Web 介面」，等後面幾集把爬到的股價寫進 MySQL 後，就會在這裡看到 `TaiwanStockPrice` 資料表和資料。

---

## 第五部分：Portainer 安裝與操作

Portainer 是「Docker 的 Web 管理介面」，用一個容器就能圖形化管理所有容器。

### Step 1：用 docker run 啟動 Portainer

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

- `-p 9000:9000`：Web 介面 port
- `-v /var/run/docker.sock:...`：讓 Portainer 能操作 Docker（掛載 Docker socket）
- `-v portainer_data:/data`：保存 Portainer 設定

### Step 2：確認啟動

```bash
docker ps | grep portainer
curl -o /dev/null -w "Portainer: %{http_code}\n" http://localhost:9000
```

✅ **預期**：容器在 running；curl 回 `200`。

### Step 3：首次設定

1. 瀏覽器開 http://localhost:9000
2. 第一次進去要**設定 admin 密碼**（至少 12 字元）
3. 選 **Get Started** → 管理 local Docker 環境

### Step 4：操作重點

| 功能 | 用途 |
|------|------|
| **Containers** | 看所有容器狀態、start / stop / restart、看 logs |
| **Images** | 管理本機 image |
| **Volumes** | 管理資料卷（mysql、portainer_data）|
| **Networks** | 管理 Docker 網路 |

✅ **預期**：在 Containers 頁看到 rabbitmq、flower、mysql、phpmyadmin、portainer 全部列出，可以直接點 log、restart。

> Portainer 讓你不用背 docker 指令也能管理容器，排錯時看 log 特別方便。

---

## 第六部分：發任務在四個介面觀察

現在四個介面都開好了，發一批爬蟲任務，同時觀察四邊變化。

### Step 1：本地啟動 Worker（新終端機）

```bash
cd ~/stock-crawler
uv run celery -A crawler.worker worker --loglevel=info
```

✅ **預期**：看到 `celery@... ready.`

### Step 2：發爬蟲任務（另一終端機）

```bash
cd ~/stock-crawler
uv run python crawler/producer_crawler_finmind_print.py
```

### Step 3：四介面同步觀察

| 介面 | 觀察 |
|------|------|
| **RabbitMQ (15672)** | Queues 頁：Ready 短暫升高 → 被 Worker 消化後降回 0 |
| **Flower (5555)** | Tasks 頁：5 個任務從 STARTED → SUCCESS |
| **Portainer (9000)** | Containers → 點 worker（若 worker 也在容器內）看即時 log |
| **phpMyAdmin (8080)** | 這批是 print 版不寫 DB，`mydb` 仍無資料表（符合預期）|

✅ **預期**：Flower 顯示 5 個 SUCCESS、RabbitMQ 的 Ready 回到 0。

---

## 第七部分：排錯 SOP

分散式系統出問題時，**依這個順序**逐層排查：

### 排錯順序

```
1. Flower       → 任務有沒有到？成功還失敗？
2. RabbitMQ     → 訊息有沒有進 queue？堆積了嗎？
3. Portainer    → 容器都還活著嗎？有沒有一直 restart？
4. phpMyAdmin   → 資料有沒有真的寫進 DB？
5. docker logs  → 上面都看不出來，直接讀原始 log
```

### 對照表

| 症狀 | 先看哪裡 | 可能原因 |
|------|---------|---------|
| 任務發了沒反應 | RabbitMQ Queues | Ready 堆積 = 沒 Worker 消費 |
| 任務一直 RETRY / FAILURE | Flower Tasks | 點進去看錯誤訊息 |
| 容器一直重啟 | Portainer Containers | 看 log 找 crash 原因 |
| 爬完了但查不到資料 | phpMyAdmin | MYSQL_HOST 沒設對 / 表沒建 |
| 以上都看不出來 | `docker logs` | 讀最原始的錯誤 |

### 看原始 log 指令

```bash
docker compose -f docker-compose-local.yml logs rabbitmq
docker compose -f docker-compose-local.yml logs flower
docker compose -f docker-compose-local.yml logs mysql
# 或看單一容器
docker logs rabbitmq
```

> 記住：**由外而內、由抽象到具體**。先用 Web 介面快速定位是哪一層出事，最後才鑽進 log。

---

## 清理

```bash
# 停 Worker：Ctrl+C
docker compose -f docker-compose-local.yml down
docker stop portainer && docker rm portainer   # 若要移除 Portainer
```

---

## 本集完成清單

- [ ] 啟動 rabbitmq + flower + mysql + phpmyadmin，curl 三個都 200
- [ ] RabbitMQ 管理介面：看懂 Ready / Unacked / Total
- [ ] Flower：看懂 Dashboard / Tasks / Workers
- [ ] phpMyAdmin：登入、看到 mydb
- [ ] Portainer：docker run 安裝、設密碼、看容器 log
- [ ] 發任務在四介面同步觀察
- [ ] 熟悉排錯 SOP（Flower → RabbitMQ → Portainer → phpMyAdmin → logs）

---

## 下集預告

下一集學多 Worker 與多 Queue：讓 twse / tpex 兩種股票分流到不同 Worker，並用 `--scale` 動態擴充 Worker 數量。
