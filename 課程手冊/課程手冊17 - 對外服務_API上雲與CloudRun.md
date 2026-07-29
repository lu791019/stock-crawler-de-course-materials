# 課程手冊17 - 對外服務：API 上雲與 Cloud Run

> 本章對應 EP19。前置：第 16 章做完（兩台 VM、Cloud SQL 都在，只是停著）。
>
> 到第 16 章為止，系統只對「自己人」服務：發任務、看 Flower、查資料庫，全都要嘛 SSH 進機器、要嘛靠防火牆放行你一個人的 IP。本章把補充B 寫好的 FastAPI 部署上雲——給全世界一個固定的網址，並學會雲端時代的發佈流程：**build → tag → push → deploy**。部署的目的地不是 VM，而是 **Cloud Run**：把容器交給託管服務跑，這是資料工程師實務上把服務開出去的標準做法。

## 做完這一章你會

1. 說得出對外服務要解的三個問題，以及託管服務怎麼一次回答
2. 用 Artifact Registry 開一個私有 image 倉庫，走通 build → tag → push
3. 一條指令把 API 容器部署上 Cloud Run，拿到固定的 HTTPS 網址
4. 用 ApacheBench 對正式網址壓測，讀懂 Requests per second 與 Failed requests
5. 走一次 v1 → v2 的換版發佈與回滾，理解 revision 版本機制
6. 說得出 Load Balancer 是什麼、為什麼你不用自己架一個

## 先搞懂

### 對外服務要解的三個問題

第 14 章的「想一想」問過：VM 停機後外部 IP 會換，把網址發給別人用是什麼問題？現在正面回答。把服務開給外面的人用，馬上撞到三件事：

| 問題 | 具體長相 |
|------|---------|
| **IP 會換** | VM 每次重開外部 IP 就換，網址發出去隔天就失效 |
| **單台會掛** | 唯一一台 VM 重開機的那幾分鐘，服務就是斷的 |
| **一台扛不住** | 流量成長後單台 CPU 打滿 |

傳統解法是自己架 **Load Balancer（負載平衡器）**：一個固定 IP 站在最前面，把請求分給後面一群機器，配上健康檢查自動繞開掛掉的。GCP 上把這套手動拼出來要七個零件——那是 infra／SRE 工程師的日常，**不是資料工程師的**。

資料工程師的答案是第 14 章學過的取捨：**交給託管服務**。本章用的 **Cloud Run** 是「容器的託管執行環境」（第 14 章對照表裡的「容器 Serverless」）：你給它一顆 image，它還你一個固定的 HTTPS 網址——IP、備援、擴縮、憑證，全部它扛。三個問題一次消失。

### Cloud Run：給它 image，拿回網址

| 你關心的事 | Cloud Run 的回答 |
|-----------|----------------|
| 網址 | 固定的 `https://…run.app`，部署當下就給你，永不換 |
| 機器 | 沒有機器——你看不到 VM，只管 image |
| 流量大 | 自動多開幾個容器分擔（水平擴充，第 7 章 `--scale` 的全自動版） |
| 沒流量 | **自動縮到 0 個容器，這段時間不計費**——對「下課要停機」的你是天大的好消息 |
| 費用 | 按請求處理時間計費＋每月免費額度（課程用量在免費額度內） |

它跟 GCE 是「託管 vs 自架」光譜的兩端：GCE 給你一台空機器什麼都自己來（IaaS）；Cloud Run 只收 image 其他全包。第 16 章資料庫做過同一道選擇題（自架 MySQL vs Cloud SQL），這章輪到「跑服務的機器」。

### Image 倉庫：build 一次，到處跑

第 16 章開 VM2 的時候，worker image 是在 VM2 上重新 build 出來的——clone repo、build、等它跑完。這條路走不遠：每台各 build 一次既慢，又不能保證 build 出來完全一樣；而且 **Cloud Run 根本沒有讓你 build 的機器**——它只收「放在倉庫裡的 image」。

