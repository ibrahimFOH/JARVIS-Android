"""
Command Processor for Jarvis V2
Processes commands and routes them to appropriate modules
"""

from typing import Dict, Any, Optional
import ipaddress
import os
import re
import socket
import tempfile
import unicodedata
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote
from utils.logger import get_logger
from core.intent_recognizer import IntentRecognizer
from core.validator import Validator
from personality.response_generator import ResponseGenerator
from modules import (
    ApplicationManager,
    ScreenshotManager,
    SystemController,
    FileManager,
    WindowManager
)
from datetime import datetime
from core.ai_brain import AIBrain
from core.memory_manager import MemoryManager

logger = get_logger()


def _normalize_direct_command(value: str) -> str:
    """Normalize Turkish voice transcripts before applying explicit URL aliases."""
    value = str(value or "").lower().replace("ı", "i")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9.\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _parse_image_download_command(command: str):
    """Return (matched, url) for explicit image-download commands."""
    original = str(command or "").strip()
    normalized = unicodedata.normalize("NFKD", original.casefold())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.replace("ı", "i")
    keywords = ("resim", "resmi", "gorsel", "foto", "fotograf", "image")
    action = any(k in normalized for k in keywords) and any(
        k in normalized for k in ("indir", "download", "kaydet")
    )
    if not action:
        return False, ""
    urls = re.findall(r"https?://[^\s<>\"']+", original, flags=re.IGNORECASE)
    if not urls:
        return True, ""
    return True, urls[0].rstrip(".,;)")


def _validate_public_http_url(url: str):
    """Reject local/private destinations and non-HTTP schemes before downloading."""
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        raise ValueError("Görsel bağlantısı geçerli bir HTTP/HTTPS adresi değil.")
    if parsed.username or parsed.password:
        raise ValueError("Kullanıcı adı/parola içeren bağlantılar kabul edilmiyor.")
    hostname = parsed.hostname
    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(item[4][0].split("%", 1)[0])
                for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
            ]
        except (OSError, ValueError, IndexError) as exc:
            raise ValueError("Bağlantı adresinin DNS kaydı doğrulanamadı.") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Yerel, özel veya herkese açık olmayan ağ adreslerine dosya indirilemez.")
    return parsed


def _download_image(url: str, max_bytes: int = 20 * 1024 * 1024) -> Path:
    """Download only image/* content to a safe, bounded Downloads subfolder."""
    import requests

    current_url = str(url or "").strip()
    response = None
    for _attempt in range(4):
        _validate_public_http_url(current_url)
        response = requests.get(
            current_url,
            stream=True,
            allow_redirects=False,
            timeout=(6, 25),
            headers={"User-Agent": "StagepulseJARVIS/1.0 image-downloader"},
        )
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            response.close()
            response = None
            if not location:
                raise ValueError("Görsel sunucusu geçerli bir yönlendirme adresi vermedi.")
            current_url = urljoin(current_url, location)
            continue
        break
    if response is None:
        raise ValueError("Görsel sunucusu çok fazla yönlendirme yaptı.")
    try:
        response.raise_for_status()
        content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
        extensions = {
            "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
            "image/gif": ".gif", "image/bmp": ".bmp", "image/tiff": ".tiff",
            "image/avif": ".avif", "image/x-icon": ".ico",
        }
        if content_type not in extensions:
            raise ValueError("Bağlantı bir desteklenen görsel dosyası döndürmedi (SVG/HTML kabul edilmez).")
        length = response.headers.get("Content-Length")
        if length:
            try:
                if int(length) > max_bytes:
                    raise ValueError("Görsel 20 MB sınırını aşıyor.")
            except ValueError as exc:
                if "sınırını" in str(exc):
                    raise
        folder = Path.home() / "Downloads" / "StagepulseJARVIS"
        folder.mkdir(parents=True, exist_ok=True)
        url_name = Path(unquote(urlparse(current_url).path)).name
        stem = Path(url_name).stem
        stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._")[:80] or "stagepulse-image"
        extension = extensions[content_type]
        destination = folder / (stem + extension)
        suffix = 2
        while destination.exists():
            destination = folder / (stem + "-" + str(suffix) + extension)
            suffix += 1
        fd, temp_name = tempfile.mkstemp(prefix=".stagepulse-image-", suffix=".part", dir=str(folder))
        os.close(fd)
        temp_path = Path(temp_name)
        total = 0
        try:
            with temp_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Görsel indirme sırasında 20 MB sınırını aştı.")
                    output.write(chunk)
            if total == 0:
                raise ValueError("İndirilen görsel boş.")
            temp_path.replace(destination)
            return destination
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    finally:
        response.close()


