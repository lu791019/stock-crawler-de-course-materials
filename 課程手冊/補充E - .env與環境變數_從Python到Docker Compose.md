# 補充 E：.env 與環境變數 — 同一份程式與設定，跑遍所有環境

> 你在課程裡其實已經三次遇到同一個哲學：`config.py` 的 `os.environ.get()`、compose 裡的 `${MYSQL_ROOT_PASSWORD:-1234}`、還有 worker 服務的 `environment:` 區塊。這份補充把它們串成一張地圖，並用 repo 現成的範例檔（`docker-compose-dotenv-demo.yml` + `.env.dotenv-demo.example`）完整跑一次。所有輸出皆 VM 實測。

---

## 為什麼需要 .env

三個現實逼出來的做法：

1. **帳密不能寫死在程式或 yml 裡**——寫死了，換個環境（本機 → 測試機 → 正式機）就要改檔案，而且密碼會跟著程式碼進 git 外洩。
2. **同一份程式要在不同環境跑**——本機連 `127.0.0.1`、容器內連服務名 `mysql`，程式碼不該為此改一行。
3. **設定和程式要分離**——改個密碼、改個 port 不應該動到任何程式碼或 yml。

解法：把「會變的值」抽到環境變數，環境變數集中放在一個**不進 git** 的 `.env` 檔。

---

## 一張地圖：同一個哲學的三層

| 層 | 誰在讀 | 語法 | 什麼時候生效 | 課程哪裡用到 |
|----|--------|------|-------------|-------------|
| **Python 程式** | `config.py` | `os.environ.get("MYSQL_HOST", "127.0.0.1")` | 程式執行時 | 第 1 章起的所有 crawler 程式 |
| **Compose 檔** | docker compose | `${MYSQL_ROOT_PASSWORD:-1234}` | **解析 yml 時**（up 的當下） | `docker-compose-local.yml` 的 MySQL 密碼 |
| **容器環境** | 容器裡的程式 | `environment:` 或 `env_file:` | **容器啟動時**注入 | worker 的 `RABBITMQ_HOST=rabbitmq` |

三層都是同一句話：**「找得到環境變數就用它，找不到就用預設值」**——差別只在「誰、在什麼時間點讀」。

---

## 機制①：`.env` 給 compose 做 `${}` 替換（解析時）

`docker-compose-local.yml` 裡這行你已經看過：

```yaml
MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-1234}
```

`${變數名:-預設值}` 的意思：compose 在**讀 yml 的當下**先找這個變數——找得到就代入、找不到就用 `1234`。它找變數的順序：

1. **shell 環境變數**（`MYSQL_ROOT_PASSWORD=abc docker compose up` 這樣帶進來的）
2. **跟 compose 檔同目錄的 `.env` 檔**（自動載入，不用任何參數）
3. 都沒有 → 用 `:-` 後面的預設值

要用別的檔名（例如一份給 demo、一份給正式），用 `--env-file` 明講：

```bash
docker compose --env-file .env.dotenv-demo -f docker-compose-dotenv-demo.yml up -d
```

**除錯神器——先看「替換後」長什麼樣再啟動**：

```bash
docker compose --env-file .env.dotenv-demo -f docker-compose-dotenv-demo.yml config | grep -E "PASS|USER"
```

VM 實測輸出（demo 檔的值全部正確代入，包括藏在 flower `command:` 連線字串裡的那組——最容易漏的地方）：

```
      - --broker=amqp://demo:demo-pass-123@rabbitmq-demo:5672//
      MYSQL_ROOT_PASSWORD: demo-secret-999
      RABBITMQ_DEFAULT_PASS: demo-pass-123
      RABBITMQ_DEFAULT_USER: demo
```

---

## 機制②：`env_file:` 把變數注入「容器內」（執行時）

長得很像、完全不同的東西：

```yaml
services:
  env-reader-demo:
    image: python:3.12-alpine
    env_file: .env.dotenv-demo     # 整份檔案的變數注入容器環境
```

這**不會**做 yml 裡的 `${}` 替換——它是把變數交給**容器裡的程式**（也就是 `config.py` 那層的 `os.environ` 讀到的東西）。VM 實測 `docker logs env-reader-demo`：

```
=== 機制②：容器內用 os.environ 讀到的變數 ===
  RABBITMQ_USER = demo
  RABBITMQ_PASS = demo-pass-123
  MYSQL_ROOT_PASSWORD = demo-secret-999
  MYSQL_DATABASE = demodb
```

**一句話區分兩種機制**：

| | 機制① `${}` 替換 | 機制② `env_file:` 注入 |
|---|---|---|
| 給誰看 | compose 自己（改寫 yml 文字）| 容器裡的程式（進 os.environ）|
| 什麼時候 | 解析 yml 時 | 容器啟動時 |
| 設定位置 | 根目錄 `.env` 或 `--env-file` | 各服務底下的 `env_file:` |
| 課程對應 | MySQL 密碼那行 | worker 的 `environment:` 是同類的逐條版 |

