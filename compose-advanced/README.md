# compose-advanced/ — 拆開版 Compose 檔案

日常使用推薦根目錄的 `docker-compose-local.yml`（整合版）。這個資料夾是「一個服務一份 compose」的拆開版，用於課堂逐步展示與 `--scale` 實驗。所有檔案都掛外部網路 `my_network`，使用前先建：

```bash
docker network create my_network
```

## 課堂使用的三份

| 檔案 | 啟動什麼 | 用在哪 |
| --- | --- | --- |
| `rabbitmq.yml` | RabbitMQ + Flower | 課程手冊03、13、速查手冊第三部分 |
| `mysql.yml` | MySQL 8.0 + phpMyAdmin | 課程手冊03、13、速查手冊第三部分 |
| `docker-compose-worker-network.yml` | twse + tpex 雙 worker（本地 build）| 課程手冊03 的 `--scale` 實驗、速查手冊第三部分 |

標準啟動順序：

```bash
docker compose -f compose-advanced/rabbitmq.yml up -d
docker compose -f compose-advanced/mysql.yml up -d
docker compose -f compose-advanced/docker-compose-worker-network.yml up -d --build
```

## legacy/ — 原課程演進史（課堂不使用）

`legacy/` 保留原課程（TibameSam/crawler）的舊版檔案，記錄 compose 設計的演進過程。**這些檔案課堂不使用**，多數依賴 DockerHub 上的 `linsamtw/tibame_crawler` image（amd64-only，Apple Silicon 跑不動）。

| 檔案 | 當年的角色 | 被誰取代 |
| --- | --- | --- |
| `rabbitmq-network.yml` | 舊版 RabbitMQ + Flower | `rabbitmq.yml` |
| `docker-compose-worker.yml` | 最早的單一 worker 版 | `docker-compose-worker-network.yml` |
| `docker-compose-worker-network-local.yml` | 本地 build 過渡版 | `docker-compose-worker-network.yml` |
| `docker-compose-producer-network.yml` | 容器化 producer | 本機 `uv run crawler/producer_multi_queue.py` |
| `docker-compose-worker-network-version.yml` | 雙 worker（DockerHub image）| `docker-compose-worker-network.yml`（本地 build）|
| `docker-compose-producer-network-version.yml` | producer（DockerHub image）| 本機 `uv run` |
| `docker-compose-producer-duplicate-network-version.yml` | 去重 upsert 版 producer | 本機 `uv run crawler/producer_crawler_finmind_duplicate.py`（課程手冊05）|
| `docker-compose-scheduler-network-version.yml` | 容器化 APScheduler | 本機 `uv run crawler/scheduler.py`（課程手冊06）；正式排程用 Airflow（課程手冊11-13）|

### `-version` 檔案在教什麼？

檔名帶 `-version` 的檔案用 `image: linsamtw/tibame_crawler:${DOCKER_IMAGE_VERSION}` 搭配環境變數切換 image 版本：

```bash
DOCKER_IMAGE_VERSION=0.0.6 docker compose -f docker-compose-worker-network-version.yml up -d
```

這是 CI/CD 部署的核心概念——build 一次、tag 版本、到處部署、出問題秒回滾。本課程走本地 build 路線所以不使用，但這個模式在正式環境很常見，值得認識。
