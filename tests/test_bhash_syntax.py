import unittest
from unicodedata import normalize

from bhash_studio.bhash_syntax import analyze


class BhashSyntaxTests(unittest.TestCase):
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
