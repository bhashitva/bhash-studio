# SPDX-License-Identifier: Apache-2.0
"""Read-only Bhash ABI 17 value inspection in LLDB's Python interpreter."""

import base64
import json
import struct

import lldb


KINDS = {1: "INT", 2: "BOOL", 3: "TEXT", 4: "OBJECT", 5: "ANY",
         6: "REAL", 7: "BYTE", 8: "INT32"}
NAMES = {"TEXT": "पाठ", "OBJECT": "वस्तु", "ANY": "सर्ववस्तु"}
COLLECTIONS = {"ARRAY": "सरणी", "LIST": "सूची", "MAP": "मानचित्र", "BUFFER": "बाइटबफ़र"}
UNAVAILABLE = "मान उपलब्ध नहीं"


def signed(bits, width=64):
    bits &= (1 << width) - 1
    return bits - (1 << width) if bits >> (width - 1) else bits


class Inspection:
    def __init__(self, target):
        self.target = target
        self.process = target.GetProcess()
        self.remaining = 5 * 1024 * 1024
        self.layout = None

    def read(self, address, size):
        if address <= 0 or not 0 <= size <= self.remaining:
            raise ValueError("Invalid read")
        self.remaining -= size
        error = lldb.SBError()
        data = self.process.ReadMemory(address, size, error) if size else b""
        if len(data or b"") != size or error.Fail():
            raise ValueError("Unreadable memory")
        return data

    def word(self, address):
        return int.from_bytes(self.read(address, 8), "little")

    def schema(self):
        if self.layout is None:
            if self.target.GetAddressByteSize() != 8 or self.target.GetByteOrder() != lldb.eByteOrderLittle:
                raise ValueError("Unsupported architecture")
            symbols = self.target.FindSymbols("bhash_debug_schema")
            if not symbols.GetSize():
                raise ValueError("Missing debug schema")
            address = symbols.GetContextAtIndex(0).GetSymbol().GetStartAddress().GetLoadAddress(self.target)
            length = self.word(address)
            if not 0 < length <= 4 * 1024 * 1024:
                raise ValueError("Invalid debug schema")
            data = json.loads(self.read(address + 8, length))
            if data.get("version") != 1 or data.get("abi") != 17:
                raise ValueError("Unsupported debug schema")
            self.layout = data
        return self.layout

    def describe(self, address, kind, expand=False):
        if kind not in NAMES:
            values = {"INT": lambda: signed(address), "INT32": lambda: signed(address, 32),
                      "BOOL": lambda: "सत्य" if address else "असत्य",
                      "BYTE": lambda: address & 255,
                      "REAL": lambda: struct.unpack("<d", address.to_bytes(8, "little"))[0]}
            return str(values[kind]()), []
        if not address:
            return "रिक्त", []
        schema = self.schema()
        if kind == "TEXT":
            length = self.word(address)
            if length > 1 << 40:
                raise ValueError("Invalid text length")
            data = self.read(address + 8, min(length, 1024)).decode("utf-8", "replace")
            return json.dumps(data, ensure_ascii=False) + (" …" if length > 1024 else ""), []
        info = self.word(address)
        if not 0 < self.word(info + 16) <= 65536:
            raise ValueError("Invalid type information")
        identity = signed(self.word(self.word(info + 24)))
        if identity in (-1, -2, -3, -6, -7, -8):
            return self.describe(self.word(address + 8), KINDS[-identity])
        collection = schema["collections"].get(str(identity))
        if collection:
            count = self.word(address + 8)
            if count > min(self.word(address + 24), 1 << 31):
                raise ValueError("Invalid collection size")
            label = f"{COLLECTIONS[collection['kind']]} ({count})"
            if not expand:
                return label, bool(count)
            start = self.word(address + 32)
            children = []
            for index in range(min(count, 50)):
                name = f"[{index}]"
                if collection["kind"] == "MAP":
                    slot = start + index * 32
                    children.append((name + ".कुंजी", self.word(slot), KINDS[collection["key"]]))
                    children.append((name + ".मान", self.word(slot + 8), KINDS[collection["value"]]))
                elif collection["kind"] == "BUFFER":
                    children.append((name, self.read(start + index, 1)[0], "BYTE"))
                else:
                    children.append((name, self.word(start + index * 8), KINDS[collection["value"]]))
            return label, children
        cls = schema["classes"].get(str(identity), {})
        fields = cls.get("fields", [])
        return cls.get("name", "वस्तु"), ([
            (field["name"], self.word(address + field["offset"]), field["type"]) for field in fields[:100]
        ] if expand else bool(fields))

    def row(self, name, address, kind):
        try:
            value, expandable = self.describe(address, kind)
        except (ValueError, RuntimeError, KeyError, TypeError, OverflowError):
            value, expandable = UNAVAILABLE, False
        row = {"name": name, "value": value, "variablesReference": 0, "type": NAMES.get(kind, kind)}
        if expandable:
            row["bhashChildren"] = [address, kind]
        return row


def inspect_values(debugger, encoded):
    request = json.loads(base64.b64decode(encoded))
    target = debugger.GetSelectedTarget()
    inspection = Inspection(target)
    try:
        inspection.schema()
    except (ValueError, RuntimeError, KeyError, TypeError, OverflowError) as error:
        rows = {"error": str(error)}
    else:
        rows = inspect_rows(inspection, request)
    print("BHASH_VALUES:" + base64.b64encode(json.dumps(rows, ensure_ascii=False).encode()).decode())


def inspect_rows(inspection, request):
    if request["expand"]:
        address, kind = request["values"]
        try:
            _, children = inspection.describe(address, kind, expand=True)
            rows = [inspection.row(*child) for child in children]
        except (ValueError, RuntimeError, KeyError, TypeError, OverflowError):
            rows = [{"name": UNAVAILABLE, "value": "", "variablesReference": 0}]
    else:
        rows = [inspection.row(*value) for value in request["values"]]
    return rows


def load_android_symbols(debugger, path, slide):
    target = debugger.GetSelectedTarget()
    module = target.AddModule(path, None, None)
    if not module.IsValid() or not module.GetNumCompileUnits():
        raise RuntimeError("Bhash library has no readable debug information")
    # The loaded stripped copy can otherwise win address-to-frame lookup.
    for index in reversed(range(target.GetNumModules())):
        loaded = target.GetModuleAtIndex(index)
        if loaded != module and loaded.GetFileSpec().GetFilename() == "libbhash_app.so":
            target.ClearModuleLoadAddress(loaded)
            target.RemoveModule(loaded)
    error = target.SetModuleLoadAddress(module, slide)
    if error.Fail():
        raise RuntimeError(error.GetCString())
