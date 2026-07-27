# 課程手冊16 - 系統搬家：多台 VM 與 Cloud SQL

> 本章對應 EP18。前置：第 14 章做完（有 GCP 專案、gcloud 可用、stock-crawler-vm 存在且會開關機）。
>
> 第 14 章把整套系統塞進一台 VM——能動，但所有服務擠在一起：資料庫跟 worker 搶記憶體、一台掛全部掛。本章把它拆開：**資料庫換成託管的 Cloud SQL、worker 搬到第二台 VM**——補充A 講的「分散式」，這次真的跨機器。

## 做完這一章你會

1. 說得出「託管服務 vs 自架」的取捨——雲的核心交易
2. 用 gcloud 建立一個 Cloud SQL（MySQL 8.0）實例，設定授權網路
3. 分清楚內部 IP 與外部 IP，知道同一個 VPC 裡的機器怎麼互相溝通
4. 開第二台 VM 專跑 worker，用 compose override 檔讓它連到別台機器的服務
5. 跑通跨機器的完整閉環：VM1 發任務 → VM2 消化 → 資料落進 Cloud SQL
6. 說得出 Swarm 與 Kubernetes 是什麼、為什麼本課程用 compose 就夠

## 先搞懂

### 託管服務 vs 自架：雲的核心交易

到上一章為止，MySQL 是你自己跑的容器：版本升級你來、備份你來、掛了半夜也是你來。**Cloud SQL 是 Google 幫你跑的 MySQL**——備份、更新、故障轉移、高可用全包，代價是錢。這就是雲的核心交易：**用錢買維運**。

| | 自架 MySQL 容器（第 5 章至今） | Cloud SQL |
|---|---|---|
| 誰負責備份／升級／修機器 | 你 | Google |
| 費用 | 機器錢（VM 反正開著＝近乎零） | 實例按時計費（課程用最小規格 db-f1-micro） |
| 控制權 | 完全（任何參數、任何版本） | 部分（參數白名單內可調） |
| 連線方式 | 容器名（同 compose 網路） | IP＋授權網路（或私有連線） |
| 什麼時候選它 | 學習、預算敏感、要完全控制 | 資料重要到「掛了會出事」、沒有專職 DBA |

判斷的口訣：**資料庫是最不想自己扛的東西**——它有狀態、掛了最痛，所以它通常是系統裡第一個換成託管的零件。

### 這一章的搬家藍圖

```
第 14 章（一台裝全部）              本章（拆成三份）
┌─────────────────────┐        ┌─────────────┐   ┌─────────────┐
│ stock-crawler-vm     │        │ VM1（infra）│   │ VM2（worker）│
│  rabbitmq  worker×2  │  →     │  rabbitmq   │←──│  worker×2    │
│  mysql  airflow ...  │        │  flower     │   └──────┬──────┘
└─────────────────────┘        └─────────────┘          │ 寫入
                                                  ┌──────▼──────┐
                                                  │  Cloud SQL   │（託管 MySQL）
                                                  └─────────────┘
```

- **VM1（既有的 stock-crawler-vm）**：收斂成 infra 角色，只跑 RabbitMQ 與 Flower
- **VM2（本章新開）**：只跑兩個 worker——爬蟲的勞力工作獨立成一台，之後要加速就再開 VM3、VM4（第 7 章 `--scale` 的跨機器版）
- **Cloud SQL**：取代 MySQL 容器。程式端只改 `MYSQL_HOST`——第 6 章 config 中心設計的紅利在這裡兌現

### 內部 IP vs 外部 IP（跨機器前必懂）

第 14 章開 VM 時你看過兩個 IP，本章開始它們有不同的用途：

| | 內部 IP（10.140.0.x） | 外部 IP（35.x.x.x） |
|---|---|---|
| 誰配的 | VPC（專案的私人網路）自動配 | 共用池借給你的 |
| 誰連得到 | 同一個 VPC 裡的其他 VM | 全世界 |
| 停機後 | **不變** | 回收，下次 start 換新的 |
| 費用 | 內部流量免費 | 對外流量計費 |
| 本章用途 | **VM2 連 VM1 的 RabbitMQ** | 你 SSH 進來、Cloud SQL 授權網路 |

兩個推論：
1. **機器之間講話用內部 IP**——免費、停機不變、而且 VPC 預設規則 `default-allow-internal` 放行內部互連，不用另開防火牆（對照第 14 章：對外開 port 才要寫規則）
2. 外部 IP 是回收再發的共用池——實測時 VM2 拿到的外部 IP，正是 VM1 上次停機被回收的那顆。所以任何寫死外部 IP 的設定，重開機後都要檢查

