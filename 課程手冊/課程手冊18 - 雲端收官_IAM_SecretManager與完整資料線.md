# 課程手冊18 - 雲端收官：IAM、Secret Manager 與完整資料線

> 本章對應 EP20，是課程最後一章。前置：第 17 章做完（兩台 VM、Cloud SQL、Artifact Registry 都在）。
>
> 系統已經能對外服務了，但還欠三件「正式環境」的事：密碼還是明碼 1234 躺在 `.env` 裡、每日同步還要手動觸發、程式改了要手動測試手動發佈。本章補齊：**Secret Manager 收密碼、自架 Airflow 排程把資料線全線串起、GitHub Actions 把測試變守門員**——然後畢業。

## 做完這一章你會

1. 說得出 IAM 的三個概念（成員、角色、資源）與最小權限原則的實作方式
2. 用 Secret Manager 管理資料庫密碼：建立、授權、程式讀取、fallback 設計
3. 在 GCE 上自架 Airflow 跑每日排程，跑通完整雲端資料線：爬蟲 → Cloud SQL → BigQuery
4. 說得出 Cloud Composer 是什麼、跟自架 Airflow 怎麼選——託管 vs 自架的期末考題
5. 看懂 GitHub Actions 的 CI 流程：push 自動跑測試
6. 完成雲端收官驗證與畢業清理

## 先搞懂

### IAM：誰、能做什麼、在哪個範圍

第 14 章建服務帳戶時說過「建立時不給角色＝最小權限的起點」，這顆伏筆現在收回。IAM（Identity and Access Management）用三個概念管理整個專案的權限：

| 概念 | 是什麼 | 課程裡的例子 |
|------|--------|-------------|
| 成員（who） | 人（Google 帳號）或程式（服務帳戶） | 你的 Gmail；`stock-crawler-sa`；VM 的預設服務帳戶 |
| 角色（what） | 一組權限的包裝 | `BigQuery 資料編輯者`、`Secret Manager 密鑰存取者` |
| 資源（where） | 權限生效的範圍 | 整個專案、單一 bucket、**單一 secret** |

兩類角色要分清楚：

- **基本角色（Owner／Editor／Viewer）**：粗顆粒的老設計。VM 預設服務帳戶掛的 Editor 幾乎什麼都能做——教學方便，但正式環境это反面教材：worker 被入侵＝整個專案淪陷
- **預定義角色**：每個服務自己的細顆粒角色。**最小權限原則＝只給做這件事需要的那一個角色、綁在最小的資源範圍上**。第 15 章給 `stock-crawler-sa` 的兩個 BigQuery 角色是第一次實作；本章的 Secret Manager 授權會再做一次教科書級的示範——授權綁在「單一 secret」上，不是整個專案

### 密碼的畢業之路：.env → Secret Manager

補充E 建立的 `.env` 紀律（密碼不進 git）在本機夠用，上雲之後極限就露出來了：

| | `.env` 檔 | Secret Manager |
|---|----------|----------------|
| 存放 | 明碼躺在每台機器的磁碟上 | 集中在 GCP，加密儲存 |
| 誰能看 | 登得進機器的人都能 cat | IAM 逐一授權，能稽核「誰在何時讀過」 |
| 換密碼 | 逐台改 `.env`、逐台重啟 | 加一個新版本，程式下次讀 `latest` 自動拿到 |
| 版本 | 沒有——改壞了就沒了 | 每版保留，可停用、可回滾 |
| 費用 | 免費 | 每 secret 每月 $0.06，課程用量趨近零 |

程式端的正確姿勢是 **fallback 設計**：先問 Secret Manager，拿不到就退回環境變數。同一份程式碼，在有授權的 VM 上自動用雲端機密、在你的筆電上照舊用 `.env`——部署環境變了，程式碼一行都不用改（config 中心設計的最後一次兌現）。

### 完整資料線：這門課的最終形態

本章把第 15 章「手動跑一次」的同步，升級成 Airflow 排程的每日管線。全線如下——每一段你都親手建過：

