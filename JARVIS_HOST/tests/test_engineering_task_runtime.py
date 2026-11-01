from pathlib import Path

from core.engineering_task_runtime import EngineeringTaskRuntime


class _FileManager:
    def __init__(self):
        self.search_timeout = 30
        self.max_results = 50
        self.queries = []

    def find_files(self, query):
        self.queries.append(query)
        return {
            "success": True,
            "files": [],
            "count": 0,
            "truncated": False,
            "timed_out": False,
        }


class _Memory:
    def context(self, limit=10):
        return "Konsol tercihi: Midas M32 Live"


class _AI:
    provider = "ollama"
    cloud_project_data_confirmed = False
    gemini_free_confirmed = False

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def _web(self, command):
        return "Araştırma sonucu: üretici sayfaları kontrol edilecek. Sorgu: " + command

    def ask(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        assert kwargs["allow_cloud_context"] is False
        return self.answer


def _runtime(tmp_path, monkeypatch, answer):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    manager = _FileManager()
    brain = _AI(answer)
    runtime = EngineeringTaskRuntime(brain, manager, _Memory())
    runtime._documents_folder = lambda entities: tmp_path / "documents"
    runtime._research = lambda command: "Bağlam: " + command
    runtime._create_pdf = lambda markdown, target: False
    return runtime, manager, brain


def test_detects_natural_language_sound_engineering_orders():
    assert EngineeringTaskRuntime.is_work_order("Mengene için teknik rider hazırla")
    assert EngineeringTaskRuntime.is_work_order(
        "Elif Kır Bahçesi işlemlerini Nişanengi Düğün Salonu'na göre hazırla"
    )
    assert not EngineeringTaskRuntime.is_work_order("Bilgisayarın RAM durumunu göster")


def test_extracts_project_entities_from_turkish_command():
    result = EngineeringTaskRuntime._entities(
        "Elif Kır Bahçesi işlemlerini Nişanengi Düğün Salonu'na göre hazırla"
    )
    normalized = [" ".join(item.casefold().split()) for item in result]
    assert any("elif" in item for item in normalized)
    assert any("nisanengi" in item.replace("ş", "s") for item in normalized)


def test_executes_local_first_task_and_writes_checkpoints_and_markdown(tmp_path, monkeypatch):
    answer = (
        "# Yönetici Özeti\nÖn teknik çalışma.\n"
        "## Gerekli Bilgiler\nYok.\n"
        "## Sonraki İş Adımları\nSaha ölçüsü doğrulansın.\n"
    )
    runtime, manager, brain = _runtime(tmp_path, monkeypatch, answer)

    result = runtime.execute("Mengene için teknik rider hazırla")

    assert result["success"] is True
    assert result["intent"] == "engineering_task"
    assert result["data"]["status"] == "draft_ready"
    assert manager.queries
    assert manager.search_timeout == 30
    assert manager.max_results == 50
    assert len(brain.calls) == 1
    markdown = Path(result["data"]["deliverables"]["markdown"])
    assert markdown.is_file()
    assert "Ön teknik çalışma" in markdown.read_text(encoding="utf-8")
    ledger = Path(runtime.ledger_dir) / (result["task_id"] + ".json")
    assert ledger.is_file()


def test_task_waits_for_user_when_critical_information_is_missing(tmp_path, monkeypatch):
    answer = (
        "# Yönetici Özeti\nTaslak.\n"
        "## Gerekli Bilgiler\n"
        "- Salonun net en ve derinlik ölçüsü.\n"
        "- Sahne koordinatı.\n"
        "## Sonraki İş Adımları\nÖlçüler geldikten sonra hesapla.\n"
    )
    runtime, _manager, _brain = _runtime(tmp_path, monkeypatch, answer)

    result = runtime.execute("Elif Kır Bahçesi salonu için PA sistem raporu hazırla")

    assert result["success"] is True
    assert result["data"]["status"] == "waiting_for_user_input"


def test_incomplete_local_search_does_not_claim_final_draft(tmp_path, monkeypatch):
    runtime, manager, _brain = _runtime(
        tmp_path,
        monkeypatch,
        "# Yönetici Özeti\nÖn analiz.\n## Gerekli Bilgiler\nYok.\n",
    )
    manager.find_files = lambda query: {
        "success": True, "files": [], "count": 0,
        "truncated": False, "timed_out": True,
    }

    result = runtime.execute("Mengene için teknik rider hazırla")

    assert result["success"] is True
    assert result["data"]["status"] == "waiting_for_user_input"
    assert "Yerel arama eksik: Evet" in result["response"]


def test_visual_files_are_not_sent_to_cloud_without_explicit_permission(tmp_path, monkeypatch):
    runtime, manager, brain = _runtime(
        tmp_path,
        monkeypatch,
        "# Yönetici Özeti\nGörsel bekleniyor.\n## Gerekli Bilgiler\nYok.\n",
    )
    image = tmp_path / "kroki.png"
    image.write_bytes(b"image bytes")
    manager.find_files = lambda query: {
        "success": True,
        "files": [{
            "name": image.name, "path": str(image), "modified": 1
        }],
        "count": 1, "truncated": False, "timed_out": False,
    }

    result = runtime.execute("Nişanengi Düğün Salonu ses sistemi raporu hazırla")

    assert result["success"] is True
    assert result["data"]["status"] == "waiting_for_visual_review"
    assert "görsel aktarımı için" in result["response"].casefold()
    assert brain.calls[0][1]["allow_cloud_context"] is False
