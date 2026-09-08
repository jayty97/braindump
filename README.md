# Dictate Workbench

**Think out loud. Build what's next.**

A small Python desktop app for recording app-testing walkthroughs and turning them into clear, ready-to-paste prompts. Start recording, test your app, say what you notice, stop, and process. Bring your own API keys. No app subscription, hosted backend, telemetry, or account to create with this project.

![Dictate Workbench interface with synthetic example text](docs/screenshot.png)

## Features

- Modern dark desktop interface, microphone selection, timer, level meter, pause/resume.
- Continues recording when minimized; closing the window hides it to the system tray where available.
- Audio writes to disk continuously, with bounded memory use for long sessions.
- Separate providers and model IDs for speech-to-text and prompt writing.
- OpenAI Responses API with GPT-5.6 Luna and low/medium reasoning.
- OpenAI GPT-Transcribe, Groq Whisper, and ElevenLabs Scribe transcription adapters.
- Ollama and custom OpenAI-compatible text endpoints, plus compatible speech servers.
- Saved session history, original transcript, editable final prompt, copy and export.
- Completed API steps are cached; retries resume when audio, model, endpoint, and instructions match.
- Optional API-key storage in the operating system credential store; otherwise keys stay in memory.

## Quick start on Windows

Requires **Python 3.11 or newer** with the Python launcher (`py`).

1. Download or clone this repository and extract it to a writable folder.
2. Double-click **setup.cmd** once to install the app's dependencies in `.venv`.
3. Double-click **Start Dictate.cmd**.
4. Open **Provider settings**. Enter your API key and choose your providers. When both stages use the same endpoint, entering a key fills both tabs.
5. Optionally enable **Remember keys**. Otherwise re-enter your key after quitting.
6. Choose the microphone, click **Start**, and speak while testing your app.
7. Click **Stop**, then **Process**. Review the result and copy it into your coding agent.

Closing the window keeps the app in the system tray. Double-click its tray icon to return, or right-click it and select **Quit**. With no system tray, closing requests a normal quit. No recording or upload starts automatically.

### Optional NVIDIA noise removal

