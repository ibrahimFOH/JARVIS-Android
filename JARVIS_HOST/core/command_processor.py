"""
Command Processor for Jarvis V2
Processes commands and routes them to appropriate modules
"""

from typing import Dict, Any, Optional
import hashlib
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


def _open_pdf_from_command(command: str):
    """Open a user-specified PDF in the operating system's default viewer."""
    original = str(command or "").strip()
    match = re.match(r"^(?:pdf\s+aç|pdf\s+ac|pdf\s+open|aç\s+pdf|ac\s+pdf)\s+(.+)$", original, flags=re.IGNORECASE)
    if not match:
        return None
    target = match.group(1).strip().strip('"').strip("'")
    path = Path(target).expanduser()
    if path.suffix.lower() != ".pdf":
        return {"success": False, "response": "PDF aç komutuna .pdf dosyasının tam yolunu ekle. Örnek: pdf aç C:\\Belgeler\\rapor.pdf", "intent": "open_pdf"}
    if not path.is_file():
        return {"success": False, "response": "PDF dosyası bulunamadı: " + str(path), "intent": "open_pdf"}
    try:
        resolved = path.resolve()
        if os.name == "nt":
            os.startfile(str(resolved))
        else:
            webbrowser.open(resolved.as_uri())
        return {"success": True, "response": "PDF varsayılan görüntüleyicide açılıyor: " + str(resolved), "intent": "open_pdf"}
    except Exception as exc:
        logger.warning("PDF harici görüntüleyicide açılamadı: " + str(exc))
        return {"success": False, "response": "PDF görüntüleyici açılamadı: " + str(exc), "intent": "open_pdf"}


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
    url_key = hashlib.sha256(current_url.encode("utf-8")).hexdigest()[:12]
    folder = Path.home() / "Downloads" / "StagepulseJARVIS"
    if folder.is_dir():
        url_name = Path(unquote(urlparse(current_url).path)).name
        cached_stem = Path(url_name).stem
        cached_stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", cached_stem).strip(" ._")[:80] or "stagepulse-image"
        cached = list(folder.glob(cached_stem + "-" + url_key + ".*"))
        if cached and cached[0].is_file() and cached[0].stat().st_size > 0:
            return cached[0]
        # Existing pre-cache downloads are reused by their original filename.
        for extension in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".avif", ".ico"):
            legacy = folder / (cached_stem + extension)
            if legacy.is_file() and legacy.stat().st_size > 0:
                return legacy
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
        folder.mkdir(parents=True, exist_ok=True)
        url_name = Path(unquote(urlparse(current_url).path)).name
        stem = Path(url_name).stem
        stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._")[:80] or "stagepulse-image"
        extension = extensions[content_type]
        destination = folder / (stem + "-" + url_key + extension)
        if destination.is_file() and destination.stat().st_size > 0:
            return destination
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
        from core.agent_tools import TaskJournal
        self.task_journal = TaskJournal()
        
        logger.info("Command processor initialized")
    
    def _collect_stagepulse_context(self, command: str) -> tuple[str, bool]:
        """Search local project records first; never download a file during discovery."""
        normalized = _normalize_direct_command(command)
        stagepulse_terms = (
            "rider", "stage plot", "stageplan", "pa tasarim", "ses sistemi",
            "spl", "dugun", "salon", "kir bahcesi", "ekipman listesi",
            "teklif", "sistem raporu", "sound system", "monitor", "iem",
        )
        if not any(term in normalized for term in stagepulse_terms):
            return "", False

        names = re.findall(
            r"[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü]*(?:\s+[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü]*){1,3}",
            str(command or ""),
        )
        names = list(dict.fromkeys(name.strip() for name in names if len(name.strip()) > 2))
        found = {}
        for name in names:
            for query in (name, name.split()[0]):
                try:
                    result = self.file_manager.find_files(query)
                except Exception as exc:
                    logger.warning("Yerel proje dosyası aranamadı: " + str(exc))
                    continue
                for item in result.get("files", []):
                    path = str(item.get("path", ""))
                    if path:
                        found.setdefault(path, item)
                    if len(found) >= 12:
                        break
                if len(found) >= 12:
                    break
            if len(found) >= 12:
                break

        sections = [
            "STAGEPULSE GÖREV AKIŞI:",
            "1. Önce bilgisayardaki mevcut proje dosyalarını ve arşivi kullan; tekrar indirme yapma.",
            "2. Kroki, ölçü, envanter, önceki teklif ve raporlardaki doğrulanmış bilgileri ayır.",
            "3. Eksik üretici verilerini yalnızca üreticinin/resmî kaynağın sayfasından araştır.",
            "4. Mekân geometrisi, kapsama, açı, SPL ve ekipman uyumluluğunu ayrı ayrı doğrula.",
            "5. İstenen rider, stage plot, ekipman listesi, maliyet ve sistem raporu çıktısını hazırla.",
            "6. Kaynak, tarih, varsayım, bilinmeyen ve gerçek ölçüm/tahmin ayrımını raporla.",
            "7. Araştırmayla bulunabilen bilgileri kullanıcıya sorma; yalnızca hesabı etkileyen kritik eksikleri sor.",
            "Dosya bulunamazsa varmış gibi davranma; indirme gerekip gerekmediğini kaynak doğrulamasından sonra kararlaştır.",
        ]
        if not names:
            sections.append("Proje/kurum adı komuttan güvenilir biçimde çıkarılamadı; kullanıcıdan tekrar istemeden önce mevcut komut bağlamında ara.")
        else:
            sections.append("Tespit edilen proje/kurum adları: " + " | ".join(names))

        # Search public web information using names from the user's command only.
        # Never send local document contents, customer notes, measurements or prices to search engines.
        public_research = []
        public_identifiers = list(names[:3])
        model_ids = re.findall(r"\b[A-Z]{2,}[A-Za-z0-9-]{1,}\b", str(command or ""))
        for model_id in model_ids[:3]:
            if model_id not in public_identifiers:
                public_identifiers.append(model_id)
        for identifier in public_identifiers[:4]:
            try:
                query = f'"{identifier}" resmi site adres kapasite teknik özellik'
                excerpt = self.ai_brain._web(query)
                if excerpt:
                    public_research.append(
                        "ARAMA TERİMİ: " + identifier + "\n" + str(excerpt)[:2200]
                    )
            except Exception as exc:
                logger.warning("Kamuya açık bilgi araştırması başarısız (%s): %s", identifier, exc)
        if public_research:
            sections.append(
                "KAMUYA AÇIK WEB ARAMA SONUÇLARI (arama motoru metni; resmî kaynakla ayrıca doğrula):\n" +
                "\n\n".join(public_research)
            )
        else:
            sections.append("KAMUYA AÇIK WEB ARAŞTIRMASI: Sonuç alınamadı veya ağ erişimi yok. Doğrulanmamış bilgileri gerçek kabul etme.")

        if not found:
            sections.append("YEREL DOSYA TARAMASI: Belirtilen adlarla eşleşen dosya bulunamadı. Bu, tüm disklerin tarandığı anlamına gelmez; yapılandırılmış arama konumları kullanıldı.")
        else:
            sections.append("YEREL DOSYA TARAMASI: " + str(len(found)) + " mevcut dosya bulundu. Bu dosyaları yeniden indirme.")
        total_chars = 0
        local_images = []
        for path, item in found.items():
            file_path = Path(path)
            sections.append(
                f"\nDOSYA: {file_path.name}\nYOL: {file_path}\nBOYUT: {item.get('size', 'bilinmiyor')}"
            )
            suffix = file_path.suffix.lower()
            extracted = ""
            try:
                if suffix == ".pdf":
                    from pypdf import PdfReader
                    reader = PdfReader(str(file_path))
                    pages = []
                    for page in reader.pages[:10]:
                        pages.append(page.extract_text() or "")
                    extracted = "\n".join(pages)
                    if not extracted.strip():
                        sections.append("PDF metin içermiyor veya taranmış görüntü; görsel incelemesi/OCR gerekli.")
                elif suffix in (".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml", ".ini"):
                    extracted = file_path.read_text(encoding="utf-8", errors="replace")
                elif suffix in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"):
                    local_images.append(str(file_path))
                    sections.append("GÖRSEL: Dosya bulundu; içerik yalnızca yerel Ollama görsel modeli destekliyorsa incelenecek.")
            except Exception as exc:
                sections.append("DOSYA OKUMA UYARISI: " + str(exc))
            if extracted:
                remaining = max(0, 14000 - total_chars)
                if remaining:
                    content = extracted[:remaining]
                    sections.append("DOSYA İÇERİĞİ (çıkarılmış metin):\n" + content)
                    total_chars += len(content)
                else:
                    sections.append("Metin bağlamı sınırına ulaşıldı; dosya bulundu ancak içeriğinin tamamı modele aktarılmadı.")
            if total_chars >= 14000:
                break
        if local_images:
            try:
                vision_result = self.ai_brain.analyze_local_images(
                    local_images,
                    "Bu Stagepulse proje krokisini incele. Ölçüler, sahne, PA noktaları, seyirci alanı, engeller, girişler ve okunabilen notları ayır. Görülmeyen ölçüyü tahmin etme.",
                )
                sections.append("YEREL GÖRSEL ANALİZİ:\n" + str(vision_result))
            except Exception as exc:
                sections.append("YEREL GÖRSEL ANALİZİ BAŞARISIZ: " + str(exc))
        return "\n".join(sections), True

    def _ask_with_memory(self, prompt: str) -> str:
        """Use specialist guidance and local project files without sending private data to cloud."""
        try:
            facts = self.memory.context(limit=15)
        except Exception as exc:
            logger.warning("Kalıcı hafıza okunamadı: " + str(exc))
            facts = ""

        task_context = ""
        private_task = False
        try:
            task_context, private_task = self._collect_stagepulse_context(prompt)
        except Exception as exc:
            logger.warning("Stagepulse görev bağlamı hazırlanamadı: " + str(exc))

        expert_context = ""
        try:
            from core.specialist_agents import prepare_expert_task, route_agent
            agent_id = route_agent(prompt)
            normalized = _normalize_direct_command(prompt)
            if not agent_id and private_task:
                agent_id = "audio_system_designer"
            if agent_id:
                instructions, tool_output = prepare_expert_task(agent_id, prompt)
                expert_context = instructions
                if tool_output:
                    expert_context += "\n\nDOĞRULANABİLİR HESAPLAMA SONUCU:\n" + tool_output
        except Exception as exc:
            logger.warning("Uzman görev yönlendirmesi başarısız: " + str(exc))

        context_parts = [part for part in (facts, task_context) if part]
        memory_context = "\n\n".join(context_parts)
        task_prompt = str(prompt or "")
        if expert_context:
            task_prompt = expert_context + "\n\nKULLANICI EMRİ:\n" + task_prompt

        # Project, venue, client, rider and local archive content are private by default.
        return self.ai_brain.ask(
            task_prompt,
            memory_context=memory_context,
            allow_cloud=not private_task,
        )

    @staticmethod
    def _is_stagepulse_document_request(command: str) -> bool:
        normalized = _normalize_direct_command(command)
        subject_terms = (
            "stagepulse", "dugun salonu", "kir bahcesi", "mekan",
            "pa", "ses sistemi", "rider", "stage plot", "stageplot",
            "input list", "ekipman", "teklif", "rapor", "spl",
            "monitor", "iem", "dante", "rf", "sistem tasarim",
        )
        action_terms = (
            "hazirla", "olustur", "cikar", "tasarla", "hesapla",
            "duzenle", "guncelle", "planla", "karsilastir", "yaz",
        )
        return (
            any(term in normalized for term in subject_terms)
            and any(term in normalized for term in action_terms)
        )

    @staticmethod
    def _should_create_stagepulse_pdf(command: str) -> bool:
        normalized = _normalize_direct_command(command)
        report_terms = (
            "rapor", "teklif", "rider", "stage plot", "stageplot",
            "input list", "ekipman listesi", "sistem listesi",
            "pa tasarim raporu", "ses sistemi raporu", "dugun salonu",
            "kir bahcesi", "mekan",
        )
        return (
            any(term in normalized for term in report_terms)
            or CommandProcessor._is_stagepulse_document_request(command)
        )

    def _create_stagepulse_pdf(self, command: str, content: str) -> Path:
        """Create a Turkish, branded PDF only for explicit Stagepulse deliverable requests."""
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
            Spacer, Table, TableStyle,
        )
        from xml.sax.saxutils import escape

        base = Path.home() / "Documents" / "Stagepulse" / "Raporlar"
        base.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "_", _normalize_direct_command(command)).strip("_")[:44] or "teknik_rapor"
        destination = base / f"{slug}_{stamp}.pdf"
        suffix = 2
        while destination.exists():
            destination = base / f"{slug}_{stamp}_{suffix}.pdf"
            suffix += 1

        regular_font = "Helvetica"
        bold_font = "Helvetica-Bold"
        font_candidates = (
            (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
             Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arialbd.ttf"),
            (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
             Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        )
        for regular_path, bold_path in font_candidates:
            if regular_path.is_file() and bold_path.is_file():
                try:
                    pdfmetrics.registerFont(TTFont("StagepulseTR", str(regular_path)))
                    pdfmetrics.registerFont(TTFont("StagepulseTR-Bold", str(bold_path)))
                    regular_font, bold_font = "StagepulseTR", "StagepulseTR-Bold"
                    break
                except Exception as exc:
                    logger.warning("Türkçe PDF fontu yüklenemedi: " + str(exc))

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="SPTitle", parent=styles["Title"], fontName=bold_font,
            fontSize=19, leading=24, textColor=colors.HexColor("#D6B23C"),
            alignment=TA_LEFT, spaceAfter=7 * mm,
        ))
        styles.add(ParagraphStyle(
            name="SPH1", parent=styles["Heading1"], fontName=bold_font,
            fontSize=14, leading=18, textColor=colors.HexColor("#8C7220"),
            spaceBefore=5 * mm, spaceAfter=2 * mm, keepWithNext=True,
        ))
        styles.add(ParagraphStyle(
            name="SPH2", parent=styles["Heading2"], fontName=bold_font,
            fontSize=11, leading=15, textColor=colors.HexColor("#343434"),
            spaceBefore=3 * mm, spaceAfter=1.5 * mm, keepWithNext=True,
        ))
        styles.add(ParagraphStyle(
            name="SPBody", parent=styles["BodyText"], fontName=regular_font,
            fontSize=9.2, leading=13.2, textColor=colors.HexColor("#202020"),
            alignment=TA_LEFT, spaceAfter=2.3 * mm,
        ))
        styles.add(ParagraphStyle(
            name="SPBullet", parent=styles["BodyText"], fontName=regular_font,
            fontSize=9, leading=12.5, leftIndent=5 * mm, firstLineIndent=-3 * mm,
            textColor=colors.HexColor("#202020"), spaceAfter=1.2 * mm,
        ))
        styles.add(ParagraphStyle(
            name="SPMeta", parent=styles["BodyText"], fontName=regular_font,
            fontSize=8, leading=11, textColor=colors.HexColor("#666666"),
            spaceAfter=1.8 * mm,
        ))

        story = [
            Paragraph("STAGEPULSE", styles["SPH2"]),
            Paragraph(escape(str(command or "Teknik Rapor")), styles["SPTitle"]),
            Paragraph("Tarih: " + datetime.now().strftime("%d.%m.%Y %H:%M"), styles["SPMeta"]),
            Paragraph("Belge türü: Otomatik hazırlanmış teknik çalışma taslağı", styles["SPMeta"]),
            HRFlowable(width="100%", thickness=1.1, color=colors.HexColor("#D6B23C"), spaceAfter=5 * mm),
        ]

        raw_lines = str(content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        in_code = False
        code_lines = []
        index = 0
        while index < len(raw_lines):
            raw = raw_lines[index].rstrip()
            stripped = raw.strip()
            if stripped.startswith("```"):
                if not in_code:
                    in_code = True
                    code_lines = []
                else:
                    story.append(Paragraph(
                        "<br/>".join(escape(line) for line in code_lines),
                        ParagraphStyle(
                            "SPCode" + str(index), parent=styles["SPBody"],
                            fontName="Courier", fontSize=7.5, leading=10,
                            backColor=colors.HexColor("#F2F2F2"),
                            borderPadding=5, leftIndent=4 * mm,
                        ),
                    ))
                    story.append(Spacer(1, 2 * mm))
                    in_code = False
                index += 1
                continue
            if in_code:
                code_lines.append(raw)
                index += 1
                continue
            if not stripped:
                story.append(Spacer(1, 1.2 * mm))
                index += 1
                continue
            if stripped.startswith("|") and "|" in stripped[1:]:
                table_lines = []
                while index < len(raw_lines) and raw_lines[index].strip().startswith("|"):
                    table_lines.append(raw_lines[index].strip())
                    index += 1
                rows = []
                for table_line in table_lines:
                    cells = [cell.strip() for cell in table_line.strip("|").split("|")]
                    if cells and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells):
                        continue
                    rows.append([Paragraph(escape(cell), styles["SPMeta"]) for cell in cells])
                if rows:
                    max_cols = max(len(row) for row in rows)
                    rows = [row + [Paragraph("", styles["SPMeta"])] * (max_cols-len(row)) for row in rows]
                    table = Table(rows, repeatRows=1, hAlign="LEFT")
                    table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#171717")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, -1), regular_font),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C5C5C5")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    story.extend([table, Spacer(1, 3 * mm)])
                continue
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                heading = stripped[level:].strip()
                story.append(Paragraph(escape(heading), styles["SPH1" if level == 1 else "SPH2"]))
            elif re.match(r"^[-*•]\s+", stripped):
                story.append(Paragraph("• " + escape(re.sub(r"^[-*•]\s+", "", stripped)), styles["SPBullet"]))
            elif re.match(r"^\d+[.)]\s+", stripped):
                story.append(Paragraph(escape(stripped), styles["SPBullet"]))
            else:
                story.append(Paragraph(escape(stripped), styles["SPBody"]))
            index += 1

        story.extend([
            Spacer(1, 5 * mm),
            HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#D6B23C"), spaceAfter=2 * mm),
            Paragraph(
                "Not: Bu belge, sağlanan dosyalar ve araştırma çıktıları üzerinden hazırlanmış bir çalışma taslağıdır. "
                "Saha ölçümü, fiziksel kurulum veya kalibrasyon yapılmadıkça gerçek ölçüm sonucu olarak kullanılmamalıdır. "
                "Doğrulanmamış ölçü, fiyat, üretici verisi ve varsayımlar ayrıca belirtilmelidir.",
                styles["SPMeta"],
            ),
        ])

        def draw_page(canvas, document):
            canvas.saveState()
            width, height = A4
            canvas.setFillColor(colors.HexColor("#101010"))
            canvas.rect(0, height - 8 * mm, width, 8 * mm, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor("#D6B23C"))
            canvas.setFont(bold_font, 8)
            canvas.drawString(17 * mm, height - 5.4 * mm, "STAGEPULSE  /  SES MÜHENDİSLİĞİ")
            canvas.setFillColor(colors.HexColor("#777777"))
            canvas.setFont(regular_font, 7)
            canvas.drawString(17 * mm, 10 * mm, "JARVIS tarafından oluşturuldu | Teknik doğrulama gerektirir")
            canvas.drawRightString(width - 17 * mm, 10 * mm, f"Sayfa {document.page}")
            canvas.restoreState()

        document = SimpleDocTemplate(
            str(destination), pagesize=A4,
            rightMargin=17 * mm, leftMargin=17 * mm,
            topMargin=18 * mm, bottomMargin=17 * mm,
            title=str(command or "Stagepulse Teknik Rapor"),
            author="Stagepulse JARVIS",
        )
        document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
        if not destination.is_file() or destination.stat().st_size < 1200:
            raise RuntimeError("PDF çıktısı doğrulanamadı veya dosya beklenenden küçük.")
        with destination.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise RuntimeError("Oluşturulan dosya geçerli PDF imzasına sahip değil.")
        return destination

    def process(self, command: str, confirmed: bool = False) -> Dict[str, Any]:
        """Track every command durably and recover pending confirmations after restart."""
        normalized = _normalize_direct_command(command)
        if not hasattr(self, "task_journal") or self.task_journal is None:
            from core.agent_tools import TaskJournal
            self.task_journal = TaskJournal()
        if normalized in (
            "gorevlerim", "islerim", "acik islerim", "yarim kalan isler",
            "son gorevler", "gorev gecmisim", "islerimin durumu",
        ):
            rows = self.task_journal.recent(15)
            if not rows:
                return {"success": True, "response": "Henüz kayıtlı görev yok.", "intent": "task_journal"}
            labels = {
                "running": "ÇALIŞIYOR",
                "awaiting_confirmation": "ONAY BEKLİYOR",
                "succeeded": "TAMAMLANDI",
                "failed": "HATA",
                "interrupted": "YARIDA KALDI",
            }
            output = ["SON GÖREVLER"]
            for task in rows:
                output.append(
                    f'[{labels.get(task["status"], task["status"].upper())}] '
                    f'{task["command"]} | {task["updated_at"]}'
                )
                if task.get("progress"):
                    output.append("  " + task["progress"])
            return {"success": True, "response": "\n".join(output), "intent": "task_journal", "tasks": rows}

        if normalized in ("devam et", "yarim kalan isi yeniden baslat", "yarim kalan ise devam et"):
            task = self.task_journal.latest_interrupted()
            if not task:
                return {"success": True, "response": "Yeniden başlatılmayı bekleyen yarım görev bulunamadı.", "intent": "task_journal"}
            self.task_journal.update(
                task["id"], "awaiting_confirmation",
                "Önceki komut kaldığı adımdan değil, baştan yeniden çalıştırılacak.",
            )
            return {
                "success": False,
                "response": (
                    "Yarım kalan görev bulundu:" + chr(10) + task["command"] +
                    chr(10) + chr(10) +
                    "Bu sürüm görevi son teknik adımdan değil, komutun başından yeniden çalıştıracak. "
                    "Önceki işlem dosya oluşturmuş olabilir. Devam etmek için onay ver."
                ),
                "intent": "task_resume",
                "requires_confirmation": True,
                "pending_command": task["command"],
                "task_id": task["id"],
            }

        task = self.task_journal.latest_awaiting(command) if confirmed else None
        if task:
            task_id = task["id"]
            self.task_journal.update(task_id, "running", "Kullanıcı onayı alındı; komut yürütülüyor.")
        else:
            task_id = self.task_journal.create(command)

        try:
            result = self._process_untracked(command, confirmed=confirmed)
            if not isinstance(result, dict):
                result = {"success": False, "response": str(result), "intent": "unknown"}
            if result.get("requires_confirmation"):
                status, progress = "awaiting_confirmation", "Geri alınamaz veya sistem değişikliği için onay bekleniyor."
            elif result.get("success"):
                status, progress = "succeeded", "Komut tamamlandı."
            else:
                status, progress = "failed", "Komut hata verdi veya doğrulama başarısız oldu."
            self.task_journal.update(
                task_id, status, progress=progress,
                result=str(result.get("response", "")),
            )
            payload = dict(result)
            payload.setdefault("task_id", task_id)
            return payload
        except Exception as exc:
            logger.exception("Görev yürütme başarısız: " + str(exc))
            self.task_journal.update(task_id, "failed", "Beklenmeyen hata.", str(exc))
            return {
                "success": False,
                "response": "Görev yürütülürken hata oluştu: " + str(exc),
                "intent": "task_execution",
                "task_id": task_id,
            }

    def _process_untracked(self, command: str, confirmed: bool = False) -> Dict[str, Any]:
        logger.command(command)

        # Explicit OS integrations run before generic intent/LLM routing so that
        # Git operations and dialer requests execute rather than merely being described.
        try:
            from core.agent_tools import RepositoryManager, PhoneManager
            if RepositoryManager.is_command(command):
                if not hasattr(self, "_repository_manager"):
                    self._repository_manager = RepositoryManager(ai_brain=self.ai_brain)
                routed = self._repository_manager.handle_command(command, confirmed=confirmed)
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

        pdf_result = _open_pdf_from_command(command)
        if pdf_result is not None:
            return pdf_result

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

        # Stagepulse engineering deliverables go through the specialist pipeline
        # directly, instead of being misrouted as ordinary desktop intents.
        if self._is_stagepulse_document_request(command):
            try:
                ai_response = self._ask_with_memory(command)
                result = {
                    "success": True,
                    "response": ai_response,
                    "intent": "stagepulse_deliverable",
                }
                if self._should_create_stagepulse_pdf(command):
                    report_path = self._create_stagepulse_pdf(command, ai_response)
                    result["report_path"] = str(report_path)
                    result["response"] = str(ai_response).rstrip() + "\n\nPDF taslağı oluşturuldu: " + str(report_path)
                return result
            except Exception as exc:
                logger.exception("Stagepulse teknik görev yürütülemedi: " + str(exc))
                return {
                    "success": False,
                    "response": "Stagepulse teknik görevi tamamlanamadı: " + str(exc),
                    "intent": "stagepulse_deliverable",
                }

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

        if intent != 'unknown' and confidence >= 0.3:
            is_valid, validation_error, warning = self.validator.validate(intent, parameters)
            if not is_valid:
                return {
                    'success': False,
                    'response': validation_error or 'Bu işlem güvenlik denetiminden geçmedi.',
                    'intent': intent,
                    'requires_confirmation': False,
                }

            confirmation_required = self.validator.requires_confirmation(intent) or bool(warning)
            if confirmation_required and not confirmed:
                return {
                    'success': False,
                    'response': warning or 'Bu işlem bilgisayarınızda değişiklik yapacak. Devam etmek için onay verin.',
                    'intent': intent,
                    'requires_confirmation': True,
                    'pending_command': command,
                }

        if intent == 'unknown' or confidence < 0.3:
            try:
                ai_response = self._ask_with_memory(command)
                result = {'success': True, 'response': ai_response, 'intent': 'ai'}
                if self._should_create_stagepulse_pdf(command):
                    try:
                        report_path = self._create_stagepulse_pdf(command, ai_response)
                        result["report_path"] = str(report_path)
                        result["response"] = str(ai_response).rstrip() + "\n\nPDF taslağı oluşturuldu: " + str(report_path)
                    except Exception as report_error:
                        result["success"] = False
                        result["report_error"] = str(report_error)
                        result["response"] = str(ai_response).rstrip() + "\n\nPDF oluşturulamadı: " + str(report_error)
                return result
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