def _resolve_direct_website(command: str):
    """Return (url, label) for high-confidence website commands, or None."""
    text = _normalize_direct_command(command)
    if not re.search(r"\b(ac|acsana|aciver|acalim|gir|git|ziyaret et|open|launch|visit)\b", text):
        return None

    # Explicit role names beat generic "site" and app names.
    if any(alias in text for alias in ("benim sitem", "sitemi", "sitem", "admin", "yonetim panel")):
        return ("https://stagepulse.com.tr/admin/", "Stagepulse yönetim paneli")
    if any(alias in text for alias in ("personel", "staff portal", "staff sayf")):
        return ("https://stagepulse.com.tr/portal/", "Stagepulse personel portalı")

    # An explicit domain always means the public site, never the admin panel.
    if "stagepulse.com.tr" in text or re.search(r"\bstagepulse\s+com\s+tr\b", text):
        return ("https://stagepulse.com.tr/", "Stagepulse ana sitesi")
    if "facebook" in text:
        return ("https://www.facebook.com/", "Facebook")
    if "site" in text or "stagepulse" in text:
        return ("https://stagepulse.com.tr/", "Stagepulse ana sitesi")
    return None


class CommandProcessor:
    """Processes and executes commands"""
    
    def __init__(self):
        self.intent_recognizer = IntentRecognizer()
        self.validator = Validator()
        self.response_generator = ResponseGenerator()
        self.ai_brain = AIBrain()
        self.memory = MemoryManager()
        
        # Initialize modules
        self.app_manager = ApplicationManager()
        self.screenshot_manager = ScreenshotManager()
        self.system_controller = SystemController()
        self.file_manager = FileManager()
        self.window_manager = WindowManager()
        
        logger.info("Command processor initialized")
    
    def _ask_with_memory(self, prompt: str) -> str:
        """Use saved facts as prompt context, never as search terms."""
        try:
            facts = self.memory.context(limit=15)
        except Exception as exc:
            logger.warning("Kalıcı hafıza okunamadı: " + str(exc))
            facts = ""
        if not facts:
            return self.ai_brain.ask(prompt)
        return self.ai_brain.ask(prompt, memory_context=facts)

    def process(self, command: str) -> Dict[str, Any]:
        logger.command(command)

        # Explicit OS integrations run before generic intent/LLM routing so that
        # Git operations and dialer requests execute rather than merely being described.
        try:
            from core.agent_tools import RepositoryManager, PhoneManager
            if RepositoryManager.is_command(command):
                if not hasattr(self, "_repository_manager"):
                    self._repository_manager = RepositoryManager()
                routed = self._repository_manager.handle_command(command)
                if routed is not None:
                    return routed
            if PhoneManager.is_command(command):
                if not hasattr(self, "_phone_manager"):
                    self._phone_manager = PhoneManager()
                routed = self._phone_manager.handle_command(command)
                if routed is not None:
                    return routed
        except Exception as exc:
            logger.error("System integration failed: " + str(exc))
            return {
                "success": False,
                "response": "Bu sistem işlemi tamamlanamadı: " + str(exc),
                "intent": "system_integration",
            }

        image_request, image_url = _parse_image_download_command(command)
        if image_request:
            if not image_url:
                return {
                    "success": False,
                    "response": "İndireceğim görselin doğrudan HTTP/HTTPS bağlantısını komuta ekle. Örnek: \"resmi indir https://site.example/resim.jpg\".",
                    "intent": "download_image",
                }
            try:
                saved = _download_image(image_url)
                return {
                    "success": True,
                    "response": "Görsel indirildi: " + str(saved),
                    "intent": "download_image",
                    "filepath": str(saved),
                }
            except Exception as exc:
                logger.warning("Görsel indirme başarısız: " + str(exc))
                return {
                    "success": False,
                    "response": "Görsel indirilemedi: " + str(exc),
                    "intent": "download_image",
                }

        # Memory actions are explicit opt-in commands and bypass intent matching.
        try:
            memory_response = self.memory.handle_command(command)
        except Exception as exc:
            logger.error("Kalıcı hafıza komutu başarısız: " + str(exc))
            return {"success": False, "response": "Kalıcı hafıza işlemi başarısız oldu.", "intent": "memory"}
        if memory_response is not None:
            return {"success": True, "response": memory_response, "intent": "memory"}

        # Run explicit personal website aliases before generic app/AI recognition.
        # This prevents "Stagepulse.com.tr" from being misheard as Facebook or
        # launched through the generic application-name matcher.
        direct_target = _resolve_direct_website(command)
        if direct_target:
            url, label = direct_target
            try:
                opened = webbrowser.open(url, new=2)
                if opened:
                    return {
                        "success": True,
                        "response": f"{label} açıldı.",
                        "intent": "open_website",
                        "url": url,
                    }
                return {
                    "success": False,
                    "response": f"{label} için varsayılan tarayıcı açılamadı: {url}",
                    "intent": "open_website",
                    "url": url,
                }
            except Exception as exc:
                logger.error(f"Website open failed for {url}: {exc}")
                return {
                    "success": False,
                    "response": f"{label} açılamadı: {exc}",
                    "intent": "open_website",
                    "url": url,
                }

        intent_result = self.intent_recognizer.recognize(command)
        intent = intent_result['intent']
        confidence = intent_result['confidence']
        parameters = intent_result['parameters']
        logger.debug(f"Intent: {intent}, Confidence: {confidence:.2f}, Params: {parameters}")

        if intent == 'unknown' or confidence < 0.3:
            try:
                ai_response = self._ask_with_memory(command)
                return {'success': True, 'response': ai_response, 'intent': 'ai'}
            except Exception:
                pass
            response = self.response_generator.generate('unknown')
            return {'success': False, 'response': response, 'intent': 'unknown'}
        # Get execution method
        executor = getattr(self, f'_execute_{intent}', None)
        
        if not executor:
            # Try generic execution
            return self._execute_generic(intent, parameters)
        
        try:
            result = executor(parameters)
            return result
        except Exception as e:
            logger.error(f"Error executing command {intent}: {e}")
            response = self.response_generator.generate('error', 
                                                       intent=intent, 
                                                       error=str(e))
            return {
                'success': False,
                'response': response,
                'intent': intent
            }
    
    # Application Control
    def _execute_launch_app(self, params: Dict) -> Dict:
        target = params.get('target', '')
        result = self.app_manager.launch(target)
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='launch_app',
                details=target
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='launch_app',
                error=result['message']
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'launch_app'
        }
    
    def _execute_close_app(self, params: Dict) -> Dict:
        target = params.get('target', '')
        
        # Check for "all"
        if 'all' in target.lower():
            # Extract type (e.g., "all browsers")
            app_type = target.lower().replace('all', '').strip()
            if app_type:
                result = self.app_manager.close_all(app_type)
            else:
                result = {'success': False, 'message': 'Please specify what to close'}
        else:
            result = self.app_manager.close(target)
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='close_app',
                details=result.get('message', target)
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='close_app',
                error=result.get('message', 'Failed to close application')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'close_app'
        }
    
    def _execute_switch_app(self, params: Dict) -> Dict:
        target = params.get('target', '')
        result = self.app_manager.switch_to(target)
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='switch_app',
                details=result.get('message', '')
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='switch_app',
                error=result.get('message', 'Failed to switch application')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'switch_app'
        }
    
    def _execute_list_apps(self, params: Dict) -> Dict:
        result = self.app_manager.list_running()
        
        if result['success']:
            apps = result['apps'][:10]  # Top 10
            app_list = '\n'.join([f"- {app['name']} ({app['memory_mb']} MB)" 
                                 for app in apps])
            details = f"Running {result['count']} applications:\n{app_list}"
            response = self.response_generator.generate(
                'success',
                intent='list_apps',
                details=details
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='list_apps',
                error=result.get('message', 'Failed to list applications')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'list_apps',
            'data': result.get('apps', [])
        }
    
    # Screenshot Operations
    def _execute_screenshot(self, params: Dict) -> Dict:
        result = self.screenshot_manager.capture_full_screen()
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='screenshot',
                details=result.get('message', '')
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='screenshot',
                error=result.get('message', 'Failed to capture screenshot')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'screenshot',
            'filepath': result.get('filepath')
        }
    
    def _execute_screenshot_window(self, params: Dict) -> Dict:
        result = self.screenshot_manager.capture_window()
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='screenshot',
                details=result.get('message', '')
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='screenshot',
                error=result.get('message', 'Failed to capture window screenshot')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'screenshot_window',
            'filepath': result.get('filepath')
        }
    
    # System Control
    def _execute_volume(self, params: Dict) -> Dict:
        if 'value' in params:
            result = self.system_controller.set_volume(params['value'])
        elif 'direction' in params:
            result = self.system_controller.adjust_volume(params['direction'])
        else:
            result = {'success': False, 'message': 'No volume value or direction specified'}
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='volume',
                details=result.get('message', '')
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='volume',
                error=result.get('message', 'Failed to adjust volume')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'volume'
        }
    
    def _execute_mute(self, params: Dict) -> Dict:
        result = self.system_controller.mute()
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='mute',
                details=result.get('message', '')
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='mute',
                error=result.get('message', 'Failed to mute')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'mute'
        }
    
    def _execute_system_info(self, params: Dict) -> Dict:
        result = self.system_controller.get_system_info()
        
        if result['success']:
            cpu = result['cpu']
            memory = result['memory']
            disk = result['disk']
            battery = result.get('battery')
            
            details = f"All systems nominal, sir. "
            details += f"CPU at {cpu['percent']:.0f}%, "
            details += f"RAM usage {memory['percent']:.0f}%, "
            
            if battery:
                details += f"battery at {battery['percent']:.0f}%. "
            
            details += f"You have {disk['free']} of free storage remaining."
            
            response = self.response_generator.generate(
                'success',
                intent='system_info',
                details=details
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='system_info',
                error=result.get('message', 'Failed to get system info')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'system_info',
            'data': result if result['success'] else None
        }
    
    def _execute_lock_screen(self, params: Dict) -> Dict:
        result = self.system_controller.lock_screen()
        
        response = self.response_generator.generate(
            'success',
            intent='lock_screen'
        )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'lock_screen'
        }
    
    def _execute_shutdown(self, params: Dict) -> Dict:
        result = self.system_controller.shutdown()
        
        return {
            'success': result['success'],
            'response': "Shutting down now, sir.",
            'intent': 'shutdown'
        }
    
    def _execute_restart(self, params: Dict) -> Dict:
        result = self.system_controller.restart()
        
        return {
            'success': result['success'],
            'response': "Restarting now, sir.",
            'intent': 'restart'
        }
    
    def _execute_sleep(self, params: Dict) -> Dict:
        result = self.system_controller.sleep()
        
        return {
            'success': result['success'],
            'response': "Putting system to sleep, sir.",
            'intent': 'sleep'
        }
    
    # File Operations
    def _execute_open_file(self, params: Dict) -> Dict:
        target = params.get('target', '')
        result = self.file_manager.open_file(target)
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='open_file',
                details=result.get('message', '')
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='open_file',
                error=result.get('message', 'Failed to open file')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'open_file'
        }
    
    def _execute_find_files(self, params: Dict) -> Dict:
        query = params.get('query', '')
        result = self.file_manager.find_files(query)
        
        if result['success']:
            count = result['count']
            if count > 0:
                files = result['files'][:5]  # Show first 5
                file_list = '\n'.join([f"- {f['name']} ({f['size']})" 
                                      for f in files])
                details = f"I found {count} file(s):\n{file_list}"
                if result.get('truncated'):
                    details += "\n(Showing first 5 results)"
            else:
                details = f"I couldn't find any files matching '{query}'"
            
            response = self.response_generator.generate(
                'success',
                intent='find_files',
                details=details
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='find_files',
                error=result.get('message', 'Failed to search for files')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'find_files',
            'data': result.get('files', [])
        }
    
    def _execute_create_folder(self, params: Dict) -> Dict:
        name = params.get('name', '')
        result = self.file_manager.create_folder(name)
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='create_folder',
                details=result.get('message', '')
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='create_folder',
                error=result.get('message', 'Failed to create folder')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'create_folder'
        }
    
    def _execute_delete_file(self, params: Dict) -> Dict:
        target = params.get('target', '')
        result = self.file_manager.delete_file(target)
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='delete_file',
                details=result.get('message', '')
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='delete_file',
                error=result.get('message', 'Failed to delete file')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'delete_file'
        }
    
    # Window Management
    def _execute_maximize(self, params: Dict) -> Dict:
        result = self.window_manager.maximize_window()
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='maximize',
                details=result.get('message', '')
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='maximize',
                error=result.get('message', 'Failed to maximize window')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'maximize'
        }
    
    def _execute_minimize(self, params: Dict) -> Dict:
        result = self.window_manager.minimize_window()
        
        if result['success']:
            response = self.response_generator.generate(
                'success',
                intent='minimize',
                details=result.get('message', '')
            )
        else:
            response = self.response_generator.generate(
                'error',
                intent='minimize',
                error=result.get('message', 'Failed to minimize window')
            )
        
        return {
            'success': result['success'],
            'response': response,
            'intent': 'minimize'
        }
    
    # Information Queries
    def _execute_time(self, params: Dict) -> Dict:
        current_time = datetime.now().strftime("%I:%M %p")
        response = f"It's {current_time}, sir."
        
        return {
            'success': True,
            'response': response,
            'intent': 'time'
        }
    
    def _execute_date(self, params: Dict) -> Dict:
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        response = f"Today is {current_date}, sir."
        
        return {
            'success': True,
            'response': response,
            'intent': 'date'
        }
    
    # General Responses
    def _execute_greeting(self, params: Dict) -> Dict:
        response = self.response_generator.generate('greeting')
        return {
            'success': True,
            'response': response,
            'intent': 'greeting'
        }
    
    def _execute_status(self, params: Dict) -> Dict:
        response = self.response_generator.generate('status')
        return {
            'success': True,
            'response': response,
            'intent': 'status'
        }
    
    def _execute_help(self, params: Dict) -> Dict:
        response = self.response_generator.generate('help')
        return {
            'success': True,
            'response': response,
            'intent': 'help'
        }
    
    def _execute_thank(self, params: Dict) -> Dict:
        response = self.response_generator.generate('thank')
        return {
            'success': True,
            'response': response,
            'intent': 'thank'
        }
    
    def _execute_generic(self, intent: str, parameters: Dict) -> Dict:
        """AI fallback for recognized intents without a local executor."""
        try:
            prompt = f"Komut: {intent.replace('_', ' ')}. Parametreler: {parameters}. Kullanıcının isteğini Türkçe yanıtla."
            response = self._ask_with_memory(prompt)
            return {
                'success': True,
                'response': response,
                'intent': 'ai'
            }
        except Exception as e:
            logger.error(f"AI generic fallback error: {e}")
            return {
                'success': False,
                'response': f"PATRON, bu işlemi şu anda gerçekleştiremedim: {e}",
                'intent': intent
            }

