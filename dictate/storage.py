from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4


def data_directory() -> Path:
    if override := os.getenv("DICTATE_DATA_DIR"):
        return Path(override)
    if sys.platform == "win32":
        return Path(os.getenv("LOCALAPPDATA", Path.home())) / "DictateWorkbench"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "DictateWorkbench"
    return Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share")) / "dictate-workbench"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_json(path: Path, data: dict) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default


def new_session(root: Path, title: str) -> Path:
    now = datetime.now()
    folder = root / "sessions" / f"{now:%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
    folder.mkdir(parents=True)
    write_json(folder / "session.json", {
        "title": title.strip() or f"Session {now:%b %d, %H:%M}",
        "created": now.isoformat(timespec="seconds"),
        "sample_rate": 16000,
    })
    return folder


def sessions(root: Path) -> list[Path]:
    return sorted((root / "sessions").glob("*/session.json"), reverse=True)
