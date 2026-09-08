# Provider integration notes

Source checks: September 8, 2026. API model availability depends on the user's account. Contract tests are mocked, not evidence of a paid live smoke test.

## OpenAI

The app uses direct HTTPS calls to the current APIs. File transcription uses `/v1/audio/transcriptions` with multipart `file`, `model`, and optional `languages[]` for GPT-Transcribe (legacy models use `language`). Writing uses `/v1/responses` with `instructions`, `input`, `max_output_tokens`, `store: false`, and selected `reasoning.effort`. Output is read from completed message/output_text content, not by assuming the first output item is text. Incomplete responses are rejected.

The selected defaults are `gpt-transcribe` and `gpt-5.6-luna` at low reasoning. GPT-6 Astra is the flagship alternative, not the inexpensive default. Reasoning can be changed to medium. Model IDs can be edited without a code release.

Sources: [file transcription](https://developers.openai.com/api/docs/guides/speech-to-text), [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [model catalog](https://developers.openai.com/api/docs/models), [Responses migration](https://developers.openai.com/api/docs/guides/migrate-to-responses), [deprecations](https://developers.openai.com/api/docs/deprecations).

## Groq

Base URL: `https://api.groq.com/openai/v1`. Uses bearer auth, multipart audio transcription, and Chat Completions text generation. The default speech model is `whisper-large-v3-turbo`; `whisper-large-v3` is also selectable.

Sources: [speech](https://console.groq.com/docs/speech-to-text), [OpenAI compatibility](https://console.groq.com/docs/openai).

## ElevenLabs

Base URL: `https://api.elevenlabs.io/v1`. Speech endpoint is `/speech-to-text`, uses `xi-api-key`, multipart `model_id` / `file`, and optional `language_code`. Audio-event tagging and diarization are disabled for individual dictation. Default model: `scribe_v2`.

Source: [Create transcript](https://elevenlabs.io/docs/api-reference/speech-to-text/convert).

## Local and custom servers

Ollama is a writing-only preset. A locally installed compatible speech server can be configured separately. The app does not install local inference runtimes or download model weights. Localhost accepts no key; remote endpoints require HTTPS and a user-supplied key. API keys are scoped to the exact base URL. Redirects are not followed.

Custom speech servers must accept multipart `POST /audio/transcriptions` and return a JSON object with a `text` string. Custom writing servers must accept `POST /chat/completions` with system/user messages and `max_tokens`, and return `choices[0].message.content`. Other protocols are not automatically compatible.

Source: [Ollama compatibility and context configuration](https://docs.ollama.com/api/openai-compatibility).

Mistral Voxtral was also researched: it offers a dedicated [audio transcription API](https://docs.mistral.ai/studio/audio/speech_to_text/offline_transcription). It is not a shipped preset in this release; a dedicated adapter should have contract tests before being advertised as supported.

## NVIDIA microphone support

NVIDIA Broadcast and RTX Voice are optional local noise-processing applications, not transcription providers. Dictate enumerates their virtual microphone devices and labels them as noise-filtered when present. Select one in the microphone picker after configuring the physical input in NVIDIA's application. Keep that application running while recording.

[NVIDIA Broadcast](https://www.nvidia.com/en-us/geforce/broadcasting/broadcast-app/) requires an RTX 2060 / Quadro RTX 3000 / TITAN RTX or newer supported GPU. A GTX 1080 does not meet Broadcast's requirement. NVIDIA's older [RTX Voice setup guide](https://www.nvidia.com/en-us/geforce/guides/nvidia-rtx-voice-setup-guide/) lists GTX and RTX support; it may be an option on a GTX 1080 with a supported Windows/driver combination. No NVIDIA software is installed or bundled by Dictate.

The system default microphone is always available as a normal fallback selection. Refreshing after a selected device disappears selects the default and reports that change. If the device fails during recording, Dictate stops and preserves the saved audio rather than silently switching microphones mid-session. A virtual device can exist but output silence if its source app is misconfigured; check the level meter after starting.

## Adding an adapter

1. Add a preset in `dictate/providers.py` with a concrete model, base URL, and adapter ID.
2. Implement its request contract in `Gateway`; keep provider-specific response objects out of the pipeline.
3. Add tests for auth, request fields, malformed responses, and incomplete/error responses.
4. Document official sources, current model IDs, limits and live validation status.
5. Never log API keys, provider response bodies, or user transcripts in error handling.
