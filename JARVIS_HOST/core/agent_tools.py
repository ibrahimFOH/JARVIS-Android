# -*- coding: utf-8 -*-
import os,sys,subprocess
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
  blocked=["format ","diskpart","reg delete","shutdown","del /s","rmdir /s","cipher /w"]
  if any(x in command.lower() for x in blocked): return {"ok":False,"error":"Komut güvenlik nedeniyle engellendi."}
  r=subprocess.run(command,cwd=self.repo,shell=True,text=True,capture_output=True,timeout=timeout); return {"ok":r.returncode==0,"code":r.returncode,"stdout":r.stdout[-30000:],"stderr":r.stderr[-15000:]}
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
import shlex
import shutil
import unicodedata
from urllib.parse import urlsplit


class RepositoryManager:
    """Small, safe Git command layer scoped to one user-selected repository."""

    def __init__(self, settings_path=None):
        if settings_path:
            self.settings_path = Path(settings_path)
        else:
            base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
            self.settings_path = base / "StagepulseJARVIS" / "repository.json"
        saved = self._read_settings()
        configured = os.environ.get("JARVIS_REPOSITORY") or saved.get("repo_path", "")
        self.repo_path = Path(configured).expanduser() if configured else None

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
        return bool(re.match(r"^(?:git|repo|depo)\\b", text)) or text.startswith(
            ("değişiklikleri ekle", "degisiklikleri ekle")
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
        if re.match(r"^git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+(?:\\.git)?$", target):
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

    def handle_command(self, command):
        text = str(command or "").strip()
        low = text.lower().strip()
        bind_match = re.match(r"^(?:(?:git\\s+)?repo|depo|depoyu|github deposunu)\\s+(?:bağla|bagla|bağlan|baglan)\\s*(.*)$", text, re.IGNORECASE)
        if bind_match:
            target = bind_match.group(1).strip()
            return self.bind(target) if target else {
                "success": False,
                "response": "Klasör veya URL belirt. Örnek: repo bağla C:\\Stagepulse\\Proje ya da repo bağla https://github.com/kullanici/depo.git",
            }
        clone_match = re.match(r"^(?:repo|depo)\\s+klonla\\s+(.+)$", text, re.IGNORECASE)
        if clone_match:
            return self.bind(clone_match.group(1))
        if low in ("değişiklikleri ekle", "degisiklikleri ekle", "git add .", "git ekle hepsi", "git ekle tümü", "git ekle tumu"):
            return self._add(".")
        add_match = re.match(r"^(?:git\\s+add|git\\s+ekle|repo\\s+ekle)\\s+(.+)$", text, re.IGNORECASE)
        if add_match:
            return self._add(add_match.group(1))
        commit_match = re.match(r"^git\\s+commit\\s*(.*)$", text, re.IGNORECASE)
        if commit_match:
            return self._commit(commit_match.group(1))
        if low in ("git push", "git gönder", "git gonder", "repo gönder", "repo gonder", "değişiklikleri gönder", "degisiklikleri gonder"):
            return self._push()
        if low in ("git pull", "git çek", "git cek", "repo güncelle", "repo guncelle"):
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
        if re.match(r"^(git|repo|depo)\\b", low):
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
        return text in ("telefonu bagla", "telefon bagla", "telefonu baglan", "phone link", "phone link ac", "telefon baglantisini ac") or text.startswith(("ara ", "telefon ara ", "telefonu ara "))

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
        match = re.match(r"^(?:ara|telefon ara|telefonu ara)\\s+(.+)$", text)
        if not match:
            return None
        tail = match.group(1).strip()
        digits = "".join(char for char in tail if char.isdigit())
        if any(char.isalpha() for char in tail) or not 7 <= len(digits) <= 15:
            return {"success": False, "response": "Geçerli bir telefon numarası belirt. Örnek: ara +905321234567"}
        number = ("+" if tail.startswith("+") else "") + digits
        return self._dial(number)
