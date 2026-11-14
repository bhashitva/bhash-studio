"""Source-level web debugging through the LLDB Debug Adapter Protocol."""

from dataclasses import dataclass
from collections import deque
import base64
import ctypes
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time

from .errors import StudioError

MANAGED_KINDS = {"पाठ": "TEXT", "वस्तु": "OBJECT", "सर्ववस्तु": "ANY"}
UNAVAILABLE = "मान उपलब्ध नहीं"


def managed_kind(variable):
    # LLDB versions can add qualifiers or expose the typedef in the raw value.
    for description in (variable.get("type") or "", variable.get("value") or ""):
        match = re.match(r"^(?:\()?\s*(?:(?:const|volatile)\s+)*(पाठ|वस्तु|सर्ववस्तु)(?=\s|\)|$)", description)
        if match:
            return MANAGED_KINDS[match[1]]
    return None


@dataclass
class DebugEvent:
    kind: str
    value: object = None


def adapter_path(configured=""):
    command = (configured or os.environ.get("BHASH_LLDB_DAP") or shutil.which("lldb-dap")
               or shutil.which("lldb-dap-18") or shutil.which("lldb-vscode-18"))
    if not command or not Path(command).is_file():
        raise StudioError("डिबगिंग के लिए LLDB डिबग अडैप्टर स्थापित करें और औज़ार सेटिंग में उसका मार्ग चुनें।")
    return str(Path(command).resolve())


def read_message(stream):
    headers = {}
    while True:
        line = stream.readline(4096)
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, separator, value = line.partition(b":")
        if not separator or not line.endswith(b"\n"):
            raise ValueError("Invalid DAP header")
        headers[key.lower()] = value.strip()
    length = int(headers.get(b"content-length", b"0"))
    if not 0 < length <= 16 * 1024 * 1024:
        raise ValueError("Invalid DAP message length")
    payload = stream.read(length)
    if len(payload) != length:
        raise EOFError("Incomplete DAP message")
    return json.loads(payload)


def scalar_value(variable, text):
    """Accept only bounded primitive values for the adapter's setVariable request."""
    if variable.get("variablesReference") or "readOnly" in variable.get("presentationHint", {}).get("attributes", ()):
        return None
    kind = variable.get("type", "")
    text = text.strip().translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    if len(text) > 64:
        return None
    if kind in {"bool", "_Bool", "तार्किक"}:
        return {"true": "true", "false": "false", "सत्य": "true", "असत्य": "false"}.get(text)
    if kind in {"double", "दशमलव"}:
        if re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text):
            return repr(float(text)) if math.isfinite(float(text)) else None
        return None
    if kind in {"पूर्णांक", "int64_t", "long long", "long long int", "long", "long int"}:
        low, high = -(2 ** 63), 2 ** 63 - 1
    elif kind in {"बाइट", "unsigned char", "uint8_t"}:
        low, high = 0, 255
    else:
        return None
    if re.fullmatch(r"[+-]?[0-9]+", text) and low <= int(text) <= high:
        return str(int(text))
    return None


