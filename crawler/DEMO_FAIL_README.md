# Demo Fail — Celery 失敗處理教學

> ⚠️ 本說明已**完整整合**進課程手冊：`課程手冊/課程手冊04 - 失敗處理retry與requeue.md`。
> 四個情境的訊息流程圖、逐行程式解讀、一步一步實測、retry vs requeue 對照表、排錯表都在那裡，請直接讀手冊第 4 章。

## 檔案速查

| 檔案 | 用途 |
|------|------|
| `worker_demo.py` | 獨立的 Celery app（全域開 acks_late，不影響 worker.py）|
| `tasks_demo_fail.py` | 4 個模擬失敗的 task |
| `producer_demo_fail.py` | 發送 demo task 的 producer（情境 3/4 預設註解，測哪個開哪個）|
