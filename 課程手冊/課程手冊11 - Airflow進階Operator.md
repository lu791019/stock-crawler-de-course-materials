# 第 11 章：Airflow 進階 Operator — 拼出複雜工作流的積木

> 上一章的 DAG 只有 start → end。但實務上的工作流會分岔、會傳資料、會互相觸發、會需要獨立環境，圖形複雜了還需要整理。這一章把五塊積木一次補齊——每一塊都有現成的範例 DAG 讓你跑。

---

## 做完這一章，你會做到

1. 用 `BranchPythonOperator` 做條件分支：「上午走 A、下午走 B」。
2. 用 XCom 在 task 之間傳資料（return 自動推送、`xcom_pull` 拉取）。
3. 用 `TriggerDagRunOperator` 讓一個 DAG 觸發另一個 DAG。
4. 用 `DockerOperator` 把任務丟進獨立的 Docker 容器執行。
5. 看懂 `DummyOperator` 怎麼把複雜依賴圖整理得清楚。

---

## 先搞懂：這五個範例各補哪一塊

上一章跑過 `example_first_dag`（基礎）和 `example_parallel_dag`（平行）。這一章跑剩下的：

| 檔案 | dag_id（UI 上看到的）| 學什麼 |
|------|---------------------|--------|
| `example_branch_operator_dag.py` | `example_branch_operator_dag` | 讓工作流依照條件走不同的路 |
| `example_xcom_dag.py` | `example_xcom_coffee_shop_dag` | 讓資料在 task 之間傳遞 |
| `example_trigger_dag_operator_dag.py` | `example_trigger_main_dag` ＋ `example_triggered_data_processing_dag`（一檔兩個 DAG）| 讓一個 DAG 觸發另一個 DAG |
| `example_docker_operator_dag.py` | `example_docker_operator_dag` | 把任務放進獨立的容器裡執行 |
| `example_dummy_tasks_dag.py` | `example_dummy_tasks_dag` | 把複雜的依賴結構整理成容易讀懂的圖 |

> 💡 注意：Airflow 列表顯示的是**程式裡定義的 dag_id**，不一定等於檔名（第 10 章練習 3 看過）。

---

## 前置準備

沿用上一章的 Airflow 環境（沒在跑就照第 10 章 Step 2~4 重新啟動）：

```bash
docker compose -f airflow/docker-compose-airflow.yml up -d
# 首次啟動記得等 init 完成後 restart webserver/scheduler（第 10 章 Step 4）
curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health   # 200 = OK
```

---

## 先認識一個新寫法：`**context`

這一章的範例函式簽名長這樣：`def decide_morning_or_afternoon(**context):`——多了一個前面章節沒見過的 `**context`。先講清楚它是什麼，後面的程式碼就都讀得懂：

- **Airflow 執行每個 task 時，會把「這次執行的環境資訊」打包成一個 dict 傳進你的函式**：裡面有 `task_instance`（這個 task 的執行實例，等下 XCom 的推拉全靠它）、執行日期、DAG 資訊等等。
- `**context` 是 Python 的關鍵字引數收集語法：把這一整包接住，需要哪個再拿哪個——例如 `ti = context["task_instance"]`。
- 函式用不到這些資訊時可以不理它（積木 1 的分支函式只用了 `datetime`），但簽名寫上 `**context` 是 Airflow 的慣例寫法——積木 2 的 XCom 就會真正用到。

---

## 積木 1：BranchPythonOperator — 條件分支

### 概念

工作流需要「根據條件走不同路」。`BranchPythonOperator` 的函式**回傳一個 task_id 字串**，Airflow 就只走那條路，另一條標成 skipped。

### 看程式碼

```python
def decide_morning_or_afternoon(**context):
    current_hour = datetime.now().hour
    if current_hour < 12:
        return "morning_task"      # 回傳 task_id（字串）
    else:
        return "afternoon_task"

time_branch = BranchPythonOperator(
    task_id="decide_time_path",
    python_callable=decide_morning_or_afternoon,
)

start_task >> time_branch >> [morning_task, afternoon_task]
```

### 跑起來

```bash
docker exec airflow-webserver airflow dags unpause example_branch_operator_dag
docker exec airflow-webserver airflow dags trigger example_branch_operator_dag
```

### 觀察

UI → `example_branch_operator_dag` → Graph：

> ✅ 根據你觸發的時間，**只有一條**分支是綠色（成功），另一條是**粉紅色（skipped）**。skipped 不是失敗——它是分支語意下的正常狀態。

