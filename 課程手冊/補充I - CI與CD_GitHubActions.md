# 補充I - CI 與 CD：GitHub Actions 從自動測試到自動部署

> 本章是選讀章節。前置：補充C（tests/ 目錄與 pytest 標記已存在）；Part B 的 CD 段另外需要做過補充G（Artifact Registry 與 Cloud Run）。
>
> 主線第 17 章結束時，資料線已經每天自動跑，但「程式改了之後」的事還是手動的：手動跑測試、手動 build、手動部署。本章把這條發佈流程交給 GitHub Actions：**Part A 實作 CI（每次 push 自動跑測試），Part B 走 CD 的路徑（測試通過後自動部署到 Cloud Run）**。

## 本章用到的工具與服務

| 工具／服務 | 類型 | 在本章做什麼 |
|-----------|------|-------------|
| GitHub Actions | 外部服務 | 每次 push 自動執行 workflow：跑測試（CI）、部署（CD） |
| GitHub Secrets | 外部服務 | 保管 workflow 要用的 GCP 憑證，不寫進 repo |
| pytest | 既有工具 | 補充C 寫好的測試，在 CI 成為上線前的檢查關卡 |
| uv | 既有工具 | CI 的臨時機器上照 uv.lock 還原依賴 |
| Artifact Registry | GCP 服務 | CD 段的 image 倉庫（補充G 建立的 stock-repo） |
| Cloud Run | GCP 服務 | CD 段的部署目的地（補充G 部署的 stock-api） |

## 做完這一章你會

1. 說得出 CI 與 CD 各自自動化了什麼、分界線在哪
2. 逐行看懂 `.github/workflows/ci.yml`，並在自己的 fork 上觸發一次 CI
3. 說得出 CD 段的三個 step 對應補充G 手動做過的哪三個動作
4. 看懂 CD workflow 的完整範例，知道 GCP 憑證在 GitHub 上怎麼保管

## 先搞懂：CI/CD 把哪段手動流程自動化

CI/CD（持續整合／持續部署）的每個環節，前面章節都手動做過：

```
git push ──▶ 自動跑測試（補充C 寫好的 pytest）──▶ 自動 build 並上傳 image ──▶ 自動部署到執行環境
         └──────────── CI（Part A）────────────┘└──────────────── CD（Part B）────────────────┘
```

兩段的分界線：**CI 回答「這次改動能不能上線」，CD 回答「怎麼把能上線的改動送上線」**。CI 的產出是一個綠勾或紅叉；CD 的產出是新版本真的在跑。

- 測試沒過的程式碼不應該上線，而且這件事不該依賴人工記得檢查——這是 CI 存在的理由
- build → push → deploy 三步每次都一樣，人工做只會慢和出錯——這是 CD 存在的理由

GitHub Actions 一份 workflow 檔就能把兩段接起來：測試 job 通過後才執行部署 job。

## 一步一步

### Part A：CI——push 自動跑測試

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

`push` 與 `pull_request` 兩個事件都觸發：合併進 main 之前就先跑過一次測試，紅了就擋 merge。

驗證方式：到課程 repo 的 GitHub 頁面 → **Actions** 分頁，能看到每次 push 觸發的 CI 紀錄。每一列左邊的綠色勾號代表那次 push 的測試全部通過，右邊顯示執行時間：

![GitHub Actions 執行紀錄](images/ch17/02-GitHubActions-CI執行紀錄全綠.jpg)

想自己觸發一次：fork 課程 repo 到自己帳號、改一個檔案後 push，你自己 repo 的 Actions 頁就會執行。

### Part B：CD——自動部署到 Cloud Run（需做過補充G）

CD 段的三個動作你在補充G 全部手動做過：

| CD 的 step | 補充G 手動做過的指令 |
|-----------|---------------------|
| build image | `docker build -f api/Dockerfile -t stock-api:vN .` |
| push 上倉庫 | `docker tag` ＋ `docker push`（Artifact Registry） |
| 部署新版本 | `gcloud run deploy stock-api --image=...` |

CD 就是把這三步接在 CI 的測試 job 後面，由 GitHub 的機器代替你執行。

**先解決身分問題。** 你在本機能跑 `gcloud`，是因為 `gcloud auth login` 過；GitHub 的臨時機器沒有任何 GCP 身分。做法沿用課程一路的憑證觀念：

1. 用第 14 章的方法建一個 CD 專用服務帳戶，只給兩個角色：`roles/artifactregistry.writer`（推 image）、`roles/run.developer`（部署 Cloud Run）——最小權限原則，跟第 15 章給 BigQuery 兩個小角色是同一個道理
2. 發一把 JSON 金鑰，內容貼進 GitHub repo 的 **Settings → Secrets and variables → Actions**，名稱取 `GCP_SA_KEY`——金鑰不進 repo，跟第 16 章「密碼不寫在 compose 檔」是同一個原則，只是保管者從 Secret Manager 換成 GitHub Secrets

workflow 完整範例（`deploy` job 接在 `test` job 之後）：

