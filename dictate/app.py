from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import keyring
import sounddevice as sd
from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QSplitter, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget,
)

from .audio import Recorder, duration
from .pipeline import Cancelled, process
from .providers import Gateway, Provider, ProviderError, SPEECH_PRESETS, TEXT_PRESETS
from .storage import data_directory, new_session, read_json, sessions, write_json, write_text


STYLE = """
QWidget { background: #10141d; color: #e8edf5; font-family: 'Segoe UI'; font-size: 14px; }
QMainWindow, QDialog { background: #10141d; }
QLabel#brand { font-size: 24px; font-weight: 700; color: #88efcc; }
QLabel#heading { font-size: 29px; font-weight: 650; }
QLabel#muted { color: #98a6bb; }
QLabel#clock { font-size: 44px; font-weight: 600; }
QFrame#card { background: #191f2c; border: 1px solid #2b3445; border-radius: 16px; }
QFrame#card QLabel { background: transparent; }
QPushButton { background: #263145; border: 1px solid #35435b; border-radius: 9px;
              padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #344560; }
QPushButton#primary { background: #84edc6; color: #10291f; border: 0; }
QPushButton#primary:hover { background: #a6f6db; }
QPushButton#stop { background: #59323d; color: #ffb9c4; border: 1px solid #7a4654; }
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#stop:disabled { background: #1e2633; color: #627086; border-color: #2a3444; }
QLineEdit, QComboBox, QPlainTextEdit { background: #171e2b; border: 1px solid #354159;
                border-radius: 8px; padding: 9px; selection-background-color: #396b60; }
QLineEdit:focus, QPlainTextEdit:focus { border-color: #84edc6; }
QComboBox QAbstractItemView { background: #202b3c; selection-background-color: #355b55; }
QListWidget { background: transparent; border: 0; outline: 0; }
QListWidget::item { padding: 12px; margin: 3px 0; border-radius: 9px; }
QListWidget::item:selected { background: #243d3d; color: #a1f2d4; }
QTabWidget::pane { border: 0; }
QTabBar::tab { padding: 12px 18px; color: #93a2b9; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #9af4d1; border-bottom-color: #84edc6; }
QProgressBar { background: #263144; border: 0; border-radius: 4px; min-height: 7px; max-height: 7px; }
QProgressBar::chunk { background: #84edc6; border-radius: 4px; }
QScrollBar:vertical { background: #182130; width: 10px; }
QScrollBar::handle:vertical { background: #3e4b61; border-radius: 5px; min-height: 24px; }
QMenu { background: #202b3c; padding: 6px; }
QMenu::item { padding: 8px 20px; }
QMenu::item:selected { background: #355b55; }
"""


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, action, name=None):
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    widget.clicked.connect(action)
    return widget


def icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#84edc6"))
    for x, height in [(10, 16), (21, 32), (32, 46), (43, 26), (54, 12)]:
        painter.drawRoundedRect(x - 4, 32 - height // 2, 7, height, 3, 3)
    painter.end()
    return QIcon(pixmap)


class KeyStore:
    def __init__(self):
        self.memory = {}

    def get(self, provider):
        if provider.key_id in self.memory:
            return self.memory[provider.key_id]
        try:
            return keyring.get_password("DictateWorkbench", provider.key_id) or ""
        except Exception:
            return ""

    def put(self, provider, value, remember):
        if remember and value:
            try:
                keyring.set_password("DictateWorkbench", provider.key_id, value)
            except Exception:
                raise ValueError("The operating system key store is unavailable. Uncheck Remember keys to use them for this run.") from None
        else:
            try:
                if keyring.get_password("DictateWorkbench", provider.key_id):
                    keyring.delete_password("DictateWorkbench", provider.key_id)
            except keyring.errors.NoKeyringError:
                pass
            except Exception:
                raise ValueError("Could not remove a saved key from the operating system key store.") from None
        self.memory[provider.key_id] = value


class ProviderForm(QWidget):
    def __init__(self, presets, provider, keys):
        super().__init__()
        self.presets = presets
        self.keys = keys
        layout = QFormLayout(self)
        layout.setSpacing(13)
        self.name = QComboBox()
        self.name.addItems(presets)
        self.url = QLineEdit()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Your API key (not needed for local servers)")
        self.adapter = "compatible"
        self.reasoning = QComboBox()
        self.reasoning.addItems(["low", "medium"])
        self.reasoning.setCurrentText(provider.reasoning)
        for title, field in [("Provider", self.name), ("Base URL", self.url), ("Model ID", self.model), ("API key", self.key)]:
            layout.addRow(title, field)
        if presets is TEXT_PRESETS:
            layout.addRow("OpenAI reasoning", self.reasoning)
        self.name.currentTextChanged.connect(self.preset_changed)
        self.url.textChanged.connect(self.endpoint_changed)
        self.name.setCurrentText(provider.name)
        self.preset_changed(provider.name)
        self.url.setText(provider.base_url)
        self.model.setCurrentText(provider.model)
        self.adapter = provider.adapter

    def preset_changed(self, name):
        url, model, self.adapter = self.presets[name]
        self.url.setText(url)
        self.url.setReadOnly(name != "Custom compatible")
        self.model.clear()
        self.model.addItem(model)
        if self.presets is SPEECH_PRESETS and name == "OpenAI":
            self.model.addItems(["whisper-1"])
        if self.presets is TEXT_PRESETS and name == "OpenAI":
            self.model.addItems(["gpt-6-astra", "gpt-5.6-terra", "gpt-5.6-sol"])
        if self.presets is SPEECH_PRESETS and name == "Groq":
            self.model.addItem("whisper-large-v3")
        self.endpoint_changed()

    def endpoint_changed(self):
        self.key.setText(self.keys.get(self.value()))

    def value(self):
        return Provider(self.name.currentText(), self.url.text().strip().rstrip("/"),
                        self.model.currentText().strip(), self.adapter, self.reasoning.currentText())


class Settings(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Providers & preferences")
        self.setMinimumWidth(650)
        self.owner = parent
        layout = QVBoxLayout(self)
        layout.addWidget(label("Bring your own providers", "heading"))
        intro = label("Choose speech and writing separately. Keys are bound to each provider URL.", "muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        tabs = QTabWidget()
        self.speech = ProviderForm(SPEECH_PRESETS, parent.speech, parent.keys)
        self.writer = ProviderForm(TEXT_PRESETS, parent.writer, parent.keys)
        # One key entry suffices when both stages use the same endpoint.
        self.speech.key.textEdited.connect(lambda value: self.writer.key.setText(value)
            if self.speech.value().key_id == self.writer.value().key_id else None)
        self.writer.key.textEdited.connect(lambda value: self.speech.key.setText(value)
            if self.speech.value().key_id == self.writer.value().key_id else None)
        tabs.addTab(self.speech, "Speech to text")
        tabs.addTab(self.writer, "Prompt writing")
        layout.addWidget(tabs)
        self.language = QLineEdit(parent.config.get("language", "en"))
        self.language.setPlaceholderText("en, es, fr… Leave blank for automatic detection")
        form = QFormLayout()
        form.addRow("Speech language", self.language)
        layout.addLayout(form)
        self.remember = QCheckBox("Remember keys in the operating system's secure key store")
        self.remember.setChecked(parent.config.get("remember", False))
        layout.addWidget(self.remember)
        note = label("Recording stays on this computer. Process sends audio to the speech provider\nand text to the writing provider. Provider usage charges apply.", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        try:
            speech, writer = self.speech.value(), self.writer.value()
            speech.validate()
            writer.validate()
            if (speech.key_id == writer.key_id and self.speech.key.text().strip()
                    != self.writer.key.text().strip()):
                raise ValueError("Both selections use the same endpoint. Enter the same key on both tabs.")
            for form in (self.speech, self.writer):
                self.owner.keys.put(form.value(), form.key.text().strip(), self.remember.isChecked())
            config = {"speech": speech.to_dict(), "writer": writer.to_dict(),
                      "language": self.language.text().strip(), "remember": self.remember.isChecked()}
            write_json(self.owner.root / "settings.json", config)
            self.owner.config = config
            self.owner.speech, self.owner.writer = speech, writer
            self.owner.update_route()
            self.accept()
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Settings", str(exc))


class ProcessingThread(QThread):
    progress = Signal(str)
    result = Signal(str)
    failed = Signal(str)

    def __init__(self, folder, speech, writer, language, context):
        super().__init__()
        self.args = folder, speech, writer, language, context
        self.cancel = threading.Event()

    def run(self):
        try:
            self.result.emit(process(*self.args, self.cancel, self.progress.emit))
        except Cancelled:
            self.failed.emit("Processing canceled. Completed work is saved for retry.")
        except (ProviderError, ValueError) as exc:
            self.failed.emit(str(exc))
        except Exception:
            # Raw exceptions can contain credentials, provider responses or personal text.
            self.failed.emit("Processing failed. Check disk space and provider settings. Your saved session can be retried.")


class Window(QMainWindow):
    def __init__(self, root=None):
        super().__init__()
        self.root = root or data_directory()
        self.root.mkdir(parents=True, exist_ok=True)
        self.config = read_json(self.root / "settings.json")
        self.keys = KeyStore()
        self.speech = Provider(**self.config.get("speech", dict(name="OpenAI", base_url=SPEECH_PRESETS["OpenAI"][0], model="gpt-transcribe", adapter="openai")))
        self.writer = Provider(**self.config.get("writer", dict(name="OpenAI", base_url=TEXT_PRESETS["OpenAI"][0], model="gpt-5.6-luna", adapter="openai")))
        self.folder = None
        self.recorder = None
        self.worker = None
        self.quitting = False
        self.dirty = False
        self.setWindowTitle("Dictate Workbench")
        self.setWindowIcon(icon())
        self.resize(1220, 820)
        self.setMinimumSize(950, 700)
        self.build_ui()
        self.build_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(120)
        self.autosave = QTimer(self)
        self.autosave.timeout.connect(self.save_edits)
        self.autosave.start(1500)
        self.refresh_sessions()
        self.refresh_devices()
        self.update_route()
        self.update_controls()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(24, 24, 24, 24)
        main.setSpacing(25)
        sidebar = QVBoxLayout()
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(icon().pixmap(32, 32))
        brand.addWidget(logo)
        brand.addWidget(label("dictate", "brand"))
        brand.addStretch()
        sidebar.addLayout(brand)
        sidebar.addWidget(label("THOUGHTS → NEXT ITERATION", "muted"))
        sidebar.addSpacing(20)
        self.new_btn = button("+  New session", self.new)
        sidebar.addWidget(self.new_btn)
        sidebar.addSpacing(14)
        sidebar.addWidget(label("YOUR SESSIONS", "muted"))
        self.history = QListWidget()
        self.history.setMinimumWidth(220)
        self.history.setMaximumWidth(270)
        self.history.currentItemChanged.connect(self.select_session)
        sidebar.addWidget(self.history, 1)
        self.settings_btn = button("Provider settings", self.settings)
        sidebar.addWidget(self.settings_btn)
        sidebar.addWidget(button("Open saved files", self.open_files))
        sidebar.addWidget(label("Local app · Your API keys\nNo app subscription", "muted"))
        main.addLayout(sidebar)
        body = QVBoxLayout()
        body.setSpacing(14)
        body.addWidget(label("Think out loud. Build what’s next.", "heading"))
        body.addWidget(label("Record your walkthrough, then turn it into a clear prompt.", "muted"))
        self.title = QLineEdit()
        self.title.setPlaceholderText("Session name — e.g. Checkout flow, round 2")
        body.addWidget(self.title)
        self.context = QLineEdit()
        self.context.setMaxLength(6000)
        self.context.setPlaceholderText("Optional context: app name, terminology, or goal for this walkthrough")
        body.addWidget(self.context)
        self.title.textEdited.connect(self.mark_dirty)
        self.context.textEdited.connect(self.mark_dirty)
        card = QFrame()
        card.setObjectName("card")
        recording = QVBoxLayout(card)
        recording.setContentsMargins(20, 14, 20, 18)
        clock_row = QHBoxLayout()
        self.clock = label("00:00:00", "clock")
        clock_row.addWidget(self.clock)
        clock_row.addStretch()
        self.state = label("READY TO RECORD", "muted")
        clock_row.addWidget(self.state)
        recording.addLayout(clock_row)
        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setValue(0)
        self.meter.setTextVisible(False)
        recording.addWidget(self.meter)
        mic_row = QHBoxLayout()
        self.device = QComboBox()
        mic_row.addWidget(self.device, 1)
        self.refresh_btn = button("Refresh", self.refresh_devices)
        mic_row.addWidget(self.refresh_btn)
        recording.addLayout(mic_row)
        self.mic_hint = label("Works with standard and virtual microphones. No GPU required.", "muted")
        self.mic_hint.setWordWrap(True)
        recording.addWidget(self.mic_hint)
        controls = QHBoxLayout()
        self.start_btn = button("●  Start", self.start, "primary")
        self.pause_btn = button("Pause", self.pause)
        self.stop_btn = button("■  Stop", self.stop, "stop")
        self.process_btn = button("Process", self.process, "primary")
        self.cancel_btn = button("Cancel", self.cancel)
        for item in (self.start_btn, self.pause_btn, self.stop_btn, self.process_btn, self.cancel_btn):
            controls.addWidget(item)
        recording.addLayout(controls)
        body.addWidget(card)
        self.route = label("", "muted")
        self.route.setWordWrap(True)
        body.addWidget(self.route)
        self.tabs = QTabWidget()
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Your next-iteration prompt will appear here.\n\nSpecific requests, examples, constraints, and open questions — with the filler removed.")
        self.prompt.textChanged.connect(self.mark_dirty)
        self.transcript = QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("The original transcript stays here so you can check every detail.")
        self.tabs.addTab(self.prompt, "Ready-to-use prompt")
        self.tabs.addTab(self.transcript, "Original transcript")
        body.addWidget(self.tabs, 1)
        footer = QHBoxLayout()
        self.status = label("Start a session whenever you’re ready.", "muted")
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        self.copy_btn = button("Copy text", self.copy)
        self.export_btn = button("Export…", self.export)
        footer.addWidget(self.copy_btn)
        footer.addWidget(self.export_btn)
        body.addLayout(footer)
        main.addLayout(body, 1)

    def build_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu(self)
        show = menu.addAction("Show Dictate")
        show.triggered.connect(self.reveal)
        self.tray_stop = menu.addAction("Stop recording")
        self.tray_stop.triggered.connect(self.stop)
        menu.addSeparator()
        menu.addAction("Quit").triggered.connect(self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.reveal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.setToolTip("Dictate Workbench")
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def reveal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def settings(self):
        Settings(self).exec()

    def update_route(self):
        self.route.setText(f"Audio → {self.speech.name} / {self.speech.model}    •    Prompt → {self.writer.name} / {self.writer.model}")

    def refresh_devices(self):
        previous = self.device.currentText()
        self.device.clear()
        self.device.addItem("System default microphone", None)
        try:
            enhanced = []
            for index, device in enumerate(sd.query_devices()):
                if device["max_input_channels"] > 0:
                    host = sd.query_hostapis(device["hostapi"])["name"]
                    name = f"{device['name']} · {host}"
                    if "nvidia broadcast" in device["name"].lower() or "rtx voice" in device["name"].lower():
                        enhanced.append((index, name))
                    else:
                        self.device.addItem(name, index)
            for index, name in reversed(enhanced):
                self.device.insertItem(1, f"Noise-filtered · {name}", index)
            self.mic_hint.setText("NVIDIA virtual microphone detected. Select its noise-filtered input above."
                                  if enhanced else "Standard microphone mode · NVIDIA Broadcast / RTX Voice also supported when installed.")
            selected = self.device.findText(previous)
            if selected >= 0:
                self.device.setCurrentIndex(selected)
            elif previous and previous != "System default microphone":
                self.status.setText("Previous microphone is unavailable. Using the system default; check the level after Start.")
        except Exception:
            self.status.setText("Microphones unavailable. Connect one, allow microphone access, then Refresh.")

    def mark_dirty(self, *_):
        self.dirty = True

    def save_edits(self):
        if not self.folder or not self.dirty or self.worker:
            return True
        try:
            metadata = read_json(self.folder / "session.json")
            metadata.update(title=self.title.text().strip() or "Untitled session", context=self.context.text())
            write_json(self.folder / "session.json", metadata)
            if self.prompt.toPlainText() or (self.folder / "prompt.md").exists():
                write_text(self.folder / "prompt.md", self.prompt.toPlainText())
            self.dirty = False
            return True
        except OSError:
            self.status.setText("Could not save edits. Check disk space; copy your text before closing.")
            return False

    def refresh_sessions(self):
        self.history.blockSignals(True)
        self.history.clear()
        for path in sessions(self.root):
            meta = read_json(path)
            item = QListWidgetItem(f"{meta.get('title', 'Untitled')}\n{meta.get('created', '').replace('T', '  ')}")
            item.setData(Qt.ItemDataRole.UserRole, str(path.parent))
            self.history.addItem(item)
            if self.folder == path.parent:
                self.history.setCurrentItem(item)
        self.history.blockSignals(False)

    def select_session(self, item, _previous):
        if not item or self.recorder or self.worker:
            return
        if not self.save_edits():
            return
        self.folder = Path(item.data(Qt.ItemDataRole.UserRole))
        meta = read_json(self.folder / "session.json")
        self.title.setText(meta.get("title", ""))
        self.context.setText(meta.get("context", ""))
        self.load_outputs()
        self.dirty = False
        self.status.setText("Saved session loaded. Process resumes completed chunks when settings match.")
        self.update_controls()

    def load_outputs(self):
        for filename, widget in [("prompt.md", self.prompt), ("transcript.txt", self.transcript)]:
            path = self.folder / filename
            widget.setPlainText(path.read_text(encoding="utf-8") if path.exists() else "")

    def new(self):
        if not self.save_edits():
            return
        self.folder = None
        self.title.clear()
        self.context.clear()
        self.prompt.clear()
        self.transcript.clear()
        self.history.clearSelection()
        self.dirty = False
        self.status.setText("Ready for a new walkthrough.")
        self.update_controls()

    def start(self):
        try:
            if not self.save_edits():
                return
            # A recorded session is immutable: Start always creates a fresh recording.
            self.folder = new_session(self.root, self.title.text())
            self.title.setText(read_json(self.folder / "session.json")["title"])
            self.prompt.clear()
            self.transcript.clear()
            self.dirty = True
            if not self.save_edits():
                return
            self.recorder = Recorder(self.folder, self.device.currentData())
            self.recorder.start()
            self.status.setText("Recording locally. You can minimize the app or close it to the system tray.")
        except Exception:
            if self.recorder:
                self.recorder.stop()
            self.recorder = None
            self.status.setText("Could not start recording. Check microphone access, selected device and disk space.")
        self.refresh_sessions()
        self.update_controls()

    def pause(self):
        if self.recorder:
            self.recorder.paused = not self.recorder.paused
            self.pause_btn.setText("Resume" if self.recorder.paused else "Pause")

    def stop(self):
        if self.recorder:
            recorder = self.recorder
            recorder.stop()
            self.recorder = None
            self.pause_btn.setText("Pause")
            self.status.setText(recorder.error or "Recording saved. Click Process when you’re ready.")
            self.save_edits()
            self.update_controls()

    def process(self):
        if not self.folder or self.recorder or self.worker:
            return
        try:
            speech = Gateway(self.speech, self.keys.get(self.speech))
            writer = Gateway(self.writer, self.keys.get(self.writer))
            if not self.save_edits():
                return
            # Keep manual edits before replacing the generated prompt.
            existing = self.folder / "prompt.md"
            if existing.exists():
                from datetime import datetime
                write_text(self.folder / f"prompt-before-processing-{datetime.now():%Y%m%d-%H%M%S-%f}.md",
                           existing.read_text(encoding="utf-8"))
            self.worker = ProcessingThread(self.folder, speech, writer,
                                           self.config.get("language", "en"), self.context.text())
            self.worker.progress.connect(self.status.setText)
            self.worker.result.connect(self.completed)
            self.worker.failed.connect(self.status.setText)
            self.worker.finished.connect(self.processing_finished)
            self.worker.start()
            self.update_controls()
        except (ProviderError, ValueError) as exc:
            QMessageBox.information(self, "Provider setup", str(exc))
            self.settings()
        except OSError:
            self.status.setText("Could not save the session. Check disk space before processing.")

    def completed(self, result):
        self.prompt.setPlainText(result)
        self.dirty = False
        self.tabs.setCurrentIndex(0)
        self.status.setText("Your prompt is ready. Review, edit, and copy it into your coding agent.")
        if not self.isVisible():
            self.tray.showMessage("Dictate", "Your prompt is ready.")

    def processing_finished(self):
        self.worker.deleteLater()
        self.worker = None
        path = self.folder / "transcript.txt"
        if path.exists():
            self.transcript.setPlainText(path.read_text(encoding="utf-8"))
        self.update_controls()

    def cancel(self):
        if self.worker:
            self.worker.cancel.set()
            self.cancel_btn.setEnabled(False)
            self.status.setText("Canceling after the current request finishes. Completed work will be saved.")

    def update_controls(self):
        recording, processing = bool(self.recorder), bool(self.worker)
        busy = recording or processing
        self.start_btn.setEnabled(not busy)
        self.pause_btn.setEnabled(recording)
        self.stop_btn.setEnabled(recording)
        self.tray_stop.setEnabled(recording)
        self.process_btn.setEnabled(not busy and self.folder is not None and duration(self.folder) > 0)
        self.cancel_btn.setVisible(processing)
        self.cancel_btn.setEnabled(processing)
        for widget in (self.new_btn, self.history, self.settings_btn, self.device, self.refresh_btn, self.title, self.context):
            widget.setEnabled(not busy)
        self.prompt.setReadOnly(processing)

    def tick(self):
        elapsed = self.recorder.frames / self.recorder.rate if self.recorder else duration(self.folder) if self.folder else 0
        total = int(elapsed)
        clock_text = f"{total // 3600:02d}:{total // 60 % 60:02d}:{total % 60:02d}"
        self.clock.setText(clock_text)
        state = "PROCESSING" if self.worker else "SAVED LOCALLY" if total else "READY TO RECORD"
        if self.recorder:
            state = "PAUSED" if self.recorder.paused else "● RECORDING"
            if self.recorder.error or (self.recorder.stream and not self.recorder.stream.active):
                if not self.recorder.error:
                    self.recorder.error = "Microphone disconnected. Recording stopped; saved audio is available."
                self.stop()
        self.meter.setValue(min(100, int(self.recorder.level * 500)) if self.recorder else 0)
        self.state.setText(state)
        self.tray.setToolTip(f"Dictate · {state} · {clock_text}")

    def current_text(self):
        return self.prompt.toPlainText() if self.tabs.currentIndex() == 0 else self.transcript.toPlainText()

    def copy(self):
        QApplication.clipboard().setText(self.current_text())
        self.status.setText("Text copied to clipboard.")

    def export(self):
        text = self.current_text()
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export text", "prompt.md" if self.tabs.currentIndex() == 0 else "transcript.txt",
                                             "Text files (*.md *.txt)")
        if path:
            try:
                Path(path).write_text(text, encoding="utf-8")
                self.status.setText("Text exported.")
            except OSError:
                QMessageBox.warning(self, "Export", "Could not write this file. Choose another location.")

    def open_files(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder or self.root)))

    def quit(self):
        if self.worker:
            self.reveal()
            QMessageBox.information(self, "Processing in progress", "Cancel processing and wait for the current request to finish before quitting.")
            return
        if self.recorder:
            answer = QMessageBox.question(self, "Stop and quit?", "Stop this recording, save it, and quit?")
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.stop()
        self.save_edits()
        if self.dirty and self.folder:
            self.reveal()
            return
        self.quitting = True
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if self.quitting:
            event.accept()
        elif self.tray.isVisible():
            self.save_edits()
            self.hide()
            self.tray.showMessage("Dictate is still running", "Double-click the tray icon to return. Use its menu to quit.")
            event.ignore()
        else:
            event.ignore()
            self.quit()


def main():
    application = QApplication(sys.argv)
    application.setApplicationName("Dictate Workbench")
    application.setOrganizationName("DictateWorkbench")
    application.setStyle("Fusion")
    application.setStyleSheet(STYLE)
    application.setQuitOnLastWindowClosed(False)
    # Protect recording files from simultaneous instances of this installation.
    from PySide6.QtCore import QLockFile
    root = data_directory()
    root.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(root / "app.lock"))
    if not lock.tryLock(0):
        QMessageBox.information(None, "Dictate", "Dictate is already running. Open it from the system tray.")
        return
    window = Window(root)
    window.show()
    application.exec()


if __name__ == "__main__":
    main()