解法是 **image 倉庫（registry）**：build 一次 → push 上去 → 誰要跑誰去 pull。你其實早就用過它——第 3 章 `docker pull rabbitmq` 拉的就是公共倉庫 **Docker Hub**。本章用的 **Artifact Registry** 是 GCP 的私有倉庫：課程的 API image 沒有理由公開，放自己專案裡，用 GCP 的身分機制控管誰能推、誰能拉。

私有倉庫的 image 名字比 `rabbitmq` 長很多，拆開看就懂：

```
asia-east1-docker.pkg.dev / stock-crawler-course / stock-repo / stock-api : v1
└──── 倉庫伺服器（區域）────┘ └───── 專案 ID ─────┘ └─ 倉庫名 ─┘ └─ image ─┘ └tag┘
```

`:v1` 這段叫 **tag**——同一個 image 的版本標籤（第 10 章 `build -t` 的 `-t` 就是它，只是當時沒管版本）。發佈新版本不是覆蓋舊的，而是推一個新 tag（v2）上去；舊版還在倉庫裡，出問題時可以退回去。本章結尾的「換版」就是用這個機制。

### 發佈流程：雲端時代的「上版本」

把這一章的動作串起來，就是業界每天在跑的發佈流程：

```
改程式 → docker build → docker tag（標版本）→ docker push（上倉庫）
                                                      │
                              gcloud run deploy ◀─────┘（Cloud Run 去倉庫拉新版、無縫切換）
```

換版的瞬間服務不中斷——Cloud Run 會先把新版本容器起好、確認能服務了，才把流量切過去。這叫**零停機部署**；自己架 LB 的世界裡要靠「多台＋健康檢查＋輪流換」手動達成，託管世界裡它是內建的。

## 一步一步

> 開工前抄好三個值（Cloud Run 網址做到 Part D 才會有）：
>
> | 值 | 查法 | 你的值 |
> |----|------|--------|
> | VM1 外部 IP | `gcloud compute instances list` | ______ |
> | Cloud SQL IP | `gcloud sql instances list` | ______ |
> | Cloud SQL 連線名稱 | `gcloud sql instances describe stock-mysql --format="value(connectionName)"` | ______ |

### Step 0：喚醒系統（含一件新的事）

本章只需要 VM1（拿它當 build 機）和 Cloud SQL——VM2 讓它繼續睡。復原流程照第 16 章，但這次**趁 VM 還停著**多做一件事：

```bash
# 1. Cloud SQL 喚醒
gcloud sql instances patch stock-mysql --activation-policy=ALWAYS

# 2. 趁停機改 VM 的存取範圍（本章要從 VM 推 image 上倉庫，預設範圍是唯讀）
gcloud compute instances set-service-account stock-crawler-vm \
  --zone=asia-east1-b --scopes=cloud-platform

# 3. 開機
gcloud compute instances start stock-crawler-vm --zone=asia-east1-b

# 4. 查新的外部 IP（換了！抄進上面的表）
gcloud compute instances list

# 5. 用新 IP 重授權 Cloud SQL（VM1 待會要本機測 API 連線用）
gcloud sql instances patch stock-mysql --authorized-networks={VM1外部IP}/32
```

第 2 步解釋一下。VM 的「身分」是它的服務帳戶（Compute Engine 預設服務帳戶，Editor 角色，權限很大），但 VM 上還有一道舊式的閘門叫**存取範圍（scopes）**：就算身分有權限，scopes 沒開的操作一樣做不了。預設 scopes 對 Storage 只有唯讀——推 image 是寫入，會被擋下來吃 401。`--scopes=cloud-platform` 的意思是「scopes 不設限，權限全交給 IAM 角色決定」。**這個設定只能在停機狀態改**——所以放在 Step 0，跟開機一氣呵成；開機後才想到的話，就得再停一次（IP 又要換、授權又要重跑）。

### Part A：開一個 image 倉庫

```bash
gcloud services enable artifactregistry.googleapis.com

gcloud artifacts repositories create stock-repo \
  --repository-format=docker \
  --location=asia-east1
```

`stock-repo` 是倉庫名（自取）；`--repository-format=docker` 指定放 Docker image（Artifact Registry 也能放 Python 套件等其他格式）；`--location` 跟其他資源同區。建好後，倉庫的網址就是「先搞懂」拆過的那段：`asia-east1-docker.pkg.dev/{你的專案ID}/stock-repo`。

