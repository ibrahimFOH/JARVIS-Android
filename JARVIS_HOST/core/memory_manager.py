"""Small, explicit opt-in persistent memory for the Windows JARVIS host.

Only facts the user explicitly asks JARVIS to remember are stored. Credentials and
common secret patterns are rejected. Memory lives in the user's local app-data folder,
not in the repository.
"""
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


_SECRET_PATTERN = re.compile(
    r"\b(password|passcode|parola|sifre|api\s*key|access\s*token|token|secret|"
    r"otp|pin\s*kodu|tc\s*kimlik|kredi\s*karti|credit\s*card)\b",
    re.IGNORECASE,
)


def _normalize(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.translate(str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"}))


class MemoryManager:
    """Manage explicit, user-controlled local memories."""

    def __init__(self, storage_path=None):
        if storage_path is not None:
            self.storage_path = Path(storage_path)
        else:
            root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            base = Path(root) if root else Path.home()
            self.storage_path = base / "Stagepulse" / "JARVIS" / "memory.json"

    def _read(self):
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            facts = data.get("facts", [])
            return [item for item in facts if isinstance(item, dict) and isinstance(item.get("text"), str)]
        except (OSError, ValueError, TypeError):
            return []

    def _write(self, facts):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "facts": facts[-100:]}
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=str(self.storage_path.parent),
                prefix="memory-", suffix=".tmp", delete=False
            ) as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                temp_path = Path(handle.name)
            temp_path.replace(self.storage_path)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def context(self, limit=15):
        facts = self._read()
        return "\n".join(f"- {item['text']}" for item in facts[-limit:])

    def handle_command(self, command):
        """Return a response for explicit memory commands, otherwise None."""
        original = str(command or "").strip()
        normalized = _normalize(original)

        if normalized in {
            "hafizami goster", "hafizamda ne var", "neleri hatirliyorsun",
            "ne hatirliyorsun", "hafizani goster", "hatirladiklarini soyle",
        }:
            facts = self._read()
            if not facts:
                return "Kalıcı hafızam henüz boş. Bir bilgiyi kaydetmemi açıkça isteyebilirsin."
            return "Kalıcı hafızamda kayıtlı olanlar:\n" + "\n".join(
                f"{index}. {item['text']}" for index, item in enumerate(facts, 1)
            )

        remember = re.match(
            r"^(?:(?:jarvis)[,\s]+)?(?:(?:bunu|şunu|sunu)\s+)?"
            r"(?:hatırla|hatirla|aklında tut|aklinda tut)\s*[:,-]?\s*(.+)$",
            original,
            re.IGNORECASE,
        )
        if remember:
            fact = original
            # Preserve the user's original Turkish spelling in local memory.
            fact = remember.group(1).strip()
            if not fact:
                return "Kaydetmem için hatırlamamı istediğin bilgiyi de yazmalısın."
            if len(fact) > 300:
                return "Tek bir hafıza kaydı en fazla 300 karakter olabilir."
            if _SECRET_PATTERN.search(normalized):
                return "Güvenlik için parola, erişim anahtarı veya benzeri gizli bilgileri hafızaya kaydetmiyorum."
            facts = self._read()
            key = _normalize(fact)
            if any(_normalize(item["text"]) == key for item in facts):
                return "Bu bilgi zaten kalıcı hafızamda kayıtlı."
            facts.append({
                "text": fact,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            self._write(facts)
            return "Bunu kalıcı hafızama kaydettim."

        forget = re.match(
            r"^(?:(?:jarvis)[,\s]+)?(?:(?:bunu|şunu|sunu)\s+)?"
            r"(?:unut|hafızandan sil|hafizandan sil)\s*[:,-]?\s*(.+)$",
            original,
            re.IGNORECASE,
        )
        if forget:
            query = forget.group(1).strip()
            if not query:
                return "Silmem için hangi bilgiyi unutmamı istediğini belirtmelisin."
            facts = self._read()
            needle = _normalize(query)
            kept = [
                item for item in facts
                if needle not in _normalize(item["text"])
                and _normalize(item["text"]) not in needle
            ]
            removed = len(facts) - len(kept)
            if removed:
                self._write(kept)
                return f"İstediğin bilgi kalıcı hafızadan silindi. Kayıt sayısı: {removed}."
            return "Bu ifadeyle eşleşen bir hafıza kaydı bulamadım."

        return None
