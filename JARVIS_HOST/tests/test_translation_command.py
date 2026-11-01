import json
from pathlib import Path

from core.command_processor import CommandProcessor


class _Brain:
    def ask(self, prompt):
        payload = json.loads(prompt.split("Kaynaklar: ", 1)[1])
        return json.dumps({
            "translations": {
                item["id"]: "Çıkış %1" for item in payload
            }
        }, ensure_ascii=False)


def test_natural_language_command_translates_qt_file_without_overwriting_source(tmp_path):
    source = tmp_path / "qlcplus_de_DE.ts"
    source.write_text(
        '<TS language="de_DE"><context><name>Audio</name>'
        '<message><source>Output %1</source>'
        '<translation type="unfinished"></translation></message>'
        '</context></TS>',
        encoding="utf-8",
    )
    processor = CommandProcessor.__new__(CommandProcessor)
    processor.ai_brain = _Brain()

    result = processor._translate_qt_catalog_command(
        f'Türkçeye çevir "{source}"'
    )

    target = tmp_path / "qlcplus_tr_TR.ts"
    assert result["success"] is True
    assert target.is_file()
    assert "Çıkış %1" in target.read_text(encoding="utf-8")
    assert 'language="de_DE"' in source.read_text(encoding="utf-8")


def test_translation_command_without_file_path_requests_only_required_path():
    processor = CommandProcessor.__new__(CommandProcessor)
    processor.ai_brain = _Brain()

    result = processor._translate_qt_catalog_command("Türkçeye çevir")

    assert result["success"] is False
    assert "tam yolunu belirt" in result["response"]