## 一步一步

> 本章的 IP 每個人都不同。開工前先開好 VM1 並把三個值抄下來，後面指令照抄你自己的：
>
> | 值 | 查法 | 你的值 |
> |----|------|--------|
> | VM1 內部 IP | `gcloud compute instances list`（INTERNAL_IP 欄） | ______ |
> | VM1 外部 IP | 同上（EXTERNAL_IP 欄） | ______ |
> | VM2 外部 IP | 建好 VM2 後同上 | ______ |
> | Cloud SQL IP | Part A 建好後 `gcloud sql instances list` | ______ |

### Part A：建立 Cloud SQL 實例

**A-1 啟用 API**（每個服務第一次用都要）：

```bash
gcloud services enable sqladmin.googleapis.com
```

**A-2 建立實例**：

```bash
gcloud sql instances create stock-mysql \
  --database-version=MYSQL_8_0 \
  --tier=db-f1-micro \
  --region=asia-east1 \
  --root-password=1234
```

參數說明：`stock-mysql` 是實例名稱（自取）；`--database-version` 跟課程一路用的 MySQL 8.0 對齊；`--tier=db-f1-micro` 是最小最便宜的規格（教學夠用）；`--region` 跟 VM 同區（連線最快）；`--root-password` 刻意設 `1234`——**跟 `.env.example` 的預設一致，這是等一下「程式一行都不用改帳密」的關鍵**。

- **建立要等約 10 分鐘**（Google 在幫你準備一台帶備份機制的資料庫伺服器），比開 VM 慢很多是正常的
- 完成後查狀態與 IP：

```bash
gcloud sql instances list
# NAME         DATABASE_VERSION  TIER         PRIMARY_ADDRESS   STATUS
# stock-mysql  MYSQL_8_0         db-f1-micro  35.xxx.xxx.xxx    RUNNABLE
```

`PRIMARY_ADDRESS` 就是 Cloud SQL 的 IP，抄進上面的表。

**A-3 授權網路＋建資料庫**：

Cloud SQL 預設誰都連不進來（跟 VM 防火牆同一個哲學）。把兩台 VM 的**外部 IP** 加進授權清單，並建立課程用的資料庫：

```bash
gcloud sql instances patch stock-mysql \
  --authorized-networks={VM1外部IP}/32,{VM2外部IP}/32

gcloud sql databases create mydb --instance=stock-mysql
```

> 為什麼授權的是「外部 IP」？VM 連 Cloud SQL 的公網位址時，流量是從 VM 的外部 IP 出去的，Cloud SQL 看到的來源就是它。也因此：**VM 重開機換了外部 IP，就要回來重跑一次 patch**——這是本章排錯表的第一名。

### Part B：VM1 收斂成 infra 角色

```bash
gcloud compute ssh stock-crawler-vm --zone=asia-east1-b
cd stock-crawler
sudo docker compose -f docker-compose-all.yml down    # 收掉上一章的全套
sudo docker compose -f docker-compose-local.yml up -d rabbitmq flower
sudo docker ps --format '{{.Names}}\t{{.Status}}'      # 只剩 rabbitmq、flower
```

同一份 repo、同一批 compose 檔——**機器的「角色」由你 up 哪些服務決定**。VM1 從「全能機」變「訊息中樞」，只花兩條指令。

### Part C：開 VM2 並準備 worker

worker 不需要 8GB，開小台的就好：

```bash
gcloud compute instances create stock-crawler-vm2 \
  --zone=asia-east1-b \
  --machine-type=e2-small \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB
```

SSH 進 VM2，重演第 14 章的環境準備（裝 Docker → clone → build worker image）：

```bash
gcloud compute ssh stock-crawler-vm2 --zone=asia-east1-b

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
git clone https://github.com/lu791019/stock-crawler-de-course-materials.git stock-crawler
cd stock-crawler && cp .env.example .env
sudo docker compose -f docker-compose-local.yml build worker_twse worker_tpex
```

### Part D：override 檔——「只改 HOST」的實作

worker 在 compose 檔裡寫的是 `RABBITMQ_HOST=rabbitmq`、`MYSQL_HOST=mysql`——那是「大家都在同一台的容器名」。現在 RabbitMQ 在別台、MySQL 在 Cloud SQL，**用一個 override 檔只蓋掉這兩個值**（在 VM2 的 `~/stock-crawler` 下建立）：

