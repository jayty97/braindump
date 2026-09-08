import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from dictate.app import KeyStore, ProviderForm, SPEECH_PRESETS, STYLE, Window
from dictate.providers import Provider
from dictate.storage import new_session, write_text


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setStyleSheet(STYLE)
    yield instance


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setattr("dictate.app.sd.query_devices", lambda: [])
    monkeypatch.setattr("dictate.app.keyring.get_password", lambda *_: None)
    instance = Window(tmp_path)
    yield instance
    instance.timer.stop()
    instance.autosave.stop()
    instance.tray.hide()
    instance.quitting = True
    instance.close()


def test_initial_controls_and_current_models(window):
    assert window.start_btn.isEnabled()
    assert not window.stop_btn.isEnabled()
    assert not window.process_btn.isEnabled()
    assert window.writer.model == "gpt-5.6-luna"
    assert window.writer.reasoning == "low"
    assert window.speech.model == "gpt-transcribe"


def test_edit_persistence_and_session_switch(window):
    window.folder = new_session(window.root, "Checkout")
    first = window.folder
    window.title.setText("Checkout")
    window.prompt.setPlainText("Keep this user edit.")
    window.save_edits()
    assert (first / "prompt.md").read_text() == "Keep this user edit."
    window.new()
    window.refresh_sessions()
    window.history.setCurrentRow(0)
    assert window.prompt.toPlainText() == "Keep this user edit."


def test_changing_provider_never_carries_key(app, monkeypatch):
    monkeypatch.setattr("dictate.app.keyring.get_password", lambda *_: None)
    keys = KeyStore()
    provider = Provider("OpenAI", "https://api.openai.com/v1", "gpt-transcribe", "openai")
    keys.memory[provider.key_id] = "test-only"
    form = ProviderForm(SPEECH_PRESETS, provider, keys)
    assert form.key.text() == "test-only"
    form.name.setCurrentText("Groq")
    assert form.key.text() == ""
    assert form.value().model == "whisper-large-v3-turbo"


def test_clear_prompt_persists(window):
    window.folder = new_session(window.root, "Test")
    window.prompt.setPlainText("Old text")
    window.save_edits()
    window.prompt.clear()
    window.save_edits()
    assert (window.folder / "prompt.md").read_text() == ""


def test_nvidia_inputs_and_missing_device_fallback(window, monkeypatch):
    monkeypatch.setattr("dictate.app.sd.query_hostapis", lambda _: {"name": "WASAPI"})
    monkeypatch.setattr("dictate.app.sd.query_devices", lambda: [
        {"name": "USB Microphone", "hostapi": 0, "max_input_channels": 1},
        {"name": "Microphone (NVIDIA RTX Voice)", "hostapi": 0, "max_input_channels": 1}])
    window.refresh_devices()
    assert "Noise-filtered" in window.device.itemText(1)
    window.device.setCurrentIndex(1)
    monkeypatch.setattr("dictate.app.sd.query_devices", lambda: [])
    window.refresh_devices()
    assert window.device.currentData() is None
    assert "system default" in window.status.text()
