from pathlib import Path

from modules.file_manager import FileManager


def _manager(tmp_path):
    manager = FileManager.__new__(FileManager)
    manager.search_locations = [str(tmp_path)]
    manager.max_results = 20
    manager.search_timeout = 5
    manager.search_all_fixed_drives = False
    manager._system_under_pressure = lambda: False
    manager.excluded_directories = {
        "appdata", "windows", "program files", ".git", "node_modules"
    }
    return manager


def test_search_finds_existing_project_file_before_any_download(tmp_path):
    project = tmp_path / "Stagepulse" / "Elif Kir Bahcesi"
    project.mkdir(parents=True)
    expected = project / "Elif_Kır_Bahçesi_Teknik_Teklif.pdf"
    expected.write_bytes(b"%PDF-test")

    result = _manager(tmp_path).find_files(
        "Elif Kir Bahcesi", location=str(tmp_path), file_type="pdf"
    )

    assert result["success"] is True
    assert result["count"] == 1
    assert Path(result["files"][0]["path"]) == expected
    assert result["timed_out"] is False


def test_search_matches_turkish_names_and_common_separators(tmp_path):
    (tmp_path / "Nişanengi-Düğün_Salonu_Sistem_Raporu.docx").write_bytes(b"docx")

    result = _manager(tmp_path).find_files(
        "Nisanengi Düğün Salonu", location=str(tmp_path)
    )

    assert result["success"] is True
    assert result["count"] == 1


def test_search_skips_git_and_dependency_folders(tmp_path):
    ignored = tmp_path / ".git"
    ignored.mkdir()
    (ignored / "Elif_Kir_Bahcesi.pdf").write_bytes(b"ignored")
    visible = tmp_path / "Elif_Kir_Bahcesi.pdf"
    visible.write_bytes(b"visible")

    result = _manager(tmp_path).find_files(
        "Elif Kir Bahcesi", location=str(tmp_path)
    )

    assert result["count"] == 1
    assert Path(result["files"][0]["path"]) == visible


def test_search_reports_invalid_empty_query_without_walking(tmp_path):
    result = _manager(tmp_path).find_files("   ", location=str(tmp_path))

    assert result["success"] is False
    assert result["files"] == []
    assert "anahtar kelime" in result["message"]



def test_local_search_pauses_immediately_when_pc_is_under_pressure(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    manager._system_under_pressure = lambda: True
    (tmp_path / "Elif_Kir_Bahcesi.pdf").write_bytes(b"pdf")

    result = manager.find_files("Elif Kir Bahcesi", location=str(tmp_path))

    assert result["success"] is True
    assert result["paused_for_resources"] is True
    assert result["files"] == []