```bash
cat > gcp-worker-override.yml <<'YML'
# worker 上雲的 override：只覆蓋兩個 HOST，其餘沿用 docker-compose-local.yml
services:
  worker_twse:
    environment:
      - RABBITMQ_HOST={VM1內部IP}     # 例：10.140.0.2——同 VPC 用內部 IP
      - MYSQL_HOST={CloudSQL IP}      # 例：35.229.208.220
  worker_tpex:
    environment:
      - RABBITMQ_HOST={VM1內部IP}
      - MYSQL_HOST={CloudSQL IP}
YML
```

用「兩個 -f」啟動——compose 會把兩份檔案**合併**，後面的蓋前面的：

```bash
sudo docker compose -f docker-compose-local.yml -f gcp-worker-override.yml \
  up -d --no-deps worker_twse worker_tpex

sudo docker logs crawler_twse --tail 5
```

預期看到兩行關鍵 log：

```
Connected to amqp://worker:**@{VM1內部IP}:5672//
twse@xxxx ready.
```

worker 跨機器連上了 VM1 的 RabbitMQ。`--no-deps` 是「只起我點名的服務」——不加的話，compose 會照 `depends_on` 把本機的 rabbitmq 也一起帶起來（worker 實際連的是 VM1，本機那顆是白吃記憶體的閒置品）。注意這裡沒有動任何防火牆——內部 IP 互連走 `default-allow-internal`。帳密也一個都沒改：Cloud SQL 的 root/1234 跟 `.env` 預設一致。**整次搬家，程式與設定的改動就是 override 檔裡那兩個 HOST。**

### Part E：跨機器端到端

回 VM1 發任務（producer 在 VM1 上跑，連的是本機的 RabbitMQ）：

```bash
# 在 VM1 上
cd stock-crawler && export PATH="$HOME/.local/bin:$PATH"
uv run crawler/producer_multi_queue.py
# send task_2330 task / send task_00679b task
```

到 VM2 確認 worker 消化：

```bash
# 在 VM2 上
sudo docker logs crawler_twse 2>&1 | grep succeeded | tail -2
```

驗資料真的進了 Cloud SQL（用一次性的 mysql 客戶端容器，用完即丟）：

```bash
# 在 VM2 上
sudo docker run --rm mysql:8.0 \
  mysql -h{CloudSQL IP} -uroot -p1234 -N \
  -e "SELECT COUNT(*) FROM mydb.TaiwanStockPrice;"
```

有筆數（兩支股票各數百筆）就是全通：**任務從 VM1 出發、在 VM2 被執行、資料落在 Cloud SQL**——三個零件在三個地方，協作靠的是第 1 章就認識的訊息佇列。表是 to_sql 自動建的，跟第 5 章在本機第一次寫入時一模一樣。

也可以在 Console 看：≡ → SQL → stock-mysql →「**Cloud SQL 研究室（Cloud SQL Studio）**」，用 root/1234 登入直接下查詢——託管服務自帶管理介面，phpMyAdmin 在雲端段就退役了。

## Swarm 一頁＋K8s 簡介

現在你有兩台機器手動分工，自然的下一個問題：機器更多的時候，誰來管「哪個容器跑在哪台」？這類工具叫**容器編排（orchestration）**：

- **Docker Swarm**：Docker 原生的編排，指令跟 compose 很像、上手最快。但業界大勢已定——**Kubernetes（K8s）成為標準，Swarm 沒落**，知道它存在即可
- **Kubernetes**：解決大規模容器的調度、自癒（容器掛了自動重啟補位）、滾動更新、水平擴縮。發源於 Google 內部系統 Borg 的經驗，GCP 上的託管版就是第 14 章對照表裡的 GKE
- **為什麼本課程不教 K8s**：它是一整門課的量；而且概念上你已經有了梯子——compose 管一台機器的容器，K8s 管一群機器的容器。**先把 compose 練熟，是學 K8s 的正路**。課程規模（兩三台 VM、十來個容器）用 compose＋手動分工完全夠

## 收工：三個東西都要停

```bash
# Cloud SQL 停止（activation-policy 設 NEVER＝停用；之後要用改回 ALWAYS）
gcloud sql instances patch stock-mysql --activation-policy=NEVER

# 兩台 VM 一起停
gcloud compute instances stop stock-crawler-vm stock-crawler-vm2 --zone=asia-east1-b
```

| 資源 | 停了之後 | 還會收的錢 |
|------|---------|-----------|
| VM ×2 | TERMINATED，外部 IP 回收 | 磁碟費（兩顆 20GB 合計每月約 NT$50） |
| Cloud SQL | 停用，資料保留 | 儲存費（少量） |

