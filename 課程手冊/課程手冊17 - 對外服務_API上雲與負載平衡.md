# 課程手冊17 - 對外服務：API 上雲與負載平衡

> 本章對應 EP19。前置：第 16 章做完（兩台 VM、Cloud SQL 都在，只是停著）。
>
> 到第 16 章為止，系統只對「自己人」服務：發任務、看 Flower、查資料庫，全都要嘛 SSH 進機器、要嘛靠防火牆放行你一個人的 IP。本章把補充B 寫好的 FastAPI 部署上雲、掛上 **Load Balancer**——給全世界一個固定的入口，並學會雲端時代的發佈流程：**build → tag → push → 換版**。

## 做完這一章你會

1. 說得出對外服務要解的三個問題，以及 Load Balancer 怎麼一次回答
2. 用 Artifact Registry 開一個私有 image 倉庫，走通 build → tag → push
3. 在兩台 VM 上用「同一顆 image」跑起 API 容器——體會 registry 的價值
4. 逐件建出 HTTP Load Balancer 的七個零件，說得出每件的角色
5. 用 ApacheBench 對 LB 壓測，讀懂 Requests per second 與 Failed requests
6. 走一次 v1 → v2 的換版發佈，理解「輪流換版」就是零停機部署的雛形

## 先搞懂

### 對外服務要解的三個問題

第 14 章的「想一想」問過：VM 停機後外部 IP 會換，把網址發給別人用是什麼問題？現在正面回答。把服務開給外面的人用，馬上撞到三件事：

| 問題 | 具體長相 | 解法 |
|------|---------|------|
| **IP 會換** | VM 每次重開外部 IP 就換，網址發出去隔天就失效 | 給一個**固定的入口 IP**，後面機器怎麼換都不影響 |
| **單台會掛** | 唯一一台 VM 重開機的那幾分鐘，服務就是斷的 | 兩台以上互為備援，**健康檢查**自動繞開掛掉的 |
| **一台扛不住** | 流量成長後單台 CPU 打滿 | 流量**分散**到多台（第 7 章 `--scale` 的對外版） |

三個解法合起來就是 **Load Balancer（負載平衡器）**：一個不變的 IP 站在最前面，把請求分給後面一群機器，並且持續巡邏、只把流量給活著的機器。

### Image 倉庫：build 一次，到處跑

第 16 章開 VM2 的時候，worker image 是在 VM2 上「重新 build」出來的——clone repo、build、等它跑完。機器一多這條路就不通：每台各 build 一次既慢，又不能保證每台 build 出來完全一樣。

解法是 **image 倉庫（registry）**：找一台大家都連得到的倉庫，**build 一次 → push 上去 → 每台 pull 下來**。你其實早就用過它——第 3 章 `docker pull rabbitmq` 拉的就是公共倉庫 **Docker Hub** 上的 image。本章用的 **Artifact Registry** 是 GCP 的私有倉庫：課程的 API image 沒有理由公開，放自己專案裡的倉庫，用 GCP 的身分機制控管誰能推、誰能拉。

私有倉庫的 image 名字比 `rabbitmq` 長很多，拆開看就懂：

```
asia-east1-docker.pkg.dev / stock-crawler-course / stock-repo / stock-api : v1
└──── 倉庫伺服器（區域）────┘ └───── 專案 ID ─────┘ └─ 倉庫名 ─┘ └─ image ─┘ └tag┘
```

`:v1` 這段叫 **tag**——同一個 image 的版本標籤。發佈新版本不是覆蓋舊的，而是推一個新 tag（v2）上去；舊版還在倉庫裡，出事隨時退回去。這是本章結尾「換版」的伏筆。

### Load Balancer 的七個零件

GCP 的 HTTP Load Balancer 不是「一個東西」，而是七個零件接成的一條管線。請求由左往右流：

