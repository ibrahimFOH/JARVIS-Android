# Recovered frontend API and command inventory

This report is derived from the local v7 recovered frontend files, not from inference about unavailable backend source.

## External services referenced

- Google Generative Language API: `generativelanguage.googleapis.com/v1beta/`
- Anthropic API: `api.anthropic.com/v1/`
- OpenAI API: `api.openai.com/v1`
- OpenAI live voice session endpoint: `api.openai.com/v1/live/sessions`
- Kie image generation API: `api.kie.ai/api/v1/jobs/`
- Open-Meteo geocoding and forecast endpoints
- CoinGecko Bitcoin price, Frankfurter exchange rates, Gold API, Truncgil gold/market data
- Google News RSS
- Gurizon updater and terms endpoints

The extracted frontend contains key-entry/help URLs for providers. A scan of recovered HTML/JS/CSS for common OpenAI `sk-`, Anthropic `sk-ant-`, and Google `AIza` API key shapes found no matching literal strings. This is a narrow pattern scan, not a guarantee that no credentials exist elsewhere in the binaries or installer.

## Native command surface

The frontend bridge requests desktop-native functionality for:
- settings and secret persistence
- HTTP requests
- speech synthesis and voice listing
- local AI invocation
- autostart configuration
- window full-screen/minimize/close
- application/folder listing, file search and path opening
- two-stage confirmation for destructive operations
- power actions, microphone permission state
- reminders
- updater checks and installation

The explicit command/argument inventory is in `TAURI_COMMAND_SURFACE.md`.

## Android porting

Reusing the HTML/JS is not sufficient by itself. Desktop-specific `Tauri.invoke` commands need Android implementations or a graceful unsupported state. In particular, file search, launching arbitrary local apps, autostart, power actions, reminders/background notifications, credential storage, and live voice permissions must be redesigned with Android APIs and user-consent boundaries.
