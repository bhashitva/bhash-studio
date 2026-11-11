"""Typed screen model shared by the preview and Android generator."""

from dataclasses import dataclass
import re
import unicodedata
import xml.etree.ElementTree as ET

from .errors import StudioError


@dataclass(frozen=True)
class TextAction:
    handler: str
    literal: str = ""
    input_id: str | None = None
    result_id: str | None = None


@dataclass(frozen=True)
class Node:
    kind: str
    text: str = ""
    identity: str | None = None
    initial: str = ""
    action: TextAction | None = None
    children: tuple["Node", ...] = ()


@dataclass(frozen=True)
class Screen:
    title: str
    content: Node


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def identifier(value):
    name = unicodedata.normalize("NFC", value)
    if not name.isidentifier():
        raise StudioError(f"‘{value}’ की जगह एक सही पहचान लिखें।")
    return name


def parse_layout(source):
    if len(source) > 1_000_000 or "<!" in source:
        raise StudioError("दृश्य में घोषणा, टिप्पणी या बाहरी इकाई का उपयोग समर्थित नहीं है।")
    try:
        root = ET.fromstring(source)
    except ET.ParseError as error:
        line, column = error.position
        raise StudioError(f"दृश्य की पंक्ति {line}, स्थान {column + 1} पर चिह्नों का मिलान जाँचें।") from error
    if root.tag != "पर्दा" or set(root.attrib) != {"पहचान", "शीर्षक"} or root.attrib["पहचान"] != "मुख्य":
        raise StudioError("मुख्य पर्दे पर पहचान=मुख्य और एक शीर्षक लिखें।")
    if len(root) != 1 or (root.text or "").strip():
        raise StudioError("पर्दे के अंदर एक स्तंभ या पंक्ति रखें।")
    if not root.attrib["शीर्षक"].strip():
        raise StudioError("पर्दे का शीर्षक खाली नहीं हो सकता।")
    count = 0

    def parse(element, depth):
        nonlocal count
        count += 1
        if count > 200 or depth > 12:
            raise StudioError("दृश्य में अधिकतम 200 भाग और 12 भीतरी स्तर रखें।")
        if (element.tail or "").strip():
            raise StudioError("दृश्य की लिखावट ‘पाठ’, ‘प्रविष्टि’ या ‘बटन’ के भीतर रखें।")
        if element.tag in {"स्तंभ", "पंक्ति"}:
            if element.attrib or (element.text or "").strip():
                raise StudioError("स्तंभ या पंक्ति में केवल भीतरी भाग रखें।")
            return Node(element.tag, children=tuple(parse(child, depth + 1) for child in element))
        if element.tag not in {"पाठ", "प्रविष्टि", "बटन"} or len(element):
            raise StudioError("दृश्य में स्तंभ, पंक्ति, पाठ, प्रविष्टि और बटन समर्थित हैं।")
        attrs = element.attrib
        text = element.text or ""
        if element.tag == "पाठ":
            if set(attrs) - {"पहचान"} or ("पहचान" not in attrs and not text.strip()):
                raise StudioError("पाठ की लिखावट दें या परिणाम रखने के लिए उसकी पहचान दें।")
            return Node("पाठ", text, identity=identifier(attrs["पहचान"]) if "पहचान" in attrs else None)
        if element.tag == "प्रविष्टि":
            if not {"पहचान"} <= set(attrs) <= {"पहचान", "आरंभिक"} or not text.strip():
                raise StudioError("प्रविष्टि की पहचान और उसका दिखाई देने वाला नाम लिखें।")
            return Node("प्रविष्टि", text, identity=identifier(attrs["पहचान"]), initial=attrs.get("आरंभिक", ""))
        if not {"दबानेपर"} <= set(attrs) <= {"दबानेपर", "तर्क", "इनपुटसे", "परिणाममें"} or not text.strip():
            raise StudioError("बटन की लिखावट और दबानेपर चलने वाला फलन लिखें।")
        if "इनपुटसे" in attrs and ("तर्क" in attrs or "परिणाममें" not in attrs):
            raise StudioError("इनपुटसे के साथ परिणाममें दें। इनपुटसे और स्थिर तर्क साथ नहीं लिख सकते।")
        return Node("बटन", text, action=TextAction(
            identifier(attrs["दबानेपर"]), attrs.get("तर्क", ""),
            identifier(attrs["इनपुटसे"]) if "इनपुटसे" in attrs else None,
            identifier(attrs["परिणाममें"]) if "परिणाममें" in attrs else None,
        ))

    if root[0].tag not in {"स्तंभ", "पंक्ति"}:
        raise StudioError("पर्दे का पहला भाग स्तंभ या पंक्ति रखें।")
    content = parse(root[0], 0)
    components = {}
    for node in walk(content):
        if node.identity is not None:
            if node.identity in components:
                raise StudioError(f"दृश्य में पहचान ‘{node.identity}’ एक से अधिक बार दी गई है।")
            components[node.identity] = node.kind
    for node in walk(content):
        if node.action:
            action = node.action
            if action.input_id is not None and components.get(action.input_id) != "प्रविष्टि":
                raise StudioError(f"इनपुटसे के लिए प्रविष्टि ‘{action.input_id}’ नहीं मिली।")
            if action.result_id is not None and components.get(action.result_id) != "पाठ":
                raise StudioError(f"परिणाममें के लिए पाठ ‘{action.result_id}’ नहीं मिला।")
    return Screen(root.attrib["शीर्षक"], content)


def handlers(screen):
    return list(dict.fromkeys(node.action.handler for node in walk(screen.content) if node.action))


def validate_handlers(screen, source):
    # This is a bridge contract check. Full Bhash type checking remains in the compiler.
    normalized = unicodedata.normalize("NFC", source)
    for handler in handlers(screen):
        pattern = r"फलन\s+" + re.escape(handler) + r"\s*\(\s*[^():\s]+\s*:\s*पाठ\s*\)\s*->\s*पाठ\s*\{"
        if not re.search(pattern, normalized):
            raise StudioError(f"बटन के लिए फलन ‘{handler}’ का रूप फलन नाम(मान: पाठ) -> पाठ रखें।")
