import io
import threading
import wave
from types import SimpleNamespace

import pytest

from dictate.audio import audio_chunks
from dictate.pipeline import Cancelled, process, split_text
from dictate.providers import Provider, ProviderError
from dictate.storage import new_session, read_json, write_json


def recording(tmp_path, seconds=1, rate=16000):
    folder = new_session(tmp_path, "Test")
    meta = read_json(folder / "session.json")
    meta["sample_rate"] = rate
    write_json(folder / "session.json", meta)
    with (folder / "audio.pcm").open("wb") as output:
        for _ in range(seconds):
            output.write(b"\x01\x00" * rate)
    return folder


class Fake:
    provider = Provider("Test", "http://localhost:1234/v1", "test")

    def __init__(self, text="Fix the checkout button. Keep the cancel link."):
        self.speech_calls = 0
        self.text_calls = 0
        self.text = text
        self.fail = False

    def transcribe(self, _wav, _language):
        self.speech_calls += 1
        return self.text

    def complete(self, _instructions, content):
        self.text_calls += 1
        if self.fail:
            raise ProviderError("Temporary failure")
        return "Fix checkout. Preserve Cancel."


def test_hour_recording_chunk_bounds_and_coverage(tmp_path):
    folder = recording(tmp_path, seconds=3600)
    covered = 0
    count = 0
    for index, start, wav in audio_chunks(folder):
        assert len(wav) < 20_000_000
        with wave.open(io.BytesIO(wav)) as stream:
            end = start + stream.getnframes() / stream.getframerate()
            assert start <= covered
            assert start >= max(0, covered - 1.001)
            covered = end
        count += 1
    assert count == 13
    assert covered == 3600


def test_high_rate_uploads_stay_bounded(tmp_path):
    folder = recording(tmp_path, seconds=100, rate=192000)
    assert all(len(wav) < 20_000_000 for _, _, wav in audio_chunks(folder))


def test_resume_does_not_retranscribe(tmp_path):
    folder = recording(tmp_path)
    speech, writer = Fake(), Fake()
    writer.fail = True
    with pytest.raises(ProviderError):
        process(folder, speech, writer, "en", "App", threading.Event(), lambda _: None)
    assert (folder / "transcript.txt").exists()
    writer.fail = False
    output = process(folder, speech, writer, "en", "App", threading.Event(), lambda _: None)
    assert output == "Fix checkout. Preserve Cancel."
    assert speech.speech_calls == 1
    process(folder, speech, writer, "en", "App", threading.Event(), lambda _: None)
    assert writer.text_calls == 2
    assert (folder / "prompt.md").read_text() == output


def test_context_change_regenerates_only_prompt(tmp_path):
    folder = recording(tmp_path)
    speech, writer = Fake(), Fake()
    for context in ["Old app", "New app"]:
        process(folder, speech, writer, "en", context, threading.Event(), lambda _: None)
    assert speech.speech_calls == 1
    assert writer.text_calls == 2


def test_cancel_before_network(tmp_path):
    folder = recording(tmp_path)
    speech = Fake()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        process(folder, speech, Fake(), "en", "", cancel, lambda _: None)
    assert speech.speech_calls == 0


def test_empty_transcription_never_calls_writer(tmp_path):
    folder = recording(tmp_path)
    writer = Fake()
    with pytest.raises(ProviderError, match="No speech"):
        process(folder, Fake(""), writer, "en", "", threading.Event(), lambda _: None)
    assert writer.text_calls == 0


def test_long_transcript_organized_before_composition(tmp_path):
    folder = recording(tmp_path)
    writer = Fake()
    process(folder, Fake("Keep this request. " * 2000), writer, "en", "", threading.Event(), lambda _: None)
    assert writer.text_calls > 2
    assert (folder / "organized-notes.md").exists()


def test_split_keeps_all_words_and_bounds():
    original = "This is a requirement.\n" * 4000
    parts = list(split_text(original))
    assert all(len(part) <= 10000 for part in parts)
    assert " ".join(" ".join(parts).split()) == " ".join(original.split())