重新開工的順序：Cloud SQL `--activation-policy=ALWAYS` → VM start → **查新的外部 IP → 重跑 authorized-networks 的 patch**（IP 換了，舊授權就失效——別忘了這步）。

## 檢查：這一章做完的狀態

- [ ] `gcloud sql instances list` 看得到 stock-mysql，STATUS 是 RUNNABLE（收工後 STOPPED）
- [ ] 授權網路含兩台 VM 的外部 IP；mydb 資料庫存在
- [ ] VM1 只跑 rabbitmq＋flower；VM2 只跑兩個 worker
- [ ] VM2 worker log 有 `Connected to amqp://...{VM1內部IP}` 與 `ready`
- [ ] VM1 發任務後，Cloud SQL 的 `mydb.TaiwanStockPrice` 查得到資料
- [ ] 三個資源全部停止

## 想一想

1. 為什麼 VM2 連 RabbitMQ 用內部 IP、連 Cloud SQL 卻用外部 IP？（提示：Cloud SQL 不在你的 VPC 裡——它是 Google 託管專案裡的機器。進階解法叫「私人服務存取」，第 18 章不會用到但值得知道名字）
2. 如果爬蟲量變大，下一台該加的是 VM3 跑更多 worker，還是把 VM1 換大台？這跟第 7 章 `--scale` 的水平擴充是同一題嗎？
3. Cloud SQL 的 root 密碼設 1234 在教學裡方便，正式環境該怎麼辦？（第 18 章 Secret Manager 會回答）

## 練習

1. 把 VM2 的 worker `--scale worker_twse=2`（override 檔加 `container_name` 要先拿掉），看 Flower（VM1 外部 IP:5555）出現兩個 twse worker——跨機器版的第 7 章實驗
2. 故意把 override 檔的 `MYSQL_HOST` 改錯一碼再發任務，觀察 worker log 的錯誤長相，再改回來——練排錯手感
3. 全部停機再全部開機，走一遍「查新 IP → 重 patch 授權網路」的復原流程，直到端到端再次全通

## 排錯

| 症狀 | 原因 | 處理 |
|------|------|------|
| worker 連 Cloud SQL 逾時 | VM 重開後外部 IP 換了，授權網路還是舊 IP | `instances list` 查新 IP → 重跑 `sql instances patch --authorized-networks` |
| worker 連不上 RabbitMQ | override 檔的內部 IP 抄錯，或 VM1 的 rabbitmq 沒起 | 核對 `instances list` 的 INTERNAL_IP；VM1 `docker ps` |
| Access denied for user 'root' | Cloud SQL root 密碼跟 `.env` 對不上 | 建實例時 `--root-password=1234`；或 `gcloud sql users set-password` 重設 |
| 建實例卡很久 | Cloud SQL 建立本來就要約 10 分鐘 | `gcloud sql instances list` 看 STATUS 從 PENDING_CREATE 變 RUNNABLE |
| Unknown database 'mydb' | 忘了建資料庫 | `gcloud sql databases create mydb --instance=stock-mysql` |
| VM2 上莫名多一個 rabbitmq 容器 | up 沒加 `--no-deps`，depends_on 連帶啟動 | `docker rm -f rabbitmq`，之後 up 記得加 `--no-deps` |
| 兩台 VM 內部 IP 一樣？ | 不可能——同 VPC 內部 IP 唯一；你看到的多半是外部 IP 回收再發 | 分清楚兩欄：INTERNAL_IP vs EXTERNAL_IP |

## 本章總結

- 託管 vs 自架是雲的核心交易：用錢買維運。資料庫最有資格先換成託管——有狀態、掛了最痛
- 內部 IP 給機器互連（免費、不變、免防火牆），外部 IP 給對外（會回收、要授權）——分清楚這兩個，跨機器架構就通了
- compose override 檔讓「搬家」縮小成兩個 HOST 的差異——config 中心＋分層設計的紅利
- 跨機器閉環：VM1 發 → VM2 做 → Cloud SQL 存。把零件放到三個地方，協作靠訊息佇列
- Swarm 沒落、K8s 是標準但屬於下一門課——compose 練熟就是 K8s 的地基
- 收工三停：VM ×2＋Cloud SQL；重開要記得「新 IP → 重 patch 授權」

下一章（第 17 章）讓系統對外開門：FastAPI 部署上雲、掛 Load Balancer、學會 image 的 build/push/tag 換版發佈流程。