```
使用者
  │
  ▼
⑦ forwarding rule ──「入口」：對外的固定 IP＋port 80
  │
  ▼
⑥ target proxy ────「接待」：終結 HTTP 連線，交給路由
  │
  ▼
⑤ url map ────────「路由」：哪個路徑給哪組後端（本章全部給同一組）
  │
  ▼
④ backend service ─「調度」：把請求分給健康的機器
  │        ▲
  │        │ 只送給「活著」的
  ▼        │
① instance group ──「名冊」：哪幾台 VM 是後端（VM1＋VM2）
  ▲
  │ 每 5 秒打一次 /
② health check ────「巡邏」：定期打每台的 8000，判定生死
③ 防火牆規則 ──────「放行」：讓 Google 的巡邏流量進得了 VM
```

為什麼拆這麼細？因為每一件都可以獨立替換：換路由規則不用動後端、加機器只改名冊、健康檢查標準自己訂。一步一步做的時候，照著這張圖對號入座，七條指令就不是咒語而是拼裝說明書。

計費上只有一件要記：**⑦ forwarding rule 建立起就開始按時計費**。①②③ 是免費的設定物件——這決定了本章收工時「哪些要刪、哪些可以留」。

### 發佈流程：雲端時代的「上版本」

把這一章的動作串起來，就是業界每天在跑的發佈流程：

```
改程式 → docker build → docker tag（標版本）→ docker push（上倉庫）
                                                      │
                          每台機器： docker pull ← ────┘ → 停舊容器、起新容器
```

多台機器**輪流**換版——換 VM1 時 VM2 還在線上服務，LB 把流量導給活著的那台——服務全程不斷線。這就是**零停機部署**的雛形；Kubernetes 的 rolling update 是同一個思想的全自動版。

## 一步一步

> 本章的 IP 每個人都不同，開工前抄好三個值（LB 的 IP 做到 Part D 才會有）：
>
> | 值 | 查法 | 你的值 |
> |----|------|--------|
> | VM1 外部 IP | `gcloud compute instances list` | ______ |
> | VM2 外部 IP | 同上 | ______ |
> | Cloud SQL IP | `gcloud sql instances list` | ______ |
> | LB IP | Part D 建完 forwarding rule 後查 | ______ |

### Step 0：喚醒系統（含兩件新的事）

第 16 章收工時三個資源都停了。復原流程跟那章結尾寫的一樣，但這次**趁 VM 還停著**多做一件事：

```bash
# 1. Cloud SQL 喚醒
gcloud sql instances patch stock-mysql --activation-policy=ALWAYS

# 2. 趁停機改 VM 的存取範圍（本章要從 VM 推 image 上倉庫，預設範圍是唯讀）
gcloud compute instances set-service-account stock-crawler-vm \
  --zone=asia-east1-b --scopes=cloud-platform
gcloud compute instances set-service-account stock-crawler-vm2 \
  --zone=asia-east1-b --scopes=cloud-platform

# 3. 兩台一起開機
gcloud compute instances start stock-crawler-vm stock-crawler-vm2 --zone=asia-east1-b

# 4. 查新的外部 IP（換了！抄進上面的表）
gcloud compute instances list

# 5. 用新 IP 重授權 Cloud SQL（第 16 章排錯表第一名，這章照樣要做）
gcloud sql instances patch stock-mysql \
  --authorized-networks={VM1外部IP}/32,{VM2外部IP}/32

# 6. 幫 VM2 補上網路標籤（第 16 章開它時沒掛；等一下健康檢查的防火牆靠標籤放行）
gcloud compute instances add-tags stock-crawler-vm2 --tags=stock-web --zone=asia-east1-b
```

第 2 步解釋一下。VM 的「身分」是它的服務帳戶（Compute Engine 預設服務帳戶，Editor 角色，權限很大），但 VM 上還有一道舊式的閘門叫**存取範圍（scopes）**：就算身分有權限，scopes 沒開的操作一樣做不了。預設 scopes 對 Storage 只有唯讀——推 image 是寫入，會被擋下來吃 401。`--scopes=cloud-platform` 的意思是「scopes 不設限，權限全交給 IAM 角色決定」。**這個設定只能在停機狀態改**——所以放在 Step 0，跟開機一氣呵成；開機後才想到的話，就得再停一次（IP 又要換、授權又要重跑）。

### Part A：開一個 image 倉庫

