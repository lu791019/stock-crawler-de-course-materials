# gcp/ — 雲端部署腳本（第 14、17、18 章）

課程雲端段用到的 gcloud 指令，整理成可重複執行的腳本。**執行前先把每個腳本開頭的變數改成你自己的值**（專案 ID、區域、IP 每個人都不同）。

| 檔案 | 用途 | 對應章節 |
|------|------|---------|
| `create-vm.sh` | 建立課程主力 VM（e2-standard-2） | 第 14 章 Part F |
| `update-api.sh` | API 一鍵換版：build → tag → push → 逐台重啟 | 第 17 章 Part F 的腳本化 |

## 為什麼要把指令存成腳本

第 14 章起你在終端機敲的每條 gcloud 指令，這裡都能重放——這就是 **Infrastructure as Code 的起點**：環境不是「手動點出來的」，而是「一份可以重跑、可以 code review、可以進 git 的描述」。業界的完整版是 Terraform；概念跟這裡一樣，只是描述格式從 shell 腳本換成宣告式設定檔。

## 使用方式

```bash
# 看清楚腳本內容與變數後再執行
bash gcp/create-vm.sh
```
