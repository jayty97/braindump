import json

import httpx
import pytest

from dictate.providers import Gateway, Provider, ProviderError


@pytest.mark.parametrize("url", ["http://example.com/v1", "https://user:secret@example.com", "https://api.example.com/v1?key=secret", "file:///tmp/test"])
def test_unsafe_urls_rejected(url):
    with pytest.raises(ValueError):
        Provider("test", url, "model").validate()


def test_openai_uses_responses_with_luna_reasoning():
    def handler(request):
        assert request.url.path == "/v1/responses"
        data = json.loads(request.content)
        assert data["model"] == "gpt-5.6-luna"
        assert data["reasoning"] == {"effort": "medium"}
        assert data["store"] is False
        assert "max_tokens" not in data
        return httpx.Response(200, json={"status": "completed", "output": [
            {"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": "Clean prompt"}]}]})
    gateway = Gateway(Provider("OpenAI", "https://api.openai.com/v1", "gpt-5.6-luna", "openai", "medium"), "test-only", httpx.MockTransport(handler))
    assert gateway.complete("Edit", "Um fix it") == "Clean prompt"


def test_current_transcribe_uses_languages_array():
    def handler(request):
        assert b'name="languages[]"' in request.content
        assert b'name="language"' not in request.content
        assert b'name="response_format"' not in request.content
        return httpx.Response(200, json={"text": "Testing"})
    gateway = Gateway(Provider("OpenAI", "https://api.openai.com/v1", "gpt-transcribe", "openai"), "test-only", httpx.MockTransport(handler))
    assert gateway.transcribe(b"wave", "en") == "Testing"


@pytest.mark.parametrize("adapter,endpoint,field", [("compatible", "/v1/audio/transcriptions", "model"), ("openai", "/v1/audio/transcriptions", "model"), ("elevenlabs", "/v1/speech-to-text", "model_id")])
def test_audio_provider_contracts(adapter, endpoint, field):
    def handler(request):
        assert request.url.path == endpoint
        assert f'name="{field}"'.encode() in request.content
        if adapter == "elevenlabs":
            assert request.headers["xi-api-key"] == "test-only"
            assert "authorization" not in request.headers
        else:
            assert request.headers["authorization"] == "Bearer test-only"
        return httpx.Response(200, json={"text": "Fix checkout"})
    gateway = Gateway(Provider("Test", "https://example.com/v1", "model", adapter), "test-only", httpx.MockTransport(handler))
    assert gateway.transcribe(b"wave", "en") == "Fix checkout"


def test_local_chat_needs_no_key():
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": "Prompt"}, "finish_reason": "stop"}]})
    gateway = Gateway(Provider("Local", "http://localhost:11434/v1", "llama3.2"), "", httpx.MockTransport(handler))
    assert gateway.complete("edit", "test") == "Prompt"


def test_errors_do_not_leak_provider_body():
    gateway = Gateway(Provider("Test", "https://example.com/v1", "model"), "test-only",
                      httpx.MockTransport(lambda _: httpx.Response(401, text="secret key test-only")))
    with pytest.raises(ProviderError) as error:
        gateway.complete("edit", "test")
    assert "test-only" not in str(error.value)


def test_truncation_not_presented_as_finished_prompt():
    gateway = Gateway(Provider("Local", "http://localhost/v1", "model"), "",
                      httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": [{"message": {"content": "Partial"}, "finish_reason": "length"}]})))
    with pytest.raises(ProviderError, match="output limit"):
        gateway.complete("edit", "test")