兩個延伸重點：

- **判斷用的 `datetime.now()` 是容器的時區。** 我們的 image 已設 `Asia/Taipei`（第 10 章的環境變數），所以上午/下午的判斷跟你的手錶一致；若在其他環境跑（容器常預設 UTC），判斷會差 8 小時——第 9 章的時區教訓在這裡同樣適用。
- **想在分支之後「匯合」？有一個必踩的坑。** 這個範例分支後就結束了，但你自己拼積木時，多半會想在 `[morning_task, afternoon_task]` 後面接一個 `end` 匯合。直接接會發現 **end 永遠不跑**：task 的觸發規則預設是 `all_success`（所有上游都成功才跑），而分支語意下必有一條是 skipped——條件永遠不成立。解法是幫 end 指定觸發規則：

  ```python
  end = DummyOperator(task_id="end", trigger_rule="none_failed_min_one_success")
  # 沒有上游失敗、且至少一條成功 → 就跑
  ```

  `trigger_rule` 這個參數第 12 章的股票 DAG 會再出現（多組平行匯合用 `all_success`），在這裡先認得它。

---

## 積木 2：XCom — task 之間傳資料

### 概念

每個 task 是獨立執行的（可能在不同行程、甚至不同機器），變數不能直接共用。**XCom**（Cross-Communication）是 Airflow 內建的小型資料交換所——task 把值存進去、別的 task 拉出來。

### 看程式碼（兩種推、一種拉）

```python
# 推送方式 1：return 值自動存入 XCom
def step1_create_data(**context):
    data = {"id": 1234, "name": "小明", "value": 50}
    return data                          # 自動推送

# 推送方式 2：手動 xcom_push
def step2_process_data(**context):
    ti = context["task_instance"]
    data = ti.xcom_pull(task_ids="step1_create_data")        # 拉 step1 的 return 值
    result = {"processed_value": data["value"] * 2}
    ti.xcom_push(key="processed_data", value=result)         # 手動推送（自訂 key）

# 拉取：可以指定 task_ids 和 key
def step3_combine_data(**context):
    ti = context["task_instance"]
    original  = ti.xcom_pull(task_ids="step1_create_data")
    processed = ti.xcom_pull(task_ids="step2_process_data", key="processed_data")
```

### 跑起來

```bash
docker exec airflow-webserver airflow dags unpause example_xcom_coffee_shop_dag
docker exec airflow-webserver airflow dags trigger example_xcom_coffee_shop_dag
```

### 觀察

UI → 該 DAG → 等全綠 → 點任一 task → **XCom** 分頁。

> ✅ 你會看到每個 task 推送的資料內容。step3 的 log 裡能看到它把前兩步的資料合併起來——資料真的跨 task 流動了。
>
> ⚠️ XCom 適合傳**小資料**（參數、狀態、路徑）。大資料（整個 DataFrame）不要塞 XCom——存到 DB 或檔案，XCom 只傳「放在哪」的路徑。

---

## 積木 3：TriggerDagRunOperator — DAG 觸發 DAG

### 概念

大系統常拆成多個 DAG：「爬蟲 DAG」跑完自動觸發「分析 DAG」。這比塞成一個巨型 DAG 更好維護——各自有自己的排程、負責人、重跑策略。

### 看程式碼

這個範例檔案裡定義了**兩個 DAG**（一個檔案可以放多個 DAG，第 10 章練習 3 看過）：

```python
# 主 DAG 裡的觸發步驟
trigger_data_processing = TriggerDagRunOperator(
    task_id="trigger_data_processing_dag",
    trigger_dag_id="example_triggered_data_processing_dag",  # 要觸發誰
    wait_for_completion=True,        # 等它跑完才繼續往下
)
```

### 跑起來

```bash
# 注意：被觸發的 DAG 也要 unpause，否則觸發不動
docker exec airflow-webserver airflow dags unpause example_trigger_main_dag
docker exec airflow-webserver airflow dags unpause example_triggered_data_processing_dag
docker exec airflow-webserver airflow dags trigger example_trigger_main_dag
```

### 觀察

1. 先看 `example_trigger_main_dag`：跑到 trigger 那步會**等待**（wait_for_completion）。
2. 切到 `example_triggered_data_processing_dag`：多了一個新的 run，正在跑。
3. 子 DAG 跑完，主 DAG 才繼續走到 end。

