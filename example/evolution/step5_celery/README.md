# Step 5：接上 Celery 與 RabbitMQ

- 相對 Step 4 的差異只有三處：新增 worker.py（Celery app）、task.py 加一行 @app.task()、producer 的 crawl(...) 改 crawl.delay(...)。
- client / transformer / repository 函式內容沒改（import 改完整套件路徑，原因見各檔案開頭註解）。

```bash
docker compose -f docker-compose-local.yml up -d rabbitmq
# 視窗一：worker（持續執行）
uv run celery -A example.evolution.step5_celery.worker worker --loglevel=info
# 視窗二：發任務
uv run python -m example.evolution.step5_celery.producer
```

驗收：worker log 出現 succeeded（不是只有 received）；多個 ForkPoolWorker 平行處理。

完整說明見 課程手冊/補充J 的 Step 5。