### Part B：在 VM1 上 build 與 push

repo 裡已經有一份 `api/Dockerfile`——跟 worker 的 Dockerfile 同一套 uv 基底，差別只在最後一行 CMD：worker 那顆跑 celery，這顆跑 `uvicorn api.main:app --host 0.0.0.0 --port 8000`（`--host 0.0.0.0` 才收得到容器外的請求；不開 `--reload`，這是上線模式）。

SSH 進 VM1 操作。**本章的 docker 指令都不加 sudo**——原因等一下講：

```bash
gcloud compute ssh stock-crawler-vm --zone=asia-east1-b

# 在 VM1 上：拉最新程式
cd stock-crawler && git pull

# 讓 docker 認得 GCP 倉庫的登入方式（VM 自帶 gcloud，用 VM 的服務帳戶身分，免金鑰）
gcloud auth configure-docker asia-east1-docker.pkg.dev --quiet

# build → tag → push（REG 換成你的專案 ID）
REG=asia-east1-docker.pkg.dev/{你的專案ID}/stock-repo
docker build -f api/Dockerfile -t stock-api:v1 .
docker tag stock-api:v1 $REG/stock-api:v1
docker push $REG/stock-api:v1
```

三條指令各做一件事：`build` 在本機做出 image（名字暫時叫 `stock-api:v1`）；`tag` 幫同一顆 image 多掛一個「倉庫格式」的名字——push 是看名字決定推去哪的，名字不帶倉庫網址就推不上去；`push` 逐層上傳。成功的最後一行長這樣：

```
v1: digest: sha256:5865cd7d... size: 856
```

為什麼不加 sudo？`configure-docker` 把「怎麼登入 GCP 倉庫」寫進**你這個使用者**的 `~/.docker/config.json`；`sudo docker` 是用 root 身分跑的，讀的是 root 的設定檔——裡面沒有這段，push 就會 401。第 14 章做過 `usermod -aG docker $USER`，重新 SSH 登入後 docker 不用 sudo 就能跑，兩邊身分一致，這個坑就不存在。

### Part C：先在 VM1 上跑起來看看

部署上雲之前，先在 VM1 本機驗證這顆 image 是好的：

```bash
# 在 VM1 上
docker run -d --name stock-api -p 8000:8000 \
  -e MYSQL_HOST={CloudSQL IP} \
  -e MYSQL_PORT=3306 \
  -e MYSQL_ACCOUNT=root \
  -e MYSQL_PASSWORD=1234 \
  $REG/stock-api:v1
```

四個 `-e` 蓋掉 `crawler/config.py` 的預設值，讓 API 連向 Cloud SQL——跟第 16 章 override 檔同一個哲學，只是這次用 `docker run -e` 傳。資料庫名不用傳：`api/main.py` 裡固定連 `mydb`，正是第 16 章 worker 寫入的那個庫。

**容器起來後要等約 30 秒**（uv 在容器裡準備環境），再驗證：

```bash
# 在 VM1 上
curl http://localhost:8000/
# {"status":"ok","database":"connected"}

curl http://localhost:8000/stocks
# [{"stock_id":"00679B","records":...,...},{"stock_id":"2330",...}]
```

`/` 是健康檢查端點（補充B 寫的）：連資料庫丟一句 `SELECT 1`，通了回 `ok`。回 `degraded` 的話是資料庫連不上——十之八九是 Step 0 第 5 步的授權網路沒做。

確認 image 是好的之後，把測試容器收掉：

```bash
docker rm -f stock-api
```

注意此刻它只活在 VM1 的 8000——外面的人連不進來（防火牆沒開 8000），而且就算開了，IP 會換、單台會掛、一台扛不住三個問題一個都沒解。**該上 Cloud Run 了。**

### Part D：部署上 Cloud Run

回你自己的電腦（或留在 VM1 都行，gcloud 指令兩邊等價）。先啟用 API，然後一條 deploy：

