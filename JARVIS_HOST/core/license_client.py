"""Supabase Auth and shared Stagepulse license-core client for JARVIS Windows."""
from __future__ import annotations

import hashlib
import platform
import uuid
from typing import Any

import requests

SUPABASE_URL = "https://itasctyjzyewcykozuex.supabase.co"
PUBLISHABLE_KEY = "sb_publishable_tP3CMhVAjv6FNtrkYfVEOA_dbF9m8Jb"


class LicenseClientError(RuntimeError):
    """A safe, user-facing licensing error."""


class LicenseClient:
    def __init__(self, base_url: str = SUPABASE_URL, publishable_key: str = PUBLISHABLE_KEY, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.publishable_key = publishable_key
        self.timeout = timeout

    @staticmethod
    def device_hash() -> str:
        raw = f"{platform.system()}|{platform.machine()}|{platform.node()}|{uuid.getnode():012x}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _request(self, url: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        headers = {"apikey": self.publishable_key, "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            try:
                data = response.json()
            except ValueError:
                data = {}
            if not response.ok:
                code = str(data.get("error") or data.get("msg") or data.get("message") or "")
                messages = {
                    "LICENSE_INVALID_OR_UNPAID": "Lisans geçersiz, süresi dolmuş veya ödemesi tamamlanmamış.",
                    "LICENSE_DEVICE_LIMIT": "Lisansın cihaz kullanım sınırına ulaşıldı.",
                    "DEVICE_BOUND_TO_OTHER_USER": "Bu cihaz başka bir hesaba bağlı.",
                    "UNAUTHENTICATED": "Oturum doğrulanamadı. Yeniden giriş yap.",
                    "FORBIDDEN_OWNER_ONLY": "Bu işlem yalnızca yönetici hesabına açık.",
                    "RATE_LIMITED": "Çok fazla deneme yapıldı. Biraz bekleyip tekrar dene.",
                }
                raise LicenseClientError(messages.get(code, code or f"Sunucu hatası: HTTP {response.status_code}"))
            if not isinstance(data, dict):
                raise LicenseClientError("Sunucudan geçersiz yanıt alındı.")
            return data
        except requests.RequestException as exc:
            raise LicenseClientError("Lisans sunucusuna bağlanılamadı. İnternet bağlantısını kontrol et.") from exc

    def sign_in(self, email: str, password: str) -> str:
        if not email.strip() or not password:
            raise LicenseClientError("E-posta ve şifre gerekli.")
        data = self._request(
            f"{self.base_url}/auth/v1/token?grant_type=password",
            {"email": email.strip(), "password": password},
        )
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise LicenseClientError("Supabase oturumu alınamadı.")
        return token

    def activate(self, token: str, license_key: str) -> dict[str, Any]:
        return self._request(
            f"{self.base_url}/functions/v1/license-core",
            {
                "action": "activate",
                "app_id": "jarvis-windows",
                "platform": "windows",
                "device_hash": self.device_hash(),
                "license_key": license_key.strip(),
            },
            token,
        )

    def status(self, token: str) -> dict[str, Any]:
        return self._request(
            f"{self.base_url}/functions/v1/license-core",
            {
                "action": "status",
                "app_id": "jarvis-windows",
                "platform": "windows",
                "device_hash": self.device_hash(),
            },
            token,
        )
