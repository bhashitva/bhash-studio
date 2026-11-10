"""JSON-derived configuration with Bhash's existing typed Hindi literals."""

import json
import math
import re
import unicodedata

from .errors import FormatError, StudioError

LITERALS = {"सत्य": True, "असत्य": False, "रिक्त": None}
NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
MAX_SOURCE = 1_000_000


class Parser:
    def __init__(self, source):
        if not isinstance(source, str) or len(source) > MAX_SOURCE:
            raise StudioError("विन्यास का आकार बहुत बड़ा है। अधिकतम दस लाख अक्षर रखें।")
        self.source = source
        self.offset = 0
        self.decoder = json.JSONDecoder()

    def fail(self, message):
        raise FormatError(message, self.source, self.offset)

    def whitespace(self):
        while self.offset < len(self.source) and self.source[self.offset] in " \t\r\n":
            self.offset += 1

    def consume(self, token):
        self.whitespace()
        if self.source.startswith(token, self.offset):
            self.offset += len(token)
            return True
        return False

    def string(self):
        self.whitespace()
        if not self.source.startswith('"', self.offset):
            self.fail("पाठ को दोहरे उद्धरण चिह्नों में लिखें।")
        try:
            value, end = self.decoder.raw_decode(self.source, self.offset)
        except json.JSONDecodeError as error:
            self.offset = error.pos
            self.fail("पाठ या उसका विशेष चिह्न सही नहीं है।")
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            self.fail("पाठ में अधूरा यूनिकोड अक्षर है।")
        self.offset = end
        return value

    def value(self, depth=0):
        if depth > 64:
            self.fail("विन्यास में बहुत अधिक भीतरी स्तर हैं।")
        self.whitespace()
        if self.offset == len(self.source):
            self.fail("यहाँ एक मान लिखें।")
        if self.source[self.offset] == '"':
            return self.string()
        if self.consume("{"):
            result = {}
            if self.consume("}"):
                return result
            while True:
                key = unicodedata.normalize("NFC", self.string())
                if key in result:
                    self.fail(f"क्षेत्र ‘{key}’ दो बार लिखा गया है।")
                if not self.consume(":"):
                    self.fail("क्षेत्र के बाद ':' चिह्न लगाएँ।")
                result[key] = self.value(depth + 1)
                if self.consume("}"):
                    return result
                if not self.consume(","):
                    self.fail("अगले क्षेत्र से पहले ',' चिह्न लगाएँ।")
        if self.consume("["):
            result = []
            if self.consume("]"):
                return result
            while True:
                result.append(self.value(depth + 1))
                if self.consume("]"):
                    return result
                if not self.consume(","):
                    self.fail("अगले मान से पहले ',' चिह्न लगाएँ।")
        for token, value in LITERALS.items():
            if self.source.startswith(token, self.offset):
                self.offset += len(token)
                return value
        number = NUMBER.match(self.source, self.offset)
        if number:
            self.offset = number.end()
            try:
                value = json.loads(number.group())
            except ValueError:
                self.fail("संख्या बहुत बड़ी है। छोटा मान लिखें।")
            if isinstance(value, float) and not math.isfinite(value):
                self.fail("संख्या सीमित परिमाण में लिखें।")
            return value
        self.fail("मान के लिए पाठ, संख्या, सत्य, असत्य, रिक्त, सूची या वस्तु लिखें।")


def loads(source):
    parser = Parser(source)
    result = parser.value()
    parser.whitespace()
    if parser.offset != len(source):
        parser.fail("मान के बाद अनपेक्षित अक्षर हैं।")
    return result


def dumps(value, level=0):
    if value is True:
        return "सत्य"
    if value is False:
        return "असत्य"
    if value is None:
        return "रिक्त"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return json.dumps(value, allow_nan=False)
    if isinstance(value, (dict, list)):
        if not value:
            return "{}" if isinstance(value, dict) else "[]"
        indent = "  " * (level + 1)
        if isinstance(value, dict):
            parts = [f"{dumps(key)}: {dumps(item, level + 1)}" for key, item in value.items()]
            opening, closing = "{", "}"
        else:
            parts = [dumps(item, level + 1) for item in value]
            opening, closing = "[", "]"
        return opening + "\n" + indent + (",\n" + indent).join(parts) + "\n" + "  " * level + closing
    raise TypeError("Unsupported configuration value")


def validate_config(config):
    if not isinstance(config, dict):
        raise StudioError("परियोजना का विन्यास एक वस्तु होना चाहिए।")
    allowed = {"योजना_संस्करण", "नाम", "लक्ष्य", "ऐप_पहचान", "न्यूनतम_एंड्रॉयड_स्तर", "संजाल_अनुमति", "प्रारंभिक_मान"}
    for key in config:
        if key not in allowed:
            raise StudioError(f"विन्यास में अज्ञात क्षेत्र ‘{key}’ है।")
    if type(config.get("योजना_संस्करण")) is not int or config["योजना_संस्करण"] != 1:
        raise StudioError("योजना_संस्करण का मान 1 रखें।")
    name = config.get("नाम")
    if not isinstance(name, str) or not name.strip() or len(name) > 100 or any(ord(c) < 32 for c in name):
        raise StudioError("ऐप का नाम 1 से 100 अक्षरों में लिखें।")
    if not isinstance(config.get("लक्ष्य"), str) or config["लक्ष्य"] not in {"एंड्रॉयड", "डेस्कटॉप", "वेब"}:
        raise StudioError("लक्ष्य के लिए एंड्रॉयड, डेस्कटॉप या वेब चुनें।")
    app_id = config.get("ऐप_पहचान", "")
    if not isinstance(app_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", app_id):
        raise StudioError("ऐप की पहचान सही नहीं है। नई परियोजना से मिली पहचान बनाए रखें।")
    if type(config.get("न्यूनतम_एंड्रॉयड_स्तर")) is not int or config["न्यूनतम_एंड्रॉयड_स्तर"] != 29:
        raise StudioError("इस प्रारूप में न्यूनतम_एंड्रॉयड_स्तर का मान 29 रखें।")
    if type(config.get("संजाल_अनुमति")) is not bool:
        raise StudioError("संजाल_अनुमति के लिए सत्य या असत्य लिखें।")
    return config
