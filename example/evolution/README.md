# evolution：從一支爬蟲到分散式的七步拆解

這個目錄是「課程手冊/補充J - 從一支爬蟲到分散式_七步拆解」的示範程式碼。
完整的步驟說明、判準、驗收方式、常見疑問都在補充 J；各資料夾另有自己的 README（怎麼跑、驗收什麼）。

## 七步一覽

| 路徑 | 步驟 | 內容 |
|---|---|---|
| `step0_single_file.py` | Step 0 | 單體版，抓與存寫在同一個函式裡 |
| `step1_functions.py` | Step 1 | 同檔拆成抓、整理、存三個函式 |
| `step2_task_function.py` | Step 2 | 同檔抽出一顆任務 `crawl()`——樞紐 |
| `step3_modules/` | Step 3 | 三個階段各自獨立成檔案，設定抽到 config |
| `step4_task/` | Step 4 | task 與 producer 分家 |
| `step5_celery/` | Step 5 | 接上 Celery 與 RabbitMQ |
| `step6_airflow/` | Step 6 | Airflow DAG 定時發任務 |

## 快速執行

```bash
# Step 0–4 只需網路，不需要容器
uv run python example/evolution/step0_single_file.py
uv run python example/evolution/step1_functions.py
uv run python example/evolution/step2_task_function.py
uv run python example/evolution/step3_modules/main.py
uv run python example/evolution/step4_task/producer.py

# Step 3 起可用環境變數換儲存目標（先啟動 MySQL）
STORAGE=csv,mysql uv run python example/evolution/step3_modules/main.py
```

Step 5（Celery）與 Step 6（Airflow）的啟動方式見各資料夾 README。

## diff 對照（每一步只改一件事的證據）

```bash
diff step3_modules/client.py step4_task/client.py       # 無輸出＝分家沒動三層
diff step4_task/task.py step5_celery/task.py            # 差異只有裝飾器與 import
diff step4_task/producer.py step5_celery/producer.py    # 差異只有 .delay()
```