> ✅ 兩個 DAG 的 run 一對得上，你就懂「工作流串工作流」了。

---

## 積木 4：DockerOperator — 在容器裡跑任務

### 概念

有些任務需要特定環境（不同 Python 版本、特殊套件、或想跟 Airflow 本體隔離）。`DockerOperator` 幫你**臨時起一個容器跑任務、跑完自動刪掉**。

### 看程式碼

```python
python_docker_task = DockerOperator(
    task_id="run_python_script",
    image="python:3.9-slim",              # 用哪個 image
    command='python -c "print(...)"',     # 容器裡跑什麼
    auto_remove=True,                      # 跑完自動刪容器
)
```

### 跑起來

```bash
docker exec airflow-webserver airflow dags unpause example_docker_operator_dag
docker exec airflow-webserver airflow dags trigger example_docker_operator_dag
```

### 觀察

Graph 上三個 Docker task 平行跑（分別是 Python、Alpine、Ubuntu 容器）。點 task → Logs 能看到**容器內部**的輸出。

> 💡 這招能成立，靠的是 compose 把 `/var/run/docker.sock` 掛進了 Airflow 容器（第 7 章 Portainer 用過同一招）——Airflow 因此有權力操作宿主機的 Docker。
>
> ⚠️ 若這個 DAG 因 docker.sock 權限問題失敗，概念理解到位即可，不影響後面章節。

---

## 積木 5：DummyOperator — 把依賴圖整理清楚

### 概念

`DummyOperator` 什麼都不做，純粹當「集合點」。看 `example_dummy_tasks_dag` 的結構：

```
start → [prepare_1, prepare_2] → validate → [process_1, process_2] → merge → end
```

這就是典型 ETL 的骨架：**準備（平行）→ 驗證（匯合）→ 處理（平行）→ 合併**。有了 Dummy 當匯合點，依賴圖就變得容易讀懂。

### 跑起來

```bash
docker exec airflow-webserver airflow dags unpause example_dummy_tasks_dag
docker exec airflow-webserver airflow dags trigger example_dummy_tasks_dag
```

到 Graph 看分岔與匯合的形狀。

---

## Operator 速查表

| Operator | 用途 | 重點 |
|----------|------|------|
| `PythonOperator` | 執行一個 Python 函式 | 函式的 return 值會自動存進 XCom |
| `BashOperator` | 執行一行 shell 指令 | stdout 的最後一行會自動存進 XCom |
| `BranchPythonOperator` | 依條件決定走哪條分支 | 函式要 return 某個 task_id 字串當路標 |
| `DummyOperator` | 當佔位節點或匯合點 | 它不執行任何事，純粹整理圖形 |
| `TriggerDagRunOperator` | 觸發另一個 DAG | 被觸發的那個 DAG 也要先 unpause |
| `DockerOperator` | 臨時起一個容器執行任務 | 前提是 compose 有掛載 docker.sock |

---

## 檢查你是不是真的做到了

| # | 你應該看到 | 它證明了什麼 |
|---|-----------|-------------|
| 1 | Branch 的圖上一條分支是綠色、另一條是粉紅色（skipped）| 條件分支真的只走了其中一邊 |
| 2 | 在 XCom 分頁看得到 task 傳遞的資料內容 | task 之間能夠交換資料 |
| 3 | 主 DAG 觸發了子 DAG，並且等它跑完才繼續 | 工作流可以串接另一個工作流 |
| 4 | Docker task 的 log 顯示的是容器內部的輸出 | 任務可以在隔離的環境裡執行 |
| 5 | Dummy DAG 的圖上有清楚的分岔和匯合結構 | 你能讀懂比較複雜的依賴圖 |

---

## 想一想（確認你懂了）

**Q1：BranchPythonOperator 的函式跟一般 PythonOperator 的函式，回傳值的意義差在哪？**

一般 PythonOperator 的 return 值只是「結果」（會存進 XCom 給別人用）。BranchPythonOperator 的 return 值是「**路標**」——它必須是某個 task_id 字串，Airflow 依它決定走哪條分支，沒被選中的分支全部 skipped。

**Q2：為什麼大 DataFrame 不該用 XCom 傳？那應該怎麼辦？**

XCom 的值存在 Airflow 的 metadata DB（Postgres）裡，塞大資料會把 metadata DB 撐爆、也拖慢排程。正確做法：大資料寫到外部（MySQL、檔案、S3），XCom 只傳「它在哪」（表名、路徑）。下一章的爬蟲 DAG 就是這樣——資料直接進 MySQL，DAG 只管流程。

