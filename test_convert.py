import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import convert as convert_mod
from convert import ConversionError, convert_module, convert_url_regex


class ConvertTests(unittest.TestCase):
    def test_converts_rule_section_and_strips_policy(self):
        module = """#!name=test
[Rule]
DOMAIN-SUFFIX,example.com,DIRECT
DOMAIN,api.example.com,DIRECT
"""
        self.assertEqual(
            convert_module(module, "DIRECT"),
            "DOMAIN-SUFFIX,example.com\nDOMAIN,api.example.com\n",
        )

    def test_ignores_metadata_comments_and_non_rule_sections(self):
        module = """#!name=test
#!comment=ignored
[General]
foo=bar
[Rule]
# still ignored
DOMAIN,example.com,DIRECT
[MITM]
foo=bar
"""
        self.assertEqual(convert_module(module, "DIRECT"), "DOMAIN,example.com\n")

    def test_converts_host_only_url_regex(self):
        self.assertEqual(
            convert_url_regex(r"^https?:\/\/(.*\.)?example\.com.*$"),
            r"DOMAIN-REGEX,^(.*\.)?example\.com$",
        )

    def test_rejects_path_url_regex(self):
        with self.assertRaisesRegex(ConversionError, "path"):
            convert_url_regex(r"^https?:\/\/example\.com\/private.*$")

    def test_rejects_raw_path_url_regex(self):
        with self.assertRaisesRegex(ConversionError, "path"):
            convert_url_regex(r"^https?:\/\/example\.com/private.*$")

    def test_rejects_port_url_regex(self):
        with self.assertRaisesRegex(ConversionError, "canonical"):
            convert_url_regex(r"^https?:\/\/example\.com:443.*$")

    def test_rejects_query_url_regex(self):
        with self.assertRaisesRegex(ConversionError, "canonical"):
            convert_url_regex(r"^https?:\/\/example\.com\?foo.*$")

    def test_rejects_fragment_url_regex(self):
        with self.assertRaisesRegex(ConversionError, "canonical"):
            convert_url_regex(r"^https?:\/\/example\.com\#frag.*$")

    def test_rejects_policy_mismatch(self):
        with self.assertRaisesRegex(ConversionError, "expected DIRECT"):
            convert_module("[Rule]\nDOMAIN,example.com,PROXY\n", "DIRECT")

    def test_rejects_unknown_rule_type(self):
        with self.assertRaisesRegex(ConversionError, "unsupported"):
            convert_module("[Rule]\nUNKNOWN,example.com,DIRECT\n", "DIRECT")

    def test_omits_user_agent_rules(self):
        module = """[Rule]
USER-AGENT,Shadowrocket,DIRECT
DOMAIN,example.com,DIRECT
"""
        self.assertEqual(convert_module(module, "DIRECT"), "DOMAIN,example.com\n")

    def test_main_warns_about_skipped_user_agent_rules(self):
        module = """[Rule]
USER-AGENT,Shadowrocket,DIRECT
DOMAIN,example.com,DIRECT
"""
        captured = {}

        def fake_write(path, text):
            captured["path"] = path
            captured["text"] = text
            return True

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(
                convert_mod,
                "SOURCE_DEFINITIONS",
                (
                    (
                        "sample",
                        "DIRECT",
                        "https://example.test/sample.module",
                        Path("rules/sample.txt"),
                    ),
                ),
            ),
            patch.object(convert_mod, "_download_text", return_value=module),
            patch.object(convert_mod, "_write_text_if_changed", side_effect=fake_write),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            self.assertEqual(convert_mod.main(), 0)

        self.assertEqual(captured["text"], "DOMAIN,example.com\n")
        self.assertIn("sample: skipped 1 USER-AGENT rules", stderr.getvalue())
        self.assertIn(
            "sample: 1 rules (updated) -> rules/sample.txt", stdout.getvalue()
        )

    def test_preserves_quoted_regex_commas(self):
        module = """[Rule]
URL-REGEX,"^https?:\\/\\/(.*\\.)?example\\.com.*$",DIRECT
"""
        self.assertEqual(
            convert_module(module, "DIRECT"),
            "DOMAIN-REGEX,^(.*\\.)?example\\.com$\n",
        )

    def test_rejects_missing_rule_section(self):
        with self.assertRaisesRegex(ConversionError, "Rule"):
            convert_module("[General]\nfoo=bar\n", "DIRECT")

    def test_rejects_empty_rule_section(self):
        with self.assertRaisesRegex(ConversionError, "zero rules"):
            convert_module("[Rule]\n", "DIRECT")

    def test_keeps_trailing_newline_deterministic(self):
        self.assertTrue(
            convert_module("[Rule]\nDOMAIN,example.com,DIRECT\n", "DIRECT").endswith(
                "\n"
            )
        )


if __name__ == "__main__":
    unittest.main()
