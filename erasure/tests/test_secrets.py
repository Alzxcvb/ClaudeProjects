from unittest.mock import patch, MagicMock

import pytest

from erasure.secrets import SecretsManager, KEYCHAIN_APP


@pytest.fixture
def mgr():
    return SecretsManager()


def test_set_and_get_token(mgr):
    with patch("erasure.secrets.keyring.set_password") as mock_set, \
         patch("erasure.secrets.keyring.get_password", return_value="tok123") as mock_get:
        mgr.set_token("twilio", "tok123")
        mock_set.assert_called_once_with(KEYCHAIN_APP, "twilio", "tok123")

        result = mgr.get_token("twilio")
        mock_get.assert_called_once_with(KEYCHAIN_APP, "twilio")
        assert result == "tok123"


def test_get_missing_token_returns_none(mgr):
    with patch("erasure.secrets.keyring.get_password", return_value=None):
        assert mgr.get_token("capsolver") is None


def test_delete_token(mgr):
    with patch("erasure.secrets.keyring.delete_password") as mock_del:
        mgr.delete_token("simplelogin")
        mock_del.assert_called_once_with(KEYCHAIN_APP, "simplelogin")


def test_all_supported_services(mgr):
    services = ["simplelogin", "addy_io", "capsolver", "twilio"]
    for svc in services:
        with patch("erasure.secrets.keyring.get_password", return_value="x"):
            assert mgr.get_token(svc) == "x"


def test_unknown_service_raises(mgr):
    with pytest.raises(ValueError, match="Unknown service"):
        mgr.get_token("unknown_broker")


def test_set_unknown_service_raises(mgr):
    with pytest.raises(ValueError):
        mgr.set_token("badservice", "token")


def test_delete_unknown_service_raises(mgr):
    with pytest.raises(ValueError):
        mgr.delete_token("badservice")