```bash
gcloud services enable artifactregistry.googleapis.com

gcloud artifacts repositories create stock-repo \
  --repository-format=docker \
  --location=asia-east1
```

`stock-repo` 是倉庫名（自取）；`--repository-format=docker` 指定放 Docker image（Artifact Registry 也能放 Python 套件等其他格式）；`--location` 跟 VM 同區。建好後，倉庫的網址就是「先搞懂」拆過的那段：`asia-east1-docker.pkg.dev/{你的專案ID}/stock-repo`。

### Part B：在 VM1 上 build 與 push

repo 裡已經有一份 `api/Dockerfile`——跟 worker 的 Dockerfile 同一套 uv 基底，差別只在最後一行 CMD：worker 那顆跑 celery，這顆跑 `uvicorn api.main:app --host 0.0.0.0 --port 8000`（`--host 0.0.0.0` 才收得到容器外的請求；不開 `--reload`，這是上線模式）。

SSH 進 VM1 操作。**本章的 docker 指令都不加 sudo**——原因等一下講：

```bash
gcloud compute ssh stock-crawler-vm --zone=asia-east1-b

# 在 VM1 上：拉最新程式（api/Dockerfile 在裡面）
cd stock-crawler && git pull

# 讓 docker 認得 GCP 倉庫的登入方式（VM 自帶 gcloud，用 VM 的服務帳戶身分，免金鑰）
gcloud auth configure-docker asia-east1-docker.pkg.dev --quiet

# build → tag → push（REG 換成你的專案 ID）
REG=asia-east1-docker.pkg.dev/{你的專案ID}/stock-repo
docker build -f api/Dockerfile -t stock-api:v1 .
docker tag stock-api:v1 $REG/stock-api:v1
docker push $REG/stock-api:v1
```

三條指令各做一件事：`build` 在本機做出 image（名字暫時叫 `stock-api:v1`）；`tag` 幫同一顆 image 多掛一個「倉庫格式」的名字——push 是看名字決定推去哪的，名字不帶倉庫網址就推不上去；`push` 逐層上傳。成功的輸出長這樣（每層一行 Pushed，最後一行是版本摘要）：

```
v1: digest: sha256:xxxx... size: 1786
```

為什麼不加 sudo？`configure-docker` 把「怎麼登入 GCP 倉庫」寫進**你這個使用者**的 `~/.docker/config.json`；`sudo docker` 是用 root 身分跑的，讀的是 root 的設定檔——裡面沒有這段，push 就會 401。第 14 章做過 `usermod -aG docker $USER`，重新 SSH 登入後 docker 不用 sudo 就能跑，兩邊身分一致，這個坑就不存在。

### Part C：兩台 VM 跑起同一顆 image

先在 VM1 上把 API 跑起來（image 剛 build 完就在本機，直接用倉庫名字跑）：

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
# [{"stock_id":"00679B","records":...,"first_date":...,"last_date":...},
#  {"stock_id":"2330",...}]
```

`/` 是健康檢查端點：連 Cloud SQL 丟一句 `SELECT 1`，通了回 `ok`。回 `degraded` 的話是資料庫連不上——十之八九是 Step 0 第 5 步的授權網路沒做（排錯表見文末）。

再到 VM2 做一次一模一樣的 `docker run`（另開一個終端機 SSH 進去；`REG` 要重新 export）。差別在 VM2 **從來沒 build 過這顆 image**——`docker run` 發現本機沒有，自動去倉庫 pull：

```bash
gcloud compute ssh stock-crawler-vm2 --zone=asia-east1-b

# 在 VM2 上
REG=asia-east1-docker.pkg.dev/{你的專案ID}/stock-repo
docker run -d --name stock-api -p 8000:8000 \
  -e MYSQL_HOST={CloudSQL IP} \
  -e MYSQL_PORT=3306 \
  -e MYSQL_ACCOUNT=root \
  -e MYSQL_PASSWORD=1234 \
  $REG/stock-api:v1

