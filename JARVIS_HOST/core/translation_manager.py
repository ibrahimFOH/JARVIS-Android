"""Safe Turkish translation for Qt Linguist catalogs.

The source catalog is never overwritten. Translations are generated through the
already-configured free-only JARVIS provider and are accepted only when all
placeholders survive unchanged.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET


_PLACEHOLDER = re.compile(
    r"%L?\d+|%n|%[sdif]|%\([^)]+\)[sdif]|\$\{[^}]+\}|\{[^{}]+\}|</?[A-Za-z][^>]*>",
    flags=re.IGNORECASE,
)


class TranslationError(RuntimeError):
    """A translation was not safe to write."""


class TurkishTranslationManager:
    def __init__(self, ai_brain, batch_size: int = 16):
        self.ai_brain = ai_brain
        self.batch_size = max(1, min(int(batch_size), 24))

    @staticmethod
    def _placeholders(value: str) -> Counter:
        return Counter(_PLACEHOLDER.findall(value or ""))

    @classmethod
    def _validate_translation(cls, source: str, translated: str) -> None:
        if not isinstance(translated, str) or not translated.strip():
            raise TranslationError("Boş çeviri kabul edilmedi.")
        if cls._placeholders(source) != cls._placeholders(translated):
            raise TranslationError("Çeviri sırasında kod yer tutucuları veya biçimlendirme değişti.")
        if source.count("\n") != translated.count("\n"):
            raise TranslationError("Çeviri sırasında satır sonları değişti.")

    def _translate_batch(self, items: list[dict[str, str]]) -> dict[str, str]:
        payload = json.dumps(items, ensure_ascii=False)
        prompt = (
            "Sen yazılım arayüzü yerelleştirme uzmanısın. Aşağıdaki Qt Linguist kaynak "
            "metinlerini Türkçeye çevir. Ses/ışık mühendisliği terimlerinde yerleşik Türkçe "
            "kullan; gerekiyorsa standart İngilizce terimi parantez içinde bırak. Ürün adlarını, "
            "dosya uzantılarını, kısayolları, ölçü birimlerini ve kodu değiştirme. Her öğenin "
            "id değerini aynen koru. Açıklama ekleme. Yalnızca geçerli JSON döndür: "
            '{"translations":{"0":"çeviri","1":"çeviri"}}. Kaynaklar: ' + payload
        )
        answer = self.ai_brain.ask(prompt)
        if not answer or answer.startswith("Yapay zekâ yanıtı alınamadı."):
            raise TranslationError("Ücretsiz yapay zekâ sağlayıcısı çeviri üretemedi: " + str(answer))
        cleaned = re.sub(r"^\s*\x60{3}(?:json)?\s*|\s*\x60{3}\s*$", "", answer.strip(), flags=re.IGNORECASE)
        try:
            data = json.loads(cleaned)
            translations = data.get("translations", {})
        except (ValueError, AttributeError) as exc:
            raise TranslationError("Yapay zekâ geçerli çeviri JSON'u döndürmedi.") from exc
        if not isinstance(translations, dict):
            raise TranslationError("Çeviri yanıtının translations alanı sözlük değil.")
        expected = {item["id"] for item in items}
        if set(translations) != expected:
            raise TranslationError("Çeviri yanıtı eksik veya fazladan kayıt içeriyor.")
        result = {}
        for item in items:
            value = translations[item["id"]]
            self._validate_translation(item["source"], value)
            result[item["id"]] = value
        return result

    def translate_qt_ts(self, source_path: str | Path, destination_path: str | Path) -> dict:
        source = Path(source_path).expanduser().resolve()
        destination = Path(destination_path).expanduser().resolve()
        if source.suffix.lower() != ".ts":
            raise TranslationError("Yalnızca Qt Linguist .ts katalogları destekleniyor.")
        if not source.is_file():
            raise TranslationError("Kaynak çeviri dosyası bulunamadı: " + str(source))
        if source == destination:
            raise TranslationError("Kaynak dosyanın üzerine yazılamaz.")
        if destination.exists():
            raise TranslationError("Hedef çeviri dosyası zaten var; üzerine yazma yapılmadı.")

        try:
            tree = ET.parse(source)
        except (ET.ParseError, OSError) as exc:
            raise TranslationError("Qt çeviri kataloğu okunamadı: " + str(exc)) from exc
        root = tree.getroot()
        root.set("language", "tr_TR")

        pending = []
        targets = []
        skipped = 0
        for message in root.findall(".//message"):
            source_node = message.find("source")
            translation_node = message.find("translation")
            if source_node is None or translation_node is None:
                skipped += 1
                continue
            if translation_node.get("type") in {"obsolete", "vanished"}:
                skipped += 1
                continue

            source_text = "".join(source_node.itertext())
            if not source_text.strip():
                skipped += 1
                continue

            plural_nodes = translation_node.findall("numerusform")
            target_nodes = plural_nodes if plural_nodes else [translation_node]
            for form_index, target_node in enumerate(target_nodes):
                current = "".join(target_node.itertext())
                if current.strip() and translation_node.get("type") != "unfinished":
                    skipped += 1
                    continue
                identifier = str(len(pending))
                pending.append({"id": identifier, "source": source_text})
                targets.append((target_node, source_text, identifier))

        for offset in range(0, len(pending), self.batch_size):
            batch = pending[offset:offset + self.batch_size]
            translated = self._translate_batch(batch)
            for target_node, source_text, identifier in targets[offset:offset + len(batch)]:
                target_node.text = translated[identifier]
                target_node.attrib.pop("type", None)

        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            tree.write(destination, encoding="utf-8", xml_declaration=True)
            # Re-open and validate the written XML before reporting success.
            check = ET.parse(destination)
            if check.getroot().get("language") != "tr_TR":
                raise TranslationError("Çıktı kataloğunun dili tr_TR olarak doğrulanamadı.")
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        return {
            "success": True,
            "source": str(source),
            "destination": str(destination),
            "translated_entries": len(pending),
            "preserved_entries": skipped,
            "language": "tr_TR",
            "original_overwritten": False,
        }
