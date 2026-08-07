# Step 6：Airflow 定時發任務

- 換掉的只有「誰來呼叫 producer」：人工指令 → DAG 排程。
- DAG 裡只呼叫 crawl.delay()，不執行爬蟲本身；爬取仍由 Step 5 的 worker 消化。

```bash
cp evolution_producer_dag.py ../../..//airflow/dags/   # 部署（Airflow 自動載入）
```

完整說明見 課程手冊/補充J 的 Step 6。