def _jarvis_process_with_ai(self, command, confirmed=False):
    try:
        result = _JARVIS_ORIGINAL_PROCESS(self, command, confirmed=confirmed)
    except Exception:
        return _jarvis_ai_fallback(self, command)

    if not isinstance(result, dict):
        return _jarvis_ai_fallback(self, command)

    # Never turn a denied or confirmation-gated system action into an AI success.
    # Preserve the original pending command and pass explicit confirmation through
    # every wrapper layer.
    if result.get("requires_confirmation") is True:
        return result
    intent = str(result.get("intent", "") or "").lower()
    if not result.get("success", False) and intent in {
        "delete_file", "shutdown", "restart", "close_app",
        "system_integration", "security_denied",
    }:
        return result

    response = str(result.get("response", "") or "")
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
    # CommandProcessor giriş noktası process(); process_command denetleyici Jarvis sınıfındadır.
    _jarvis_original_process = CommandProcessor.process

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

    def _jarvis_fast_process_command(self, command, confirmed=False):
        local = _jarvis_fast_local_response(command)
        if local is not None:
            return local
        return _jarvis_original_process(self, command, confirmed=confirmed)

    CommandProcessor.process = _jarvis_fast_process_command

except Exception as _jarvis_fast_patch_error:
    print("JARVIS fast patch uyarısı:", _jarvis_fast_patch_error)
