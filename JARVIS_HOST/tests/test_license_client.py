from unittest.mock import Mock, patch

from core.license_client import LicenseClient


def test_device_hash_is_stable_sha256():
    first = LicenseClient.device_hash()
    second = LicenseClient.device_hash()
    assert first == second
    assert len(first) == 64
    assert all(char in "0123456789abcdef" for char in first)


def test_sign_in_uses_supabase_auth_and_returns_access_token():
    response = Mock()
    response.ok = True
    response.json.return_value = {"access_token": "test-access-token"}
    with patch("core.license_client.requests.post", return_value=response) as post:
        client = LicenseClient()
        token = client.sign_in("owner@example.com", "not-a-real-password")

    assert token == "test-access-token"
    args, kwargs = post.call_args
    assert args[0].endswith("/auth/v1/token?grant_type=password")
    assert kwargs["json"] == {"email": "owner@example.com", "password": "not-a-real-password"}


def test_activation_calls_shared_license_core_with_windows_identity():
    response = Mock()
    response.ok = True
    response.json.return_value = {"ok": True, "licensed": True}
    with patch("core.license_client.requests.post", return_value=response) as post:
        client = LicenseClient()
        result = client.activate("user-jwt", "JARVIS-TEST-KEY")

    assert result["licensed"] is True
    args, kwargs = post.call_args
    assert args[0].endswith("/functions/v1/license-core")
    assert kwargs["headers"]["Authorization"] == "Bearer user-jwt"
    assert kwargs["json"]["app_id"] == "jarvis-windows"
    assert kwargs["json"]["platform"] == "windows"
    assert kwargs["json"]["license_key"] == "JARVIS-TEST-KEY"
