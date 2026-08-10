# probe_network_dag.py：驗證 Composer 經 VPC attachment 連得到 VM1 的 RabbitMQ
# 用法（手冊17 C-6）：把 {VM1內部IP} 換成實際值, 上傳到 Composer 的 DAGs bucket:
#   gcloud storage cp gcp/probe_network_dag.py {你的DAGs bucket}/
# 這支是 Composer 專用的一次性探測工具, 不放 airflow/dags/——那裡會被自架 Airflow 載入。
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


def try_rabbitmq():
    import socket

    s = socket.socket()
    s.settimeout(15)
    try:
        s.connect(("{VM1內部IP}", 5672))
        print("MQ_CONNECT=OK")
    except Exception as e:
        print(f"MQ_CONNECT=FAIL {type(e).__name__}: {e}")
    finally:
        s.close()


with DAG("probe_network_dag", start_date=datetime(2024, 1, 1),
         schedule_interval=None, catchup=False) as dag:
    PythonOperator(task_id="try_rabbitmq", python_callable=try_rabbitmq)
