"""Project persistence with atomic files and external-change detection."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import tempfile
import uuid

from .config import dumps, loads, validate_config, MAX_SOURCE
from .errors import StudioError


class LocalPath(type(Path())):
    """Use Windows extended paths for filesystem calls, retaining readable display paths."""

    def __fspath__(self):
        text = str(self)
        if os.name == "nt" and self.is_absolute() and len(text) >= 248 and not text.startswith("\\\\?\\"):
            return "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text
        return text

CONFIG = "परियोजना.भाषविन्यास"
LAYOUT = "पर्दा.भाषदृश्य"
SOURCE = "मुख्य.bhash"
FILES = (CONFIG, LAYOUT, SOURCE)
DEFAULT_LAYOUT = '''<पर्दा पहचान="मुख्य" शीर्षक="मेरा पहला ऐप">
  <स्तंभ>
    <पाठ>भाष में आपका स्वागत है</पाठ>
    <बटन दबानेपर="अभिवादन" तर्क="दुनिया">अभिवादन करें</बटन>
  </स्तंभ>
</पर्दा>
'''
DEFAULT_SOURCE = '''फलन अभिवादन(नाम: पाठ) -> पाठ {
    लौटाओ "नमस्ते, " + नाम + "!";
}
'''


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_write(file, text):
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=file.parent, delete=False) as stream:
            temp = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, file)
    finally:
        if temp and temp.exists():
            temp.unlink()


@dataclass
class Project:
    root: Path

    @classmethod
    def create(cls, directory, name):
        root = LocalPath(directory).expanduser().absolute()
        config = {
            "योजना_संस्करण": 1, "नाम": name, "लक्ष्य": "एंड्रॉयड",
            "ऐप_पहचान": "org.bhashitva.app" + uuid.uuid4().hex,
            "न्यूनतम_एंड्रॉयड_स्तर": 29, "संजाल_अनुमति": False,
            "प्रारंभिक_मान": None,
        }
        validate_config(config)
        if root.exists() or root.is_symlink():
            raise StudioError("यह फ़ोल्डर पहले से मौजूद है। नया फ़ोल्डर नाम चुनें।")
        # Publish the project only after all initial files have been written.
        with tempfile.TemporaryDirectory(prefix="bhash-new-", dir=root.parent) as staging:
            folder = Path(staging) / "project"
            folder.mkdir()
            for filename, content in zip(FILES, (dumps(config) + "\n", DEFAULT_LAYOUT, DEFAULT_SOURCE)):
                atomic_write(folder / filename, content)
            if root.exists() or root.is_symlink():
                raise StudioError("यह फ़ोल्डर पहले से मौजूद है। नया फ़ोल्डर नाम चुनें।")
            folder.rename(root)
        return cls(root.resolve())

    @classmethod
    def open(cls, directory):
        selected = LocalPath(directory).expanduser()
        if selected.is_dir():
            root = selected
        elif selected.name == CONFIG:
            root = selected.parent
        elif selected.is_file():
            raise StudioError(f"परियोजना खोलने के लिए ‘{CONFIG}’ चुनें। चुनी गई फ़ाइल — {selected}")
        else:
            raise StudioError(f"परियोजना फ़ोल्डर नहीं मिला — {selected.absolute()}")
        project = cls(root.resolve())
        for filename in FILES:
            project.read(filename)
        return project

    def file(self, filename):
        if filename not in FILES:
            raise StudioError("इस परियोजना फ़ाइल को खोलने की अनुमति नहीं है।")
        file = self.root / filename
        if file.is_symlink() or file.resolve().parent != self.root:
            raise StudioError("परियोजना फ़ाइल का मार्ग उसके फ़ोल्डर के अंदर होना चाहिए।")
        return file

    def read(self, filename):
        file = self.file(filename)
        if not file.is_file():
            raise StudioError(f"परियोजना फ़ाइल ‘{filename}’ नहीं मिली। खोजा गया मार्ग — {file}")
        if file.stat().st_size > MAX_SOURCE * 4:
            raise StudioError("परियोजना फ़ाइल का आकार बहुत बड़ा है।")
        try:
            return file.read_text(encoding="utf-8")
        except UnicodeError as error:
            raise StudioError("फ़ाइल को यूनिकोड के यूटीएफ 8 रूप में सहेजें।") from error

    def save(self, filename, text, expected):
        if len(text) > MAX_SOURCE:
            raise StudioError("फ़ाइल में अधिकतम दस लाख अक्षर रखें।")
        if digest(self.read(filename)) != expected:
            raise StudioError("फ़ाइल बाहर से बदली गई है। अपनी लिखावट की प्रति रखें और परियोजना फिर खोलें।")
        if filename == CONFIG:
            old = loads(self.read(filename))
            new = loads(text)
            if isinstance(old, dict) and isinstance(new, dict) and old.get("ऐप_पहचान") != new.get("ऐप_पहचान"):
                raise StudioError("मौजूदा ऐप की पहचान बदलने से उसके अद्यतन टूट सकते हैं। नई पहचान के लिए नई परियोजना बनाएँ।")
        atomic_write(self.file(filename), text)
        return digest(text)

    def snapshot(self):
        return {filename: self.read(filename) for filename in FILES}
