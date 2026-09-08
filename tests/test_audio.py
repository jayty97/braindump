import queue

import pytest

from dictate.audio import Recorder
from dictate.storage import new_session


def test_pause_does_not_enqueue_audio(tmp_path):
    recorder = Recorder(new_session(tmp_path, "Test"))
    recorder.paused = True
    recorder._callback(b"\x00\x01" * 1600, 1600, None, False)
    assert recorder.blocks.empty()
    assert recorder.level == 0


def test_writer_drains_recording_before_stop(tmp_path):
    recorder = Recorder(new_session(tmp_path, "Test"))
    block = b"\x00\x01" * 1600
    for _ in range(3):
        recorder._callback(block, 1600, None, False)
    recorder.done.set()
    recorder._write()
    assert (recorder.folder / "audio.pcm").read_bytes() == block * 3
    assert recorder.frames == 4800


def test_queue_overflow_reported_instead_of_silent_loss(tmp_path):
    recorder = Recorder(new_session(tmp_path, "Test"))
    recorder.blocks = queue.Queue(maxsize=1)
    recorder._callback(b"\x00\x01" * 1600, 1600, None, False)
    import sounddevice
    with pytest.raises(sounddevice.CallbackAbort):
        recorder._callback(b"\x00\x01" * 1600, 1600, None, False)
    assert "Disk" in recorder.error
