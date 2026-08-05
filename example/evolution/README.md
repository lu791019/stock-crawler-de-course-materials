# evolution：從一支爬蟲到分散式的六步拆解

這個目錄是「補充 J - 從一支爬蟲到分散式_六步拆解」的示範程式碼。
完整的步驟說明、判準、驗收方式、常見疑問都在補充 J，這裡只列檔案與執行指令。

## 目錄結構

| 路徑 | 步驟 | 內容 |
|---|---|---|
| `step0_single_file.py` | Step 0 | 單體版，抓與存寫在同一個函式裡，沒有整理階段 |
| `step1_functions.py` | Step 1 | 同一支檔案內拆成抓、整理、存三個函式 |
| `step2_modules/` | Step 2 | 三個函式各自獨立成檔案，設定抽到 config |
| `step3_task/` | Step 3 | 任務參數化，多了 task 與 producer |
| `step4_celery/` | Step 4 | 接上 Celery 與 RabbitMQ，多了 worker |
| `step5_airflow/` | Step 5 | Airflow DAG，定時發任務 |

三個階段與檔案的對應：

| 階段 | Step 1 的函式 | Step 2 之後的檔案 |
|---|---|---|
| 抓資料 | `fetch_stock_price()` | `client.py` |
| 整理資料 | `transform()` | `transformer.py` |
| 存資料 | `save()` | `repository.py` |

Step 2 到 Step 4 各自都有 `config.py`、`client.py`、`transformer.py`、`repository.py`，內容刻意重複，
目的是讓你可以直接比對兩個步驟之間改了什麼：

```bash
diff step2_modules/client.py step3_task/client.py       # 沒有輸出代表完全沒改
diff step2_modules/transformer.py step4_celery/transformer.py  # 只有檔頭說明不同
diff step3_task/task.py step4_celery/task.py            # 差異只有裝飾器與 import
diff step3_task/producer.py step4_celery/producer.py    # 差異只有 .delay()
```

## 執行指令

以下指令都在專案根目錄執行。

Step 0 到 Step 3 只需要網路連線，不需要任何容器：

```bash
uv run python example/evolution/step0_single_file.py
uv run python example/evolution/step1_functions.py
uv run python example/evolution/step2_modules/main.py
uv run python example/evolution/step3_task/producer.py
```

Step 1 要同時寫入 MySQL，把檔案裡的 `WRITE_MYSQL` 改成 `True`（先啟動 MySQL 容器）。

Step 2 之後改用環境變數決定儲存目標，不必改程式碼：

```bash
docker compose -f docker-compose-local.yml up -d mysql
STORAGE=mysql uv run python example/evolution/step2_modules/main.py
STORAGE=csv,mysql uv run python example/evolution/step2_modules/main.py
```

Step 4 需要 RabbitMQ，並且要開兩個終端機視窗：

```bash
# 準備：啟動 RabbitMQ
docker compose -f docker-compose-local.yml up -d rabbitmq

# 視窗一：啟動 worker，這個指令會持續執行
uv run celery -A example.evolution.step4_celery.worker worker --loglevel=info

# 視窗二：發送任務
uv run python -m example.evolution.step4_celery.producer
```

Step 5 把 DAG 檔複製到 Airflow 的 dags 目錄：

```bash
cp example/evolution/step5_airflow/evolution_producer_dag.py airflow/dags/
```

## 注意事項

- Step 4 的 `client.py` 與 `repository.py` 用完整套件路徑 import，Step 2、Step 3 用同目錄模組名稱 import。
  差異的原因是執行方式不同，說明見補充 J 的 Step 4 一節。
- Step 4 的 producer 要用 `python -m` 以模組路徑啟動，直接執行檔案路徑會找不到模組。
- 預設的儲存目標是 CSV，輸出在 `output/` 目錄。
