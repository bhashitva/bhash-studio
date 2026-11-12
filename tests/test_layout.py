import unittest

from bhash_studio.android import generate_activity, generate_exports, generate_device_tests, kotlin_text
from bhash_studio.errors import StudioError
from bhash_studio.layout import handlers, parse_layout, validate_handlers
from bhash_studio.project import DEFAULT_LAYOUT, DEFAULT_SOURCE


LEGACY_LAYOUT = DEFAULT_LAYOUT.replace(
    'इनपुटसे="नाम" परिणाममें="संदेश"', 'तर्क="दुनिया"',
).replace('    <प्रविष्टि पहचान="नाम">अपना नाम लिखें</प्रविष्टि>\n', "").replace(
    '    <पाठ पहचान="संदेश"/>\n', "",
)


class ScreenTests(unittest.TestCase):
    def test_shared_screen_model_and_bridge_contract(self):
        screen = parse_layout(DEFAULT_LAYOUT)
        validate_handlers(screen, DEFAULT_SOURCE)
        self.assertEqual(handlers(screen), ["अभिवादन"])
        action = screen.content.children[2].action
        self.assertEqual((action.input_id, action.result_id), ("नाम", "संदेश"))

    def test_generated_kotlin_calls_bhash_worker(self):
        screen = parse_layout(DEFAULT_LAYOUT)
        activity = generate_activity(screen)
        self.assertIn("val input = textState0", activity)
        self.assertIn("textState1 = BhashRuntime.onWorker { BhashBindings.bhash_studio_action_0(input) }", activity)
        self.assertIn('Text(textState1, modifier = Modifier.testTag("text:संदेश"))', activity)
        self.assertIn("OutlinedTextField", activity)
        self.assertIn("rememberSaveable", activity)
        self.assertIn("throw cancelled", activity)
        self.assertEqual(generate_exports(screen), "bhash_studio_action_0 = अभिवादन(पाठ) -> पाठ\n")

    def test_kotlin_strings_cannot_inject_code(self):
        self.assertEqual(kotlin_text('"\\$\n'), '"\\"\\\\\\$\\u000a"')
        screen = parse_layout(LEGACY_LAYOUT.replace("दुनिया", "$value &quot;x&quot;"))
        self.assertIn('\\$value \\"x\\"', generate_activity(screen))

    def test_legacy_layout_still_uses_literal_and_status(self):
        screen = parse_layout(LEGACY_LAYOUT)
        activity = generate_activity(screen)
        self.assertIn('status = BhashRuntime.onWorker { BhashBindings.bhash_studio_action_0("दुनिया") }', activity)
        self.assertIn("Text(status)", activity)

    def test_binding_rejects_missing_duplicate_and_wrong_component_ids(self):
        for source in (
            DEFAULT_LAYOUT.replace('इनपुटसे="नाम"', 'इनपुटसे="गुम"'),
            DEFAULT_LAYOUT.replace('परिणाममें="संदेश"', 'परिणाममें="नाम"'),
            DEFAULT_LAYOUT.replace('इनपुटसे="नाम"', 'इनपुटसे="संदेश"'),
            DEFAULT_LAYOUT.replace('<पाठ पहचान="संदेश"/>', '<पाठ पहचान="नाम"/>'),
            DEFAULT_LAYOUT.replace('इनपुटसे="नाम"', 'इनपुटसे="नाम" तर्क="दुनिया"'),
            DEFAULT_LAYOUT.replace(' परिणाममें="संदेश"', ''),
        ):
            with self.subTest(source=source), self.assertRaises(StudioError):
                parse_layout(source)

    def test_two_actions_route_to_independent_fields(self):
        source = DEFAULT_LAYOUT.replace("</स्तंभ>", """
    <प्रविष्टि पहचान="नगर" आरंभिक="वाराणसी">नगर</प्रविष्टि>
    <बटन दबानेपर="अभिवादन" इनपुटसे="नगर" परिणाममें="स्थान">नगर दिखाएँ</बटन>
    <पाठ पहचान="स्थान">अभी खाली</पाठ>
  </स्तंभ>""")
        screen = parse_layout(source)
        activity = generate_activity(screen)
        self.assertIn('var textState2 by rememberSaveable { mutableStateOf("वाराणसी") }', activity)
        self.assertIn('var textState3 by rememberSaveable { mutableStateOf("अभी खाली") }', activity)
        self.assertIn("val input = textState2", activity)
        self.assertIn("textState3 = BhashRuntime.onWorker { BhashBindings.bhash_studio_action_0(input) }", activity)
        self.assertNotIn("Text(status)", activity)
        self.assertEqual(handlers(screen), ["अभिवादन"])

    def test_missing_handler_is_actionable(self):
        with self.assertRaises(StudioError):
            validate_handlers(parse_layout(DEFAULT_LAYOUT), "फलन दूसरा() {}")

    def test_device_tests_match_generated_screen_and_binding(self):
        tests = generate_device_tests(parse_layout(DEFAULT_LAYOUT))
        self.assertIn("StudioScreenTest", tests)
        self.assertIn("SCREEN_ORIENTATION_LANDSCAPE", tests)
        self.assertIn("scenario.recreate()", tests)
        self.assertIn("startWithForcedGc()", tests)
        self.assertIn("BhashBindings.bhash_studio_action_0(value)", tests)
        self.assertIn('compose.onNodeWithTag("input:नाम")', tests)
        self.assertIn('awaitText(value, "text:संदेश")', tests)
        self.assertIn("performTextReplacement(changedInput)", tests)
        self.assertNotIn("bhash_greeting", tests)

    def test_static_screen_tests_do_not_reference_a_missing_action(self):
        screen = parse_layout('<पर्दा पहचान="मुख्य" शीर्षक="शीर्षक"><स्तंभ><पाठ>केवल पाठ</पाठ></स्तंभ></पर्दा>')
        tests = generate_device_tests(screen)
        self.assertIn('awaitText("शीर्षक")', tests)
        self.assertNotIn("bhash_studio_action_0", tests)

    def test_invalid_layouts_are_rejected(self):
        for source in ("<bad/>", DEFAULT_LAYOUT.replace("<पाठ>", "<गलत>"),
                       DEFAULT_LAYOUT.replace("दबानेपर", "onclick"),
                       DEFAULT_LAYOUT.replace("अभिवादन\"", "a);bad()\""),
                       '<!DOCTYPE a [<!ENTITY x SYSTEM "file:///secret">]><a>&x;</a>',
                       DEFAULT_LAYOUT.replace("<स्तंभ>", '<स्तंभ unknown="x">'),
                       DEFAULT_LAYOUT.replace("</बटन>", "</बटन>bad")):
            with self.subTest(source=source), self.assertRaises(StudioError):
                parse_layout(source)

    def test_layout_limits(self):
        source = '<पर्दा पहचान="मुख्य" शीर्षक="ऐप"><स्तंभ>' + '<पाठ>क</पाठ>' * 201 + '</स्तंभ></पर्दा>'
        with self.assertRaises(StudioError):
            parse_layout(source)
