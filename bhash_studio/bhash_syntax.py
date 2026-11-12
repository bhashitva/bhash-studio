"""Lightweight editor tokenization for the Bhash 0.25.0 grammar."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from unicodedata import normalize
from zipfile import BadZipFile, ZipFile

from .errors import StudioError


# Keep these spellings aligned with the compiler release pinned by AndroidTarget.
KEYWORDS = tuple("""
संकुल आयात उपनाम फलन असमकालिक प्रतीक्षा वर्ग अभिलेख परिगणना परिवर्तित प्रकारहै
सुरक्षितरूप अनुबंध पालन साझा विस्तार निर्माता नया यह आधार सार्वजनिक निजी संरक्षित
अधिलेखन रिक्त मान स्थिर यदि अन्यथा जबतक प्रत्येक में चयन विकल्प शेष संसाधन
प्रयास पकड़ो अंततः फेंको लौटाओ विराम जारी लिखो पूर्णांक बाइट लघुपूर्णांक सर्ववस्तु
बाइटबफ़र दशमलव तार्किक पाठ शून्य सत्य असत्य
""".split())
KEYWORD_FOR = {normalize("NFC", word): word for word in KEYWORDS}
COMMON_KEYWORDS = (
    "फलन", "मान", "स्थिर", "यदि", "अन्यथा", "जबतक", "प्रत्येक", "लौटाओ", "लिखो",
    "पूर्णांक", "दशमलव", "पाठ", "तार्किक", "शून्य", "सत्य", "असत्य", "रिक्त",
)
# Each pair surrounds the caret after insertion.
CONSTRUCTS = {
    "फलन": ("फलन नाम() -> शून्य {\n    ", "\n}"),
    "मान": ("मान नाम: पूर्णांक = ०;", ""),
    "यदि": ("यदि (सत्य) {\n    ", "\n}"),
    "यदि और अन्यथा": ("यदि (सत्य) {\n    ", "\n} अन्यथा {\n    \n}"),
    "जबतक": ("जबतक (असत्य) {\n    ", "\n}"),
    "लिखो": ("लिखो(", ");"),
    "लौटाओ": ("लौटाओ ", ";"),
}

WORD = r"[\w\u0900-\u0903\u093a-\u094f\u0951-\u0957\u0962-\u0963\u200c\u200d]"
TOKENS = re.compile(
    r'(?P<comment>//[^\r\n]*|/\*[\s\S]*?(?:\*/|\Z))'
    r'|(?P<string>"(?:\\[^\r\n]|[^"\\\r\n])*\\?"?)'
    rf'|(?P<word>{WORD}+)'
)
IMPORT_PREFIX = re.compile(
    rf"(?:^|;)[ \t]*(?P<keyword>आयात)[ \t]+(?P<root>{WORD}*)"
    rf"(?:[ \t]*\.[ \t]*(?P<member>{WORD}*))?\Z", re.MULTILINE,
)
CORE_IMPORTS = ("गणित", "जेसन", "पाठ्य", "फ़ाइल", "यादृच्छिक", "समय")
STDLIB_DIRECTORY = "dev/bhash/stdlib/"
STDLIB_IMPORT = re.compile(
    rf"(?<!{WORD})आयात\s+मानक\s*\.\s*({WORD}+)(?:\s+उपनाम\s+({WORD}+))?\s*;"
)
MEMBER_PREFIX = re.compile(rf"(?<!{WORD})({WORD}+)\s*\.\s*({WORD}*)\Z")
LIBRARY_DECLARATION = re.compile(
    rf"{TOKENS.pattern}|(?P<brace>[{{}}])"
)
LIBRARY_TYPE = re.compile(rf"सार्वजनिक\s+(?:वर्ग|अनुबंध|अभिलेख|परिगणना)\s+({WORD}+)")
LIBRARY_METHOD = re.compile(rf"सार्वजनिक\s+साझा\s+(?:असमकालिक\s+)?(?:फलन|कार्य)\s+({WORD}+)")


def standard_imports(compiler):
    return standard_library(compiler)[0]


def standard_library(compiler):
    if compiler:
        try:
            path = Path(compiler)
            stat = path.stat()
            imports, methods = read_standard_library(path, stat.st_mtime_ns, stat.st_size)
            return imports or CORE_IMPORTS, methods
        except (OSError, BadZipFile, UnicodeError):
            pass
    return CORE_IMPORTS, {}


@lru_cache(maxsize=4)
def read_standard_library(path, modified_ns, size):
    names = {}
    methods = {}

    def add(owner, method=None):
        key = normalize("NFC", owner)
        names.setdefault(key, owner)
        if method:
            methods.setdefault(key, {}).setdefault(normalize("NFC", method), method)

    with ZipFile(path) as jar:
        for resource in jar.namelist():
            if not resource.startswith(STDLIB_DIRECTORY):
                continue
            if resource.endswith("-api.txt") or resource == STDLIB_DIRECTORY + "api.txt":
                lines = jar.read(resource).decode("utf-8").splitlines()
                for line in lines:
                    if line.count("|") == 4 and not line.startswith("#"):
                        owner, method, *_ = line.split("|")
                        add(owner, method)
            elif resource.endswith(".bhash"):
                source = jar.read(resource).decode("utf-8")
                if not re.search(r"^संकुल\s+मानक\s*;", source, re.MULTILINE):
                    continue
                depth, owner = 0, None
                for token in LIBRARY_DECLARATION.finditer(source):
                    if token.lastgroup == "brace":
                        depth += 1 if token[0] == "{" else -1
                        if depth == 0:
                            owner = None
                    elif token.lastgroup == "word" and token[0] == "सार्वजनिक":
                        if depth == 0 and (declaration := LIBRARY_TYPE.match(source, token.start())):
                            owner = declaration[1]
                            add(owner)
                        elif depth == 1 and owner and (method := LIBRARY_METHOD.match(source, token.start())):
                            add(owner, method[1])
    preferred = [normalize("NFC", name) for name in CORE_IMPORTS]
    imports = tuple(names[key] for key in preferred if key in names) + tuple(
        names[key] for key in sorted(names.keys() - set(preferred))
    )
    return imports, {owner: tuple(sorted(entries.values())) for owner, entries in methods.items()}


@dataclass(frozen=True)
class Completion:
    start: int
    end: int
    options: tuple[str, ...]


def analyze(source, caret=None, imports=CORE_IMPORTS, methods=None):
    """Return keyword ranges and, when requested, prefix matches at the caret."""
    ranges = []
    names = {}
    active = None
    excluded = []
    import_match = IMPORT_PREFIX.search(source, 0, caret) if caret is not None else None
    for token in TOKENS.finditer(source):
        if token.lastgroup != "word":
            if caret is not None and token.start() < caret:
                excluded.append(token.span())
            if import_match and token.start() <= import_match.start("keyword") < token.end():
                import_match = None
            continue
        start, end = token.span()
        word = token.group()
        canonical = normalize("NFC", word)
        if canonical in KEYWORD_FOR:
            ranges.append((start, end))
        if caret is not None and start < caret <= end:
            active = (start, end, canonical)
        elif caret is not None and canonical not in KEYWORD_FOR and not word[0].isdigit():
            names.setdefault(canonical, word)

    if import_match:
        member = import_match["member"]
        root = normalize("NFC", import_match["root"])
        if member is None and "मानक".startswith(root):
            tail = re.match(rf"{WORD}*(?:[ \t]*\.[ \t]*{WORD}*)?", source[caret:])
            return ranges, Completion(import_match.start("root"), caret + tail.end(),
                                      tuple("मानक." + name for name in imports))
        if member is not None and root == "मानक":
            tail = re.match(rf"{WORD}*", source[caret:]).group()
            prefix = normalize("NFC", member)
            current = normalize("NFC", member + tail)
            options = tuple(name for name in imports
                            if normalize("NFC", name).startswith(prefix) and normalize("NFC", name) != current)
            return ranges, Completion(import_match.start("member"), caret + len(tail), options) if options else None

    if caret is not None and methods:
        completion = complete_member(source, caret, methods, excluded)
        if completion:
            return ranges, completion

    if active is None:
        return ranges, None
    start, end, current = active
    if source[:start].rstrip().endswith("."):
        return ranges, None
    prefix = normalize("NFC", source[start:caret])
    matches = ((key, word) for key, word in (names | KEYWORD_FOR).items()
               if key.startswith(prefix) and key != current)
    options = [word for _, word in sorted(matches, key=lambda item: (len(item[0]), item[0]))[:6]]
    return ranges, Completion(start, end, tuple(options)) if options else None


def complete_member(source, caret, methods, excluded):
    match = MEMBER_PREFIX.search(source, 0, caret)
    if not match or source[:match.start()].rstrip().endswith("."):
        return None

    def is_code(offset):
        return not any(start <= offset < end for start, end in excluded)

    if not is_code(match.start()):
        return None
    receiver = normalize("NFC", match[1])
    owner = next((normalize("NFC", item[1]) for item in STDLIB_IMPORT.finditer(source, 0, match.start())
                  if is_code(item.start()) and normalize("NFC", item[2] or item[1]) == receiver), None)
    if owner is None:
        return None
    tail = re.match(rf"{WORD}*", source[caret:]).group()
    prefix = normalize("NFC", match[2])
    current = normalize("NFC", match[2] + tail)
    options = tuple(name for name in methods.get(owner, ())
                    if normalize("NFC", name).startswith(prefix) and normalize("NFC", name) != current)
    return Completion(match.start(2), caret + len(tail), options) if options else None


def display_diagnostic(message):
    # ANTLR's vocabulary escapes Devanagari in expected tokens. Leave the
    # offending source text and any literal backslashes in the message intact.
    before, separator, expected = message.rpartition(" expecting ")
    if not separator or not re.fullmatch(r"\{.*\}|'[^']*'", expected):
        return message
    readable = re.sub(r"(?<!\\)\\u(09[0-7][0-9a-fA-F])",
                      lambda match: chr(int(match[1], 16)), expected)
    return before + separator + readable


def check_syntax(tools, source):
    """Check an unsaved UTF-8 buffer using the compiler's syntax-only command."""
    tools.validate()
    compiler = Path(tools.compiler).resolve()
    java = str(Path(tools.java).resolve())
    with TemporaryDirectory(prefix="yantra-syntax-") as directory:
        folder = Path(directory)
        (folder / "buffer.bhash").write_text(source, encoding="utf-8", newline="\n")
        jar = str(compiler)
        if not jar.isascii():
            # Windows Java can lose non-ASCII characters in command-line paths.
            shutil.copyfile(compiler, folder / "compiler.jar")
            jar = "compiler.jar"
        result = subprocess.run(
            [java, "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8",
             "-Dsun.stdout.encoding=UTF-8", "-Dsun.stderr.encoding=UTF-8", "-jar", jar, "check", "buffer.bhash"],
            cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace", timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    diagnostics = tuple(
        (int(match[1]), int(match[2]), display_diagnostic(match[3]))
        for match in re.finditer(r"^.*buffer\.bhash:(\d+):(\d+):\s*([^\r\n]+)", result.stdout, re.MULTILINE)
    )
    if result.returncode and not diagnostics:
        raise StudioError("वाक्यविन्यास जाँच नहीं चल सकी। जावा और भाष कंपाइलर की सेटिंग जाँचें।")
    return diagnostics
