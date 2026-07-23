#!/bin/bash
# cron 示範用腳本（課程手冊 09）：發送一批 print 版爬蟲任務給 Celery worker。
#
# 為什麼要包這支腳本？cron 執行指令時的環境非常精簡：
# PATH 只有幾個系統目錄（找不到 uv）、工作目錄也不在專案裡（找不到 crawler 模組）。
# 把「補 PATH、進專案目錄、執行 producer」三件事收進腳本，
# crontab 那邊就只需要乾淨的一行——這也是實務上排 cron 工作的標準做法。

# 把 uv 所在的目錄加進 PATH（uv 預設安裝在 ~/.local/bin）
export PATH="$HOME/.local/bin:$PATH"

# 進入專案根目錄（此腳本位於 example/，上一層就是專案根目錄）
cd "$(dirname "$0")/.." || exit 1

# 發送一批 print 版任務（worker 收到後只印出、不寫資料庫）
uv run python -m crawler.producer_crawler_finmind_print
