# -*- coding: utf-8 -*-
import os,sys,subprocess
import base64
from pathlib import Path
import requests
class ToolEngine:
 def __init__(self,repo=None): self.repo=Path(repo or Path.cwd()).resolve()
 def list_dir(self,path="."):
  p=Path(path).expanduser().resolve(); return {"ok":p.exists(),"path":str(p),"items":[x.name for x in p.iterdir()] if p.exists() else []}
 def read_text(self,path,max_chars=30000):
  p=Path(path).expanduser().resolve()
  if not p.is_file(): return {"ok":False,"error":"Dosya bulunamadı"}
  return {"ok":True,"path":str(p),"content":p.read_text(encoding="utf-8",errors="replace")[:max_chars]}
 def write_text(self,path,content):
  p=Path(path).expanduser().resolve(); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding="utf-8"); return {"ok":True,"path":str(p)}
 def git(self,*args):
  r=subprocess.run(["git",*args],cwd=self.repo,text=True,capture_output=True,timeout=60); return {"ok":r.returncode==0,"stdout":r.stdout[-30000:],"stderr":r.stderr[-10000:]}
 def run_safe(self,command,timeout=120):
  # This legacy helper accepted arbitrary shell text and relied on a bypassable
  # substring blocklist. Keep its interface but fail closed until a dedicated,
  # argument-based command allowlist is implemented.
  return {"ok":False,"error":"Serbest kabuk komutu çalıştırma devre dışı. Doğrulanmış JARVIS komut entegrasyonlarını kullan."}
 def fetch_text(self,url):
  if not url.lower().startswith(("http://","https://")): return {"ok":False,"error":"Sadece HTTP/HTTPS kullanılabilir."}
  r=requests.get(url,timeout=20,headers={"User-Agent":"JARVIS/1.0"}); return {"ok":r.ok,"status":r.status_code,"content":r.text[:50000]}
 def audio_separate(self,input_file):
  p=Path(input_file).expanduser().resolve()
  if not p.exists(): return {"ok":False,"error":"Dosya bulunamadı"}
  r=subprocess.run([sys.executable,"-m","demucs",str(p)],cwd=self.repo,text=True,capture_output=True,timeout=3600); return {"ok":r.returncode==0,"stdout":r.stdout[-20000:],"stderr":r.stderr[-20000:]}

# Explicitly scoped integrations used by the desktop GUI and the Android bridge.
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
import shlex
import shutil
import unicodedata
from urllib.parse import urlsplit


