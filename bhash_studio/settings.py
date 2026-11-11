"""Per-user tool settings for Bhash Yantra."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

from .android import Toolchain
from .errors import StudioError
from .project import atomic_write


def settings_path():
    home = Path.home()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        configured = Path(os.environ.get("XDG_CONFIG_HOME", ""))
        base = configured if configured.is_absolute() else home / ".config"
    return base / "bhash-yantra" / "settings.json"


def load_settings(path, defaults):
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defaults, ""
    except (OSError, ValueError) as error:
        raise StudioError("सहेजी गई औज़ार सेटिंग नहीं पढ़ी जा सकी। डिफ़ॉल्ट सेटिंग उपयोग में हैं।") from error
    fields = asdict(defaults)
    if not isinstance(saved, dict) or any(
        key in saved and not isinstance(saved[key], str) for key in (*fields, "device")
    ):
        raise StudioError("सहेजी गई औज़ार सेटिंग का रूप गलत है। डिफ़ॉल्ट सेटिंग उपयोग में हैं।")
    return Toolchain(**{key: saved.get(key, value) for key, value in fields.items()}), saved.get("device", "")


def save_settings(path, tools, device):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, json.dumps({**asdict(tools), "device": device}, ensure_ascii=False, indent=2) + "\n")
    except OSError as error:
        raise StudioError(f"औज़ार सेटिंग सहेजी नहीं जा सकी — {path}") from error
