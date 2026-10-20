# Tauri native command surface reconstructed from recovered frontend

This list is derived from the recovered `kopru.js` bridge. It records commands the frontend invokes by name and the arguments visible on the JavaScript side. It is not recovered Rust implementation code.

## Persistence and network

| Command | Frontend arguments / apparent purpose |
|---|---|
| `dosya_oku` | `{ ad }`; read application data by logical name |
| `dosya_yaz` | `{ ad, veri }`; persist application data |
| `sir_oku` | `{ ad }`; read secret/key storage |
| `sir_yaz` | `{ ad, deger }`; write secret/key storage |
| `http_istek` | `{ url, yontem, basliklar, govde, sure }`; HTTP requests; response shape `{ durum, govde }` |
| `baglanti_ac` | `{ url }`; open an external URL |
| `gunluk` | `{ metin }`; append diagnostics/log text |

## System and window integration

| Command | Frontend arguments / apparent purpose |
|---|---|
| `sistem` | returns system metrics/info |
| `konus` | `{ metin, ses, hiz }`; text-to-speech |
| `sus` | stops speech playback |
| `sesler` | enumerates speech voices |
| `yerel_zeka` | `{ istek }`; optional local-device model request, serialized as JSON |
| `oto_baslat_oku` / `oto_baslat_yaz` | read/write startup setting |
| `brifing_zamani` | briefing schedule / last-run state |
| `acilis_sebebi` | why the app window was opened |
| `tam_ekran` / `tam_ekran_mi` | toggle/query fullscreen |
| `klasorler` / `uygulamalar` | enumerate local folders/apps |
| `uygulama_ac` | `{ yol }`; launch an application by path |
| `dosya_ara` | `{ ad, tur, uzantilar, kok }`; search files/folders |
| `yol_ac` | `{ yol, goster }`; open/reveal a path |
| `cop_ac` | open recycle/trash |
| `silme_hazirla` | `{ islem, yol }`; prepare a destructive operation |
| `silme_onayla` | `{ kod }`; confirm a prepared destructive operation |
| `silme_vazgec` | cancel a prepared delete operation |
| `guc` | `{ ne }`; sleep/lock; comments indicate shutdown/restart require prepare + confirm |
| `mikrofon_izni` | `{ ne }`; inspect/request microphone permission settings |
| `hatirlatici_kur` | `{ metin, saniye }`; create reminder |
| `hatirlaticilar` / `hatirlatici_sil` | list/remove reminders |
| `guncelleme_denetle` / `guncelleme_kur` | check/download/install an app update |

The bridge also exposes Tauri window/app/event APIs directly for current-window close/minimize, version lookup and event subscription. The update progress event is named `guncelleme-ilerleme`.

## External API endpoints discovered in frontend

- Gemini Generate Content and model listing: `generativelanguage.googleapis.com/v1beta`
- Anthropic Messages and Models API: `api.anthropic.com/v1`
- OpenAI-compatible `/models` and `/chat/completions` endpoints
- OpenAI live voice sessions: `api.openai.com/v1/live/sessions`
- Kie image generation jobs: `api.kie.ai/api/v1/jobs`
- Open-Meteo geocoding and forecast endpoints
- Google News RSS, Frankfurter exchange rates and gold-price endpoint
- Gurizon update/terms endpoints

## Android porting implications

The JavaScript frontend depends on the command names above. A native Android implementation cannot simply copy the HTML and expect filesystem, startup, power-management, local AI and desktop-window commands to exist. These must be replaced by Android-specific implementations or disabled with a visible unsupported-state result. Destructive operations should retain the existing prepare/confirm boundary; never map them to immediate deletion.
