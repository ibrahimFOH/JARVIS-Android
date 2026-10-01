# JARVIS Android Client

Native, dependency-free Android client for the existing Stagepulse JARVIS host.

## What is adapted
- Turkish Android SpeechRecognizer (`tr-TR`)
- Android TextToSpeech (`tr-TR` when the installed engine provides it)
- Stagepulse black/gold/white HUD
- Ollama-only backend through the existing Windows JARVIS CommandProcessor
- LAN bridge with token authentication
- Existing JARVIS desktop actions stay on the PC, instead of pretending a 4 GB Windows automation stack belongs inside a phone. Humanity survives another architecture decision.

## Build
Open this folder in Android Studio. The project targets API 35, min API 26, and uses AGP 8.7.3 / Gradle 8.9. Android Studio Quail/Panda-era tooling supports this range; API 35 requires AGP 8.6+.

## Connect
1. On the Windows JARVIS host run `JARVIS_HOST/scripts/START_ANDROID_BRIDGE.bat`.
2. Read the printed LAN IP and token.
3. Enter `http://PC_IP:8765` and the token in the app.
4. Tap CONNECT.
