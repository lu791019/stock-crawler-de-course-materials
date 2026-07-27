#!/usr/bin/env bash
# API 一鍵換版（第 17 章 Part F 的腳本版）：build → tag → push → 本機重啟新版容器
# 在 VM 上、專案根目錄執行：bash gcp/update-api.sh v3
# 多台環境：每台輪流跑「重啟」那段（先跑一台、確認 LB 照常回 200、再跑下一台）
set -euo pipefail

# ===== 改成你自己的值 =====
PROJECT_ID="stock-crawler-course"
REGION="asia-east1"
CLOUDSQL_IP="35.229.208.220"
# ==========================

VERSION="${1:?用法: bash gcp/update-api.sh <版本號，例如 v3>}"
REG="${REGION}-docker.pkg.dev/${PROJECT_ID}/stock-repo"

echo "=== 1/3 build ${VERSION} ==="
docker build -f api/Dockerfile -t "stock-api:${VERSION}" .

echo "=== 2/3 tag + push ==="
docker tag "stock-api:${VERSION}" "${REG}/stock-api:${VERSION}"
docker push "${REG}/stock-api:${VERSION}"

echo "=== 3/3 本機換版（停舊、起新）==="
docker rm -f stock-api 2>/dev/null || true
docker run -d --name stock-api -p 8000:8000 \
  -e MYSQL_HOST="${CLOUDSQL_IP}" \
  -e MYSQL_PORT=3306 \
  -e MYSQL_ACCOUNT=root \
  -e MYSQL_PASSWORD=1234 \
  "${REG}/stock-api:${VERSION}"

echo "等 API 啟動（uv 準備環境約 30 秒）..."
sleep 30
curl -s -o /dev/null -w "本機健康檢查: %{http_code}\n" http://localhost:8000/
