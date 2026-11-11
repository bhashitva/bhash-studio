"""Lightweight editor tokenization for the Bhash 0.25.0 grammar."""

from dataclasses import dataclass
import re
from unicodedata import normalize


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

TOKENS = re.compile(
    r'(?P<comment>//[^\r\n]*|/\*[\s\S]*?(?:\*/|\Z))'
    r'|(?P<string>"(?:\\[^\r\n]|[^"\\\r\n])*\\?"?)'
    r'|(?P<word>[\w\u0900-\u0903\u093a-\u094f\u0951-\u0957\u0962-\u0963\u200c\u200d]+)'
)


@dataclass(frozen=True)
class Completion:
    start: int
    end: int
    options: tuple[str, ...]


def analyze(source, caret=None):
    """Return keyword ranges and, when requested, prefix matches at the caret."""
    ranges = []
    names = {}
    active = None
    for token in TOKENS.finditer(source):
        if token.lastgroup != "word":
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
