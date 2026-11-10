import unittest

from bhash_studio.android import generate_activity, generate_exports, kotlin_text
from bhash_studio.errors import StudioError
from bhash_studio.layout import handlers, parse_layout, validate_handlers
from bhash_studio.project import DEFAULT_LAYOUT, DEFAULT_SOURCE


class ScreenTests(unittest.TestCase):
    def test_shared_screen_model_and_bridge_contract(self):
        screen = parse_layout(DEFAULT_LAYOUT)
        validate_handlers(screen, DEFAULT_SOURCE)
        self.assertEqual(handlers(screen), ["अभिवादन"])
        self.assertEqual(screen.content.children[1].argument, "दुनिया")

    def test_generated_kotlin_calls_bhash_worker(self):
        screen = parse_layout(DEFAULT_LAYOUT)
        activity = generate_activity(screen)
        self.assertIn('BhashRuntime.onWorker { BhashBindings.studio_action_0("दुनिया") }', activity)
        self.assertIn("rememberSaveable", activity)
        self.assertIn("throw cancelled", activity)
        self.assertEqual(generate_exports(screen), "studio_action_0 = अभिवादन(पाठ) -> पाठ\n")

    def test_kotlin_strings_cannot_inject_code(self):
        self.assertEqual(kotlin_text('"\\$\n'), '"\\"\\\\\\$\\u000a"')
        screen = parse_layout(DEFAULT_LAYOUT.replace("दुनिया", "$value &quot;x&quot;"))
        self.assertIn('\\$value \\"x\\"', generate_activity(screen))

    def test_missing_handler_is_actionable(self):
        with self.assertRaises(StudioError):
            validate_handlers(parse_layout(DEFAULT_LAYOUT), "फलन दूसरा() {}")

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
