"""Typed screen model shared by the preview and Android generator."""

from dataclasses import dataclass
import re
import unicodedata
import xml.etree.ElementTree as ET

from .errors import StudioError


@dataclass(frozen=True)
class Node:
    kind: str
    text: str = ""
    handler: str = ""
    argument: str = ""
    children: tuple = ()


@dataclass(frozen=True)
class Screen:
    title: str
    content: Node


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
            raise StudioError("दृश्य का पाठ ‘पाठ’ या ‘बटन’ के भीतर लिखें।")
        if element.tag in {"स्तंभ", "पंक्ति"}:
            if element.attrib or (element.text or "").strip():
                raise StudioError("स्तंभ या पंक्ति में केवल भीतरी भाग रखें।")
            return Node(element.tag, children=tuple(parse(child, depth + 1) for child in element))
        if element.tag not in {"पाठ", "बटन"} or len(element):
            raise StudioError("दृश्य में स्तंभ, पंक्ति, पाठ और बटन समर्थित हैं।")
        text = element.text or ""
        if not text.strip():
            raise StudioError("पाठ और बटन की लिखावट खाली नहीं हो सकती।")
        if element.tag == "पाठ":
            if element.attrib:
                raise StudioError("पाठ पर अतिरिक्त गुण समर्थित नहीं हैं।")
            return Node("पाठ", text=text)
        if not {"दबानेपर"} <= set(element.attrib) <= {"दबानेपर", "तर्क"}:
            raise StudioError("बटन पर दबानेपर और वैकल्पिक तर्क लिखें।")
        handler = unicodedata.normalize("NFC", element.attrib["दबानेपर"])
        if not handler.isidentifier():
            raise StudioError("बटन के फलन का नाम एक सही भाष पहचान होना चाहिए।")
        return Node("बटन", text, handler, element.attrib.get("तर्क", ""))

    if root[0].tag not in {"स्तंभ", "पंक्ति"}:
        raise StudioError("पर्दे का पहला भाग स्तंभ या पंक्ति रखें।")
    return Screen(root.attrib["शीर्षक"], parse(root[0], 0))


def handlers(screen):
    result = []

    def visit(node):
        if node.handler and node.handler not in result:
            result.append(node.handler)
        for child in node.children:
            visit(child)

    visit(screen.content)
    return result


def validate_handlers(screen, source):
    # This is a bridge contract check. Full Bhash type checking remains in the compiler.
    normalized = unicodedata.normalize("NFC", source)
    for handler in handlers(screen):
        pattern = r"फलन\s+" + re.escape(handler) + r"\s*\(\s*[^():\s]+\s*:\s*पाठ\s*\)\s*->\s*पाठ\s*\{"
        if not re.search(pattern, normalized):
            raise StudioError(f"बटन के लिए फलन ‘{handler}’ का रूप फलन नाम(मान: पाठ) -> पाठ रखें।")