class TaskJournal:
    """Persistent task history for the Windows assistant; standard-library SQLite only."""

    def __init__(self, db_path=None):
        if db_path is None:
            root = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
            db_path = root / "Stagepulse" / "JARVIS" / "tasks.sqlite3"
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _connect(self):
        connection = sqlite3.connect(str(self.db_path), timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress TEXT NOT NULL DEFAULT '',
                    result TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_updated ON tasks(status, updated_at)")
            # A process killed by Windows is not allowed to remain falsely marked running.
            db.execute(
                "UPDATE tasks SET status='interrupted', progress='Uygulama kapandığı için yarıda kaldı.', updated_at=? WHERE status='running'",
                (self._now(),),
            )

    def create(self, command):
        task_id = uuid.uuid4().hex
        now = self._now()
        with self._connect() as db:
            db.execute(
                "INSERT INTO tasks(id, command, status, progress, result, created_at, updated_at) VALUES (?, ?, 'running', ?, '', ?, ?)",
                (task_id, str(command or "").strip(), "Komut yürütülüyor.", now, now),
            )
        return task_id

    def update(self, task_id, status, progress="", result=""):
        allowed = {"running", "awaiting_confirmation", "succeeded", "failed", "interrupted"}
        if status not in allowed:
            raise ValueError("Geçersiz görev durumu: " + str(status))
        with self._connect() as db:
            db.execute(
                "UPDATE tasks SET status=?, progress=?, result=?, updated_at=? WHERE id=?",
                (status, str(progress or "")[:500], str(result or "")[:6000], self._now(), str(task_id)),
            )

    def latest_awaiting(self, command):
        with self._connect() as db:
            row = db.execute(
                "SELECT id, command, status FROM tasks WHERE status='awaiting_confirmation' AND command=? ORDER BY updated_at DESC LIMIT 1",
                (str(command or "").strip(),),
            ).fetchone()
        return dict(row) if row else None

    def latest_interrupted(self):
        with self._connect() as db:
            row = db.execute(
                "SELECT id, command, status, progress, updated_at FROM tasks WHERE status='interrupted' ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def recent(self, limit=12):
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, command, status, progress, result, created_at, updated_at FROM tasks ORDER BY updated_at DESC LIMIT ?",
                (max(1, min(int(limit), 50)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self):
        # Connections are short-lived; this method exists for a consistent manager lifecycle.
        return None


class RepositoryManager:
    """Git operations and read-only GitHub research scoped to Stagepulse."""

    ALLOWED_LICENSES = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0", "GPL-3.0"})
    STAGEPULSE_SEARCH_AREAS = (
        ("Ses ölçüm ve analiz", "live sound measurement software RTA SPL impulse response phase coherence"),
        ("PA tasarımı ve kapsama", "loudspeaker system design simulator coverage prediction open source"),
        ("Stage plot ve teknik doküman", "live sound stage plot generator input list technical rider"),
        ("Ağ ses ve Dante", "audio network monitoring routing Dante AES67 open source"),
        ("Sahne ışığı ve DMX", "DMX lighting control software live event open source"),
    )

    def __init__(self, settings_path=None, ai_brain=None):
        if settings_path:
            self.settings_path = Path(settings_path)
        else:
            base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
            self.settings_path = base / "StagepulseJARVIS" / "repository.json"
        saved = self._read_settings()
        configured = os.environ.get("JARVIS_REPOSITORY") or saved.get("repo_path", "")
        self.repo_path = Path(configured).expanduser() if configured else None
        self.ai_brain = ai_brain

    def _read_settings(self):
        try:
            value = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _save_path(self):
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.settings_path.with_suffix(".tmp")
        temp.write_text(json.dumps({"repo_path": str(self.repo_path)}, indent=2), encoding="utf-8")
        os.replace(str(temp), str(self.settings_path))

    @staticmethod
    def is_command(command):
        text = str(command or "").strip().lower()
        normalized = unicodedata.normalize("NFKD", text)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return (
            bool(re.match(r"^(?:git|repo|depo|github)\b", text))
            or text.startswith(("değişiklikleri ekle", "degisiklikleri ekle"))
            or any(term in normalized for term in (
                "stagepulse icin github", "stagepulse icin acik kaynak",
                "stagepulse araclarini tara", "stagepulse araclarini arastir",
                "github repolarini tara", "github repolarini arastir",
            ))
            or ("acik kaynak" in normalized and any(word in normalized for word in ("ara", "arastir", "bul")))
            or ("github" in normalized and any(word in normalized for word in ("ara", "tara", "arastir", "bul")))
        )

    @staticmethod
    def _run_git(cwd, *args, timeout=60):
        try:
            result = subprocess.run(
                ["git", *[str(arg) for arg in args]],
                cwd=str(cwd), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                text=True, encoding="utf-8", errors="replace", timeout=timeout,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            return {"ok": result.returncode == 0, "code": result.returncode,
                    "stdout": result.stdout[-7000:], "stderr": result.stderr[-4500:]}
        except FileNotFoundError:
            return {"ok": False, "code": 127, "stdout": "", "stderr": "Git bulunamadı. Git for Windows kurulumunu kontrol et."}
        except subprocess.TimeoutExpired:
            return {"ok": False, "code": 124, "stdout": "", "stderr": "Git işlemi zaman aşımına uğradı."}

    @staticmethod
    def _github_json(path):
        response = requests.get(
            "https://api.github.com" + path,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Stagepulse-JARVIS",
            },
            timeout=18,
        )
        if response.status_code in (403, 429):
            raise RuntimeError("GitHub ücretsiz API sınırına ulaşıldı. Ücretli API kullanılmayacak.")
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _safe_repository_name(value):
        name = str(value or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name):
            raise ValueError("Depo adı owner/repo biçiminde olmalı.")
        return name

    def _search_github_repositories(self, query, per_page=3):
        prepared = requests.Request(
            "GET", "https://api.github.com/search/repositories",
            params={
                "q": query + " archived:false fork:false",
                "sort": "stars", "order": "desc",
                "per_page": max(1, min(int(per_page), 5)),
            },
        ).prepare()
        path = prepared.url.replace("https://api.github.com", "")
        data = self._github_json(path)
        return data.get("items", []) if isinstance(data, dict) else []

    def search_stagepulse_repositories(self):
        """Find public GitHub projects relevant to published Stagepulse services."""
        candidates = {}
        failures = []
        for area, query in self.STAGEPULSE_SEARCH_AREAS:
            try:
                for item in self._search_github_repositories(query, per_page=3):
                    if not isinstance(item, dict) or item.get("archived") or item.get("fork"):
                        continue
                    full_name = str(item.get("full_name", "")).strip()
                    if not full_name:
                        continue
                    license_data = item.get("license") or {}
                    spdx = str(license_data.get("spdx_id", "")).upper()
                    allowed = spdx in self.ALLOWED_LICENSES
                    candidate = candidates.setdefault(full_name, {
                        "name": full_name,
                        "description": str(item.get("description") or "Açıklama yok"),
                        "url": str(item.get("html_url") or ""),
                        "license": spdx or "BELİRSİZ",
                        "language": str(item.get("language") or "Belirtilmemiş"),
                        "stars": int(item.get("stargazers_count") or 0),
                        "updated": str(item.get("pushed_at") or ""),
                        "areas": [],
                        "license_allowed": allowed,
                        "install_recommended": False,
                        "reason": (
                            "Açık lisans bulundu; kurulumdan önce teknik ve güvenlik incelemesi zorunlu."
                            if allowed else "Lisans yok veya izin listesinde değil; kurulum önerilmez."
                        ),
                    })
                    if area not in candidate["areas"]:
                        candidate["areas"].append(area)
                    candidate["license_allowed"] = candidate["license_allowed"] and allowed
            except Exception as exc:
                failures.append(area + ": " + str(exc))
        ordered = sorted(
            candidates.values(),
            key=lambda item: (item["license_allowed"], item["stars"], item["updated"]),
            reverse=True,
        )
        evaluation = ""
        if ordered and self.ai_brain is not None:
            summary = [
                {
                    "name": item["name"],
                    "description": item["description"],
                    "license": item["license"],
                    "language": item["language"],
                    "stars": item["stars"],
                    "areas": item["areas"],
                    "url": item["url"],
                }
                for item in ordered[:10]
            ]
            prompt = (
                "Stagepulse'un PA/FOH/monitor-IEM/RF/Dante/DMX/ses ölçümü/stage plot/teknik rider "
                "hizmetleri açısından aşağıdaki açık GitHub depo adaylarını değerlendir. Yalnızca "
                "verilen açıklama, lisans, dil, ilgi alanı ve yıldız sayılarını kullan. En fazla 5 "
                "gerçekten ilgili adayı kısa gerekçeyle sırala; ne yaptığını belli olmayanı önerme. "
                "Lisansı BELİRSİZ olanı kurulum için önerme. Bu yalnızca ön elemedir; kod güvenliği "
                "ve gerçek kurulum uyumluluğu henüz doğrulanmadı.\n\nADAYLAR:\n" +
                json.dumps(summary, ensure_ascii=False)
            )
            try:
                evaluation = self.ai_brain.ask(prompt, allow_cloud=True)
                if not evaluation or evaluation.startswith("Yapay zekâ yanıtı alınamadı."):
                    evaluation = ""
            except Exception as exc:
                failures.append("JARVIS aday değerlendirmesi: " + str(exc))

        return {
            "success": bool(ordered),
            "repositories": ordered[:15],
            "failures": failures,
            "ai_evaluation": evaluation,
            "message": (
                "GitHub taraması tamamlandı. Arama sonuçları ön adaydır; lisans ve kod güvenliği onayı olmadan depo kurulmayacak."
                if ordered else "Uygun GitHub deposu bulunamadı veya ücretsiz GitHub API erişimi kullanılamıyor."
            ),
        }

    def inspect_github_repository(self, repository):
        """Read repository metadata and README without cloning or executing code."""
        full_name = self._safe_repository_name(repository)
        metadata = self._github_json("/repos/" + full_name)
        license_data = metadata.get("license") or {}
        spdx = str(license_data.get("spdx_id", "")).upper()
        license_allowed = spdx in self.ALLOWED_LICENSES
        readme = ""
        readme_error = ""
        try:
            raw = self._github_json("/repos/" + full_name + "/readme")
            encoded = raw.get("content", "")
            readme = (
                base64.b64decode(encoded).decode("utf-8", errors="replace")
                if raw.get("encoding") == "base64" else str(encoded)
            )
        except Exception as exc:
            readme_error = str(exc)

        tree_warnings = []
        try:
            tree = self._github_json(
                "/repos/" + full_name + "/git/trees/" +
                str(metadata.get("default_branch") or "main") + "?recursive=1"
            )
            paths = [
                str(item.get("path", "")) for item in tree.get("tree", [])
                if isinstance(item, dict)
            ]
            risky_names = [
                name for name in paths
                if name.lower().endswith((".exe", ".msi", ".dll", ".bat", ".cmd", ".ps1", ".sh"))
                or Path(name).name.lower() in ("setup.py", "install.py")
            ]
            if risky_names:
                tree_warnings.append(
                    "Çalıştırılabilir kurulum betiği/binary bulundu; elle kod incelemesi gerekir: " +
                    ", ".join(risky_names[:12])
                )
        except Exception as exc:
            tree_warnings.append("Dosya ağacı taranamadı: " + str(exc))

        translated = ""
        translation_error = ""
        if readme and self.ai_brain is not None:
            prompt = (
                "Aşağıdaki herkese açık GitHub README belgesini teknik anlamını koruyarak Türkçeye çevir. "
                "Başlıkları, madde işaretlerini, Markdown tablolarını ve kod bloklarını koru. "
                "Komutları, dosya yollarını, API adlarını ve lisans metnini değiştirme. "
                "Kaynakta olmayan kurulum adımı veya özellik ekleme.\n\nREADME:\n" + readme[:18000]
            )
            try:
                translated = self.ai_brain.ask(prompt)
                if not translated or translated.startswith((
                    "Yapay zekâ yanıtı alınamadı.", "Ollama bağlantısında sorun",
                    "Bulut AI kapalı;",
                )):
                    translation_error = translated or "Türkçe çeviri üretilemedi."
                    translated = ""
            except Exception as exc:
                translation_error = str(exc)

        return {
            "success": True,
            "repository": full_name,
            "description": str(metadata.get("description") or "Açıklama yok"),
            "url": str(metadata.get("html_url") or ""),
            "stars": int(metadata.get("stargazers_count") or 0),
            "language": str(metadata.get("language") or "Belirtilmemiş"),
            "license": spdx or "BELİRSİZ",
            "license_allowed": license_allowed,
            "install_recommended": license_allowed and not tree_warnings,
            "warnings": tree_warnings,
            "readme_excerpt": readme[:18000],
            "readme_translation_tr": translated,
            "translation_error": translation_error,
            "readme_error": readme_error,
            "message": (
                "Açık lisanslı depo; kod ve bağımlılık güvenlik incelemesinden sonra kuruluma aday."
                if license_allowed else "Lisans doğrulanamadı veya izin listesinde değil. Kurulum önerilmez."
            ),
        }

    def install_github_repository(self, repository, confirmed=False):
        """Clone only reviewed repositories; isolate supported Python dependencies."""
        full_name = self._safe_repository_name(repository)
        if not confirmed:
            return {
                "success": False, "intent": "github_install",
                "requires_confirmation": True,
                "pending_command": "repo kur " + full_name,
                "response": (
                    full_name + " deposu lisans ve güvenlik incelemesinden sonra ayrı bir klasöre alınacak. "
                    "Kurulum yönetici yetkisi olmadan, proje içi sanal ortamda ve yalnızca hazır wheel paketleriyle yapılır. "
                    "Devam etmek için onay gerekli."
                ),
            }

        review = self.inspect_github_repository(full_name)
        if not review.get("license_allowed"):
            return {
                "success": False, "intent": "github_install",
                "response": "Açık ve izin verilen lisans doğrulanamadı; kurulum engellendi.",
            }
        if review.get("warnings"):
            return {
                "success": False, "intent": "github_install",
                "response": "Dosya ağacı güvenlik uyarısı verdi; otomatik kurulum durduruldu.\n" +
                            "\n".join(review["warnings"]),
            }

        parent = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents" / "Stagepulse-Repositories"
        parent.mkdir(parents=True, exist_ok=True)
        destination = parent / full_name.split("/", 1)[1]
        if destination.exists():
            if not (destination / ".git").is_dir():
                return {
                    "success": False, "intent": "github_install",
                    "response": "Hedef klasör Git deposu değil; mevcut dosyalara dokunulmadı: " + str(destination),
                }
            clone_message = "Mevcut yerel depo bulundu; yeniden klonlanmadı."
        else:
            result = self._run_git(
                parent, "clone", "--depth", "1",
                "https://github.com/" + full_name + ".git", str(destination), timeout=240,
            )
            if not result["ok"]:
                return {
                    "success": False, "intent": "github_install",
                    "response": "Depo klonlanamadı: " + (result["stderr"] or result["stdout"]),
                }
            clone_message = "Kaynak kodu klonlandı."

        translated_path = destination / "README_TR.md"
        if translated_path.is_file():
            translation_status = "README_TR.md zaten var; üzerine yazılmadı."
        elif review.get("readme_translation_tr"):
            translated_path.write_text(review["readme_translation_tr"], encoding="utf-8")
            translation_status = "README Türkçeye çevrildi: " + str(translated_path)
        else:
            translation_status = "README çevirisi üretilemedi; kaynak README korundu."

        install_status = "Kaynak alındı; otomatik kurulum için doğrulanmış paket tarifi bulunamadı."
        requirements = destination / "requirements.txt"
        if requirements.is_file():
            lines = requirements.read_text(encoding="utf-8", errors="replace").splitlines()
            active = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
            unsafe = [
                line for line in active
                if line.startswith(("-", ".", "/", "\\"))
                or "://" in line or "git+" in line.lower()
                or not re.match(
                    r"^[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?(?:\s*(?:==|>=|<=|~=|!=|>|<)\s*[A-Za-z0-9.*+!_-]+)?(?:\s*#.*)?$",
                    line,
                )
            ]
            if unsafe:
                install_status = "Bağımlılık listesinde URL, yerel yol veya pip seçeneği var; otomatik kurulum yapılmadı: " + "; ".join(unsafe[:5])
            else:
                venv_path = destination / ".venv"
                if not venv_path.exists():
                    create = subprocess.run(
                        [sys.executable, "-m", "venv", str(venv_path)],
                        cwd=str(destination), stdin=subprocess.DEVNULL,
                        capture_output=True, text=True, timeout=180, shell=False,
                    )
                    if create.returncode != 0:
                        return {
                            "success": False, "intent": "github_install",
                            "response": "İzole Python ortamı oluşturulamadı: " + create.stderr[-2500:],
                        }
                python_exe = venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                pip_result = subprocess.run(
                    [str(python_exe), "-m", "pip", "install", "--only-binary=:all:", "-r", str(requirements)],
                    cwd=str(destination), stdin=subprocess.DEVNULL,
                    capture_output=True, text=True, timeout=900, shell=False,
                )
                if pip_result.returncode == 0:
                    install_status = "Bağımlılıklar yönetici yetkisi olmadan, proje içindeki .venv ortamına ve yalnızca wheel paketleriyle kuruldu."
                else:
                    install_status = (
                        "İzole kurulum tamamlanamadı; sistem Python'una dokunulmadı.\n" +
                        pip_result.stderr[-3500:]
                    )

        return {
            "success": True, "intent": "github_install", "path": str(destination),
            "response": (
                full_name + " için işlem tamamlandı.\n" + clone_message + "\n" +
                translation_status + "\n" + install_status +
                "\nLisans: " + review["license"] + "\nKaynak: " + review["url"]
            ),
        }

    def _root(self):
        if self.repo_path is None:
            return None, "Git deposu bağlı değil. Önce 'repo bağla C:\\Projeler\\Depo' veya 'repo bağla https://github.com/kullanici/depo.git' komutunu kullan."
        path = self.repo_path.expanduser().resolve()
        if not path.is_dir():
            return None, "Bağlı depo klasörü bulunamadı: " + str(path)
        result = self._run_git(path, "rev-parse", "--show-toplevel")
        if not result["ok"]:
            return None, "Bağlı klasör geçerli bir Git deposu değil: " + str(path)
        self.repo_path = Path(result["stdout"].splitlines()[0]).resolve()
        return self.repo_path, ""

    @staticmethod
    def _validate_remote(target):
        if target.lower().startswith(("https://", "http://")):
            parts = urlsplit(target)
            if not parts.hostname or parts.username or parts.password:
                return False, "Remote URL içine parola/token yazma. Git Credential Manager veya SSH anahtarı kullan."
            if parts.scheme != "https":
                return False, "Düz HTTP güvenli değil. HTTPS veya SSH kullan."
            return True, ""
        if re.match(r"^git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+(?:\.git)?$", target):
            return True, ""
        return False, ""

    def bind(self, target):
        target = str(target or "").strip().strip('"').strip("'")
        if not target:
            return {"success": False, "response": "Depo klasörü veya GitHub HTTPS/SSH URL'si belirt."}
        is_remote, reason = self._validate_remote(target)
        if reason:
            return {"success": False, "response": reason}
        if is_remote:
            name = target.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
            if ":" in name:
                name = name.rsplit(":", 1)[-1]
            name = re.sub(r"[^A-Za-z0-9._-]", "_", name) or "repository"
            parent = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents" / "Stagepulse-Repositories"
            parent.mkdir(parents=True, exist_ok=True)
            destination = parent / name
            if destination.exists():
                if (destination / ".git").exists():
                    self.repo_path = destination.resolve()
                    self._save_path()
                    return {"success": True, "response": "Mevcut yerel klon bağlandı: " + str(self.repo_path)}
                return {"success": False, "response": "Hedef klasör zaten var ve Git deposu değil: " + str(destination)}
            result = self._run_git(parent, "clone", "--", target, str(destination), timeout=300)
            if not result["ok"]:
                return {"success": False, "response": "Klonlama başarısız: " + (result["stderr"] or result["stdout"])}
            self.repo_path = destination.resolve()
            self._save_path()
            return {"success": True, "response": "Git deposu klonlandı ve bağlandı: " + str(self.repo_path)}
        folder = Path(target).expanduser()
        if not folder.is_dir():
            return {"success": False, "response": "Klasör bulunamadı: " + str(folder)}
        result = self._run_git(folder.resolve(), "rev-parse", "--show-toplevel")
        if not result["ok"]:
            return {"success": False, "response": "Seçilen klasör Git deposu değil. GitHub'dan klonla veya .git klasörü bulunan depoyu seç."}
        self.repo_path = Path(result["stdout"].splitlines()[0]).resolve()
        self._save_path()
        return {"success": True, "response": "Git deposu bağlandı: " + str(self.repo_path)}

    def _run(self, *args, timeout=60):
        root, error = self._root()
        if root is None:
            return {"success": False, "response": error}
        result = self._run_git(root, *args, timeout=timeout)
        if not result["ok"]:
            return {"success": False, "response": "Git hatası: " + (result["stderr"] or result["stdout"] or "işlem başarısız")}
        return {"success": True, "response": result["stdout"] or "Git işlemi tamamlandı."}

    def _add(self, raw):
        root, error = self._root()
        if root is None:
            return {"success": False, "response": error}
        raw = str(raw or "").strip()
        if not raw:
            return {"success": False, "response": "Dosya veya klasör belirt. Hepsi için: git add ."}
        try:
            paths = shlex.split(raw, posix=False)
        except ValueError:
            paths = [raw]
        paths = [item.strip('"').strip("'") for item in paths if item.strip()]
        if not paths or any(Path(item).is_absolute() or ".." in Path(item).parts for item in paths):
            return {"success": False, "response": "Yollar depo içindeki göreli yollar olmalı; mutlak yol ve '..' kabul edilmiyor."}
        result = self._run_git(root, "add", "--", *paths)
        if not result["ok"]:
            return {"success": False, "response": "git add başarısız: " + (result["stderr"] or result["stdout"])}
        return {"success": True, "response": "git add tamamlandı: " + ", ".join(paths)}

    def _commit(self, message):
        message = str(message or "").strip().strip('"').strip("'")
        if not message:
            return {"success": False, "response": 'Commit mesajı gerekli. Örnek: git commit "PDF hatasını düzelt"'}
        root, error = self._root()
        if root is None:
            return {"success": False, "response": error}
        staged = self._run_git(root, "diff", "--cached", "--quiet")
        if staged["code"] == 0:
            return {"success": False, "response": "Commit için staged değişiklik yok. Önce git add . veya git add dosya.py çalıştır."}
        if staged["code"] != 1:
            return {"success": False, "response": "Staged değişiklikler denetlenemedi: " + staged["stderr"]}
        result = self._run_git(root, "commit", "-m", message, timeout=120)
        if not result["ok"]:
            return {"success": False, "response": "Commit başarısız: " + (result["stderr"] or result["stdout"])}
        return {"success": True, "response": result["stdout"] or "Commit oluşturuldu."}

    def _pull(self):
        root, error = self._root()
        if root is None:
            return {"success": False, "response": error}
        status = self._run_git(root, "status", "--porcelain")
        if not status["ok"]:
            return {"success": False, "response": "Git durumu okunamadı: " + status["stderr"]}
        if status["stdout"]:
            return {"success": False, "response": "Yerel değişiklikler var. Çakışma riskini önlemek için pull durduruldu; önce commit et veya değişiklikleri yedekle."}
        return self._run("pull", "--ff-only", timeout=180)

    def _push(self):
        root, error = self._root()
        if root is None:
            return {"success": False, "response": error}
        upstream = self._run_git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        if upstream["ok"]:
            return self._run("push", timeout=180)
        return self._run("push", "--set-upstream", "origin", "HEAD", timeout=180)

    @staticmethod
    def _confirmation_result(command, reason, confirmed):
        if confirmed:
            return None
        return {
            "success": False,
            "response": reason,
            "intent": "repository_operation",
            "requires_confirmation": True,
            "pending_command": command,
        }

    def handle_command(self, command, confirmed=False):
        text = str(command or "").strip()
        low = text.lower().strip()

        normalized = unicodedata.normalize("NFKD", low)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        if normalized in (
            "github tara", "github arastir",
            "stagepulse icin arac tara", "stagepulse icin acik kaynak ara",
        ) or "stagepulse icin github" in normalized:
            result = self.search_stagepulse_repositories()
            lines = [result["message"]]
            for item in result["repositories"]:
                status = "AÇIK LİSANS / TEKNİK İNCELEME GEREKLİ" if item["license_allowed"] else "LİSANS ENGELİ"
                lines.append(
                    f'{status} | {item["name"]} | {item["license"]} | {item["stars"]} yıldız | '
                    f'{", ".join(item["areas"])} | {item["url"]}\n{item["description"]}'
                )
            if result.get("ai_evaluation"):
                lines.append("JARVIS ÖN DEĞERLENDİRMESİ:\\n" + result["ai_evaluation"])
            if result["failures"]:
                lines.append("Erişim uyarıları: " + " | ".join(result["failures"][:3]))
            return {
                "success": result["success"],
                "response": "\n\n".join(lines),
                "intent": "github_research",
                "data": result,
            }

        search_match = re.match(
            r"^(?:github|repo)\s+(?:ara|araştır|arastir)\s+(.+)$",
            text, re.IGNORECASE,
        )
        if search_match:
            query = search_match.group(1).strip().strip('"').strip("'")
            try:
                items = self._search_github_repositories(query, per_page=5)
                lines = ["GitHub arama sonuçları: " + query]
                for item in items:
                    license_data = item.get("license") or {}
                    spdx = str(license_data.get("spdx_id", "")).upper() or "BELİRSİZ"
                    eligible = spdx in self.ALLOWED_LICENSES
                    lines.append(
                        ("AÇIK LİSANS / TEKNİK İNCELEME GEREKLİ" if eligible else "LİSANS DOĞRULANMADI") +
                        f' | {item.get("full_name", "")} | {spdx} | {item.get("stargazers_count", 0)} yıldız | ' +
                        str(item.get("html_url", "")) + "\n" + str(item.get("description") or "Açıklama yok")
                    )
                return {
                    "success": True, "response": "\n\n".join(lines),
                    "intent": "github_research", "data": items,
                }
            except Exception as exc:
                return {"success": False, "response": "GitHub araması başarısız: " + str(exc), "intent": "github_research"}

        install_match = re.match(
            r"^(?:repo|depo|github)\s+kur\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)$",
            text, re.IGNORECASE,
        )
        if install_match:
            return self.install_github_repository(install_match.group(1), confirmed=confirmed)

        inspect_match = re.match(
            r"^(?:github|repo|depo)\s+(?:incele|analiz et)\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)$",
            text, re.IGNORECASE,
        )
        if inspect_match:
            try:
                result = self.inspect_github_repository(inspect_match.group(1))
            except Exception as exc:
                return {
                    "success": False, "response": "GitHub deposu incelenemedi: " + str(exc),
                    "intent": "github_inspection",
                }
            sections = [
                f'Depo: {result["repository"]}',
                f'Lisans: {result["license"]}',
                f'Dil: {result["language"]} | Yıldız: {result["stars"]}',
                result["message"],
                "Kaynak: " + result["url"],
            ]
            if result["warnings"]:
                sections.extend(result["warnings"])
            if result["readme_translation_tr"]:
                sections.append("README TÜRKÇE ÇEVİRİSİ:\n" + result["readme_translation_tr"][:9000])
            elif result["translation_error"]:
                sections.append("Çeviri durumu: " + result["translation_error"])
            return {
                "success": True, "response": "\n\n".join(sections),
                "intent": "github_inspection", "data": result,
            }
        bind_match = re.match(r"^(?:(?:git\s+)?repo|depo|depoyu|github deposunu)\s+(?:bağla|bagla|bağlan|baglan)\s*(.*)$", text, re.IGNORECASE)
        if bind_match:
            target = bind_match.group(1).strip()
            if target and self._validate_remote(target)[0]:
                pending = self._confirmation_result(
                    text, "GitHub deposu internetten klonlanacak ve yerel dosyalar oluşturulacak.", confirmed
                )
                if pending:
                    return pending
            return self.bind(target) if target else {
                "success": False,
                "response": "Klasör veya URL belirt. Örnek: repo bağla C:\\Stagepulse\\Proje ya da repo bağla https://github.com/kullanici/depo.git",
            }
        clone_match = re.match(r"^(?:repo|depo)\s+klonla\s+(.+)$", text, re.IGNORECASE)
        if clone_match:
            pending = self._confirmation_result(
                text, "Uzak Git deposu bilgisayarınıza klonlanacak ve yeni bir klasör oluşturulacak.", confirmed
            )
            if pending:
                return pending
            return self.bind(clone_match.group(1))
        if low in ("değişiklikleri ekle", "degisiklikleri ekle", "git add .", "git ekle hepsi", "git ekle tümü", "git ekle tumu"):
            pending = self._confirmation_result(
                text, "Bağlı depodaki tüm değişiklikler Git staging alanına eklenecek.", confirmed
            )
            if pending:
                return pending
            return self._add(".")
        add_match = re.match(r"^(?:git\s+add|git\s+ekle|repo\s+ekle)\s+(.+)$", text, re.IGNORECASE)
        if add_match:
            pending = self._confirmation_result(
                text, "Belirtilen dosyalar Git staging alanına eklenecek.", confirmed
            )
            if pending:
                return pending
            return self._add(add_match.group(1))
        commit_match = re.match(r"^git\s+commit\s*(.*)$", text, re.IGNORECASE)
        if commit_match:
            pending = self._confirmation_result(
                text, "Staged değişiklikler yerel Git geçmişine kalıcı bir commit olarak kaydedilecek.", confirmed
            )
            if pending:
                return pending
            return self._commit(commit_match.group(1))
        if low in ("git push", "git gönder", "git gonder", "repo gönder", "repo gonder", "değişiklikleri gönder", "degisiklikleri gonder"):
            pending = self._confirmation_result(
                text, "Yerel commit'ler uzak Git deposuna gönderilecek.", confirmed
            )
            if pending:
                return pending
            return self._push()
        if low in ("git pull", "git çek", "git cek", "repo güncelle", "repo guncelle"):
            pending = self._confirmation_result(
                text, "Uzak Git değişiklikleri bilgisayarınızdaki çalışma klasörüne alınacak.", confirmed
            )
            if pending:
                return pending
            return self._pull()
        if low in ("git status", "git durum", "git durumu", "repo", "repo durum", "repo durumu", "depo", "depo durumu", "git"):
            root, error = self._root()
            if root is None:
                return {"success": False, "response": error}
            result = self._run_git(root, "status", "--short", "--branch")
            if not result["ok"]:
                return {"success": False, "response": "Git status başarısız: " + result["stderr"]}
            return {"success": True, "response": "Depo: " + str(root) + "\\n" + (result["stdout"] or "Çalışma ağacı temiz.")}
        if low in ("git diff", "repo diff", "git fark"):
            root, error = self._root()
            if root is None:
                return {"success": False, "response": error}
            unstaged = self._run_git(root, "diff", "--stat")
            staged = self._run_git(root, "diff", "--cached", "--stat")
            if not unstaged["ok"] or not staged["ok"]:
                return {"success": False, "response": "Git diff başarısız: " + (unstaged["stderr"] or staged["stderr"])}
            return {"success": True, "response": "Çalışma ağacı:\\n" + (unstaged["stdout"] or "(boş)") + "\\n\\nStaged:\\n" + (staged["stdout"] or "(boş)")}
        if low in ("git log", "repo geçmişi", "git geçmişi", "git gecmisi"):
            return self._run("log", "-5", "--oneline", "--decorate")
        if low in ("git branch", "git dallar", "repo dalları", "repo dallari"):
            return self._run("branch", "--list")
        if re.match(r"^(git|repo|depo)\b", low):
            return {"success": False, "response": "Komutlar: repo bağla <klasör/URL>, git status, git add <dosya|.>, git commit <mesaj>, git push, git pull, git diff, git log, git branch."}
        return None


class PhoneManager:
    """Connect to Phone Link or open Android's dialer through an authorized ADB device."""

    @staticmethod
    def _normalize(text):
        value = unicodedata.normalize("NFKD", str(text or "").lower())
        value = "".join(char for char in value if not unicodedata.combining(char))
        return value.replace("ı", "i").strip()

    @classmethod
    def is_command(cls, command):
        text = cls._normalize(command)
        return text in ("telefonu bagla", "telefon bagla", "telefonu baglan", "phone link", "phone link ac", "telefon baglantisini ac") or bool(re.match(r"^(?:ara|telefon ara|telefonu ara)\s+[+0-9() .-]+$", text))

    @staticmethod
    def _adb_path():
        candidates = [shutil.which("adb")]
        for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
            root = os.environ.get(var, "")
            if root:
                candidates.append(str(Path(root) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")))
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidates.append(str(Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe"))
        return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)

    @staticmethod
    def open_phone_link():
        if os.name != "nt":
            return {"success": False, "response": "Phone Link, Windows PC üzerinde kullanılabilir."}
        try:
            os.startfile("ms-phone:")
            return {"success": True, "response": "Phone Link açıldı. Android telefonunu eşleştir; aramayı Phone Link içindeki Aramalar bölümünden başlatabilirsin."}
        except Exception:
            try:
                subprocess.Popen(["explorer.exe", r"shell:AppsFolder\\Microsoft.YourPhone_8wekyb3d8bbwe!App"], shell=False)
                return {"success": True, "response": "Phone Link uygulaması açılmaya çalışıldı. İlk bağlantıda Windows ve telefondaki eşleştirme adımlarını tamamla."}
            except Exception as exc:
                return {"success": False, "response": "Phone Link açılamadı. Başlat menüsünden Phone Link'i aç. Ayrıntı: " + str(exc)}

    @staticmethod
    def _run(args, timeout=15):
        return subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout, shell=False)

    def _dial(self, number):
        adb = self._adb_path()
        if not adb:
            self.open_phone_link()
            return {"success": False, "response": "ADB bulunamadı. Phone Link'i açıp telefonu Bluetooth ile eşleştir veya Android SDK Platform-Tools kurup USB hata ayıklamayı yetkilendir. JARVIS arama ekranını açabilir; aramayı gizlice başlatmaz."}
        try:
            listing = self._run([adb, "devices"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"success": False, "response": "ADB çalıştırılamadı: " + str(exc)}
        devices = [line.split()[0] for line in listing.stdout.splitlines()[1:] if len(line.split()) > 1 and line.split()[1] == "device"]
        if not devices:
            return {"success": False, "response": "Yetkilendirilmiş Android cihazı bulunamadı. USB hata ayıklamayı açıp telefondaki bu bilgisayara izin ver."}
        try:
            result = self._run([adb, "-s", devices[0], "shell", "am", "start", "-a", "android.intent.action.DIAL", "-d", "tel:" + number], timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"success": False, "response": "Telefonda arama ekranı açılamadı: " + str(exc)}
        if result.returncode != 0:
            return {"success": False, "response": "Telefon arama ekranı açılamadı: " + (result.stderr or result.stdout)[:900]}
        return {"success": True, "response": "Telefonda numara hazırlandı: " + number + ". Aramayı cihazdaki arama düğmesiyle sen onayla."}

    def handle_command(self, command):
        raw = str(command or "").strip()
        text = self._normalize(raw)
        if text in ("telefonu bagla", "telefon bagla", "telefonu baglan", "phone link", "phone link ac", "telefon baglantisini ac"):
            return self.open_phone_link()
        match = re.match(r"^(?:ara|telefon ara|telefonu ara)\s+(.+)$", text)
        if not match:
            return None
        tail = match.group(1).strip()
        digits = "".join(char for char in tail if char.isdigit())
        if any(char.isalpha() for char in tail) or not 7 <= len(digits) <= 15:
            return {"success": False, "response": "Geçerli bir telefon numarası belirt. Örnek: ara +905321234567"}
        number = ("+" if tail.startswith("+") else "") + digits
        return self._dial(number)
