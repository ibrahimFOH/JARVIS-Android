"""Stagepulse hizmetlerine uygun ücretsiz ses/ışık yazılımlarını GitHub üzerinden denetler.

Bu modül yazılımı yalnızca popüler diye önermemelidir: lisans, güncellik,
Windows desteği, yayın dosyası ve Türkçe yerelleştirme durumunu ayrı raporlar.
Kurulum/indirme bu modül tarafından otomatik başlatılmaz; açık kullanıcı onayı
ve doğrulanabilir yayın bütünlüğü gerektirir.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import os
import re
import shutil
import requests


GITHUB_API = "https://api.github.com"
OPEN_SOURCE_LICENSES = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "MPL-2.0",
}

STAGEPULSE_CATEGORIES = {
    "lighting": {
        "label": "DMX / ışık kontrolü",
        "query": "DMX lighting control software Windows stars:>10 archived:false",
        "services": ["DMX", "Avolites iş akışları", "ışık ve sahne kontrolü"],
    },
    "room_measurement": {
        "label": "Akustik / oda ve hoparlör ölçümü",
        "query": "audio room acoustics measurement analysis software stars:>10 archived:false",
        "services": ["SPL", "akustik analiz", "hoparlör ve subwoofer ölçümü"],
    },
    "loudspeaker_design": {
        "label": "PA / hoparlör sistem tasarımı",
        "query": "loudspeaker array simulation sound system design software stars:>5 archived:false",
        "services": ["PA tasarımı", "kapsama analizi", "sistem optimizasyonu"],
    },
    "audio_network": {
        "label": "Ses ağı / Dante yardımcı araçları",
        "query": "audio network Dante AES67 audio tools stars:>5 archived:false",
        "services": ["Dante", "AES67", "ağ üzerinden ses"],
    },
    "stage_plot": {
        "label": "Stage plot / sahne çizimi",
        "query": "stage plot stage plan event production software stars:>5 archived:false",
        "services": ["Stage Plot", "sahne yerleşimi", "teknik rider"],
    },
}


class SoftwareScoutError(RuntimeError):
    """Araştırma sırasında oluşan güvenli, kullanıcıya gösterilebilir hata."""


class StagepulseSoftwareScout:
    """Public GitHub repositories are evaluated, never blindly installed."""

    def __init__(self, session=None, timeout: int = 15):
        self.session = session or requests.Session()
        self.timeout = max(3, min(int(timeout), 30))
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Stagepulse-JARVIS-Software-Scout",
        }

    def _get_json(self, url: str, params: dict | None = None) -> dict[str, Any]:
        if not url.startswith(GITHUB_API + "/"):
            raise SoftwareScoutError("Yalnızca resmi GitHub API adresleri kabul edilir.")
        try:
            response = self.session.get(
                url, params=params, headers=self.headers,
                timeout=self.timeout, allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise SoftwareScoutError("GitHub araştırması sırasında ağ hatası: " + str(exc)) from exc

        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            raise SoftwareScoutError("GitHub ücretsiz API arama kotası doldu; ücretli hizmete geçilmedi.")
        if response.status_code == 404:
            return {}
        if not response.ok:
            raise SoftwareScoutError(f"GitHub API HTTP {response.status_code}.")
        try:
            data = response.json()
        except ValueError as exc:
            raise SoftwareScoutError("GitHub API geçerli JSON döndürmedi.") from exc
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _windows_hint(repo: dict, tree: dict) -> str:
        text = " ".join([
            str(repo.get("description") or ""),
            " ".join(repo.get("topics") or []),
            " ".join(item.get("path", "") for item in (tree.get("tree") or [])[:5000]),
        ]).casefold()
        if any(token in text for token in ("windows", "win32", "win64", ".msi", ".exe", "windows installer")):
            return "Windows desteğine dair depo işareti bulundu; gerçek kurulum ayrıca doğrulanmalı."
        return "Windows desteği depo metaverisinden doğrulanamadı."

    @staticmethod
    def _license_state(spdx: str) -> str:
        if spdx in OPEN_SOURCE_LICENSES:
            return "Açık kaynak lisansı doğrulandı: " + spdx
        if not spdx:
            return "Lisans bilgisi yok; ücretsiz kullanım doğrulanamadı."
        return "Lisans izin listesinde değil: " + spdx

    @staticmethod
    def _turkish_locale(tree: dict) -> dict[str, Any]:
        paths = [
            item.get("path", "") for item in (tree.get("tree") or [])
            if re.search(r"(?i)(^|[/_.-])(tr[_-]tr|turkish|tur)([/_.-]|$)", item.get("path", ""))
            and item.get("type") == "blob"
        ]
        return {
            "available": bool(paths),
            "files": paths[:30],
            "status": "Türkçe dil dosyası bulundu." if paths else
                      "Depo ağacında Türkçe dil dosyası bulunamadı; çeviri çalışması gerekir.",
            "tree_complete": not bool(tree.get("truncated")),
        }

    def inspect_repository(self, full_name: str) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", str(full_name or "")):
            raise SoftwareScoutError("GitHub depo adı owner/repository biçiminde olmalı.")

        repo = self._get_json(f"{GITHUB_API}/repos/{full_name}")
        if not repo:
            raise SoftwareScoutError("GitHub deposu bulunamadı: " + full_name)

        spdx = str((repo.get("license") or {}).get("spdx_id") or "")
        branch = str(repo.get("default_branch") or "main")
        tree = self._get_json(
            f"{GITHUB_API}/repos/{full_name}/git/trees/{branch}",
            {"recursive": "1"},
        )
        release = self._get_json(f"{GITHUB_API}/repos/{full_name}/releases/latest")
        assets = []
        for asset in release.get("assets") or []:
            name = str(asset.get("name") or "")
            if name.lower().endswith((".exe", ".msi", ".msix", ".zip")):
                assets.append({
                    "name": name,
                    "url": asset.get("browser_download_url", ""),
                    "size": asset.get("size", 0),
                    "digest": asset.get("digest", ""),
                })

        return {
            "full_name": repo.get("full_name", full_name),
            "description": repo.get("description") or "",
            "html_url": repo.get("html_url", ""),
            "homepage": repo.get("homepage") or "",
            "license": spdx or "UNKNOWN",
            "license_state": self._license_state(spdx),
            "license_approved": spdx in OPEN_SOURCE_LICENSES,
            "archived": bool(repo.get("archived")),
            "updated_at": repo.get("pushed_at") or repo.get("updated_at"),
            "stars": int(repo.get("stargazers_count") or 0),
            "default_branch": branch,
            "windows_support": self._windows_hint(repo, tree),
            "turkish_localization": self._turkish_locale(tree),
            "release": {
                "tag": release.get("tag_name", ""),
                "published_at": release.get("published_at", ""),
                "assets": assets,
                "has_verified_installer_candidate": any(bool(a["digest"]) for a in assets),
            },
            "install_policy": (
                "Kurulum adayı; önce yerel PC'de zaten kurulu olup olmadığı kontrol edilmeli."
                if spdx in OPEN_SOURCE_LICENSES and not repo.get("archived")
                else "Kurulum önerilmez; lisans veya depo durumu doğrulamadan geçmedi."
            ),
        }

    @staticmethod
    def find_installed_program(names: list[str]) -> list[dict[str, str]]:
        """Check Windows uninstall registry and PATH before suggesting any download."""
        wanted = [str(name).casefold() for name in names if str(name).strip()]
        found = []
        seen = set()

        for name in names:
            executable = shutil.which(str(name))
            if executable:
                key = os.path.normcase(executable)
                if key not in seen:
                    found.append({"display_name": str(name), "path": executable, "source": "PATH"})
                    seen.add(key)

        if os.name != "nt":
            return found

        try:
            import winreg
        except ImportError:
            return found

        registry_roots = (
            (winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
        )

        for hive, root_path in registry_roots:
            try:
                with winreg.OpenKey(hive, root_path) as root:
                    count = winreg.QueryInfoKey(root)[0]
                    for index in range(count):
                        try:
                            subkey_name = winreg.EnumKey(root, index)
                            with winreg.OpenKey(root, subkey_name) as entry:
                                display_name = str(winreg.QueryValueEx(entry, "DisplayName")[0])
                                display_version = str(winreg.QueryValueEx(entry, "DisplayVersion")[0]) if _has_value(entry, "DisplayVersion") else ""
                                install_location = str(winreg.QueryValueEx(entry, "InstallLocation")[0]) if _has_value(entry, "InstallLocation") else ""
                        except (OSError, WindowsError):
                            continue

                        folded = display_name.casefold()
                        if wanted and any(term in folded for term in wanted):
                            key = os.path.normcase(install_location or display_name)
                            if key not in seen:
                                found.append({
                                    "display_name": display_name,
                                    "version": display_version,
                                    "path": install_location,
                                    "source": "Windows uninstall registry",
                                })
                                seen.add(key)
            except OSError:
                continue

        return found

    def scan(self, category: str = "all", per_category: int = 3) -> dict[str, Any]:
        selected = (
            list(STAGEPULSE_CATEGORIES)
            if category == "all"
            else [category] if category in STAGEPULSE_CATEGORIES else []
        )
        if not selected:
            raise SoftwareScoutError("Bilinmeyen Stagepulse yazılım kategorisi: " + str(category))

        results = []
        for key in selected:
            spec = STAGEPULSE_CATEGORIES[key]
            data = self._get_json(
                f"{GITHUB_API}/search/repositories",
                {"q": spec["query"], "sort": "updated", "order": "desc", "per_page": max(1, min(per_category, 5))},
            )
            candidates = data.get("items") or []
            inspected = []
            for candidate in candidates[:max(1, min(per_category, 5))]:
                full_name = candidate.get("full_name")
                if not full_name:
                    continue
                try:
                    item = self.inspect_repository(full_name)
                    item["category"] = key
                    item["category_label"] = spec["label"]
                    program_names = {
                        "mcallegari/qlcplus": ["QLC+", "Q Light Controller"],
                    }.get(str(item.get("full_name", "")).casefold(), [])
                    item["installed_on_pc"] = self.find_installed_program(program_names)
                    item["local_install_status"] = (
                        "Bu yazılım bilgisayarda kurulu; yeniden indirme/kurulum önerilmez."
                        if item["installed_on_pc"]
                        else "Bilgisayarda kurulu olduğuna dair kayıt bulunamadı; bu sonuç tek başına yokluğunu kanıtlamaz."
                    )
                    item["stagepulse_services"] = spec["services"]
                    item["recommendation"] = (
                        "İncelemeye değer"
                        if item["license_approved"] and not item["archived"]
                        else "Öneri dışı"
                    )
                    inspected.append(item)
                except SoftwareScoutError as exc:
                    inspected.append({
                        "full_name": full_name,
                        "recommendation": "Doğrulanamadı",
                        "error": str(exc),
                    })
            results.extend(inspected)

        return {
            "success": True,
            "scope": "Stagepulse.com.tr hizmetleriyle ilişkili açık kaynak ses/ışık yazılımları",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
            "install_rule": (
                "Önce yerel bilgisayarda mevcut kurulum aranır. Yalnızca lisansı ve kaynağı "
                "doğrulanan, Windows uyumu kontrol edilen, imza/hash doğrulaması yapılabilen "
                "ve kullanıcı tarafından onaylanan kurulum başlatılabilir."
            ),
        }
