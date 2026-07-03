"""
測試爬蟲任務的解析邏輯（單元測試，用 mock 隔離網路）

重點：完全不打真實的 FinMind API —— 把 requests.get 換成假物件（mock），
就能測「200 回應走 DataFrame 路徑、非 200 走錯誤路徑」，而且快、穩定、不吃 API 額度。
"""
from unittest.mock import MagicMock, patch

from crawler.tasks_crawler_finmind import crawler_finmind_print


def _fake_response(status=200, data=None, msg="ok"):
    """做一個假的 requests 回應物件"""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"msg": msg, "status": status, "data": data or []}
    return resp


# patch 的路徑是「使用方」的路徑：tasks_crawler_finmind 模組裡的 requests.get
@patch("crawler.tasks_crawler_finmind.requests.get")
def test_success_prints_dataframe(mock_get, capsys):
    mock_get.return_value = _fake_response(
        200,
        data=[{"date": "2025-01-02", "stock_id": "2330", "close": 1000.0}],
    )
    # 直接呼叫 = 本地同步執行（第 1 章 Q1），不經過 RabbitMQ，適合單元測試
    crawler_finmind_print("2330")

    out = capsys.readouterr().out
    assert "2330" in out                      # DataFrame 有被印出來

    # 驗證對 API 的呼叫參數組對了
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["dataset"] == "TaiwanStockPrice"
    assert kwargs["params"]["data_id"] == "2330"


@patch("crawler.tasks_crawler_finmind.requests.get")
def test_api_error_prints_msg(mock_get, capsys):
    mock_get.return_value = _fake_response(402, msg="Reached request limit")
    crawler_finmind_print("2330")
    assert "Reached request limit" in capsys.readouterr().out


@patch("crawler.tasks_crawler_finmind.requests.get")
def test_no_real_network_call(mock_get):
    mock_get.return_value = _fake_response(200, data=[])
    crawler_finmind_print("0050")
    mock_get.assert_called_once()             # 整個測試只「假裝」打了一次 API