```
VM2 worker 爬蟲 ──寫入──▶ Cloud SQL（OLTP：即時、逐筆）
                              │
              VM1 自架 Airflow 每個交易日 20:00 觸發 sync
                              ▼
                        BigQuery（OLAP：分析、聚合）
                         主表＋每日行情／MA5·MA20 趨勢／大盤摘要
                              │
                              ▼
                     Looker Studio（BI 儀表板，第 15 章 Bonus 已接）
```

OLTP 和 OLAP 分開的理由第 15 章講過（分析不拖累營運庫）；本章的新東西是**排程**：讓「同步」從一個你要記得做的動作，變成一條自己會跑的管線。

### Composer：託管版 Airflow，期末考題

排程主線用的是 GCE 上自架的 Airflow 容器——跟第 10 章以來完全同一套 image 和 DAG。GCP 也有託管版：**Cloud Composer**，第 16 章「託管 vs 自架」的期末考題：

| | 自架 Airflow（本章主線） | Cloud Composer |
|---|------------------------|----------------|
| 機器與維運 | 你的 VM、你顧 | Google 全包（底層其實是 GKE） |
| 費用 | VM 錢（已經在付了，邊際成本≈0） | **最小環境每月數百美元起** |
| 建置 | image build 約 10 分鐘 | 環境建置 20-30 分鐘 |
| DAG 部署 | 放進 dags/ 目錄 | 上傳到指定的 Cloud Storage bucket |
| 適合誰 | 學習、小規模、預算敏感 | DAG 多、團隊大、沒人想半夜修 scheduler |

課程的選擇：**主線自架（學員零額外費用），Composer 由講師 demo**——看一次建置流程、把同一支 DAG 上傳到 bucket、在託管的 UI 上觸發成功，體會「DAG 兩邊通用、差的只是誰養機器」，然後**立刻刪除環境**（它按小時計費，留著過夜就是在燒錢）。額度充足又好奇的同學可以照 demo 步驟自己走一遍，做完務必刪。

### CI/CD：你已經有全部零件

CI/CD（持續整合／持續部署）聽起來很大，拆開看你每個零件都有了：

```
git push ──▶ 自動跑測試（補充C 寫好的 pytest）──▶ 自動 build/push image（第 17 章的發佈流程）──▶ 逐台換版（第 17 章做過）
         └────────── CI（本章實作）──────────┘└──────────────── CD（概念，指出路徑）────────────────┘
```

本章實作 CI 段：repo 裡放一份 GitHub Actions 的 workflow 檔，之後每次 push，GitHub 自動開一台臨時虛擬機跑你的測試——**紅燈的程式碼不該上線，而且這件事不該靠人記得**。補充C 那句「測試是上線守門員」在這裡兌現。

## 一步一步

> 開工前照第 17 章 Step 0 的 SOP 喚醒系統：Cloud SQL `ALWAYS` → 兩台 VM start → 查新外部 IP → 重跑 authorized-networks patch。scopes 上一章已改過 `cloud-platform`，這次不用再動。

### Part A：把密碼收進 Secret Manager

```bash
# 1. 啟用 API（老規矩）
gcloud services enable secretmanager.googleapis.com

# 2. 建立 secret：名字 mysql-password、內容 1234
#    printf 不帶換行；--data-file=- 表示「內容從管線讀」——密碼不出現在指令歷史的參數裡
printf "1234" | gcloud secrets create mysql-password \
  --data-file=- --replication-policy=automatic

# 3. 授權 VM 的服務帳戶讀這顆 secret（最小權限的教科書示範）
#    專案編號先查出來：
gcloud projects describe {你的專案ID} --format="value(projectNumber)"

gcloud secrets add-iam-policy-binding mysql-password \
  --member="serviceAccount:{專案編號}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

第 3 步值得慢讀：授的角色是 `secretAccessor`（只能讀 secret 內容，不能改不能刪不能列別的），綁的範圍是 `mysql-password` **這一顆**（不是專案層級）——「誰、能做什麼、在哪個範圍」三個維度都收到最小。VM 的服務帳戶雖然掛著 Editor，但 **Editor 不含讀取 secret 內容的權限**——不補這行授權，程式讀 secret 會被 403 擋下。

驗證（兩邊都做）：

```bash
# 在本機（你是 Owner，本來就能讀）
gcloud secrets versions access latest --secret=mysql-password
# 1234