（`environment:` 和 `env_file:` 做同一件事——前者逐條寫在 yml、後者整份檔案倒進去。）

---

## 動手跑一次（repo 現成範例，四步驟）

範例檔的設計：**帳密和 port 全部參數化**，且 port（15673/5673/5556/3307/8081）、容器名（`*-demo`）、volume 都跟主課程錯開——主課程服務跑著也能同時做這個實驗。

```bash
# ① 複製範本（範本刻意用「跟預設不同」的帳密，好證明 .env 真的生效）
cp .env.dotenv-demo.example .env.dotenv-demo

# ② 先驗證替換結果（不啟動）
docker compose --env-file .env.dotenv-demo -f docker-compose-dotenv-demo.yml config

# ③ 啟動 + 用 .env 裡的帳密登入驗證
docker compose --env-file .env.dotenv-demo -f docker-compose-dotenv-demo.yml up -d
#    RabbitMQ UI http://localhost:15673 → demo / demo-pass-123 ✅
#    phpMyAdmin  http://localhost:8081  → root / demo-secret-999 ✅

# ④ 收工
docker compose --env-file .env.dotenv-demo -f docker-compose-dotenv-demo.yml down -v
```

VM 實測的關鍵證據：用 `demo / demo-pass-123` 呼叫 RabbitMQ API 成功（回 administrator）；**用預設的 `worker / worker` 被拒 HTTP 401**——證明 .env 的帳密真的接管了，不是巧合。

---

## 三個必踩的坑

1. **MySQL 密碼只在資料卷「第一次初始化」時寫入**。之後改 `.env` 再 up，密碼**不會**變——這是登入失敗最常見的原因。確定不要資料的話 `down -v` 重建才會吃新密碼。
2. **`.env` 絕對不能進 git**。repo 的 `.gitignore` 已擋掉 `.env` 和 `.env.dotenv-demo`；版本庫裡只放 `.env.example` / `.env.dotenv-demo.example` 這種**範本**（沒有真密碼），學員 `cp` 一份再改。
3. **優先順序：shell 環境變數 > `.env` 檔 > `:-` 預設值**。所以 `MYSQL_ROOT_PASSWORD=abc docker compose up` 會蓋過 `.env` 裡的值——跟 `config.py` 的 `os.environ.get(key, default)` 是同一個規則，只是發生在 compose 層。

---

## 之後會怎麼用（伏筆）

- **受限帳號 + .env**：補充D 教的 `GRANT`（app 帳號只給份內權限）搭配 .env 帶帳密，就是正式環境的標準組合——密碼不進 git、權限不過大。
- **雲端的下一步**：`.env` 檔還是躺在機器上，正式雲端環境會再升一級——用 **Secret Manager** 這類服務集中管密碼（GCP 段會遇到，repo 的 `crawler/print_secret_manager.py` 就是預告）。

---

## 想一想（確認你懂了）

**Q1：`${MYSQL_ROOT_PASSWORD:-1234}` 和 `os.environ.get("MYSQL_HOST", "127.0.0.1")` 有什麼共同點？**

同一個模式：「找得到環境變數就用、找不到用預設值」。前者是 compose 在解析 yml 時做，後者是 Python 程式在執行時做——層不同、哲學相同。

**Q2：我在 `.env` 改了 MySQL 密碼、重新 up，為什麼登入還是舊密碼？**

因為 MySQL 的 root 密碼只在資料卷第一次初始化時設定，之後的環境變數不會回頭改它。要換密碼得 `down -v` 清掉資料卷重建（資料會消失），或進 MySQL 用 `ALTER USER` 改。

**Q3：`env_file:` 寫在服務底下，跟根目錄的 `.env`，是同一個東西嗎？**

不是。根目錄 `.env` 是給 **compose** 做 `${}` 替換用的（解析時）；`env_file:` 是把變數**注入容器**給裡面的程式讀（執行時）。同一份檔案可以同時被兩種機制用（範例檔就是），但用途完全不同。

---

## 速查表

| 我想要… | 做法 |
|---------|------|
| yml 裡不寫死密碼 | `${VAR:-預設值}` + 同目錄 `.env` |
| 用另一份 env 檔 | `docker compose --env-file 檔名 ...` |
| 確認變數有沒有代入 | `docker compose ... config` 看替換後結果 |
| 把變數給容器裡的程式 | 服務底下 `environment:`（逐條）或 `env_file:`（整份）|
| 暫時蓋掉某個值 | `VAR=值 docker compose up`（shell 優先權最高）|
| 密碼不進 git | `.gitignore` 擋 `.env*`，repo 只放 `*.example` 範本 |
