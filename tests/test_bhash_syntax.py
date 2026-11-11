import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unicodedata import normalize
from zipfile import ZipFile

from bhash_studio.bhash_syntax import analyze, standard_imports, standard_library


class BhashSyntaxTests(unittest.TestCase):
    def test_imported_member_completion_and_aliases(self):
        methods = {"पाठ्य": ("लंबाई", "अंश")}
        for declaration, receiver in (("आयात मानक.पाठ्य;", "पाठ्य"), ("आयात मानक.पाठ्य उपनाम प;", "प")):
            source = f"{declaration}\n{receiver}.लअधूरा()"
            caret = source.index("लअधूरा") + 1
            _, completion = analyze(source, caret, methods=methods)
            self.assertEqual(completion.options, ("लंबाई",))
            self.assertEqual(source[completion.start:completion.end], "लअधूरा")
            source = f"{declaration}\n{receiver}."
            self.assertEqual(analyze(source, len(source), methods=methods)[1].options, ("लंबाई", "अंश"))
        for source in ("// आयात मानक.पाठ्य;\nपाठ्य.", 'आयात मानक.पाठ्य;\n"पाठ्य.',
                       "आयात मानक.पाठ्य;\n// पाठ्य.", "आयात मानक.पाठ्य;\nवस्तु.पाठ्य."):
            self.assertIsNone(analyze(source, len(source), methods=methods)[1])

    def test_standard_import_completion_uses_context_and_replaces_the_member(self):
        for source in ("आयात ", "आयात म", "आयात मानक"):
            with self.subTest(source=source):
                _, completion = analyze(source, len(source))
                self.assertIn("मानक.पाठ्य", completion.options)
                self.assertEqual(completion.start, len("आयात "))
        source = "आयात मानक.फ़ााइल;"
        caret = len("आयात मानक.फ़ा")
        _, completion = analyze(source, caret)
        self.assertEqual(completion.options, ("फ़ाइल",))
        self.assertEqual(source[completion.start:completion.end], "फ़ााइल")
        for source in ("// आयात मानक.", "/*\nआयात मानक.", '"आयात मानक.', "मानक."):
            self.assertIsNone(analyze(source, len(source))[1])

    def test_import_catalog_comes_from_the_compiler_jar(self):
        with TemporaryDirectory() as temp:
            jar = Path(temp) / "compiler.jar"
            with ZipFile(jar, "w") as archive:
                archive.writestr("dev/bhash/stdlib/api.txt", "पाठ्य|नाम|read|पाठ|\n")
                archive.writestr("dev/bhash/stdlib/foundations.bhash", """संकुल मानक;
सार्वजनिक वर्ग संग्रह<T> {
    सार्वजनिक साझा फलन बनाओ() {}
    सार्वजनिक फलन रखो() {}
    // सार्वजनिक साझा फलन टिप्पणी() {}
}
""")
            source = "आयात मानक."
            _, completion = analyze(source, len(source), standard_imports(jar))
            self.assertEqual(set(completion.options), {"पाठ्य", "संग्रह"})
            self.assertEqual(standard_library(jar)[1], {"पाठ्य": ("नाम",), "संग्रह": ("बनाओ",)})

    def test_keywords_respect_token_boundaries_comments_and_strings(self):
        source = 'फलन फलननाम() { लिखो("यदि \\"सत्य\\""); // अन्यथा\n /* लौटाओ */ असत्य रिक्त }'
        ranges, _ = analyze(source)
        self.assertEqual([source[start:end] for start, end in ranges],
                         ["फलन", "लिखो", "असत्य", "रिक्त"])
        decomposed = normalize("NFD", "पकड़ो बाइटबफ़र")
        self.assertEqual(len(analyze(decomposed)[0]), 2)

    def test_completion_uses_the_prefix_and_replaces_the_current_token(self):
        source = "मान परिणाम: पाठ;\nपरिअधूरा"
        start = source.rindex("\n") + 1
        _, completion = analyze(source, start + len("परि"))
        self.assertEqual((completion.start, completion.end), (start, len(source)))
        self.assertIn("परिणाम", completion.options)
        self.assertIn("परिवर्तित", completion.options)
        self.assertNotIn("परिअधूरा", completion.options)

    def test_no_completion_inside_text_comments_or_after_member_access(self):
        for source in ('"यद', '// यद', '/* यद', 'वस्तु.यद'):
            with self.subTest(source=source):
                self.assertIsNone(analyze(source, len(source))[1])
