# Step 4：task 與 producer 分家

- 上一步（Step 3）：crawl() 和「要抓什麼」的迴圈都在 main.py。
- 這一步：crawl() 搬進 task.py、迴圈與清單搬進 producer.py（build_jobs 產生任務清單）。
- 沒動的：client / transformer / repository / config 四支檔案（可 diff 驗證）。

```bash
uv run python example/evolution/step4_task/producer.py
diff ../step3_modules/client.py client.py   # 無輸出 = 完全沒改
```

任務顆粒度在 producer 的 build_jobs() 決定。此時仍未使用 Celery。

完整說明見 課程手冊/補充J 的 Step 4。