```bash
gcloud services enable run.googleapis.com

gcloud run deploy stock-api \
  --image=asia-east1-docker.pkg.dev/{你的專案ID}/stock-repo/stock-api:v1 \
  --region=asia-east1 \
  --port=8000 \
  --add-cloudsql-instances={Cloud SQL連線名稱} \
  --set-env-vars="MYSQL_UNIX_SOCKET=/cloudsql/{Cloud SQL連線名稱},MYSQL_ACCOUNT=root,MYSQL_PASSWORD=1234" \
  --allow-unauthenticated \
  --memory=1Gi
```

參數逐一看：

- `--image`：跑倉庫裡的哪顆 image——Cloud Run 自己去 pull，這就是 Part B push 的意義
- `--port=8000`：容器裡 uvicorn 聽的 port，Cloud Run 把對外流量轉進來
- `--add-cloudsql-instances`＋`MYSQL_UNIX_SOCKET`：**這兩個是一組的**——前者幫你在容器裡接好一條到 Cloud SQL 的專線，後者告訴程式「改走這條專線」。走專線的好處：**授權網路完全不用碰**（Cloud Run 的容器沒有固定 IP 可以授權，Google 直接從內部把線接好）。`api/main.py` 裡有一小段切換邏輯：有設 `MYSQL_UNIX_SOCKET` 就走專線、沒設就照舊走 `MYSQL_HOST`——所以本機和 VM 的用法完全不受影響
- `--allow-unauthenticated`：允許匿名存取——這是「開放 API」，誰都能打；不加的話要帶 Google 身分憑證才能呼叫
- `--memory=1Gi`：容器記憶體上限（預設 512Mi 對 pandas 偏緊）

跑完的最後兩行是這一章的重點輸出：

```
Service [stock-api] revision [stock-api-00001-kfp] has been deployed and is serving 100 percent of traffic.
Service URL: https://stock-api-{一串數字}.asia-east1.run.app
```

**Service URL 就是這個服務對外的網址**：固定、HTTPS、全球可連。從你自己的電腦（或手機）驗證：

```bash
curl https://stock-api-{一串數字}.asia-east1.run.app/
# {"status":"ok","database":"connected"}

curl https://stock-api-{一串數字}.asia-east1.run.app/stocks/2330/latest
# {"date":"...","stock_id":"2330","close":...,...}
```

這個網址可以給任何人使用：不需要 SSH、不需要防火牆授權，VM 關機也不影響（它執行的是倉庫裡的 image，跟 VM 已經無關）。**系統第一次有了對外可用的網址**，而過程中你沒有管理任何一台機器。

另外留意輸出裡的 `revision [stock-api-00001-kfp]`——**revision 是這次部署的版本快照**（image＋環境變數＋設定的組合）。每 deploy 一次就多一個 revision，舊的留著——Part F 的換版與回滾靠的就是它。

### Part E：壓力測試

門開了，扛得住多少人？用 ApacheBench 壓一下（macOS 內建，路徑 `/usr/sbin/ab`；Windows 可用 WSL 安裝 `apache2-utils`）：

```bash
ab -n 200 -c 10 https://stock-api-{一串數字}.asia-east1.run.app/stocks
```

`-n 200` 共發 200 個請求、`-c 10` 同時 10 個併發——模擬 10 個人同時狂打。輸出重點三行：

```
Requests per second:    88.86 [#/sec] (mean)
Time per request:       112.536 [ms] (mean)
Failed requests:        0
```

- **Failed requests 必須是 0**——服務在併發下穩定的證據
- **Requests per second** 是吞吐量：每秒能服務幾個請求。數字本身跟網路與當下狀態有關，重要的是它給了你一條基準線——之後任何改動都能量出變快還是變慢
- **Time per request** 是使用者體感的延遲（HTTPS＋跨網路，比第 16 章內網數字大是正常的）

如果壓測規模再大十倍，Cloud Run 會自動多開容器分擔——你什麼都不用做。這就是「一台扛不住」問題的託管式答案。

### Part F：發佈 v2——換版與回滾

模擬一次真實的發佈：程式改好了（這裡不真的改程式，直接把 v1 重新標成 v2——流程一模一樣），推新版、切換：

