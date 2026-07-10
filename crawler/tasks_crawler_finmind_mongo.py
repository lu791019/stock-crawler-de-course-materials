# 補充F 教學任務: 跟 crawler_finmind 同一套爬蟲, 但落地改成 MongoDB
# 對照重點: MySQL 要先有表、欄位型別都對好才寫得進去;
#          MongoDB 沒有 schema —— dict 直接塞, 資料庫/集合不存在會自動出現
import requests
from pymongo import MongoClient

from crawler.config import (
    MONGO_ACCOUNT,
    MONGO_HOST,
    MONGO_PASSWORD,
    MONGO_PORT,
)
from crawler.worker import app


def upload_data_to_mongo(data: list):
    """把 list of dict 直接寫進 MongoDB（冪等版）

    MySQL 版 (tasks_crawler_finmind_duplicate) 用複合主鍵 + on_duplicate_key_update;
    MongoDB 版做同一件事: 用 (stock_id, date) 當文件的身分, update_one(upsert=True)
    —— 存在就更新、不存在就新增, 重跑幾次結果都一樣
    """
    client = MongoClient(
        host=MONGO_HOST,
        port=MONGO_PORT,
        username=MONGO_ACCOUNT,
        password=MONGO_PASSWORD,
    )
    # 選資料庫和集合(collection, 相當於 MySQL 的表) —— 不存在會在第一次寫入時自動建立
    collection = client["mydb"]["TaiwanStockPrice"]
    for doc in data:
        # filter 找「同股同日」那份文件; $set 整份更新; upsert=True 找不到就新增
        collection.update_one(
            {"stock_id": doc["stock_id"], "date": doc["date"]},
            {"$set": doc},
            upsert=True,
        )
    client.close()


@app.task()
def crawler_finmind_mongo(stock_id):
    # 前半段跟 MySQL 版一模一樣: 打 FinMind API 拿 JSON
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": "2024-01-01",
        "token": "",
    }
    resp = requests.get(url, params=parameter)
    data = resp.json()["data"]  # list of dict

    # 後半段換落地方式: 不轉 DataFrame、不建表, dict 直接 upsert 進 MongoDB
    upload_data_to_mongo(data)
    print(f"✅ {stock_id}: {len(data)} 份文件 upsert 進 MongoDB")
    return f"{stock_id} done"
