import unittest

from bhash_studio.config import dumps, loads, validate_config
from bhash_studio.errors import FormatError, StudioError


class HindiConfigTests(unittest.TestCase):
    def test_existing_bhash_literals_are_typed(self):
        value = loads('{"सक्रिय": सत्य, "बंद": असत्य, "मान": रिक्त}')
        self.assertIs(value["सक्रिय"], True)
        self.assertIs(value["बंद"], False)
        self.assertIsNone(value["मान"])

    def test_quoted_literals_remain_text(self):
        self.assertEqual(loads('["सत्य", "असत्य", "रिक्त", "true", "नहीं"]'), ["सत्य", "असत्य", "रिक्त", "true", "नहीं"])

    def test_round_trip_nested_unicode_data(self):
        value = {"नाम": "क्ष ज्ञ क़ 😀", "मान": [True, False, None, -3, 1.25, {"पाठ": 'quote " slash \\'}]}
        self.assertEqual(loads(dumps(value)), value)

    def test_invalid_values_fail_in_hindi(self):
        for source in ('true', 'false', 'null', 'हाँ', 'नहीं', 'अनिर्दिष्ट', 'NaN', '1e999', '01', 'सत्यअसत्य', '[1,]', '{"a":1,}', '"\\ud800"'):
            with self.subTest(source=source), self.assertRaises(StudioError):
                loads(source)

    def test_keywords_inside_escaped_strings_are_untouched(self):
        self.assertEqual(loads('"\\\"सत्य\\\""'), '"सत्य"')

    def test_duplicate_keys_and_normalized_collisions_fail(self):
        for source in ('{"नाम": 1, "नाम": 2}', '{"क़": 1, "क़": 2}'):
            with self.subTest(source=source), self.assertRaises(StudioError):
                loads(source)

    def test_error_position_uses_original_hindi_source(self):
        with self.assertRaises(FormatError) as raised:
            loads('{\n"मान": सत्य,\n"गलत": ?}')
        self.assertEqual(raised.exception.line, 3)
        self.assertEqual(raised.exception.column, 8)

    def test_depth_and_source_limits(self):
        for source in ('[' * 70 + 'रिक्त' + ']' * 70, ' ' * 1_000_001):
            with self.assertRaises(StudioError):
                loads(source)

    def test_config_types_are_strict(self):
        valid = {"योजना_संस्करण": 1, "नाम": "ऐप", "लक्ष्य": "एंड्रॉयड", "ऐप_पहचान": "org.example.test",
                 "न्यूनतम_एंड्रॉयड_स्तर": 29, "संजाल_अनुमति": False, "प्रारंभिक_मान": None}
        self.assertEqual(validate_config(valid), valid)
        for field, value in [("योजना_संस्करण", True), ("संजाल_अनुमति", "असत्य"), ("नाम", ""),
                             ("ऐप_पहचान", "invalid"), ("लक्ष्य", "other"), ("न्यूनतम_एंड्रॉयड_स्तर", 28), ("unknown", 1)]:
            with self.subTest(field=field), self.assertRaises(StudioError):
                validate_config(valid | {field: value})

    def test_bad_nested_target_and_huge_number_have_hindi_errors(self):
        with self.assertRaises(StudioError):
            validate_config({"योजना_संस्करण": 1, "नाम": "ऐप", "लक्ष्य": {}})
        with self.assertRaises(StudioError):
            loads("9" * 5000)


if __name__ == "__main__":
    unittest.main()