```bash
# 在 VM1 上：標 v2、push
docker tag stock-api:v1 $REG/stock-api:v2
docker push $REG/stock-api:v2

# 部署 v2（其他設定沿用上次的，只要給新 image）
gcloud run deploy stock-api \
  --image=asia-east1-docker.pkg.dev/{你的專案ID}/stock-repo/stock-api:v2 \
  --region=asia-east1
```

deploy 進行的期間，從另一個終端機每兩秒 curl 一次網址——**全程 200，沒有任何一次失敗**。Cloud Run 先把 v2 的容器起好、確認健康，才把流量從 v1 切過去：零停機換版，內建。

換完看版本清單：

```bash
gcloud run revisions list --service=stock-api --region=asia-east1
# REVISION             ACTIVE
# stock-api-00002-w8d  yes      ← v2，正在服務
# stock-api-00001-kfp           ← v1，留著
```

v2 上線後發現有 bug？**一條指令退回 v1**，不用重新 build、不用重新 push：

```bash
gcloud run services update-traffic stock-api --region=asia-east1 \
  --to-revisions=stock-api-00001-kfp=100

# 確認退回去了、服務照常
curl -s -o /dev/null -w "%{http_code}\n" https://stock-api-{一串數字}.asia-east1.run.app/stocks
# 200

# 玩完切回最新版
gcloud run services update-traffic stock-api --region=asia-east1 --to-latest
```

倉庫裡的 image 有版本（v1/v2），Cloud Run 的部署也有版本（revision），兩層都能退回。`--to-revisions` 也可以寫 `00001=50,00002=50` 讓兩個版本各分一半流量，這種做法叫**金絲雀發佈**：先讓新版承接一小部分流量，確認沒問題再全部切換。

### 那 Load Balancer 呢？

一頁把它講完。傳統上「固定入口＋分流＋健康檢查」要自己拼一台 Load Balancer：GCP 上是 instance group（機器名冊）、health check（巡邏）、backend service（調度）、url map（路由）、proxy＋forwarding rule（入口）等七個零件接成的管線——這是 infra／SRE 工程師的日常工具。

你不用自己拼的原因很直接：**Cloud Run 的網址背後，Google 已經幫你放了一台**——每個請求先落在 Google 的邊緣節點，再被分給你的容器（可能不只一個），健康檢查與擴縮全自動。這正是第 14 章那句「越往託管走、要管的越少」的具體長相。什麼時候才需要自己架？服務跑在自管的 VM／K8s 上、要做複雜的路由規則（不同路徑導不同後端）、或要掛自己的網域與憑證策略時——那已經是另一個職位的工作範圍，你知道找誰、講得出需求，就夠了。

## 收工：只停要錢的

```bash
gcloud sql instances patch stock-mysql --activation-policy=NEVER
gcloud compute instances stop stock-crawler-vm --zone=asia-east1-b
```

**Cloud Run 不用停**——沒有流量它自動縮到 0 個容器，不產生任何費用；服務與網址保留，下次有請求進來它再醒過來（第一個請求會慢幾秒，這叫**冷啟動**，是縮到零的代價）。Artifact Registry 的 image 留著（儲存費極低）。

## 檢查：這一章做完的狀態

- [ ] `gcloud artifacts repositories list` 看得到 stock-repo；倉庫裡有 stock-api 的 v1 與 v2
- [ ] VM1 能用倉庫路徑跑起容器，`curl localhost:8000/` 回 `"status":"ok"`
- [ ] `gcloud run services list` 看得到 stock-api；從自己電腦 curl Service URL 通
- [ ] `ab` 壓測 Failed requests = 0
- [ ] 完成 v1 → v2 的換版與回滾，`revisions list` 看得到兩個版本
- [ ] 收工：VM 與 Cloud SQL 已停（Cloud Run 留著，縮零不計費）

## 想一想

