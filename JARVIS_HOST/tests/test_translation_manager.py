import json
from pathlib import Path

import pytest

from core.translation_manager import TurkishTranslationManager, TranslationError


class _TranslationBrain:
    def __init__(self, replacement):
        self.replacement = replacement
        self.calls = []

    def ask(self, prompt):
        self.calls.append(prompt)
        marker = "Kaynaklar: "
        payload = json.loads(prompt.split(marker, 1)[1])
        translations = {
            item["id"]: self.replacement(item["source"])
            for item in payload
        }
        return json.dumps({"translations": translations}, ensure_ascii=False)


def _write_catalog(path: Path):
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<TS version="2.1" language="de_DE">'
        '<context><name>Audio</name>'
        '<message><source>Output %1</source>'
        '<translation type="unfinished"></translation></message>'
        '</context></TS>',
        encoding="utf-8",
    )


def test_qt_catalog_translation_creates_separate_turkish_file(tmp_path):
    source = tmp_path / "qlcplus_de_DE.ts"
    destination = tmp_path / "qlcplus_tr_TR.ts"
    _write_catalog(source)
    original = source.read_text(encoding="utf-8")
    brain = _TranslationBrain(lambda text: "Çıkış %1" if text == "Output %1" else text)

    result = TurkishTranslationManager(brain).translate_qt_ts(source, destination)

    assert result["success"] is True
    assert result["translated_entries"] == 1
    assert result["original_overwritten"] is False
    assert source.read_text(encoding="utf-8") == original
    translated = destination.read_text(encoding="utf-8")
    assert 'language="tr_TR"' in translated
    assert "Çıkış %1" in translated


def test_translation_rejects_changed_placeholders_and_does_not_write(tmp_path):
    source = tmp_path / "source_de_DE.ts"
    destination = tmp_path / "target_tr_TR.ts"
    _write_catalog(source)
    brain = _TranslationBrain(lambda _text: "Çıkış %2")

    with pytest.raises(TranslationError, match="yer tutucuları"):
        TurkishTranslationManager(brain).translate_qt_ts(source, destination)

    assert not destination.exists()


def test_translation_never_overwrites_existing_source_or_destination(tmp_path):
    source = tmp_path / "source_de_DE.ts"
    destination = tmp_path / "target_tr_TR.ts"
    _write_catalog(source)
    destination.write_text("keep this file", encoding="utf-8")

    with pytest.raises(TranslationError, match="zaten var"):
        TurkishTranslationManager(_TranslationBrain(lambda text: text)).translate_qt_ts(source, destination)

    assert destination.read_text(encoding="utf-8") == "keep this file"
