"""Signature help from the compiler's language server and Bhash reference."""

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import json
from pathlib import Path
from queue import Empty, Queue
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
from unicodedata import normalize
from urllib.parse import quote

from .bhash_syntax import STDLIB_IMPORT, TOKENS, WORD
from .errors import StudioError


CALL_TOKENS = re.compile(rf"{TOKENS.pattern}|(?P<delimiter>[(){{}}\[\];])")
CALL_NAME = re.compile(rf"(?P<name>{WORD}+)(?:\s*<[^(){{}};]*>)?\s*\Z")
RECEIVER = re.compile(rf"(?P<owner>{WORD}+)\s*\.\s*\Z")
STANDARD_SYMBOL = re.compile(rf"^मानक\.({WORD}+)\.({WORD}+)$", re.MULTILINE)
STANDARD_MEMBER = re.compile(rf"^मानक\.{WORD}+$", re.MULTILINE)
HOVER_TYPE = re.compile(rf"```bhash\n(?P<type>(?:मानक\.)?{WORD}+)(?:<[^\n]+>)?\n```")


def call_site(source, caret):
    stack = []
    excluded = []
    for token in CALL_TOKENS.finditer(source):
        if token.start() >= caret:
            break
        if token.lastgroup in {"string", "comment"}:
            excluded.append(token.span())
        elif token.lastgroup == "delimiter":
            value = token[0]
            if value in "([{":
                stack.append((value, token.start()))
            elif value in ")]}" and stack and stack[-1][0] == "([{"[")]}".index(value)]:
                stack.pop()
            elif value == ";":
                while stack and stack[-1][0] in "([":
                    stack.pop()
    if not stack or stack[-1][0] == "{":
        return None
    for bracket, offset in reversed(stack):
        if bracket == "{":
            return None
        if (bracket == "(" and (match := CALL_NAME.search(source, 0, offset))
                and not any(start <= match.start("name") < end for start, end in excluded)):
            return match.start("name"), match["name"], excluded
    return None