Select the NVIDIA Broadcast or RTX Voice virtual microphone in the picker if installed. These inputs are labeled **Noise-filtered**. Otherwise use your normal microphone; Dictate needs no GPU. Configure noise removal in the NVIDIA application first. Broadcast requires an RTX-class GPU; a GTX 1080 may use the older RTX Voice option. See [requirements and fallback behavior](docs/PROVIDERS.md#nvidia-microphone-support).

## macOS / Linux / developer setup

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m dictate
```

Linux may require system PortAudio (`libportaudio2`), Qt/X11 dependencies, and a desktop credential-store service. macOS requires microphone permission for the launching application. Windows is the primary tested platform; macOS/Linux packaging and microphone behavior need testing on those systems.

## Providers and current defaults

Documentation checked **September 8, 2026**. Model IDs remain editable because provider availability changes.

| Stage | Provider | Default model | API |
| --- | --- | --- | --- |
| Speech | OpenAI | `gpt-transcribe` | `/v1/audio/transcriptions` |
| Speech | Groq | `whisper-large-v3-turbo` | `/openai/v1/audio/transcriptions` |
| Speech | ElevenLabs | `scribe_v2` | `/v1/speech-to-text` |
| Speech | Custom compatible | User chosen | `/audio/transcriptions` below the base URL |
| Writing | OpenAI | `gpt-5.6-luna` | `/v1/responses`, low reasoning by default |
| Writing | Groq | `llama-3.3-70b-versatile` | `/openai/v1/chat/completions` |
| Writing | Ollama | `llama3.2` | Local `/v1/chat/completions` |
| Writing | Custom compatible | User chosen | `/chat/completions` below the base URL |

OpenAI Settings also offers GPT-6 Astra, GPT-5.6 Terra, and GPT-5.6 Sol. Luna is the selected cost-sensitive default. Low/medium reasoning applies to OpenAI writing requests, not speech processing. Whisper remains manually selectable for legacy compatibility; OpenAI's deprecation notice schedules `whisper-1` retirement for February 26, 2027. The default uses its current recommended replacement.

“Custom compatible” means the server must implement the indicated API contract. It is not a promise that every AI vendor uses the same API. Providers with different authentication or request formats need an adapter. No provider is silently substituted when a request fails.

For Ollama, install and start Ollama separately and pull a model (for example `ollama pull llama3.2`). Enter the exact installed model ID. No API key is needed for localhost. Larger sessions may require increasing the model's context size; see [Ollama's compatibility documentation](https://docs.ollama.com/api/openai-compatibility).

## Cost and privacy

Recording itself is offline. **Process** sends saved audio to your selected speech provider and transcript/context to your writing provider. You pay those services directly under their pricing and account terms. A ChatGPT subscription does not supply API credit.

As checked September 8, 2026, [GPT-Transcribe](https://developers.openai.com/api/docs/models/gpt-transcribe) lists $0.0045/minute (about $0.27 for one hour, plus small chunk overlap). [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna) lists $0.20/million input tokens and $1.20/million output tokens; reasoning contributes to output usage. These are reference rates, not a billing quote. [Groq's speech documentation](https://console.groq.com/docs/speech-to-text) lists $0.04/hour for Whisper Large V3 Turbo. Check your provider's current account pricing and limits.

No microphone audio is sent while recording. The app does not implement live captions, spoken replies, voice cloning, or an always-listening wake word. Paused time is not recorded. Recordings are not encrypted by the app. Protect the local user account and disk accordingly. OpenAI writing requests set `store: false`; provider retention policies still apply.

Keys are never written to project files or exported transcripts. If **Remember keys** is checked, `keyring` uses the OS credential store. If that store is unavailable, leave Remember unchecked for temporary in-memory keys. To remove a saved key, select its endpoint, clear the key, and save. Custom remote endpoints require HTTPS; HTTP is allowed only for localhost. Confirm the custom endpoint belongs to the provider you intend to trust.

## Saved recordings and recovery

Use **Open saved files** to locate the current session. Defaults:

- Windows: `%LOCALAPPDATA%\DictateWorkbench`
- macOS: `~/Library/Application Support/DictateWorkbench`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/dictate-workbench`

Set `DICTATE_DATA_DIR` to override the data folder. Keep it outside the source tree, particularly before publishing the repository.

Each session stores `audio.pcm` (mono signed 16-bit PCM), its sample rate in `session.json`, `transcript.txt`, `prompt.md`, and reusable processing cache entries. These contain your private session material. Recordings remain until you delete them through your file manager. Quit the app first when deleting session folders.

The recorder tries 16 kHz and falls back to the microphone's default sample rate. One hour is about 115 MB at 16 kHz, or 346 MB at 48 kHz. Processing wraps at most five minutes at a time in WAV with one second of overlap, and keeps each upload below 20 MB. Previously recorded PCM can be recovered after an unexpected shutdown as long as the session metadata survives; the latest unflushed operating-system writes can be lost on power failure.

After a network error, reopen the session and click **Process** again. Completed chunks are reused. A timed-out request may already have been billed, and retrying that request may cost again. Cancel stops after the in-flight request returns; it does not undo a request already sent.

Prompt writing preserves explicit corrections, details, constraints, and unresolved questions in its instructions. This is not a guarantee that a model never omits or mishears a detail. Review the original transcript and final prompt before using them. Longer transcripts for smaller compatible models are organized in sections before final composition; intermediate notes are saved. Errors and truncation are reported instead of treating partial output as complete.

## Development

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

Tests use synthetic audio and mocked provider responses, with no credentials, paid requests, or microphone capture. To render the real UI with synthetic example text:

```sh
python -m scripts.preview
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [docs/PROVIDERS.md](docs/PROVIDERS.md), and [docs/RELEASING.md](docs/RELEASING.md). Public distribution is pending the project owner's license selection; see [LICENSE-PENDING.md](LICENSE-PENDING.md).

## Official references

- [OpenAI model catalog](https://developers.openai.com/api/docs/models)
- [OpenAI file transcription](https://developers.openai.com/api/docs/guides/speech-to-text)
- [OpenAI Responses API migration guidance](https://developers.openai.com/api/docs/guides/migrate-to-responses)
- [OpenAI deprecations](https://developers.openai.com/api/docs/deprecations)
- [Groq speech-to-text](https://console.groq.com/docs/speech-to-text) and [compatibility](https://console.groq.com/docs/openai)
- [ElevenLabs Scribe API](https://elevenlabs.io/docs/api-reference/speech-to-text/convert)
- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
