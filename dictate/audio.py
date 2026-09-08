from __future__ import annotations

import io
import queue
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from .storage import read_json, write_json


class Recorder:
    """A bounded queue keeps disk writes out of the audio callback."""

    def __init__(self, folder: Path, device=None):
        self.folder = folder
        self.device = device
        self.rate = 16000
        self.level = 0.0
        self.frames = 0
        self.error = ""
        self.paused = False
        self.stream = None
        self.blocks = queue.Queue(maxsize=256)
        self.done = threading.Event()
        self.thread = None

    def start(self):
        try:
            sd.check_input_settings(device=self.device, channels=1, dtype="int16", samplerate=self.rate)
        except sd.PortAudioError:
            self.rate = int(sd.query_devices(self.device, "input")["default_samplerate"])
        metadata = read_json(self.folder / "session.json")
        metadata["sample_rate"] = self.rate
        write_json(self.folder / "session.json", metadata)
        self.stream = sd.RawInputStream(device=self.device, channels=1, dtype="int16",
                                        samplerate=self.rate, blocksize=int(self.rate / 10),
                                        callback=self._callback)
        self.thread = threading.Thread(target=self._write, daemon=True)
        self.thread.start()
        try:
            self.stream.start()
        except Exception:
            self.stop()
            raise

    def _callback(self, data, frames, _time, status):
        if status:
            self.error = "Microphone data was interrupted. Recording stopped to avoid silently losing notes."
            raise sd.CallbackAbort
        if self.paused:
            self.level = 0
            return
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        self.level = float(np.sqrt(np.mean(samples * samples)) / 32768)
        try:
            self.blocks.put_nowait(bytes(data))
        except queue.Full:
            self.error = "Disk could not keep up with recording. Saved audio is still available."
            raise sd.CallbackAbort

    def _write(self):
        try:
            with (self.folder / "audio.pcm").open("wb") as output:
                while not self.done.is_set() or not self.blocks.empty():
                    try:
                        block = self.blocks.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    output.write(block)
                    output.flush()
                    self.frames += len(block) // 2
        except OSError:
            self.error = "Could not save recording. Check free disk space and folder permissions."

    def stop(self):
        try:
            if self.stream:
                try:
                    self.stream.stop()
                finally:
                    self.stream.close()
        except sd.PortAudioError:
            self.error = self.error or "Microphone disconnected. Available audio was saved."
        finally:
            self.done.set()
            if self.thread:
                self.thread.join()


def audio_chunks(folder: Path, seconds=300, overlap=1):
    """Bound every WAV to <20 MB, with a second of context across boundaries."""
    rate = int(read_json(folder / "session.json")["sample_rate"])
    if not 8000 <= rate <= 384000:
        raise ValueError("Unsupported recording sample rate.")
    size = min(int(seconds * rate), 18_000_000 // 2)
    overlap_frames = min(int(overlap * rate), size // 4)
    total = (folder / "audio.pcm").stat().st_size // 2
    start = 0
    index = 0
    with (folder / "audio.pcm").open("rb") as source:
        while start < total:
            source.seek(start * 2)
            pcm = source.read(min(size, total - start) * 2)
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(rate)
                output.writeframes(pcm)
            yield index, start / rate, buffer.getvalue()
            if start + size >= total:
                break
            start += size - overlap_frames
            index += 1


def duration(folder: Path) -> float:
    try:
        rate = read_json(folder / "session.json")["sample_rate"]
        return (folder / "audio.pcm").stat().st_size / (2 * rate)
    except (OSError, KeyError, ZeroDivisionError):
        return 0