# SSH 進 VM1（用的是 VM 服務帳戶的身分——證明剛才的授權生效）
gcloud secrets versions access latest --secret=mysql-password
# 1234
```

### Part B：程式接上 Secret Manager

打開 `crawler/config.py`，把 Secret Manager 區塊**取消註解**（連同上面的 `GCP_PROJECT_ID`，第 15 章取消過的話它已經是開的）。取消後的邏輯：

```python
def _password_from_secret_manager():
    """讀 Secret Manager 的 mysql-password; 任何原因失敗回 None, 讓呼叫端退回原值"""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT_ID}/secrets/mysql-password/versions/latest"
        return client.access_secret_version(name=name).payload.data.decode()
    except Exception:
        return None

MYSQL_PASSWORD = _password_from_secret_manager() or MYSQL_PASSWORD
```

在 VM1 上驗證。這裡有個小問題：secret 的值和 `.env` 預設值都是 1234，印出來根本分不出密碼是從哪條路來的。解法用上 Secret Manager 的**版本**功能——暫時加一版辨識用的值，測完再加一版換回來：

```bash
# 在本機：加一版辨識值（versions add＝新增版本，latest 從此指向它）
printf "sm-test-42" | gcloud secrets versions add mysql-password --data-file=-

# 在 VM1 的 ~/stock-crawler：
export PATH="$HOME/.local/bin:$PATH"
GCP_PROJECT_ID={你的專案ID} uv run python -c \
  "from crawler.config import MYSQL_PASSWORD; print('password =', MYSQL_PASSWORD)"
# password = sm-test-42        ← 值來自雲端，不是 .env——Secret Manager 路徑實證

# fallback 路徑也驗一下：給一個不存在的專案 ID，讀取失敗就退回環境變數
GCP_PROJECT_ID=no-such-project uv run python -c \
  "from crawler.config import MYSQL_PASSWORD; print('password =', MYSQL_PASSWORD)"
# password = 1234              ← 退回 .env 預設值——fallback 路徑實證

# 在本機：加一版 1234 換回正確密碼（舊版本還在，這就是「可回滾」）
printf "1234" | gcloud secrets versions add mysql-password --data-file=-
```

順帶你已經體驗了**密碼輪替**的完整動作：`versions add` 一次，所有讀 `latest` 的程式下次啟動自動拿到新值——沒有逐台改檔案這回事。

### Part C：Airflow 上雲——排程主線開工

在 VM1 上準備自架 Airflow。三個學員步驟：

**C-1 build image**（跟第 10 章本機同一份 Dockerfile）：

```bash
# 在 VM1 的 ~/stock-crawler
git pull
docker build -f airflow/Dockerfile -t stock-airflow:latest .   # 約 10 分鐘
```

> 如果你第 17 章排錯時跑過 `docker system prune -af`——它會把「沒有容器在用」的 image 全部清掉，所以這裡幾乎一定要重 build。build 等待的時間正好把 Part E 的 CI 段看完。

**C-2 取消 `crawler/bigquery.py` 的註解**（第 15 章在本機做過同一件事，這次在 VM 上）：把 `from crawler.config import GCP_PROJECT_ID as PROJECT_ID` 打開、把寫死的 `PROJECT_ID = "your-project-id"` 註解掉。

**C-3 寫 Airflow 的雲端 override 檔**（第 16 章 override 手法第三次上場）：

```bash
cat > gcp-airflow-override.yml <<'YML'
# Airflow 上雲 override：MySQL 改連 Cloud SQL、補 GCP 專案 ID
# BigQuery 認證走 VM 中繼資料（服務帳戶），不需要金鑰檔
services:
  airflow-webserver:
    environment:
      MYSQL_HOST: {CloudSQL IP}
      GCP_PROJECT_ID: {你的專案ID}
  airflow-scheduler:
    environment:
      MYSQL_HOST: {CloudSQL IP}
      GCP_PROJECT_ID: {你的專案ID}