```yaml
  deploy:
    needs: test                     # test job 綠了才會執行——CI 擋住 CD 的入口
    if: github.ref == 'refs/heads/main'   # 只有 main 分支的 push 才部署，PR 不部署
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}   # 用 Secrets 裡的金鑰對 GCP 表明身分
      - uses: google-github-actions/setup-gcloud@v2
      - run: gcloud auth configure-docker asia-east1-docker.pkg.dev --quiet
      - run: |
          REG=asia-east1-docker.pkg.dev/{你的專案ID}/stock-repo
          docker build -f api/Dockerfile -t $REG/stock-api:${{ github.sha }} .
          docker push $REG/stock-api:${{ github.sha }}
          gcloud run deploy stock-api \
            --image=$REG/stock-api:${{ github.sha }} \
            --region=asia-east1
```

範例裡三個值得停下來看的設計：

- `needs: test`——部署 job 依賴測試 job，測試紅了整條停在原地。這一行就是「CI 擋住 CD」的實作
- image tag 用 `${{ github.sha }}`（這次 commit 的雜湊值）而不是 v1/v2——每次部署都有唯一版本號，回滾時 revision 清單直接對得回是哪次 commit
- deploy 只給 `--image` 和 `--region`——其他設定（port、Cloud SQL 專線、secrets、記憶體）沿用上一次部署，跟補充G 的 v2 換版同一個行為

本章把 CD 段列為路徑示範：課程 repo 不掛這個 deploy job（每次 push 都部署會持續動用 GCP 資源）。想實際走一遍的話，在自己的 fork 上做完補充G 之後照上面三步設定即可，部署完成的驗證方式與補充G Part D 相同。

### 那 Secret Manager 跟 GitHub Secrets 是什麼關係？

兩個都是「把機密跟程式碼分開放」的保管箱，差別在誰來讀：

| | Secret Manager | GitHub Secrets |
|---|---------------|----------------|
| 誰來讀 | 在 GCP 裡跑的程式（worker、Cloud Run） | GitHub Actions 的 workflow |
| 讀取憑證 | VM／容器的服務帳戶身分，免金鑰 | 不用憑證——GitHub 自己注入 |
| 課程用它保管 | 資料庫密碼（第 16 章） | CD 用的 GCP 金鑰（本章） |

原則一致：**機密永遠不出現在 repo 和指令歷史裡**，換的只是保管箱在哪一邊。

## 檢查：這一章做完的狀態

- [ ] 自己 fork 的 Actions 頁看得到 CI 綠勾
- [ ] 說得出 ci.yml 四個 step 各自對應本機的哪個動作
- [ ] 說得出 CD 三個 step 對應補充G 的哪三個指令，以及 `needs: test` 擋住了什麼
- [ ] 說得出 GCP 金鑰為什麼放 GitHub Secrets 而不是 repo

## 想一想

1. CI 排除了 `-m integration` 的測試，代表整合測試在上線前沒有自動跑過。要讓 CI 也跑整合測試，臨時機器上缺什麼？查一下 GitHub Actions 的 `services:` 設定能不能補上
2. 範例的 deploy job 只在 push main 時執行。如果團隊規定「所有改動走 PR」，這個設計等於什麼時候部署？這樣安排的好處是什麼？
3. 金鑰貼進 GitHub Secrets 之後，還留在你電腦的下載資料夾裡。照第 14 章金鑰保管的規矩，接下來該做什麼？

## 練習

1. 把 `ci.yml` 的 pytest 改成故意會失敗的指令、push 到自己的 fork，看 Actions 變紅——確認測試失敗時 CI 會把這次 push 標成不通過，再改回來
2. 在 fork 上開一個 PR（改 README 即可），觀察 `pull_request` 事件觸發的 CI——確認測試在合併前就先跑了
3. 讀一次 `github.sha` 的值（Actions 執行紀錄裡看得到），對照 `git log` 確認它就是那次 commit 的雜湊值

## 排錯

| 症狀 | 原因 | 處理 |
|------|------|------|
| CI 的 uv sync 失敗 | uv.lock 跟 pyproject 不同步 | 本機 `uv lock` 後重新 push |
| push 了但 Actions 頁沒動靜 | push 的不是 main 分支，或 fork 的 Actions 功能沒啟用 | 確認分支名；fork 第一次要在 Actions 頁按啟用 |
| deploy job 報 permission denied | CD 服務帳戶缺角色，或 Secrets 貼的金鑰不完整 | 確認兩個角色都綁了；金鑰 JSON 要整份貼入 |
| deploy job 跳過沒執行 | `needs: test` 的測試 job 紅了，或觸發事件是 PR | 先修測試；PR 不部署是設計行為 |

## 本章總結

- CI 回答「能不能上線」：push 觸發、臨時機器、四個 step 重演你本機的測試流程，紅了擋 merge
- CD 回答「怎麼送上線」：build → push → deploy 三步接在測試後面，`needs: test` 讓 CI 成為 CD 的門檻
- 憑證的原則不變：GCP 金鑰放 GitHub Secrets、資料庫密碼放 Secret Manager——機密永遠不進 repo
- image tag 用 commit 雜湊值，部署紀錄與版本控制對得起來

---

回到主線：資料線每天自動跑（第 17 章）、對外服務在 Cloud Run 上（補充G）、每次 push 自動測試與部署（本章）——整條「改程式到上線」的流程到此沒有一步需要人工記得執行。
