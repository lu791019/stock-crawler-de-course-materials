"""
XCom 資料傳遞 Airflow DAG 範例。

對應課程：Airflow 章節的「task 之間傳資料（XCom）」主題。
教學目的：說明 task 之間如何透過 XCom 傳遞小型資料。

核心概念：
- 每個 task 是獨立的行程，彼此的區域變數不能直接共用，所以無法用一般變數把資料交給下一個 task。
- XCom（Cross-Communication）是 Airflow 內建的小型資料交換機制，用來在 task 之間傳遞資料。
- 三種常見用法：
  1. 函式直接 return 一個值，這個值會被自動推送進 XCom；
  2. 用 xcom_push(key=..., value=...) 以自訂 key 手動推送；
  3. 用 xcom_pull(task_ids=...) 指定要從哪個 task 拉取，需自訂 key 時再加 key=...。
- `**context` 是 Airflow 注入的執行環境資訊，task_instance（簡稱 ti）就藏在裡面，
  透過它才能呼叫 xcom_push / xcom_pull。
- XCom 的值存在 Airflow 的 metadata 資料庫，只適合傳小型資料；大型資料應改走外部儲存
  （例如檔案系統或資料庫），XCom 只傳它的路徑或識別碼。

觸發方式：
    airflow dags unpause example_xcom_coffee_shop_dag
    airflow dags trigger example_xcom_coffee_shop_dag
"""
from datetime import datetime
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.dummy_operator import DummyOperator
import random


# 這支 DAG 的共用預設參數。
default_args = {
    'owner': 'data-team',              # 負責團隊
    'start_date': datetime(2024, 1, 1),  # 排程起算日
}


# ===== Python Functions =====

def step1_create_data(**context):
    """
    步驟1 - 建立資料。

    示範第一種 XCom 用法：函式 return 的值會被 Airflow 自動推送進 XCom，
    下游 task 之後可用 xcom_pull(task_ids='step1_create_data') 取回。
    """
    print("📝 步驟1 - 建立資料")

    data = {
        'id': random.randint(1000, 9999),
        'name': random.choice(['小明', '小華', '小美']),
        'value': random.randint(10, 100)
    }

    print(f"建立的資料：{data}")

    # 直接 return，Airflow 會把這個回傳值自動存進 XCom（預設 key 為 return_value）。
    return data


def step2_process_data(**context):
    """
    步驟2 - 處理資料。

    示範從 XCom 拉取上游資料，再用自訂 key 手動推送處理結果。
    """
    print("🔄 步驟2 - 處理資料")

    # 從 context 取出 task_instance，再用 xcom_pull 拉取 step1 的回傳值。
    # 沒指定 key 時，預設拉的就是上游 return 的值。
    data = context['task_instance'].xcom_pull(task_ids='step1_create_data')

    print(f"取得資料：{data}")

    # 處理資料
    processed_value = data['value'] * 2
    result = {
        'original_value': data['value'],
        'processed_value': processed_value,
        'status': 'processed'
    }

    print(f"處理結果：{result}")

    # 用自訂 key（processed_data）手動推送，讓下游可以指名拉取這一份資料。
    context['task_instance'].xcom_push(key='processed_data', value=result)

    return "資料處理完成"


def step3_combine_data(**context):
    """
    步驟3 - 合併資料。

    示範一次從多個上游 task 拉取 XCom：一份用預設 key，一份用自訂 key。
    """
    print("🔗 步驟3 - 合併資料")

    ti = context['task_instance']  # 先取出 task_instance，後面重複使用較簡潔

    # 拉取 step1 的回傳值（預設 key）
    original_data = ti.xcom_pull(task_ids='step1_create_data')
    # 拉取 step2 用自訂 key 推送的那一份資料，所以要指定 key='processed_data'
    processed_data = ti.xcom_pull(task_ids='step2_process_data', key='processed_data')

    # 合併資料
    combined_data = {
        'id': original_data['id'],
        'name': original_data['name'],
        'original_value': processed_data['original_value'],
        'final_value': processed_data['processed_value'],
        'summary': f"{original_data['name']} 的資料已處理完成"
    }

    print(f"合併結果：{combined_data}")

    return combined_data


# ===== DAG Definition =====

# 用 with DAG(...) as dag 建立 DAG。
with DAG(
    dag_id='example_xcom_coffee_shop_dag',
    default_args=default_args,
    description='咖啡店訂單系統 - XCom 資料傳遞範例',
    schedule_interval=None,  # 不自動排程，只能手動觸發
    start_date=datetime(2024, 1, 1),
    catchup=False,           # 不補跑歷史排程區間
    tags=['example', 'xcom', 'coffee'],
) as dag:

    # ===== Tasks Definition =====

    # 開始任務：流程起點，本身不做事。
    start_task = DummyOperator(
        task_id='start',
    )

    # 步驟1：建立資料，示範以 return 自動推送到 XCom。
    step1_task = PythonOperator(
        task_id='step1_create_data',
        python_callable=step1_create_data,
    )

    # 步驟2：處理資料，示範 xcom_pull 拉取與 xcom_push 推送。
    step2_task = PythonOperator(
        task_id='step2_process_data',
        python_callable=step2_process_data,
    )

    # 步驟3：合併資料，示範一次拉取多個上游的 XCom。
    step3_task = PythonOperator(
        task_id='step3_combine_data',
        python_callable=step3_combine_data,
    )

    # 結束任務：流程終點，本身不做事。
    end_task = DummyOperator(
        task_id='end',
    )

    # ===== Task Dependencies =====
    # 依序執行，讓資料能沿著 XCom 一步步往下傳：開始 → 步驟1 → 步驟2 → 步驟3 → 結束。
    start_task >> step1_task >> step2_task >> step3_task >> end_task
