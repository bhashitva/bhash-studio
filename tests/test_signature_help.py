import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bhash_studio.android import Toolchain
from bhash_studio.project import Project
from bhash_studio.signature_help import LanguageServer, call_site, library_help, position


class SignatureHelpTests(unittest.TestCase):
    def test_call_site_respects_strings_and_nested_calls(self):
        source = 'आयात मानक.पाठ्य उपनाम प;\nप.अंश(फल("😀,("), '
        site = call_site(source, len(source))
        self.assertEqual(site[1], "अंश")
        self.assertEqual(position(source, len(source))["character"], len(source.splitlines()[-1]) + 1)
        description, link = library_help(source, site, None)
        self.assertIn("शून्य", description)
        self.assertIn("github.com/bhashitva/bhash", link)
        self.assertIsNone(call_site('// प.अंश(', len('// प.अंश(')))

    @unittest.skipUnless(os.environ.get("BHASH_COMPILER_JAR"), "Needs the Bhash compiler and Java")
    def test_compiler_resolves_library_and_cross_file_instance_calls(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "types.bhash").write_text(
                "सार्वजनिक वर्ग नमूना { सार्वजनिक फलन योग(पहला: पूर्णांक, दूसरा: पूर्णांक) -> पूर्णांक "
                "{ लौटाओ पहला + दूसरा; } }", encoding="utf-8",
            )
            server = LanguageServer()
            try:
                cases = (
                    ('आयात मानक.पाठ्य उपनाम प;\nफलन चलो() -> शून्य { प.अंश("😀", ', "आरंभ", True),
                    ('आयात मानक.समुच्चय उपनाम समूह;\nफलन चलो() -> शून्य { '
                     'स्थिर वस्तु: समूह<पूर्णांक> = नया समूह<पूर्णांक>(); वस्तु.जोड़ो(', "तत्वमान", True),
                    ('फलन चलो() -> शून्य { स्थिर व: नमूना = नया नमूना(); व.योग(१, ', "दूसरा", False),
                )
                for source, parameter, documented in cases:
                    with self.subTest(parameter=parameter):
                        help = server.help(Toolchain.discover(), Project(root), "main.bhash",
                                           {"main.bhash": source}, len(source), call_site(source, len(source)))
                        self.assertIsNotNone(help)
                        self.assertIn(parameter, help.parameter)
                        self.assertEqual(bool(help.url), documented)
            finally:
                server.close()