1. `--add-cloudsql-instances` 接的「專線」技術名稱叫 **unix socket**：程式連的不是 `IP:port` 而是容器裡的一個檔案路徑，Google 把這個路徑接到你的資料庫。為什麼 Cloud Run 不能像第 16 章那樣用「授權網路」連 Cloud SQL？（提示：授權網路要填來源 IP，Cloud Run 的容器有固定 IP 嗎？）
2. 縮到零的代價是冷啟動——第一個請求要等容器醒來。什麼樣的服務不能接受冷啟動？Cloud Run 的解法是 `--min-instances=1`（至少留一個容器醒著），代價是什麼？
3. 健康檢查端點 `/` 在資料庫掛掉時回 `degraded` 但 HTTP 狀態碼還是 200——對「自動判斷服務好壞」的系統來說，這是好設計嗎？該怎麼改？（提示：讓檢查失敗的方式是回 5xx）

## 練習

1. 實際改一次程式：在 `api/main.py` 的 `/` 回應裡加一個 `"version": "v3"` 欄位，完整執行 build → tag v3 → push → deploy，用 curl 驗證新欄位上線且過程中服務不中斷
2. 用 `--to-revisions={v3的revision}=50,{v2的revision}=50` 做一次金絲雀發佈，連續 curl `/` 十次，觀察 version 欄位兩種值交替出現
3. 把 `ab` 的 `-c` 從 10 拉到 50，比較 Requests per second 與 Time per request 的變化——吞吐量和延遲的取捨

## 排錯

| 症狀 | 原因 | 處理 |
|------|------|------|
| `docker push` 回 401 unauthenticated | ①VM 的 scopes 還是預設唯讀 ②用了 `sudo docker`（讀不到你的登入設定） | ①停機 → `set-service-account --scopes=cloud-platform` → 開機（IP 換了記得重授權）②不加 sudo 重跑；`groups` 確認在 docker 群組裡 |
| `docker build` 報 no space left on device | 20GB 磁碟被舊 image／build cache 塞滿 | `docker system prune -af` 清掉沒在用的（注意：它會把沒在跑的 image 全清掉，第 18 章要用的 stock-airflow 得重 build） |
| VM1 測試容器 curl 回 000 | uv 還在容器裡準備環境 | 等 30 秒；`docker logs stock-api` 看到 `Application startup complete` 就緒 |
| VM1 測試 `/` 回 `degraded` | 授權網路是舊 IP，或 Cloud SQL 沒醒 | 重跑 Step 0 的第 4、5 步 |
| `run deploy` 說 image 拉不到 | image 路徑打錯，或 push 根本沒成功 | `gcloud artifacts docker images list $REG` 確認倉庫裡有它 |
| Cloud Run 網址回 `degraded` | `--add-cloudsql-instances` 或 `MYSQL_UNIX_SOCKET` 其中一個沒給／打錯（兩個是一組的） | 兩個參數裡的連線名稱要一模一樣；改完重新 deploy |
| Cloud Run 網址回 403 | 沒給 `--allow-unauthenticated` | 重新 deploy 加上它 |
| 網址通但第一次特別慢 | 冷啟動——容器從 0 醒來 | 正常現象；在意的話 `--min-instances=1`（會開始計費） |

## 本章總結

- 對外服務的三個問題——IP 會換、單台會掛、一台扛不住——資料工程師的答案是交給託管服務，不是自己架 LB
- Image 倉庫讓「build 一次、到處跑」成立；私有倉庫的名字＝伺服器／專案／倉庫／image／tag 五段
- Cloud Run：給它 image、拿回固定 HTTPS 網址；自動擴縮、閒置縮零不計費、冷啟動是縮零的代價
- 連 Cloud SQL 走 `--add-cloudsql-instances` 的專線，授權網路不用碰——託管環境連託管資料庫的標準姿勢
- 發佈流程 build → tag → push → deploy；revision 讓換版零停機、回滾一條指令
- LB 沒有消失，只是 Google 幫你管了——需要自己拼七件套的場景屬於 infra／SRE，你知道找誰就夠

下一章（第 18 章）是最後一章：用 Secret Manager 管理密碼、把爬蟲到 BigQuery 的每日管線用排程串起來、認識 Composer 與 CI/CD——把課程的系統整理成可以交接給其他人維護的狀態。
