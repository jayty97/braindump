"""Render the real UI with synthetic content; no microphone or API request."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import tempfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from dictate.app import STYLE, Window

app = QApplication([])
if os.name == "nt":
    for font in ("segoeui.ttf", "segoeuib.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / font))
app.setStyle("Fusion")
app.setStyleSheet(STYLE)
with tempfile.TemporaryDirectory() as folder:
    with patch("dictate.app.sd.query_devices", return_value=[]):
        window = Window(Path(folder))
    window.title.setText("Checkout experience · Round 2")
    window.context.setText("A walkthrough of the cart, checkout, and confirmation screens")
    window.prompt.setPlainText("I tested the checkout flow and want to make these changes.\n\n1. Keep the cart visible\nWhen I return from checkout, preserve the items and quantities I already selected.\n\n2. Make validation easier to follow\nShow a clear message beside the missing field. Keep the information I have already entered.\n\n3. Clarify the final step\nRename the last button to “Place order” so it is clear what will happen.\n\nOpen question\nShould the confirmation screen also include an estimated delivery date?")
    window.status.setText("Example preview · Review, edit, and copy your next prompt.")
    window.show()
    app.processEvents()
    Path("docs").mkdir(exist_ok=True)
    window.grab().save("docs/screenshot.png")
    window.timer.stop()
    window.autosave.stop()
    window.tray.hide()
    window.quitting = True
    window.close()