# === JARVIS AI ROUTER V2 ===
_JARVIS_ORIGINAL_PROCESS = CommandProcessor.process

def _jarvis_ai_fallback(self, command):
    try:
        if not hasattr(self, "_jarvis_ai_brain"):
            self._jarvis_ai_brain = AIBrain()
        answer = self._ask_with_memory(command)
        return {
            "success": True,
            "response": answer,
            "intent": "ai"
        }
    except Exception as exc:
        return {
            "success": False,
            "response": f"PATRON, AI bağlantısında hata oluştu: {exc}",
            "intent": "ai_error"
        }

def _jarvis_process_with_ai(self, command):
    try:
        result = _JARVIS_ORIGINAL_PROCESS(self, command)
    except Exception:
        return _jarvis_ai_fallback(self, command)

    if not isinstance(result, dict):
        return _jarvis_ai_fallback(self, command)

    response = str(result.get("response", "") or "")
    intent = str(result.get("intent", "") or "").lower()
    success = bool(result.get("success", False))

    if success and intent not in ("unknown", "ai", "ai_error"):
        old_markers = (
            "haven't implemented",
            "have not implemented",
            "not implemented",
            "henüz uygulanmadı",
            "uygulanmadı",
            "gerçekleştiremiyorum",
        )
        if not any(x in response.lower() for x in old_markers):
            return result

    return _jarvis_ai_fallback(self, command)