# 等 30 秒
curl http://localhost:8000/stocks
```

對比第 16 章：VM2 當時要 clone＋build 十來分鐘，這次一條 `docker run` 拉下來就跑。**build 一次、到處跑**——這就是倉庫存在的理由。

注意此刻從你自己的電腦 curl `http://{VM外部IP}:8000` 是**不通的**——防火牆沒開 8000 給公網，這是故意的：對外的門只留一個，就是接下來的 LB。

### Part D：拼裝 Load Balancer

照「先搞懂」的圖，由後往前拼。先建後端三件（名冊、巡邏、放行）：

```bash
# ① 名冊：建一個 instance group，把兩台 VM 加進去
gcloud compute instance-groups unmanaged create api-group --zone=asia-east1-b
gcloud compute instance-groups unmanaged add-instances api-group --zone=asia-east1-b \
  --instances=stock-crawler-vm,stock-crawler-vm2

# 幫 group 的 8000 port 取名（等一下 backend service 用名字對接）
gcloud compute instance-groups unmanaged set-named-ports api-group --zone=asia-east1-b \
  --named-ports=http8000:8000

# ② 巡邏：每 5 秒打一次每台機器的 8000 的 /，通＝健康
gcloud compute health-checks create http api-hc --port=8000 --request-path=/

# ③ 放行：讓 Google 的健康檢查流量進得了 VM 的 8000
#（130.211.0.0/22 與 35.191.0.0/16 是 Google 健康檢查的固定來源網段，寫法全球通用）
gcloud compute firewall-rules create allow-lb-hc \
  --allow=tcp:8000 \
  --source-ranges=130.211.0.0/22,35.191.0.0/16 \
  --target-tags=stock-web
```

`unmanaged`（非代管）的意思是名冊由你手動維護——加減機器自己來；代管版（managed）能按 CPU 自動增減機器，屬於進階題。防火牆規則綁的還是 `stock-web` 標籤——Step 0 第 6 步幫 VM2 補標籤就是為了這裡。

再建前端四件（調度、路由、接待、入口）：

```bash
# ④ 調度：backend service，掛上名冊與巡邏
gcloud compute backend-services create api-backend \
  --protocol=HTTP --port-name=http8000 --health-checks=api-hc --global
gcloud compute backend-services add-backend api-backend \
  --instance-group=api-group --instance-group-zone=asia-east1-b --global

# ⑤ 路由：所有路徑都給 api-backend
gcloud compute url-maps create api-map --default-service=api-backend

# ⑥ 接待：HTTP proxy，掛上路由
gcloud compute target-http-proxies create api-proxy --url-map=api-map

# ⑦ 入口：對外 IP＋port 80（計費從這件開始）
gcloud compute forwarding-rules create api-fr --global \
  --target-http-proxy=api-proxy --ports=80
```

建完先確認兩件事。第一，巡邏結果——兩台都要 HEALTHY：

```bash
gcloud compute backend-services get-health api-backend --global
# 兩台的 healthState 都是 HEALTHY
```

第二，入口 IP（抄進開工表）：

```bash
gcloud compute forwarding-rules describe api-fr --global --format="value(IPAddress)"
```

然後從**你自己的電腦**打這個 IP——注意是 port 80，不用加 :8000（LB 在 80 收、轉給後端的 8000）：

```bash
curl http://{LB IP}/stocks
curl http://{LB IP}/stocks/2330/latest
# {"date":"...","stock_id":"2330","close":...,"spread":...,"Trading_Volume":...}
```

**LB 建好後要 2-3 分鐘才通**——它是全球性的設施，設定要傳遍 Google 的邊緣節點。前幾次 `connection reset` 是正常的，等一下再試；只要 get-health 是 HEALTHY，通是遲早的事。通了之後，這個網址可以貼給任何人——不用 SSH、不用防火牆授權、VM 重開換 IP 也不影響。**系統第一次有了對外的門牌。**

### Part E：壓力測試

門開了，扛得住多少人？用 ApacheBench 壓一下（macOS 內建，路徑 `/usr/sbin/ab`；Windows 可用 WSL 安裝 `apache2-utils`）：

```bash
ab -n 200 -c 10 http://{LB IP}/stocks
```

`-n 200` 共發 200 個請求、`-c 10` 同時 10 個併發——模擬 10 個人同時狂打。輸出重點三行：

