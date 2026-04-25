import os
import pytest


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("OWM_API_KEY", raising=False)
    monkeypatch.delenv("AUTHORIZED_USER_ID", raising=False)
    import importlib
    import sys
    # Remove config from sys.modules to force fresh import
    sys.modules.pop("config", None)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        import config as cfg_module


def test_authorized_user_id_is_int(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("OWM_API_KEY", "test-key")
    monkeypatch.setenv("AUTHORIZED_USER_ID", "12345")
    import sys
    # Remove config from sys.modules to force fresh import
    sys.modules.pop("config", None)
    import config as cfg_module
    assert cfg_module.AUTHORIZED_USER_ID == 12345
    assert isinstance(cfg_module.AUTHORIZED_USER_ID, int)