**Q3：什麼時候該把流程拆成多個 DAG、用 TriggerDagRunOperator 串，而不是全塞在一個 DAG？**

當兩段流程有**不同的排程週期、不同的負責人、或不同的重跑需求**時就該拆。例如「每天爬資料」和「每週產報表」——排程不同，硬塞一個 DAG 反而彆扭。拆開後用 Trigger 串（或讓下游自己排程），各自獨立演進。

---

## 換你試試看

**練習 1：改分支條件**

把 `example_branch_operator_dag` 的判斷改成「偶數分鐘走 A、奇數分鐘走 B」（`datetime.now().minute % 2`），多觸發幾次，看它兩條路輪流走。這讓你確認分支邏輯完全由你的函式決定。

**練習 2：加一個 XCom 消費者**

在 `example_xcom_dag` 裡加一個 `step4_report` task，拉取 step3 的合併結果並 print 出來，接在 step3 後面。改完存檔等 scheduler 重新掃描（或到 UI 確認 Graph 多了一格），觸發驗證。這讓你練習「改 DAG → 掛載自動生效」的開發循環。

**練習 3：把 wait_for_completion 改成 False**

把 TriggerDagRunOperator 的 `wait_for_completion` 改成 `False` 再觸發一次，觀察主 DAG **不等**子 DAG、直接跑完。想一想：什麼情境要等（下游依賴子 DAG 的產出）、什麼情境不用等（射後不理的通知類流程）？

---

## 卡住了？常見錯誤這樣排

| 你遇到的狀況 | 原因 | 怎麼解 |
|-------------|------|--------|
| 觸發主 DAG 之後子 DAG 沒有動 | 子 DAG 還在 paused 狀態，觸發不會執行 | 主 DAG 和子 DAG 兩個都要 unpause |
| 分支的另一條顯示粉紅色 | 那是 skipped 狀態，不是錯誤——分支語意下沒被選中的路就是這樣 | 這是正常現象，不需要處理 |
| XCom 分頁是空白的 | 那個 task 的函式沒有 return 值、也沒有呼叫 xcom_push | 確認函式有 return 或有呼叫 `xcom_push` |
| DockerOperator 報權限錯誤 | docker.sock 沒有掛載進容器，或掛載了但權限不足 | 確認 compose 有掛 `/var/run/docker.sock`；真的解不了就跳過這個範例，概念懂了即可 |
| 改了 DAG 檔案但 UI 沒有更新 | scheduler 每隔幾十秒才重新掃描一次 dags 資料夾 | 等 30~60 秒讓它掃到，或直接重啟 scheduler |

---

## 這一章你學到了

- 這一章學了五塊積木：Branch 負責分岔、XCom 負責傳資料、Trigger 負責串接 DAG、DockerOperator 負責隔離執行、Dummy 負責整理圖形。
- `**context` 是 Airflow 執行 task 時注入的執行環境資訊，`task_instance` 就放在裡面——XCom 的推送和拉取都要靠它。
- XCom 只適合傳小資料（參數、狀態、路徑）；大資料要寫到外部儲存，XCom 只傳「它放在哪裡」。
- 分支之後要匯合的話，記得幫匯合節點改 `trigger_rule`——預設的 `all_success` 會因為 skipped 的分支永遠不成立，匯合節點就永遠不會執行。
- 複雜系統應該拆成多個各自獨立的 DAG，再用 TriggerDagRunOperator 串起來，讓每個 DAG 有自己的排程、負責人和重跑策略。

## 下一章要做什麼

積木都齊了，下一章逐塊收割——把 Airflow 接上你的爬蟲 pipeline：

| 這一章的積木 | 下一章蓋在哪 |
|---|---|
| `DummyOperator` | `stock_crawler_twse_tpex_dag` 用它當上市/上櫃的分組節點 |
| `DockerOperator` | 串法三用它起容器跑第 3 章的多佇列 producer |
| XCom 的「大資料走外部」原則 | 爬蟲資料直接進 MySQL，DAG 只管流程 |
| `trigger_rule` | 股票 DAG 的 end 用 `all_success` 接住多組匯合 |

**三種串法（直接呼叫 / 透過 Celery / 容器化 producer）＋完整 ETL DAG——前面所有章節在下一章整合起來。**
