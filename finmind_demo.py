import requests
import pandas as pd

def crawler_finmind(stock_id):
   url = "https://api.finmindtrade.com/api/v4/data"
   parameter = {
       "dataset": "TaiwanStockPrice",
       "data_id": stock_id,
       "start_date": "2025-01-01",
       "end_date": "2025-08-18",
   }
   resp = requests.get(url, params=parameter)
   data = resp.json()
   if resp.status_code == 200:
       df = pd.DataFrame(data["data"])
       print(df)
   else:
       print(data["msg"])

crawler_finmind(stock_id="0050")
