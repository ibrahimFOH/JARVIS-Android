import sys
import tempfile
import unittest
from pathlib import Path

HOST = Path(__file__).resolve().parents[1] / "JARVIS_HOST"
sys.path.insert(0, str(HOST))

import importlib.util

MEMORY_PATH = HOST / "core" / "memory_manager.py"
SPEC = importlib.util.spec_from_file_location("jarvis_memory_manager", MEMORY_PATH)
MEMORY_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEMORY_MODULE)
MemoryManager = MEMORY_MODULE.MemoryManager


class MemoryManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory = MemoryManager(Path(self.temp_dir.name) / "memory.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_explicit_remember_persists_between_instances(self):
        response = self.memory.handle_command("Bunu hatırla: Stagepulse renkleri siyah altın beyaz")
        self.assertIn("kaydettim", response)
        reloaded = MemoryManager(self.memory.storage_path)
        self.assertIn("Stagepulse renkleri siyah altın beyaz", reloaded.context())

    def test_duplicate_is_not_added(self):
        self.memory.handle_command("Hatırla: Midas M32 tercih ediyorum")
        response = self.memory.handle_command("Hatırla: Midas M32 tercih ediyorum")
        self.assertIn("zaten", response)
        self.assertEqual(len(self.memory._read()), 1)

    def test_secret_is_rejected(self):
        response = self.memory.handle_command("Hatırla: benim API key gizli-deger")
        self.assertIn("Güvenlik", response)
        self.assertEqual(self.memory._read(), [])

    def test_forget_removes_matching_record(self):
        self.memory.handle_command("Hatırla: Stagepulse renkleri siyah altın beyaz")
        response = self.memory.handle_command("Unut: Stagepulse renkleri")
        self.assertIn("silindi", response)
        self.assertEqual(self.memory._read(), [])

    def test_list_empty_memory(self):
        self.assertIn("henüz boş", self.memory.handle_command("Hafızamı göster"))


if __name__ == "__main__":
    unittest.main()
