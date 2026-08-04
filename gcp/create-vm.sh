#!/usr/bin/env bash
# 建立課程主力 VM（第 14 章 Part F 的腳本版）
# 執行前：確認 gcloud 已登入、專案已設定（gcloud config list）
set -euo pipefail

# ===== 改成你自己的值 =====
VM_NAME="stock-crawler-vm"
ZONE="asia-east1-b"          # 台灣彰化；跟你其他資源同區
MACHINE_TYPE="e2-standard-2" # 2 vCPU / 8GB——跑整套 compose 的最低舒適規格
DISK_SIZE="20GB"
# ==========================

gcloud compute instances create "${VM_NAME}" \
  --zone="${ZONE}" \
  --machine-type="${MACHINE_TYPE}" \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size="${DISK_SIZE}" \
  --scopes=cloud-platform \
  --tags=stock-web            # 防火牆規則綁這個標籤（第 14 章 Part H）
# --scopes=cloud-platform: VM 身分可呼叫全部 GCP API（爬蟲雙寫 BigQuery 用，第 14 章 Part F）

gcloud compute instances list
echo "VM 建好了。下一步：gcloud compute ssh ${VM_NAME} --zone=${ZONE}"
