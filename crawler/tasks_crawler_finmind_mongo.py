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
    # 選資料庫 mydb、集合 TaiwanStockPrice（collection 相當於 MySQL 的表）
    # 兩者都不用事先建立——第一次寫入時自動出現（對照 MySQL 要先 CREATE TABLE）
    collection = client["mydb"]["TaiwanStockPrice"]
    for doc in data:
        # update_one(filter, update, upsert) 三個參數逐一看：
        #   filter：{"stock_id", "date"}——用「同股同日」當這份文件的身分，
        #           對應 MySQL 版的複合主鍵 (stock_id, date)
        #   update：{"$set": doc}——$set 是 MongoDB 的更新運算子，意思是
        #           「把 doc 裡列出的欄位改成這些值」；沒列到的欄位保持原樣
        #   upsert=True：filter 找不到文件時改成插入一份新的（update + insert = upsert）
        # 效果：第一次執行全部是插入；重跑時全部變成更新——
        #       同股同日永遠只有一份文件，這就是冪等（對應 MySQL 版的 on_duplicate_key_update）
        collection.update_one(
            {"stock_id": doc["stock_id"], "date": doc["date"]},
            {"$set": doc},
            upsert=True,
        )
    # 關閉連線，釋放資源（每個任務自己開自己關，多 worker 併發時互不干擾）
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