YML

docker network create my_network    # airflow compose 宣告要用的外部網路（建過就跳過）
docker compose -f airflow/docker-compose-airflow.yml -f gcp-airflow-override.yml up -d
```

注意 override 裡**沒有** `GOOGLE_APPLICATION_CREDENTIALS`——第 15 章在本機要金鑰檔，是因為你的筆電對 GCP 是陌生人；VM 本身有身分（服務帳戶），Google 的程式庫會自動用它。**金鑰檔在雲上是不需要的**，這是「服務帳戶」設計的完全體。

### Part D：觸發完整資料線

等 Airflow init 完成（`docker ps` 看 webserver healthy），觸發 BigQuery ETL DAG：

```bash
docker exec airflow-scheduler airflow dags unpause stock_bigquery_etl_dag
docker exec airflow-scheduler airflow dags trigger stock_bigquery_etl_dag
```

這支 DAG 你在第 12 章見過但跳過了（當時沒有 GCP）：`sync_mysql_to_bigquery` 先把 Cloud SQL 的股價全量同步進 BigQuery，然後三個 transform task 建出每日行情、MA5/MA20 趨勢、大盤摘要的 View 與實體表。它掛著 `schedule_interval="0 20 * * 1-5"`——每個交易日 20:00 自動跑，手動觸發只是驗收用。

> unpause 之後 Graph 上可能突然多出一個你沒觸發的 run——那是排程 DAG 被 unpause 時補跑的最近一期（即使 `catchup=False` 也會跑一期），不是鬼。

等 run 全綠後，回**本機**用 bq 驗證資料真的落地：

```bash
bq query --nouse_legacy_sql \
  "SELECT COUNT(*) AS n, COUNT(DISTINCT stock_id) AS stocks, MAX(date) AS latest
   FROM stock.TaiwanStockPrice"
# 筆數與 Cloud SQL 一致、股票數＝你爬過的支數

bq query --nouse_legacy_sql \
  "SELECT stock_id, trade_date, ROUND(ma5,2) AS ma5, ROUND(ma20,2) AS ma20
   FROM stock.stock_trend_analysis
   WHERE ma20 IS NOT NULL ORDER BY trade_date DESC LIMIT 4"
# 每支股票最近日期的 MA5 / MA20 有值
```

到這裡，**完整資料線閉環**：worker 爬進 Cloud SQL 的資料，被排程的 Airflow 同步進 BigQuery、算出技術指標，第 15 章接好的 Looker Studio 儀表板下次重新整理就會看到新資料。而且這條線從今天起每個交易日 20:00 自己跑——只要 VM1 開著。

> 💡 想讓它真的天天跑，VM1 就得一直開著（每月約 NT$1,600）。課程的折衷：上課期間手動觸發驗證，理解「排程已就位」即可——這正是 Composer 這類託管服務的賣點之一：排程機器由 Google 養著。

### Part E：CI——push 自動跑測試

repo 裡已經有 `.github/workflows/ci.yml`，逐行讀：

```yaml
name: CI
on:
  push:
    branches: [main]      # push 到 main 就觸發
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest          # GitHub 免費提供的臨時虛擬機
    steps:
      - uses: actions/checkout@v4   # 等於 git clone
      - uses: astral-sh/setup-uv@v5 # 裝 uv——跟你本機同一套工具
      - run: uv sync --frozen       # 完全照 uv.lock 還原依賴（環境可重現）
      - run: uv run pytest tests/ -m "not integration" -v
