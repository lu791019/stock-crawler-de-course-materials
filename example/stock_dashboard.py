"""
用 Streamlit 幫 Stock Price API 加一個網頁前端（手冊補充B 附錄範例）

定位：Streamlit 是「API 的呼叫方」——只打 API，不直接連 MySQL。
     資料庫躲在 API 後面，這就是守門員架構的完整閉環。

前置：API 要先跑著
    uv run uvicorn api.main:app --port 8000

啟動（streamlit 不在本課依賴裡，要先自行安裝：uv add streamlit 或 pip install streamlit）
    streamlit run example/stock_dashboard.py
    # 瀏覽器自動開 http://localhost:8501
"""
import pandas as pd
import requests
import streamlit as st

API = "http://localhost:8000"


# Streamlit 每次互動都「整個腳本從頭重跑」——用 cache 避免重複打 API
@st.cache_data(ttl=60)
def fetch_json(url: str, params: dict | None = None):
    r = requests.get(url, params=params, timeout=5)
    r.raise_for_status()  # 非 2xx 直接拋錯，不讓壞回應往下走
    return r.json()


st.title("台股看盤板")

# 跟第 2 章打 FinMind 同一套 requests——只是這次打的是自己開的 API
stocks = fetch_json(f"{API}/stocks")
stock_ids = [str(s["stock_id"]) for s in stocks]

stock_id = st.selectbox("選一支股票", stock_ids)

prices = fetch_json(f"{API}/stocks/{stock_id}/prices", params={"limit": 120})
df = pd.DataFrame(prices).sort_values("date")

latest = df.iloc[-1]
st.metric("最新收盤", f'{latest["close"]}', delta=float(latest["spread"]))
st.line_chart(df.set_index("date")["close"])
