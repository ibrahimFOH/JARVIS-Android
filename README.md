# JARVIS Android Adaptasyonu

Bu paket, mevcut JARVIS.zip ve Downloads.zip içeriğinin Android'e uyarlanmış sürümüdür.

Mimari:
- **JARVIS_HOST/**: Mevcut Windows JARVIS, Ollama-only yapı ve Android LAN bridge.
- **JARVIS_ANDROID/**: Native Android uygulaması. Türkçe STT + TTS + Stagepulse altın/beyaz HUD + LAN bridge bağlantısı.
- Android, ağır Python masaüstü otomasyonunu telefona taşımak yerine mevcut JARVIS hostunu uzaktan kontrol eder. 4 GB RAM'li makinede Ollama `qwen3:0.6b` korunur.

Android gereksinimi: Android Studio.
Host gereksinimi: Mevcut Python/venv + Ollama `qwen3:0.6b`.