```

四個 step 就是你在本機做過無數次的動作：clone → 裝工具 → 裝依賴 → 跑測試。`-m "not integration"` 排除需要真實 MySQL 的整合測試（CI 的臨時機器上沒有 MySQL；補充C 設計的標記在這裡發揮作用）。

驗證方式：到課程 repo 的 GitHub 頁面 → **Actions** 分頁，能看到每次 push 觸發的 CI 紀錄與綠勾。想親手觸發：fork 課程 repo 到自己帳號、隨便改個檔案 push，你自己 repo 的 Actions 頁就會跑起來。

CD 段課程不實作，但路徑你已經看得懂：在 workflow 後面加 steps——`docker build` → `push` 到 Artifact Registry → SSH 到 VM 跑第 17 章的換版指令。`gcp/update-api.sh` 就是那段的腳本化，接上去 CI/CD 就全通了。

### Part F：Composer demo（講師示範，選做）

流程走一遍給你看（額度充足者可跟做，**做完立刻刪**）：

1. 啟用 API：`gcloud services enable composer.googleapis.com`
2. Console：≡ → Composer → 建立環境（Composer 3）→ 名稱、區域 asia-east1、規格選最小 → 建立（**等 20-30 分鐘**——它在幫你架一整套 GKE 上的 Airflow）
3. 建好後環境詳情頁有個 **DAGs 資料夾**連結（一個 Cloud Storage bucket）——把 `airflow/dags/stock_crawler_dag.py` 上傳進去
4. 開「Airflow 網頁介面」——跟你自架的 UI 一模一樣，DAG 幾分鐘後自動出現，unpause → trigger → 全綠
5. **示範結束立刻刪除環境**（Console 的刪除鈕）——它按小時計費

要帶走的一句話：**DAG 兩邊通用**。你寫的編排邏輯不綁機器，搬家成本趨近零——這是先學自架再看託管的紅利。

## 收工：兩種收法

**今天先收工（課程還沒結束）**——照第 16 章三停：SQL `NEVER`、兩台 VM stop。

**畢業清理（課程結束、確定不玩了）**——照順序全刪，刪完帳單歸零：

| 順序 | 資源 | 指令／位置 | 為什麼是這個順序 |
|------|------|-----------|----------------|
| 1 | Composer 環境（若建了） | Console → Composer → 刪除 | 最貴，秒殺 |
| 2 | LB 計費四件（若還在） | 第 17 章收工段的四條 delete | 按時計費 |
| 3 | 兩台 VM | `gcloud compute instances delete ...` | 磁碟跟著 VM 一起消失 |
| 4 | Cloud SQL | `gcloud sql instances delete stock-mysql` | 儲存費 |
| 5 | Artifact Registry | `gcloud artifacts repositories delete stock-repo` | image 儲存費 |
| 6 | BigQuery dataset | `bq rm -r -d stock` | 儲存費（免費層內，可留最後） |
| 7 | Secret | `gcloud secrets delete mysql-password` | 費用趨近零 |
| 8 | 整個專案（終極選項） | Console → IAM與管理 → 設定 → 關閉 | 上面全部一次帶走；**30 天寬限期**內可反悔還原 |

## 檢查：這一章做完的狀態

- [ ] `gcloud secrets list` 看得到 mysql-password；VM 上 `versions access` 讀得到
- [ ] VM 上 python 印出的 MYSQL_PASSWORD 走過 Secret Manager 與 fallback 兩條路
- [ ] VM1 的 Airflow 起得來，`stock_bigquery_etl_dag` 全綠
- [ ] bq 查得到 TaiwanStockPrice 主表與 stock_trend_analysis 的 MA 值
- [ ] GitHub Actions 頁看得到 CI 綠勾
- [ ] 說得出 Composer 與自架的取捨、CD 段還缺哪些 step
- [ ] 收工（三停），或畢業清理（全刪）

## 想一想

1. VM 的服務帳戶已經是 Editor 了，為什麼還要特地授 `secretAccessor`？這說明基本角色和預定義角色的什麼關係？
2. 密碼輪替時，正在跑的 worker 拿的還是舊密碼（它啟動時讀的）——什麼時機會真的切到新密碼？這對「輪替後舊密碼何時才能作廢」有什麼含意？
3. sync 用的是全量 replace（每次整表重傳）。資料量大十倍後該怎麼改？（提示：BigQuery 的分區正是為增量寫入設計的——只重傳當天的分區）

## 練習

1. 建第二顆 secret `rabbitmq-password`，只授權給 VM 服務帳戶，把 config.py 的 `WORKER_PASSWORD` 也接上同一套 fallback——把學到的模式再走一遍
2. 把 `ci.yml` 的 pytest 改成故意會失敗的指令、push 到自己的 fork，看 Actions 變紅——體會「守門員擋下紅燈」長什麼樣，再改回來
3. 對 `stock_bigquery_etl_dag` 的 `schedule_interval` 解讀：`"0 20 * * 1-5"` 是什麼時間？改成「每小時」怎麼寫？（第 9 章 cron 語法的複習）

## 排錯

| 症狀 | 原因 | 處理 |
|------|------|------|
| 程式讀 secret 回 403 Permission denied | 沒做 `add-iam-policy-binding`，或 member 打錯（要 VM 用的那個服務帳戶） | 對照 Part A 第 3 步；`gcloud secrets get-iam-policy mysql-password` 檢查 |
| config.py import 報 GCP_PROJECT_ID 未定義 | Secret Manager 區塊開了，但上面的 GCP_PROJECT_ID 那行還註解著 | 兩處一起取消註解 |
| airflow up 報 stock-airflow image 不存在 | 第 17 章的 `prune -af` 把沒在用的 image 清了 | C-1 重 build |
| airflow up 報 network my_network not found | compose 宣告的外部網路還沒建 | `docker network create my_network` |
| sync task 報 400：DAY partitioning 只接受 DATE，found STRING | 來源表是 to_sql 自動建的，`date` 欄是文字型別；舊版 sync 沒做型別轉換 | `git pull` 拉最新版（sync 上傳前已加 `pd.to_datetime`）；順便記住：**to_sql 自動建表的欄位型別要用 `SHOW COLUMNS` 驗過，不能想當然** |
| unpause 後多一個沒觸發過的 run | 排程 DAG unpause 會補跑最近一期（catchup=False 也一樣） | 正常現象；不想要就在 unpause 前先 trigger 手動 run 驗證 |
| BigQuery 寫入 403 | VM scopes 還是預設唯讀（沒做第 17 章 Step 0 的 scopes 步驟） | 停機 → `set-service-account --scopes=cloud-platform` → 開機 → 重授權 SQL |
| CI 的 uv sync 失敗 | uv.lock 跟 pyproject 不同步 | 本機 `uv lock` 後重新 push |

## 本章總結

- IAM 三概念：成員、角色、資源。最小權限＝最小的角色綁最小的範圍——`secretAccessor` 綁單顆 secret 是教科書示範；Editor 很方便，也很危險
- 密碼從 .env 畢業到 Secret Manager：集中、可稽核、版本化；程式端用 fallback 讓同一份 code 雲端讀機密、本機讀 .env
- 金鑰檔只有「GCP 外面的程式」才需要；VM 上的程式用自己的服務帳戶身分，零金鑰
- 完整資料線：爬蟲 → Cloud SQL → 排程 Airflow → BigQuery → Looker Studio；排程讓管線從「記得做」變成「自己跑」
- Composer＝託管 Airflow：DAG 兩邊通用，差的是誰養機器和多少錢——託管 vs 自架這道題你現在能自己答了
- CI 四步＝你手動做過無數次的 clone/裝工具/裝依賴/跑測試，交給 GitHub 每次 push 自動跑；CD 是第 17 章發佈流程的自動化，零件你全有了
- 畢業清理照順序刪：貴的先刪、專案關閉是終極選項（30 天可反悔）

---

十八章走完：從一支印「發送任務」的 Celery 腳本，到一條有佇列分流、失敗重試、去重冪等、容器化、多機分工、託管資料庫、對外負載平衡、機密管理、每日排程、自動測試的**雲端資料管線**。課程給你的不是這條管線本身，而是拆解它的每一刀——下一條管線，換你自己切。
