from types import SimpleNamespace

from core import command_processor as command_processor_module
from core.command_processor import CommandProcessor
from core.validator import Validator


class _QuietLogger:
    def command(self, _command):
        pass

    def debug(self, _message):
        pass

    def error(self, _message):
        pass

    def warning(self, _message):
        pass


class _IntentRecognizer:
    def recognize(self, _command):
        return {
            "intent": "delete_file",
            "confidence": 0.99,
            "parameters": {"target": r"C:\Users\Test\Documents\sample.txt"},
        }


class _ResponseGenerator:
    def generate(self, *_args, **_kwargs):
        return "Test işlemi tamamlandı."


class _Memory:
    def handle_command(self, _command):
        return None


def _processor(monkeypatch, *, deletion_enabled):
    processor = CommandProcessor.__new__(CommandProcessor)
    processor.intent_recognizer = _IntentRecognizer()
    processor.validator = Validator()
    processor.validator.allowed_operations = {"file_deletion": deletion_enabled}
    processor.validator.require_confirmation = {"system_shutdown": True}
    processor.response_generator = _ResponseGenerator()
    processor.memory = _Memory()
    processor.ai_brain = SimpleNamespace(ask=lambda *_args, **_kwargs: "Test yanıtı.")
    processor.deleted = []
    processor.file_manager = SimpleNamespace(
        delete_file=lambda target: (
            processor.deleted.append(target)
            or {"success": True, "message": "Test dosyası silindi."}
        )
    )
    monkeypatch.setattr(command_processor_module, "logger", _QuietLogger())
    return processor


def test_file_deletion_is_denied_when_not_explicitly_enabled(monkeypatch):
    processor = _processor(monkeypatch, deletion_enabled=False)

    result = processor.process("test dosyasını sil")

    assert result["success"] is False
    assert result.get("requires_confirmation") is False, result
    assert "devre dışı" in result["response"].lower()
    assert processor.deleted == []


def test_file_deletion_requires_explicit_confirmation(monkeypatch):
    processor = _processor(monkeypatch, deletion_enabled=True)

    pending = processor.process("test dosyasını sil")

    assert pending["success"] is False
    assert pending.get("requires_confirmation") is True, pending
    assert pending["pending_command"] == "test dosyasını sil"
    assert processor.deleted == []

    completed = processor.process("test dosyasını sil", confirmed=True)

    assert completed["success"] is True
    assert processor.deleted == [r"C:\Users\Test\Documents\sample.txt"]


def test_repository_push_requires_confirmation(monkeypatch):
    from core.agent_tools import RepositoryManager

    manager = RepositoryManager.__new__(RepositoryManager)
    pushed = []
    monkeypatch.setattr(
        manager,
        "_push",
        lambda: pushed.append(True) or {"success": True, "response": "Gönderildi."},
    )

    pending = manager.handle_command("git push")

    assert pending["requires_confirmation"] is True
    assert pending["pending_command"] == "git push"
    assert pushed == []

    completed = manager.handle_command("git push", confirmed=True)

    assert completed["success"] is True
    assert pushed == [True]
