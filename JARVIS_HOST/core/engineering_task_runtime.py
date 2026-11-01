"""Stagepulse icin yerel-oncelikli muhendislik gorev yurutucusu."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
import json
import os
import re
import time
import unicodedata
import uuid
import zipfile
import xml.etree.ElementTree as ET


_TEXT_TYPES = {".pdf", ".docx", ".txt", ".md", ".csv", ".json"}
_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


def _norm(value: str) -> str:
    value = str(value or "").casefold().replace("ı", "i")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def _slug(value: str) -> str:
    return re.sub(r"_+", "_", _norm(value).replace(" ", "_")).strip("_")[:54] or "stagepulse_is"


class EngineeringTaskRuntime:
    """Kullanici emrini uzmanlik, yerel kaynak, arastirma ve rapor adimlarina baglar."""

    ACTIONS = ("hazirla", "olustur", "tasarla", "planla", "duzenle", "raporla", "hesapla", "cikar")
    DOMAIN = (
        "rider", "input list", "stage plot", "stageplot", "sahne plani",
        "ses sistemi", "pa tasarim", "line array", "spl", "desibel",
        "dante", "iem", "monitor", "rf", "dmx", "teknik teklif",
        "sistem raporu", "dugun salonu", "kir bahcesi", "etkinlik",
        "konser", "festival", "sahne",
    )

    def __init__(self, ai_brain, file_manager, memory=None):
        self.ai_brain = ai_brain
        self.file_manager = file_manager
        self.memory = memory
        app_data = os.environ.get("APPDATA")
        base = Path(app_data) if app_data else Path.home() / ".stagepulse-jarvis"
        self.ledger_dir = base / "StagepulseJARVIS" / "tasks"

    @classmethod
    def is_work_order(cls, command: str) -> bool:
        text = _norm(command)
        return any(word in text for word in cls.ACTIONS) and any(term in text for term in cls.DOMAIN)

    @staticmethod
    def _entities(command: str) -> list[str]:
        pattern = re.compile(
            r"(?<![A-Za-zÇĞİÖŞÜçğıöşü])[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9&.-]*"
            r"(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9&.-]*){0,4}"
        )
        excluded = {"Stagepulse", "Jarvis", "Hazırla", "Oluştur", "Rapor", "Teknik", "Sistem", "Ses"}
        values, seen = [], set()
        for match in pattern.finditer(str(command or "")):
            value = match.group(0).strip(" .,'\\"")
            if not value or value in excluded:
                continue
            key = _norm(value)
            if key and key not in seen:
                values.append(value)
                seen.add(key)
        return values[:3]

    @staticmethod
    def _route(command: str) -> str:
        from core.specialist_agents import route_agent
        agent = route_agent(command)
        if agent:
            return agent
        text = _norm(command)
        if "dugun salon" in text or "kir bahcesi" in text or "etkinlik" in text:
            if any(x in text for x in ("ses sistemi", "pa ", "line array", "spl", "hoparlor")):
                return "audio_system_designer"
            return "event_production_manager"
        return "audio_system_designer"

    def _search_local(self, command: str, entities: list[str]) -> dict[str, Any]:
        queries = entities[:2]
        if not queries:
            text = _norm(command)
            queries = ["rider" if "rider" in text else "stage plot" if "stage plot" in text else "ses sistemi"]

        old_timeout = getattr(self.file_manager, "search_timeout", 30)
        old_max = getattr(self.file_manager, "max_results", 50)
        found, errors, incomplete, seen = [], [], False, set()
        try:
            self.file_manager.search_timeout = min(int(old_timeout), 10)
            self.file_manager.max_results = min(int(old_max), 20)
            for query in queries:
                result = self.file_manager.find_files(query)
                if not result.get("success"):
                    errors.append(str(result.get("message", "Yerel arama başarısız.")))
                    continue
                incomplete = incomplete or bool(result.get("timed_out") or result.get("truncated") or result.get("paused_for_resources"))
                for item in result.get("files", []):
                    path = str(item.get("path", ""))
                    key = os.path.normcase(path)
                    if key not in seen:
                        seen.add(key)
                        found.append(item)
        finally:
            self.file_manager.search_timeout = old_timeout
            self.file_manager.max_results = old_max
        found.sort(key=lambda item: item.get("modified", 0), reverse=True)
        return {"files": found[:12], "queries": queries, "incomplete": incomplete, "errors": errors}

    @staticmethod
    def _extract_file(item: dict[str, Any]) -> dict[str, Any]:
        path = Path(item.get("path", ""))
        ext = path.suffix.lower()
        out = {"name": path.name, "path": str(path), "status": "not_read", "text": ""}
        try:
            if not path.is_file() or path.stat().st_size > 30 * 1024 * 1024:
                out["status"] = "missing_or_over_30mb"
            elif ext == ".pdf":
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                pages = [(page.extract_text() or "") for page in reader.pages[:20]]
                out["text"] = "\n".join(pages)[:9000]
                out["status"] = "text_extracted" if out["text"].strip() else "scanned_or_image_pdf"
                out["pages_read"] = min(len(reader.pages), 20)
            elif ext == ".docx":
                with zipfile.ZipFile(path) as archive:
                    root = ET.fromstring(archive.read("word/document.xml"))
                out["text"] = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))[:9000]
                out["status"] = "text_extracted" if out["text"].strip() else "empty_document"
            elif ext in {".txt", ".md", ".csv", ".json"}:
                out["text"] = path.read_text(encoding="utf-8", errors="replace")[:9000]
                out["status"] = "text_extracted" if out["text"].strip() else "empty_document"
            elif ext in _IMAGE_TYPES:
                out["status"] = "image_requires_vision"
            else:
                out["status"] = "unsupported_format"
        except Exception as exc:
            out["status"] = "read_error"
            out["error"] = str(exc)[:300]
        return out

    def _research(self, command: str) -> str:
        try:
            # Web aramasina yalnizca kullanicinin emri gider; yerel dosya icerigi gitmez.
            return str(self.ai_brain._web(command) or "")[:5000]
        except Exception as exc:
            return "Web araştırması gerçekleştirilemedi: " + str(exc)

    def _save(self, record: dict[str, Any]) -> None:
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        target = self.ledger_dir / (record["task_id"] + ".json")
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(target)

    def _documents_folder(self, entities: list[str]) -> Path:
        try:
            from utils.helpers import get_documents_path
            documents = Path(get_documents_path())
        except Exception:
            documents = Path.home() / "Documents"
        project = entities[0] if entities else "Genel Ses Muhendisligi"
        folder = documents / "Stagepulse" / "Projeler" / _slug(project)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @staticmethod
    def _create_pdf(markdown: str, target: Path) -> bool:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        except Exception:
            return False

        fonts = [
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "tahoma.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        ]
        font = next((path for path in fonts if path.is_file()), None)
        if not font:
            return False
        try:
            pdfmetrics.registerFont(TTFont("StagepulseTR", str(font)))
        except Exception:
            return False

        base = getSampleStyleSheet()
        body = ParagraphStyle("SPBody", parent=base["BodyText"], fontName="StagepulseTR", fontSize=9, leading=13, spaceAfter=6)
        h1 = ParagraphStyle("SPH1", parent=base["Heading1"], fontName="StagepulseTR", fontSize=17, leading=21, textColor=colors.HexColor("#111111"), spaceAfter=12)
        h2 = ParagraphStyle("SPH2", parent=base["Heading2"], fontName="StagepulseTR", fontSize=12, leading=16, textColor=colors.HexColor("#9A762E"), spaceBefore=9, spaceAfter=5)
        h3 = ParagraphStyle("SPH3", parent=base["Heading3"], fontName="StagepulseTR", fontSize=10, leading=14, textColor=colors.HexColor("#303030"), spaceBefore=7)
        small = ParagraphStyle("SPSmall", parent=body, fontSize=7, leading=9)
        story = [
            Paragraph("STAGEPULSE | ÖN TEKNİK RAPOR", h1),
            Paragraph("Ses mühendisliği ve etkinlik operasyon dosyası", small),
            Spacer(1, 12),
        ]
        lines = markdown.replace("\r\n", "\n").split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                story.append(Spacer(1, 3))
                i += 1
                continue
            if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?[-:| ]+\|?\s*$", lines[i + 1]):
                header = [c.strip() for c in line.strip("|").split("|")]
                i += 2
                rows = [[Paragraph(escape(c), small) for c in header]]
                while i < len(lines) and lines[i].strip().startswith("|"):
                    rows.append([Paragraph(escape(c.strip()), small) for c in lines[i].strip().strip("|").split("|")])
                    i += 1
                table = Table(rows, repeatRows=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C7A45A")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8B8B8")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.extend([table, Spacer(1, 7)])
                continue
            if line.startswith("# "):
                story.append(Paragraph(escape(line[2:]), h1))
            elif line.startswith("## "):
                story.append(Paragraph(escape(line[3:]), h2))
            elif line.startswith("### "):
                story.append(Paragraph(escape(line[4:]), h3))
            elif line.startswith(("- ", "* ")):
                story.append(Paragraph("• " + escape(line[2:]).replace("**", ""), body))
            else:
                story.append(Paragraph(escape(line).replace("**", "").replace(chr(96), ""), body))
            i += 1

        def footer(canvas, document):
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor("#C7A45A"))
            canvas.line(36, 30, A4[0] - 36, 30)
            canvas.setFont("StagepulseTR", 7)
            canvas.setFillColor(colors.HexColor("#555555"))
            canvas.drawString(36, 18, "STAGEPULSE | Teknik rapor")
            canvas.drawRightString(A4[0] - 36, 18, "Sayfa " + str(document.page))
            canvas.restoreState()

        try:
            doc = SimpleDocTemplate(str(target), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=45, bottomMargin=45, title="Stagepulse Ön Teknik Rapor", author="Stagepulse JARVIS")
            doc.build(story, onFirstPage=footer, onLaterPages=footer)
            return target.is_file() and target.stat().st_size > 0
        except Exception:
            target.unlink(missing_ok=True)
            return False

    def execute(self, command: str) -> dict[str, Any] | None:
        if not self.is_work_order(command):
            return None

        from core.specialist_agents import get_agent, prepare_expert_task
        agent_id = self._route(command)
        agent = get_agent(agent_id)
        entities = self._entities(command)
        task_id = uuid.uuid4().hex
        created = datetime.now(timezone.utc).isoformat()
        record = {
            "task_id": task_id,
            "created_at": created,
            "updated_at": created,
            "command": str(command),
            "status": "researching",
            "specialist": agent.name if agent else agent_id,
            "local_sources": [],
            "web_research": False,
            "deliverables": {},
            "steps": [],
        }

        def checkpoint(step: str, status: str, details: dict | None = None):
            record["steps"].append({
                "step": step,
                "status": status,
                "at": datetime.now(timezone.utc).isoformat(),
                "details": details or {},
            })
            record["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save(record)

        self._save(record)
        checkpoint("uzman_yonlendirme", "completed", {"agent_id": agent_id, "entities": entities})

        local = self._search_local(command, entities)
        checkpoint("yerel_dosya_arama", "incomplete" if local["incomplete"] else "completed", {
            "queries": local["queries"],
            "matches": len(local["files"]),
            "incomplete": local["incomplete"],
            "errors": local["errors"][:3],
        })

        extracted = [self._extract_file(item) for item in local["files"][:8]]
        record["local_sources"] = [
            {"name": item["name"], "path": item["path"], "status": item["status"]}
            for item in extracted
        ]
        checkpoint("belge_inceleme", "completed", {
            "readable": sum(x["status"] == "text_extracted" for x in extracted),
            "visuals_pending": sum(x["status"] in {"image_requires_vision", "scanned_or_image_pdf"} for x in extracted),
        })

        web_context = self._research(command)
        record["web_research"] = bool(web_context and not web_context.startswith("Web araştırması gerçekleştirilemedi:"))
        checkpoint("web_arastirmasi", "completed" if record["web_research"] else "unavailable", {
            "characters": len(web_context), "query": command,
        })

        system_prompt, tool_output = prepare_expert_task(agent_id, command)
        source_blocks = []
        for item in extracted:
            source_blocks.append(
                "DOSYA: " + item["name"] + "\nYOL: " + item["path"] +
                "\nDURUM: " + item["status"] + "\n" +
                (item.get("text") or item.get("error") or "")
            )
        images_pending = [
            item["path"] for item in extracted
            if item["status"] in {"image_requires_vision", "scanned_or_image_pdf"}
        ]

        prompt = (
            "STAGEPULSE OTONOM MUHENDISLIK GOREVI\n"
            "Kullanici dogal dilde emir verdi. Prompt secimi veya kullaniciya uzman rolu secimi sorma.\n"
            "EMIR:\n" + str(command) +
            "\n\nUZMAN TALIMATI:\n" + system_prompt +
            "\n\nDETERMINISTIK HESAPLAMA ARACLARI:\n" + tool_output +
            "\n\nBILGISAYARDA BULUNAN DOSYALAR:\n" +
            ("\n\n".join(source_blocks) if source_blocks else "Yerel aramada okunabilir dosya bulunamadi.") +
            "\n\nWEB ARASTIRMASI:\n" +
            (web_context if web_context else "Kullanilabilir web arastirma cikisi alinmadi.") +
            "\n\nZORUNLU KURALLAR:\n"
            "1. Kaynaksiz olcu, fiyat, marka-model, adet, grup uyesi, enstruman, aci veya uyumluluk uydurma.\n"
            "2. Yerel dosya ve web bilgisini ayri kaynaklar olarak belirt.\n"
            "3. Her sayisal hesapta formulu, birimi, varsayimi ve belirsizligi yaz. Olcum yapilmadiysa tahmin de.\n"
            "4. Arastirmayla bulunabilecek seyi kullaniciya sorma. Yalnizca kritik eksikleri GEREKLI BILGI olarak sor.\n"
            "5. Yerel arama zaman asimina ugradiysa dosyanin bulunmadigini kesin soyleme ve indirme onerme.\n"
            "6. Fiyat kaynagi yoksa teklif toplamiyla rakam uydurma; TBC olarak birak.\n"
            "7. Gercekte olusturulmayan dosyayi olusturuldu, gercek test yapilmayan seyi dogrulandi diye anlatma.\n"
            "8. Cikti Turkce, profesyonel ve uygulanabilir olsun.\n\n"
            "RAPOR BASLIKLARI:\n"
            "# Yonetici Ozeti\n## Kaynak Incelemesi\n## Teknik Degerlendirme\n"
            "## Hesaplar ve Varsayimlar\n## Ekipman / Is Kalemleri\n"
            "## Riskler ve Dogrulama\n## Gerekli Bilgiler\n## Sonraki Is Adimlari"
        )

        memory_context = ""
        if self.memory:
            try:
                memory_context = str(self.memory.context(limit=10) or "")
            except Exception:
                pass
        cloud_data_allowed = bool(
            getattr(self.ai_brain, "cloud_project_data_confirmed", False)
        )
        gemini_allowed = bool(
            getattr(self.ai_brain, "gemini_free_confirmed", False)
        )
        image_transfer = bool(
            image_files
            and cloud_data_allowed
            and gemini_allowed
            and getattr(self.ai_brain, "provider", "") in ("auto", "gemini")
        )

        if image_transfer:
            answer = self.ai_brain.ask_with_images(
                prompt,
                image_files,
                max_output_tokens=2200,
                confirm_external_transfer=True,
            )
        else:
            answer = self.ai_brain.ask(
                prompt,
                memory_context=memory_context,
                max_output_tokens=2200,
                web_context=web_context,
                allow_cloud_context=cloud_data_allowed,
            )

        if not answer or answer.startswith("Yapay zekâ yanıtı alınamadı."):
            record["status"] = "waiting_for_ai_provider"
            checkpoint("uzman_analizi", "blocked", {"reason": str(answer)[:500]})
            return {
                "success": False,
                "response": "Görev kaydedildi. Yerel dosya ve araştırma adımları saklandı ancak analiz tamamlanamadı. Ücretli servise geçiş yapılmadı.\n" + str(answer),
                "intent": "engineering_task",
                "task_id": task_id,
            }

        checkpoint("uzman_analizi", "completed", {"characters": len(answer)})
        folder = self._documents_folder(entities)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = stamp + "_" + _slug(agent_id) + "_" + task_id[:6]
        md_path = folder / (stem + ".md")
        pdf_path = folder / (stem + ".pdf")
        report = (
            "# STAGEPULSE | ÖN TEKNİK RAPOR\n\n"
            + "**Görev:** " + str(command) + "\n\n"
            + "**Uzmanlık:** " + agent_id + "\n\n"
            + "**Tarih:** " + created + "\n\n"
            + answer.strip() + "\n"
        )
        md_path.write_text(report, encoding="utf-8")
        pdf_created = self._create_pdf(report, pdf_path)
        record["deliverables"] = {
            "markdown": str(md_path),
            "pdf": str(pdf_path) if pdf_created else None,
        }
        required_section = re.search(
            r"(?is)##\s*Gerekli Bilgiler\s*(.*?)(?=##\s|$)",
            answer,
        )
        required_text = _norm(required_section.group(1)) if required_section else ""
        no_missing_data = (
            not required_text
            or required_text in {"yok", "bulunmadi", "gerekli bilgi yok", "eksik bilgi yok", "tbc yok"}
        )
        record["status"] = "draft_ready" if no_missing_data and not local["incomplete"] else "waiting_for_user_input"
        if image_files and not image_transfer:
            record["status"] = "waiting_for_visual_review"
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        checkpoint("rapor_uretimi", "completed", {
            "markdown": str(md_path), "pdf_created": pdf_created,
        })
        checkpoint("capraz_dogrulama", "pending", {
            "note": "İkinci bağımsız kaynak kontrolü ve fiziksel saha ölçümü henüz yapılmadı."
        })

        lines = [
            "Görev iş akışı başlatıldı ve ön rapor oluşturuldu.",
            "Uzmanlık: " + agent_id,
            "Yerel kaynak: " + str(len(extracted)) + " dosya incelendi.",
            "Yerel arama eksik: " + ("Evet" if local["incomplete"] else "Hayır"),
            "Web araştırması: " + ("alındı" if record["web_research"] else "alınamadı"),
            "Rapor: " + str(md_path),
            "PDF: " + (str(pdf_path) if pdf_created else "Türkçe font/üretim doğrulanamadı; Markdown hazır."),
        ]
        if images_pending and image_transfer:
            lines.append("Görseller ücretsiz Gemini katmanına, açık veri aktarım onayıyla gönderildi.")
        elif images_pending:
            lines.append(
                "Görsel veya taranmış PDF çözümlemesi bekliyor: " +
                ", ".join(images_pending[:4]) +
                ". Görsel aktarımı için ücretsiz Gemini onayı ve proje verisi aktarım izni gerekli."
            )
        if record["status"] == "waiting_for_user_input":
            lines.append("Durum: Kritik eksik bilgi veya tamamlanmamış yerel tarama nedeniyle kullanıcı/veri bekleniyor.")
        return {
            "success": True,
            "response": "\n".join(lines),
            "intent": "engineering_task",
            "task_id": task_id,
            "data": record,
        }