CommandProcessor.process = _jarvis_process_with_ai

# ============================================================
# JARVIS FAST LOCAL PATCH
# Basit konuşma komutlarını eski intent sisteminden önce yakalar.
# ============================================================

_JARVIS_FAST_LOCAL_PATCH = True

try:
    _jarvis_original_process_command = CommandProcessor.process_command

    def _jarvis_fast_local_response(command):
        s = str(command or "").strip().lower()
        s = s.replace("?", "").replace("!", "").replace(".", "").strip()

        identity = {
            "kimsin",
            "sen kimsin",
            "kendini tanıt",
            "sen nesin",
            "jervis kimsin",
            "jarvis kimsin",
        }

        capabilities = {
            "ne yapabilirsin",
            "neler yapabilirsin",
            "neler yapabiliyorsun",
            "ne yapabiliyorsun",
            "yeteneklerin neler",
            "özelliklerin neler",
            "komutların neler",
            "ne işe yarıyorsun",
        }

        greetings = {
            "merhaba",
            "selam",
            "selam jarvis",
            "merhaba jarvis",
            "günaydın",
            "iyi akşamlar",
            "iyi geceler",
        }

        ready = {
            "hazır mısın",
            "hazır mısın jarvis",
            "hazır ol",
        }

        if s in identity:
            return {
                "success": True,
                "response": "Ben J.A.R.V.I.S., PATRON. Stagepulse için tasarlanmış Türkçe yapay zekâ asistanınızım. Ses, sahne, yazılım ve teknik işlerde size yardımcı olabilirim.",
                "intent": "ai_identity",
                "fast_local": True,
            }

        if s in capabilities:
            return {
                "success": True,
                "response": "Doğal Türkçe komutları anlayabilirim; Stagepulse dosyaları ve projeleri üzerinde çalışabilir, web bilgilerini araştırabilir, kod ve dosyalarla çalışabilir, ses işlemleri ve teknik işler konusunda yardımcı olabilirim. Ollama ile çalışan yerel AI motorunu kullanırım.",
                "intent": "ai_capabilities",
                "fast_local": True,
            }

        if s in greetings:
            return {
                "success": True,
                "response": "Hazırım PATRON. J.A.R.V.I.S. çevrimiçi.",
                "intent": "greeting",
                "fast_local": True,
            }

        if s in ready:
            return {
                "success": True,
                "response": "Hazırım PATRON.",
                "intent": "ready",
                "fast_local": True,
            }

        return None

    def _jarvis_fast_process_command(self, command):
        local = _jarvis_fast_local_response(command)
        if local is not None:
            return local
        return _jarvis_original_process_command(self, command)

    CommandProcessor.process_command = _jarvis_fast_process_command

except Exception as _jarvis_fast_patch_error:
    print("JARVIS fast patch uyarısı:", _jarvis_fast_patch_error)
