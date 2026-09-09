"""Хранилище последней загруженной выгрузки: в памяти + резервная копия на диск.

Кадровик утром загружает файл через /api/process — результат кладётся сюда,
и обычные сотрудники читают его на странице «Во сколько мне уйти».
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
_FILE = DATA_DIR / "latest.json"
_lock = threading.Lock()
_latest: dict[str, Any] | None = None


def _load() -> None:
    global _latest
    try:
        if _FILE.exists():
            _latest = json.loads(_FILE.read_text("utf-8"))
    except Exception:
        _latest = None


def get_latest() -> dict[str, Any] | None:
    return _latest


def set_latest(payload: dict[str, Any]) -> None:
    global _latest
    with _lock:
        _latest = payload
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = _FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
            tmp.replace(_FILE)
        except Exception:
            pass


def clear() -> None:
    global _latest
    with _lock:
        _latest = None
        try:
            _FILE.unlink(missing_ok=True)
        except Exception:
            pass


_load()
