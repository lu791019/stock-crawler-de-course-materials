"""
測試 config.py 的環境變數機制（單元測試，不需要任何外部服務）

驗證第 1 章的核心設計：os.environ.get(key, default)
- 沒設環境變數 → 用預設值
- 有設環境變數 → 覆蓋預設值，且 PORT 有做 int 轉型
"""
import importlib

import crawler.config


def _reload_config():
    """config 的值在 import 時就固定了，改環境變數後要 reload 才會重讀"""
    return importlib.reload(crawler.config)


def test_default_values(monkeypatch):
    # 確保環境變數不存在 → 應該用預設值
    monkeypatch.delenv("RABBITMQ_HOST", raising=False)
    monkeypatch.delenv("RABBITMQ_PORT", raising=False)
    config = _reload_config()
    assert config.RABBITMQ_HOST == "127.0.0.1"
    assert config.RABBITMQ_PORT == 5672
    assert config.MYSQL_ACCOUNT == "root"


def test_env_override(monkeypatch):
    # 設了環境變數 → 應該覆蓋預設值
    monkeypatch.setenv("RABBITMQ_HOST", "rabbitmq")
    monkeypatch.setenv("RABBITMQ_PORT", "9999")
    config = _reload_config()
    assert config.RABBITMQ_HOST == "rabbitmq"
    assert config.RABBITMQ_PORT == 9999          # 不是字串 "9999" —— int() 轉型有效
    assert isinstance(config.RABBITMQ_PORT, int)


def teardown_module():
    """全部跑完後把 config 恢復成乾淨狀態，避免影響其他測試"""
    importlib.reload(crawler.config)