class WebDebugger:
    def __init__(self, executable, sources, adapter, arguments, port, breakpoints, cancel, emit,
                 *, android_port=None, android_slide=None):
        self.executable = executable
        self.sources = sources
        self.adapter = adapter
        self.arguments = arguments
        self.port = port
        self.android_port = android_port
        self.android_slide = android_slide
        self.breakpoints = breakpoints
        self.cancel = cancel
        self.emit = emit
        self.inbox = queue.Queue()
        self.commands = queue.Queue()
        self.responses = {}
        self.events = deque()
        self.seq = 0
        self.thread = None
        self.stop_id = 0
        self.terminated = False
        self.ready = False
        self.output_tail = ""
        self.inspection_warning = False
        self.inferior_handle = None

    def _read(self):
        try:
            while message := read_message(self.process.stdout):
                self.inbox.put(message)
        except (OSError, ValueError, EOFError) as error:
            self.inbox.put(error)
        finally:
            self.inbox.put(None)

    def _send(self, message):
        self.seq += 1
        payload = json.dumps({"seq": self.seq, **message}).encode("utf-8")
        self.process.stdin.write(f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload)
        self.process.stdin.flush()
        return self.seq

    def _request(self, command, **arguments):
        return self._send({"type": "request", "command": command, "arguments": arguments})

    def _receive(self, timeout=0.1):
        try:
            message = self.inbox.get(timeout=timeout)
        except queue.Empty:
            return
        if message is None or isinstance(message, Exception):
            raise StudioError("डिबग अडैप्टर का संपर्क टूट गया।")
        if message["type"] == "response":
            self.responses[message["request_seq"]] = message
        elif message["type"] == "event":
            if (os.name == "nt" and self.android_port is None and message["event"] == "process"
                    and self.inferior_handle is None):
                pid = message.get("body", {}).get("systemProcessId")
                if isinstance(pid, int) and pid > 0:
                    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel.OpenProcess.restype = ctypes.c_void_p
                    handle = kernel.OpenProcess(0x00100001, False, pid)  # synchronize and terminate
                    if handle:
                        self.inferior_handle = ctypes.c_void_p(handle)
            self.events.append(message)
        elif message["type"] == "request":
            self._send({"type": "response", "request_seq": message["seq"], "command": message["command"],
                        "success": False, "message": "This client does not support reverse requests."})

    def _wait(self, predicate, timeout=20, *, cancelling=True):
        deadline = time.monotonic() + timeout
        while not predicate():
            if cancelling and self.cancel.is_set():
                raise InterruptedError
            if time.monotonic() >= deadline:
                raise StudioError("डिबग अडैप्टर से समय पर उत्तर नहीं मिला।")
            self._receive()

    def _response(self, seq, **options):
        self._wait(lambda: seq in self.responses, **options)
        response = self.responses.pop(seq)
        if not response.get("success"):
            detail = response.get("message") or response.get("body", {}).get("message")
            if response["command"] == "attach":
                output = "".join(event.get("body", {}).get("output", "") for event in self.events
                                 if event.get("event") == "output")
                detail = "\n".join(part for part in (detail, output[-4000:]) if part)
            raise StudioError(detail or f"डिबग आदेश असफल — {response['command']}")
        return response.get("body", {})

    def _call(self, command, **arguments):
        return self._response(self._request(command, **arguments))

    def _set_breakpoints(self, name, lines):
        result = self._call("setBreakpoints", source={"path": str(self.sources / name)},
                            breakpoints=[{"line": line} for line in lines])
        for line, breakpoint in zip(lines, result.get("breakpoints", ())):
            if not breakpoint.get("verified"):
                self.emit(DebugEvent("output", f"विराम बिंदु अपुष्ट — {name}:{line} {breakpoint.get('message', '')}\n"))
            elif breakpoint.get("line", line) != line:
                self.emit(DebugEvent("output", f"विराम बिंदु — {name}:{line} → {breakpoint['line']}\n"))

    def _launch(self):
        self.capabilities = self._call("initialize", adapterID="lldb-dap", clientID="bhash-yantra",
                                       linesStartAt1=True, columnsStartAt1=True, pathFormat="path")
        inspector = ascii(str(Path(__file__).with_name("debug_values.py").resolve()))
        options = dict(program=str(self.executable), enableAutoVariableSummaries=False,
                       enableSyntheticChildDebugging=False,
                       initCommands=["settings set target.enable-synthetic-value false",
                                     "settings set target.load-script-from-symbol-file false",
                                     "settings set target.process.thread.step-avoid-regexp ^bh_",
                                     f"script exec(compile(open({inspector}, 'rb').read(), {inspector}, 'exec'), globals())"])
        if self.android_port is None:
            launch = self._request("launch", **options, cwd=str(self.executable.parent),
                                   args=self.arguments, env=["BHASH_ENV=dev"], disableASLR=False)
        else:
            launch = self._request("attach", **options, timeout=15, attachCommands=[
                f"settings set target.exec-search-paths {json.dumps(str(self.executable.parent), ensure_ascii=False)}",
                f"!gdb-remote 127.0.0.1:{self.android_port}",
                f"!script load_android_symbols(lldb.debugger, {ascii(str(self.executable))}, {self.android_slide})",
            ])
        self._wait(lambda: any(event["event"] == "initialized" for event in self.events)
                   or launch in self.responses and not self.responses[launch].get("success"))
        if launch in self.responses:
            self._response(launch)
            launch = None
        for name, lines in self.breakpoints.items():
            self._set_breakpoints(name, lines)
        self._call("configurationDone")
        if launch is not None:
            self._response(launch)
        self.emit(DebugEvent("running"))

    def run(self):
        log = self.executable.parent.parent / "debug-adapter.log"
        self.emit(DebugEvent("output", f"डिबग अडैप्टर लॉग — {log}\n"))
        self.emit(DebugEvent("output", f"LLDB — {self.adapter}\n"))
        with log.open("wb") as stderr:
            self.process = subprocess.Popen([self.adapter], cwd=self.executable.parent, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=stderr,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            reader = threading.Thread(target=self._read, daemon=True)
            reader.start()
            try:
                self._launch()
                while not self.cancel.is_set() and not self.terminated:
                    while self.events:
                        self._event(self.events.popleft())
                    try:
                        command = self.commands.get_nowait()
                    except queue.Empty:
                        self._receive()
                    else:
                        try:
                            self._command(*command)
                        except StudioError as error:
                            self.emit(DebugEvent("output", f"{error}\n"))
                            self.emit(DebugEvent("idle"))
            except InterruptedError:
                pass
            finally:
                self._close()
                reader.join(timeout=2)

    def _close(self):
        if self.process.poll() is None:
            try:
                self._response(self._request("disconnect", terminateDebuggee=self.android_port is None),
                               timeout=3, cancelling=False)
                self.process.wait(timeout=2)
            except (StudioError, OSError, subprocess.TimeoutExpired):
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if self.process.poll() is None:
                    self.process.kill()
                self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()
        if self.inferior_handle is not None:
            # Retain the original process handle so PID reuse cannot affect cleanup.
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            if kernel.WaitForSingleObject(self.inferior_handle, 500) == 258:
                kernel.TerminateProcess(self.inferior_handle, 1)
                kernel.WaitForSingleObject(self.inferior_handle, 3000)
            kernel.CloseHandle(self.inferior_handle)
            self.inferior_handle = None

    def _event(self, message):
        event = message["event"]
        body = message.get("body", {})
        if event == "output":
            output = body.get("output", "")
            self.emit(DebugEvent("output", output))
            if self.port is not None and not self.ready and body.get("category") == "stdout":
                self.output_tail = (self.output_tail + output)[-4096:]
                if re.search(rf"(?m)^READY {self.port}\r?\n", self.output_tail):
                    self.ready = True
                    self.emit(DebugEvent("ready", self.port))
        elif event == "continued":
            self.thread = None
            self.emit(DebugEvent("running"))
        elif event == "stopped":
            self.thread = body.get("threadId")
            if self.thread is None:
                threads = self._call("threads").get("threads", ())
                self.thread = threads[0]["id"] if threads else None
            self.stop_id += 1
            frames = self._call("stackTrace", threadId=self.thread, levels=40).get("stackFrames", [])
            for frame in frames:
                path = frame.get("source", {}).get("path")
                if path:
                    candidate = Path(path).resolve()
                    if candidate.is_relative_to(self.sources):
                        frame["project_file"] = candidate.relative_to(self.sources).as_posix()
            self.emit(DebugEvent("stopped", (self.stop_id, body.get("reason"), frames)))
        elif event in {"exited", "terminated"}:
            self.terminated = True

    def _command(self, command, stop_id, arguments):
        if command == "setBreakpoints":
            self._set_breakpoints(*arguments)
            return
        if stop_id != self.stop_id or self.thread is None:
            return
        if command in {"continue", "next", "stepIn", "stepOut"}:
            self._call(command, threadId=self.thread)
            self.thread = None
            self.emit(DebugEvent("running"))
        elif command == "scopes":
            frame, = arguments
            scopes = self._call("scopes", frameId=frame).get("scopes", [])
            self.emit(DebugEvent("scopes", (stop_id, frame, scopes, self.capabilities.get("supportsSetVariable"))))
        elif command == "variables":
            node, reference = arguments
            if isinstance(reference, list):
                variables = self._inspect_values(reference, expand=True)
            else:
                variables = self._call("variables", variablesReference=reference).get("variables", [])[:200]
                self._format_variables(variables)
            self.emit(DebugEvent("variables", (stop_id, node, reference, variables)))
        elif command == "setVariable":
            node, reference, variable, value = arguments
            result = self._call("setVariable", variablesReference=reference, name=variable["name"], value=value)
            # LLDB 18 uses "result" instead of the DAP setVariable "value".
            self.emit(DebugEvent("edited", (stop_id, node, result.get("value", result.get("result", value)))))

    def _inspect_values(self, values, *, expand=False):
        request = base64.b64encode(json.dumps({"expand": expand, "values": values}).encode()).decode()
        try:
            response = self._call("evaluate", context="repl", expression=f"`script inspect_values(lldb.debugger, '{request}')")
            encoded = re.search(r"BHASH_VALUES:([A-Za-z0-9+/=]+)", response.get("result", ""))
            if encoded:
                payload = json.loads(base64.b64decode(encoded[1]))
                if isinstance(payload, list):
                    return payload
                detail = payload.get("error", "अमान्य निरीक्षण उत्तर")
            else:
                detail = response.get("result") or "LLDB ने निरीक्षण उत्तर नहीं दिया।"
        except (StudioError, ValueError) as error:
            detail = str(error)
        if not self.inspection_warning:
            self.inspection_warning = True
            self.emit(DebugEvent("output", f"भाष मान नहीं पढ़े जा सके — Python-सक्षम LLDB और भाष कंपाइलर जाँचें।\n{detail[:1000]}\n"))
        return [{"name": UNAVAILABLE, "value": "", "variablesReference": 0}] if expand else []

    def _format_variables(self, variables):
        slots, values = [], []
        for index, variable in enumerate(variables):
            kind = managed_kind(variable)
            if kind is None:
                continue
            raw = variable.get("value", "")
            variable.update(value=UNAVAILABLE, variablesReference=0)
            pointer = re.fullmatch(r"\s*(?:\([^)]*\)\s*)?(0[xX][0-9a-fA-F]{1,16})\s*", raw)
            if raw.strip() in {"nullptr", "NULL", "nil"}:
                variable["value"] = "रिक्त"
            elif pointer:
                slots.append(index)
                values.append((variable["name"], int(pointer[1], 16), kind))
        if values:
            rows = self._inspect_values(values)
            if len(rows) == len(slots):
                for index, row in zip(slots, rows):
                    variables[index].update(row)
