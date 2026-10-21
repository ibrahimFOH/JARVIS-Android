# Stagepulse JARVIS: Windows + Android + Gemini

## Windows build package
1. Download and extract the complete `Stagepulse-JARVIS-Windows-Package.zip` folder. Do not move `StagepulseJARVIS.exe` out of its folder; the `_internal` directory is part of the application.
2. Start with `Start-StagepulseJARVIS.bat` or `StagepulseJARVIS.exe`.
3. Open **AI SETUP**. Choose `auto` to try Gemini first and fall back to Ollama, `gemini` to require Gemini, or `ollama` for the local provider.
4. Paste your own Gemini API key and review the chat/vision and image-generation model names. The key is not embedded into the build. On Windows, the saved key is protected with DPAPI when available.
5. Select **SAVE SETTINGS**.

Default model values:
- Chat and image analysis: `gemini-2.5-flash`
- Image generation: `gemini-3.1-flash-image`
- Local Ollama: `qwen3:0.6b` at `http://127.0.0.1:11434`

Gemini features require internet access, a valid API key, and available quota. Ollama requires Ollama and the selected model to be installed locally.

## Android APK
1. Install `Stagepulse-JARVIS-Gemini-debug.apk` on the phone. It is a debug-signed install package, not a Play Store release.
2. Open JARVIS and tap **GEMINI** to enter the API key and chat/vision model. The API key and Windows bridge token are stored using Android Keystore encryption; old plaintext preference values are migrated at startup.
3. Tap **IMAGE** to pick an image, then press **EXECUTE** with the desired analysis instruction in the command box.
4. Ask for image generation with a command such as: `Görsel oluştur: siyah ve altın renklerde Stagepulse ses mühendisliği amblemi`. Generated images are saved to Pictures/StagepulseJARVIS.
5. Voice input uses Android's speech recognizer and replies are spoken through the local Piper voice engine. Speech recognition can depend on the speech service installed on the phone.

## Pair Android with Windows
1. Keep both devices on the same trusted Wi-Fi/LAN.
2. Start the Windows app, then click **ANDROID**. Copy the host URL and authentication token shown in the pairing window.
3. In Android, tap **HOST** and enter the URL/token, then use **KAYDET VE TEST ET**.
4. Allow the Windows JARVIS application through Windows Firewall on the **Private** network if Windows asks.

The bridge uses HTTP on the local network with bearer-token authentication for pairing compatibility. **Do not forward port 8765 from your router, expose the bridge to the public internet, or share the token.** When Windows is offline, Android continues with on-device commands and may use Gemini if an API key is configured; cloud Gemini still requires internet.

## What has been validated
GitHub Actions builds the APK and Windows package and checks Python syntax. Unit tests cover provider fallback and image-generation response handling. These checks do not substitute for testing on your actual phone, Windows PC, microphone/speaker devices, account quota, or local Wi-Fi/firewall.
