"""Small provider adapters. No SDK-specific objects cross this boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

import httpx


SPEECH_PRESETS = {
    "OpenAI": ("https://api.openai.com/v1", "gpt-transcribe", "openai"),
    "Groq": ("https://api.groq.com/openai/v1", "whisper-large-v3-turbo", "compatible"),
    "ElevenLabs": ("https://api.elevenlabs.io/v1", "scribe_v2", "elevenlabs"),
    "Custom compatible": ("http://localhost:8000/v1", "whisper-1", "compatible"),
}
TEXT_PRESETS = {
    "OpenAI": ("https://api.openai.com/v1", "gpt-5.6-luna", "openai"),
    "Groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "compatible"),
    "Ollama (local)": ("http://localhost:11434/v1", "llama3.2", "compatible"),
    "Custom compatible": ("http://localhost:1234/v1", "", "compatible"),
}


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    model: str
    adapter: str = "compatible"
    reasoning: str = "low"

    def validate(self):
        url = urlsplit(self.base_url)
        if (not url.hostname or url.username or url.password or url.query or url.fragment
                or url.scheme not in ("http", "https")):
            raise ValueError("Enter a base URL with no credentials, query, or fragment.")
        if url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Remote providers require HTTPS. HTTP is allowed only on this computer.")
        if not self.model.strip():
            raise ValueError("Enter a model ID for each provider.")
        if self.adapter not in ("compatible", "elevenlabs", "openai"):
            raise ValueError("Unsupported provider adapter.")
        if self.reasoning not in ("low", "medium"):
            raise ValueError("Choose low or medium reasoning.")

    @property
    def local(self):
        return urlsplit(self.base_url).hostname in ("localhost", "127.0.0.1", "::1")

    @property
    def key_id(self):
        # Credentials stay bound to the exact endpoint, including custom URLs.
        return self.base_url.rstrip("/")

    def to_dict(self):
        return asdict(self)


class ProviderError(Exception):
    pass


class Gateway:
    def __init__(self, provider: Provider, key: str, transport=None):
        provider.validate()
        if not key and not provider.local:
            raise ProviderError(f"Add an API key for {provider.name} in Settings.")
        self.provider = provider
        self.key = key
        self.transport = transport

    def request(self, endpoint: str, **kwargs):
        headers = {}
        if self.key:
            headers["xi-api-key" if self.provider.adapter == "elevenlabs" else "Authorization"] = (
                self.key if self.provider.adapter == "elevenlabs" else f"Bearer {self.key}"
            )
        try:
            # No automatic paid retries or redirects to a different host.
            with httpx.Client(timeout=httpx.Timeout(180, connect=15),
                              follow_redirects=False, transport=self.transport) as client:
                result = client.post(self.provider.base_url.rstrip("/") + endpoint,
                                     headers=headers, **kwargs)
            if result.status_code >= 300:
                explanations = {
                    401: "API key rejected. Check this provider's key in Settings.",
                    403: "Access denied. Check model and project permissions.",
                    404: "Endpoint or model not found. Check Settings.",
                    413: "Audio upload too large for this provider.",
                    429: "Rate limit or credit balance reached. Check your provider account, then retry.",
                }
                raise ProviderError(explanations.get(result.status_code,
                                    f"Provider returned HTTP {result.status_code}. Your session is saved; retry later."))
            return result.json()
        except httpx.TimeoutException:
            raise ProviderError("The provider timed out. Your session is saved. Retry may incur a duplicate charge.") from None
        except httpx.HTTPError:
            raise ProviderError("Could not reach the provider. Check the URL and internet connection.") from None
        except ValueError:
            raise ProviderError("Provider returned an unexpected response format.") from None

    def transcribe(self, wav: bytes, language: str = "") -> str:
        if self.provider.adapter == "elevenlabs":
            data = {"model_id": self.provider.model, "tag_audio_events": "false", "diarize": "false"}
            if language:
                data["language_code"] = language
            result = self.request("/speech-to-text", data=data,
                                  files={"file": ("recording.wav", wav, "audio/wav")})
        else:
            data = {"model": self.provider.model}
            if self.provider.adapter == "openai" and self.provider.model.startswith("gpt-transcribe"):
                if language:
                    data["languages[]"] = language
            else:
                data["response_format"] = "json"
                if language:
                    data["language"] = language
            result = self.request("/audio/transcriptions", data=data,
                                  files={"file": ("recording.wav", wav, "audio/wav")})
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ProviderError("Transcription provider did not return text.")
        return result["text"].strip()

    def complete(self, instructions: str, content: str) -> str:
        if self.provider.adapter == "openai":
            payload = {"model": self.provider.model, "instructions": instructions,
                       "input": content, "max_output_tokens": 16384, "store": False}
            if self.provider.model.startswith(("gpt-5", "gpt-6")):
                payload["reasoning"] = {"effort": self.provider.reasoning}
            result = self.request("/responses", json=payload)
            try:
                if result.get("status") != "completed":
                    raise ProviderError("OpenAI did not finish the response. Your transcript is saved; retry or choose another model.")
                text = "\n".join(
                    item["text"] for output in result["output"]
                    if output.get("type") == "message"
                    for item in output.get("content", []) if item.get("type") == "output_text"
                )
                if not text.strip():
                    raise ValueError()
                return text.strip()
            except (AttributeError, KeyError, TypeError, ValueError):
                raise ProviderError("OpenAI did not return usable text.") from None
        result = self.request("/chat/completions", json={
            "model": self.provider.model,
            "messages": [{"role": "system", "content": instructions},
                         {"role": "user", "content": content}],
            "max_tokens": 8192,
        })
        try:
            choice = result["choices"][0]
            text = choice["message"]["content"]
            if choice.get("finish_reason") == "length":
                raise ProviderError("The model hit its output limit. Choose another model; your transcript is saved.")
            if not isinstance(text, str) or not text.strip():
                raise ValueError()
            return text.strip()
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("Text provider did not return usable text.") from None