def position(source, offset):
    prefix = source[:offset]
    line = prefix.rsplit("\n", 1)[-1]
    return {"line": prefix.count("\n"), "character": len(line.encode("utf-16-le")) // 2}


@lru_cache(maxsize=1)
def reference():
    raw = json.loads(files("bhash_studio").joinpath("stdlib_reference.json").read_text(encoding="utf-8"))
    raw["spellings"] = {normalize("NFC", name): name for name in raw["types"]}
    for key in ("types", "methods", "notes"):
        raw[key] = {normalize("NFC", name): text for name, text in raw[key].items()}
    return raw


def hover_value(hover):
    contents = (hover or {}).get("contents", {})
    return contents.get("value", "") if isinstance(contents, dict) else ""


def library_help(source, site, hover, receiver_hover=None):
    start, method, excluded = site
    value = hover_value(hover)
    symbol = STANDARD_SYMBOL.search(value)
    if value and not symbol and not STANDARD_MEMBER.search(value):
        return "", ""
    owner = symbol[1] if symbol else None
    imports = {normalize("NFC", item[2] or item[1]): item[1]
               for item in STDLIB_IMPORT.finditer(source, 0, start)
               if not any(a <= item.start() < b for a, b in excluded)}
    if not owner and (receiver := RECEIVER.search(source, 0, start)):
        owner = imports.get(normalize("NFC", receiver["owner"]))
    if not owner and (receiver_type := HOVER_TYPE.search(hover_value(receiver_hover))):
        name = normalize("NFC", receiver_type["type"])
        owner = name.removeprefix("मानक.") if name.startswith("मानक.") else imports.get(name, name)
    if not owner:
        return "", ""
    data = reference()
    key, member = normalize("NFC", owner), normalize("NFC", method)
    class_name = data["spellings"].get(key)
    if not class_name:
        return "", ""
    description = data["methods"].get(f"{key}.{member}") or data["methods"].get(member)
    summary = description or data["notes"].get(key) or data["types"][key]
    # GitHub paths use the spelling in the reference, before NFC normalization.
    base = f"https://github.com/bhashitva/bhash/blob/{data['revision']}/tutorial/standard-library/reference"
    return summary, f"{base}/types/{quote(class_name)}.md"


@dataclass(frozen=True)
class SignatureHelp:
    signatures: tuple[str, ...]
    parameter: str
    description: str = ""
    url: str = ""


class LanguageServer:
    """Serial client for the Bhash stdio protocol, owned by one editor worker."""

    def __init__(self):
        self.process = None
        self.scratch = None
        self.identity = None
        self.documents = {}
        self.serial = 0

    def close(self):
        if self.process:
            self.process.kill()
            self.process.wait()
            self.process.stdin.close()
            self.process.stdout.close()
            self.process = None
        if self.scratch:
            self.scratch.cleanup()
            self.scratch = None
        self.identity = None
        self.documents.clear()

    @staticmethod
    def read_responses(stream, responses):
        try:
            while header := stream.readline():
                headers = {}
                while header.strip():
                    key, value = header.decode("ascii").split(":", 1)
                    headers[key.lower()] = value.strip()
                    header = stream.readline()
                message = json.loads(stream.read(int(headers["content-length"])))
                if "id" in message:
                    responses.put(message)
        except (OSError, ValueError, KeyError):
            pass
        finally:
            responses.put(None)

    def send(self, method, params, request=False):
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        if request:
            self.serial += 1
            message["id"] = self.serial
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
        self.process.stdin.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data)
        self.process.stdin.flush()
        if request:
            response = self.responses.get(timeout=15)
            if response is None or response.get("id") != self.serial or "error" in response:
                raise OSError("Bhash language server request failed")
            return response.get("result")

    def start(self, tools, identity):
        self.close()
        self.scratch = TemporaryDirectory(prefix="yantra-lsp-")
        root = Path(self.scratch.name)
        self.source_root = root / "src"
        self.source_root.mkdir()
        (root / "bhash.project").write_text("name=yantra\nsources=src\nkind=application\n", encoding="utf-8")
        jar = str(Path(tools.compiler).resolve())
        if not jar.isascii():
            shutil.copyfile(jar, root / "compiler.jar")
            jar = "compiler.jar"
        self.process = subprocess.Popen(
            [str(Path(tools.java).resolve()), "-Dfile.encoding=UTF-8", "-Djava.io.tmpdir=.",
             "-jar", jar, "language-server"],
            cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.responses = Queue()
        Thread(target=self.read_responses, args=(self.process.stdout, self.responses), daemon=True).start()
        self.send("initialize", {"rootUri": root.as_uri(), "capabilities": {}}, request=True)
        self.send("initialized", {})
        self.identity = identity

    def sync(self, sources):
        for name in self.documents.keys() - sources.keys():
            uri = (self.source_root / name).as_uri()
            self.send("textDocument/didClose", {"textDocument": {"uri": uri}})
            del self.documents[name]
        for name, source in sources.items():
            uri = (self.source_root / name).as_uri()
            previous = self.documents.get(name)
            if previous is None:
                self.send("textDocument/didOpen", {
                    "textDocument": {"uri": uri, "languageId": "bhash", "version": 1, "text": source},
                })
                self.documents[name] = (1, source)
            elif source != previous[1]:
                version = previous[0] + 1
                self.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": version},
                                                    "contentChanges": [{"text": source}]})
                self.documents[name] = (version, source)

    def help(self, tools, project, filename, buffers, caret, site):
        try:
            tools.validate()
            jar = Path(tools.compiler).stat()
            identity = (project.root, tools.compiler, tools.java, jar.st_mtime_ns, jar.st_size)
            if self.identity != identity:
                self.start(tools, identity)
            sources = project.source_snapshot(buffers)
            self.sync(sources)
            source = buffers[filename]
            document = {"uri": (self.source_root / filename).as_uri()}
            result = self.send("textDocument/signatureHelp", {"textDocument": document,
                               "position": position(source, caret)}, request=True)
            if not result or not result.get("signatures"):
                return None
            options = result["signatures"]
            active = result.get("activeSignature") or 0
            selected = options[active]
            parameters = selected.get("parameters", [])
            index = result.get("activeParameter")
            parameter = parameters[index]["label"] if index is not None and index < len(parameters) else ""
            hover = self.send("textDocument/hover", {"textDocument": document,
                              "position": position(source, site[0])}, request=True)
            description, url = library_help(source, site, hover)
            if not url and STANDARD_MEMBER.search(hover_value(hover)) and (receiver := RECEIVER.search(source, 0, site[0])):
                receiver_hover = self.send("textDocument/hover", {"textDocument": document,
                                           "position": position(source, receiver.start("owner"))}, request=True)
                description, url = library_help(source, site, hover, receiver_hover)
            ordered = [selected, *options[:active], *options[active + 1:]]
            return SignatureHelp(tuple(item["label"] for item in ordered), parameter, description, url)
        except (OSError, StudioError, Empty):
            self.close()
            return None
