from datetime import datetime
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.dummy_operator import DummyOperator
import random


# 預設參數
default_args = {
    'owner': 'data-team',
    'start_date': datetime(2024, 1, 1),
}


# ===== Python Functions =====

def step1_create_data(**context):
    """
    步驟1 - 建立資料
    示範：使用 return 自動推送到 XCom
    """
    print("📝 步驟1 - 建立資料")
    
    data = {
        'id': random.randint(1000, 9999),
        'name': random.choice(['小明', '小華', '小美']),
        'value': random.randint(10, 100)
    }
    
    print(f"建立的資料：{data}")
    
    # return 會自動存到 XCom
    return data


def step2_process_data(**context):
    """
    步驟2 - 處理資料
    示範：從 XCom 拉取資料 + 手動推送
    """
    print("🔄 步驟2 - 處理資料")
    
    # 從前一步取得資料
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
    
    # 手動推送到 XCom
    context['task_instance'].xcom_push(key='processed_data', value=result)
    
    return "資料處理完成"


def step3_combine_data(**context):
    """
    步驟3 - 合併資料
    示範：拉取多個 XCom 資料
    """
    print("🔗 步驟3 - 合併資料")
    
    ti = context['task_instance']
    
    # 拉取原始資料
    original_data = ti.xcom_pull(task_ids='step1_create_data')
    # 拉取處理後的資料
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

# 使用 with DAG 語法
with DAG(
    dag_id='example_xcom_coffee_shop_dag',
    default_args=default_args,
    description='咖啡店訂單系統 - XCom 資料傳遞範例',
    schedule_interval=None,  # 手動觸發
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['example', 'xcom', 'coffee'],
) as dag:

    # ===== Tasks Definition =====
    
    # 開始任務
    start_task = DummyOperator(
        task_id='start',
    )
    
    # 步驟1：建立資料 - 展示 return 自動推送到 XCom
    step1_task = PythonOperator(
        task_id='step1_create_data',
        python_callable=step1_create_data,
    )
    
    # 步驟2：處理資料 - 展示 XCom pull 和 push
    step2_task = PythonOperator(
        task_id='step2_process_data',
        python_callable=step2_process_data,
    )
    
    # 步驟3：合併資料 - 展示多個 XCom 資料的使用
    step3_task = PythonOperator(
        task_id='step3_combine_data',
        python_callable=step3_combine_data,
    )
    
    # 結束任務
    end_task = DummyOperator(
        task_id='end',
    )

    # ===== Task Dependencies =====
    # 設定任務依賴關係：開始 → 步驟1 → 步驟2 → 步驟3 → 結束
    start_task >> step1_task >> step2_task >> step3_task >> end_task