```
Requests per second:    187.35 [#/sec] (mean)
Time per request:       53.375 [ms] (mean)
Failed requests:        0
```

- **Failed requests 必須是 0**——這是「兩台後端都健康、LB 分流正常」的證據
- **Requests per second** 是吞吐量：每秒能服務幾個請求。數字本身跟網路與機器規格有關，重要的是它給了你一條基準線——之後任何改動（加機器、改程式）都能量出變快還是變慢
- **Time per request** 是使用者體感的延遲

順帶一提：兩台後端各自分到約一半的請求。想親眼看分流，兩台各跑 `docker logs stock-api --tail 20`，兩邊都有請求紀錄。

### Part F：發佈 v2——第一次換版

模擬一次真實的發佈：程式改好了（這裡不真的改程式，直接把 v1 重新標成 v2——流程一模一樣），推新版、逐台換。

```bash
# 在 VM1 上：標 v2、push
docker tag stock-api:v1 $REG/stock-api:v2
docker push $REG/stock-api:v2

# 換版：停掉舊容器、用 v2 起新的
docker rm -f stock-api
docker run -d --name stock-api -p 8000:8000 \
  -e MYSQL_HOST={CloudSQL IP} \
  -e MYSQL_PORT=3306 \
  -e MYSQL_ACCOUNT=root \
  -e MYSQL_PASSWORD=1234 \
  $REG/stock-api:v2
```

VM1 換版的那 30 秒裡，從你的電腦再 curl 一次 LB：

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://{LB IP}/stocks
# 200
```

**照樣通**——健康檢查發現 VM1 的 8000 沒回應，流量全導給還在跑 v1 的 VM2；VM1 的 v2 起來、巡邏連續過關後，又自動回到分流。接著用同樣四條指令把 VM2 也換成 v2，整個過程服務不中斷。這就是零停機部署：**多台＋健康檢查＋輪流換**，三個你這章都有了。

倉庫裡現在躺著 v1 和 v2 兩個版本（`gcloud artifacts docker images list $REG` 看得到）。哪天 v2 有 bug，`docker run ...v1` 就退回去了——版本化的 image 就是你的後悔藥。

## 收工：先拆計費的，再停機器

LB 七件裡只有前端四件計費（forwarding rule 是大宗，backend service 隨流量），**由前往後拆**——跟建立順序相反，因為每件被後一件引用著，反著拆才拆得動：

```bash
gcloud compute forwarding-rules delete api-fr --global --quiet
gcloud compute target-http-proxies delete api-proxy --quiet
gcloud compute url-maps delete api-map --quiet
gcloud compute backend-services delete api-backend --global --quiet
```

instance group、health check、防火牆規則是免費的設定物件，**留著**——下次要開門，從 Part D 的第 ④ 件接著拼就好。然後照第 16 章的三停：

```bash
gcloud sql instances patch stock-mysql --activation-policy=NEVER
gcloud compute instances stop stock-crawler-vm stock-crawler-vm2 --zone=asia-east1-b
```

Artifact Registry 的 image 留著（儲存費很低，v1/v2 合計不到 1GB）；要清也可以 `gcloud artifacts docker images delete`。

## 檢查：這一章做完的狀態

- [ ] `gcloud artifacts repositories list` 看得到 stock-repo；倉庫裡有 stock-api 的 v1 與 v2
- [ ] 兩台 VM 都能用倉庫路徑跑起 stock-api 容器，`curl localhost:8000/` 回 `"status":"ok"`
- [ ] `get-health` 兩台都 HEALTHY（LB 在的時候）
- [ ] 從自己電腦 `curl http://{LB IP}/stocks` 通，`ab` 壓測 Failed requests = 0
- [ ] 走完一次 v1 → v2 換版，換版過程中 LB 持續回 200
- [ ] 收工：forwarding rule／proxy／url map／backend service 已刪，VM 與 Cloud SQL 已停

## 想一想

