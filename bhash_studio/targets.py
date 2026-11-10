"""Target registry keeps the workspace independent of Android tools."""

from dataclasses import dataclass

from .config import loads, validate_config
from .errors import StudioError
from .layout import parse_layout, validate_handlers
from .project import CONFIG, LAYOUT, SOURCE


@dataclass(frozen=True)
class Target:
    name: str
    implemented: bool


TARGETS = (Target("एंड्रॉयड", True), Target("डेस्कटॉप", False), Target("वेब", False))


def validate_snapshot(snapshot):
    config = validate_config(loads(snapshot[CONFIG]))
    screen = parse_layout(snapshot[LAYOUT])
    if not snapshot[SOURCE].strip():
        raise StudioError("मुख्य भाष फ़ाइल में कम से कम एक फलन लिखें।")
    validate_handlers(screen, snapshot[SOURCE])
    return config, screen


def require_android(config):
    if config["लक्ष्य"] != "एंड्रॉयड":
        raise StudioError("डेस्कटॉप और वेब निर्माण अगले चरण में आएँगे। अभी एंड्रॉयड लक्ष्य चुनें।")
