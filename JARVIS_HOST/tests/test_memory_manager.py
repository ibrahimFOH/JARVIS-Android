from core.memory_manager import MemoryManager


def test_explicit_remember_persists_between_instances(tmp_path):
    memory = MemoryManager(tmp_path / "memory.json")
    response = memory.handle_command("Bunu hatırla: Stagepulse renkleri siyah altın beyaz")
    assert "kaydettim" in response
    reloaded = MemoryManager(memory.storage_path)
    assert "Stagepulse renkleri siyah altın beyaz" in reloaded.context()


def test_duplicate_is_not_added(tmp_path):
    memory = MemoryManager(tmp_path / "memory.json")
    memory.handle_command("Hatırla: Midas M32 tercih ediyorum")
    response = memory.handle_command("Hatırla: Midas M32 tercih ediyorum")
    assert "zaten" in response
    assert len(memory._read()) == 1


def test_secret_is_rejected(tmp_path):
    memory = MemoryManager(tmp_path / "memory.json")
    response = memory.handle_command("Hatırla: benim API key gizli-deger")
    assert "Güvenlik" in response
    assert memory._read() == []


def test_forget_removes_matching_record(tmp_path):
    memory = MemoryManager(tmp_path / "memory.json")
    memory.handle_command("Hatırla: Stagepulse renkleri siyah altın beyaz")
    response = memory.handle_command("Unut: Stagepulse renkleri")
    assert "silindi" in response
    assert memory._read() == []


def test_list_empty_memory(tmp_path):
    memory = MemoryManager(tmp_path / "memory.json")
    assert "henüz boş" in memory.handle_command("Hafızamı göster")
