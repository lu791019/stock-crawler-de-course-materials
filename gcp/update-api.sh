#!/usr/bin/env bash
# API 一鍵換版（第 17 章的腳本版）：build → tag → push → deploy 上 Cloud Run
# 在 VM1 上、專案根目錄執行：bash gcp/update-api.sh v3
# 這支腳本就是 CI/CD 的 CD 段（第 18 章）——把它接到 GitHub Actions 後面就自動化了
set -euo pipefail

# ===== 改成你自己的值 =====
PROJECT_ID="stock-crawler-course"
REGION="asia-east1"
SERVICE="stock-api"
# Cloud SQL 連線名稱：gcloud sql instances describe stock-mysql --format="value(connectionName)"
CLOUDSQL_CONN="stock-crawler-course:asia-east1:stock-mysql"
# ==========================

VERSION="${1:?用法: bash gcp/update-api.sh <版本號，例如 v3>}"
REG="${REGION}-docker.pkg.dev/${PROJECT_ID}/stock-repo"

echo "=== 1/3 build ${VERSION} ==="
docker build -f api/Dockerfile -t "stock-api:${VERSION}" .

echo "=== 2/3 tag + push ==="
docker tag "stock-api:${VERSION}" "${REG}/stock-api:${VERSION}"
docker push "${REG}/stock-api:${VERSION}"

echo "=== 3/3 deploy 上 Cloud Run（零停機切換）==="
gcloud run deploy "${SERVICE}" \
  --image="${REG}/stock-api:${VERSION}" \
  --region="${REGION}" \
  --port=8000 \
  --add-cloudsql-instances="${CLOUDSQL_CONN}" \
  --set-env-vars="MYSQL_UNIX_SOCKET=/cloudsql/${CLOUDSQL_CONN},MYSQL_ACCOUNT=root,MYSQL_PASSWORD=1234" \
  --allow-unauthenticated \
  --memory=1Gi

URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --format="value(status.url)")
curl -s -o /dev/null -w "健康檢查 ${URL}/ → %{http_code}\n" "${URL}/"

echo "出問題要退版：gcloud run services update-traffic ${SERVICE} --region=${REGION} --to-revisions={舊revision}=100"