1. 健康檢查打的 `/` 端點，在資料庫掛掉時回 `degraded` 但 HTTP 狀態碼還是 200——LB 會判定這台「健康」，繼續把流量送給一台查不到資料的 API。這是好設計嗎？該怎麼改？（提示：讓健康檢查失敗的方式是回 4xx／5xx）
2. 換版期間 v1 和 v2 同時在線，不同使用者可能拿到不同版本的回應。什麼樣的改動可以這樣發佈、什麼樣的不行？（提示：如果 v2 改了回傳欄位的名字呢？）
3. 為什麼不乾脆把 8000 開放給全世界、每台 VM 各自見客，還要多一層 LB？三個問題各自會發生什麼事？

## 練習

1. 把 VM2 的 stock-api 容器 `docker rm -f` 掉，觀察 `get-health` 變 UNHEALTHY、curl LB 依然通（流量全給 VM1）；再把容器跑回來，看它自動回到 HEALTHY——健康檢查的自癒閉環
2. 把 `ab` 的 `-c` 從 10 拉到 50，比較 Requests per second 與 Time per request 的變化——吞吐量和延遲的取捨
3. 真的改一次程式：在 `api/main.py` 的 `/` 回應裡加一個 `"version": "v3"` 欄位，走完整的 build → tag v3 → push → 兩台輪流換版，用 `curl http://{LB IP}/` 驗證新欄位上線且全程不斷線

## 排錯

| 症狀 | 原因 | 處理 |
|------|------|------|
| `docker push` 回 401 unauthenticated | ①VM 的 scopes 還是預設唯讀 ②用了 `sudo docker`（讀不到你的登入設定） | ①停機 → `set-service-account --scopes=cloud-platform` → 開機（IP 換了記得重授權 Cloud SQL）②不加 sudo 重跑；`groups` 確認在 docker 群組裡，不在就重做 usermod＋重新 SSH |
| `docker build` 報 no space left on device | 20GB 磁碟被舊 image／build cache 塞滿 | `docker system prune -af` 清掉沒在用的（實際可清出十幾 GB），再 build |
| 容器剛起來 curl 回 000／connection refused | uv 還在容器裡準備環境 | 等 30 秒再試；`docker logs stock-api` 看到 uvicorn 的 `Application startup complete` 就緒 |
| `/` 回 `"status":"degraded"` | API 連不上 Cloud SQL：授權網路是舊 IP，或 Cloud SQL 沒醒 | 重跑 Step 0 的第 4、5 步；`gcloud sql instances list` 確認 RUNNABLE |
| get-health 顯示 UNHEALTHY | ①allow-lb-hc 防火牆沒建 ②VM 沒掛 stock-web 標籤 ③該台的 api 容器沒在跑 | 照 ①→③ 檢查：`firewall-rules list`、`instances describe --format="value(tags.items)"`、VM 上 `docker ps` |
| LB IP 前幾次 curl 被 connection reset | LB 設定還在向全球邊緣節點收斂 | 等 2-3 分鐘；只要 get-health 是 HEALTHY 就只是時間問題 |
| 收工後帳單還在走 | forwarding rule 沒刪乾淨 | `gcloud compute forwarding-rules list` 確認為空；四件由前往後拆 |

## 本章總結

- 對外服務的三個問題——IP 會換、單台會掛、一台扛不住——LB 用固定入口＋健康檢查＋分流一次回答
- Image 倉庫讓「build 一次、到處跑」成立；私有倉庫的名字＝伺服器／專案／倉庫／image／tag 五段
- LB 是七個零件的管線：名冊、巡邏、放行、調度、路由、接待、入口——只有入口（forwarding rule）是計費大宗
- VM 推 image 要過兩道門：IAM 角色（身分）＋存取範圍 scopes（舊式閘門，停機才能改）；docker 與 gcloud 要用同一個使用者身分
- 發佈流程 build → tag → push → 輪流換版；多台＋健康檢查＋輪流換＝零停機部署的雛形，K8s 的 rolling update 是它的全自動版
- 收工由前往後拆計費四件，免費三件留著下次重建省工

下一章（第 18 章）收官：帳密不再寫 1234（Secret Manager）、爬蟲到 BigQuery 的每日管線串起來、看一眼 Composer 與 CI/CD——把課程系統修成「可以交接給下一個人」的樣子。
