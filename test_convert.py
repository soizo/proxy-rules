import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import convert as convert_mod
from convert import (
    ConversionError,
    convert_fixed_rules,
    convert_module,
    convert_url_regex,
    update_fixed_providers_in_script,
    write_fixed_rule_outputs,
)


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
            patch.object(convert_mod, "convert_fixed_rules", return_value=({}, 0)),
            patch.object(
                convert_mod,
                "write_fixed_rule_outputs",
                return_value={policy: "absent" for policy in convert_mod.FIXED_POLICIES},
            ),
            patch.object(
                convert_mod, "update_fixed_providers_in_script", return_value=False
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

    def test_converts_fixed_module_plain_and_mixed_policies(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "module.txt").write_text(
                """#!name=module
[General]
DOMAIN,ignored.example,DIRECT
[Rule]
; comment
DOMAIN,direct.example,DIRECT
DOMAIN-SUFFIX,proxy.example,PROXY
[MITM]
DOMAIN,also-ignored.example,REJECT
""",
                encoding="utf-8",
            )
            (source / "plain.list").write_text(
                """# comment
DOMAIN,reject.example,REJECT
URL-REGEX,^https?:\\/\\/plain\\.example.*$,DIRECT
""",
                encoding="utf-8",
            )

            converted, skipped = convert_fixed_rules(source)

        self.assertEqual(
            converted,
            {
                "DIRECT": [
                    "DOMAIN,direct.example",
                    r"DOMAIN-REGEX,^plain\.example$",
                ],
                "PROXY": ["DOMAIN-SUFFIX,proxy.example"],
                "REJECT": ["DOMAIN,reject.example"],
            },
        )
        self.assertEqual(skipped, 0)

    def test_fixed_rules_are_recursive_sorted_hidden_ignored_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "z").mkdir()
            (source / "a").mkdir()
            (source / ".hidden").mkdir()
            (source / "z" / "last.txt").write_text(
                "DOMAIN,last.example,DIRECT\nDOMAIN,duplicate.example,DIRECT\n",
                encoding="utf-8",
            )
            (source / "a" / "first.txt").write_text(
                "DOMAIN,first.example,DIRECT\nDOMAIN,duplicate.example,DIRECT\n",
                encoding="utf-8",
            )
            (source / ".hidden" / "ignored.txt").write_text(
                "DOMAIN,hidden.example,DIRECT\n", encoding="utf-8"
            )
            (source / ".ignored.txt").write_text(
                "DOMAIN,hidden-file.example,DIRECT\n", encoding="utf-8"
            )

            converted, _ = convert_fixed_rules(source)

        self.assertEqual(
            converted["DIRECT"],
            [
                "DOMAIN,first.example",
                "DOMAIN,duplicate.example",
                "DOMAIN,last.example",
            ],
        )

    def test_empty_fixed_rules_returns_no_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            converted, skipped = convert_fixed_rules(Path(directory))

        self.assertEqual(converted, {})
        self.assertEqual(skipped, 0)

    def test_fixed_rules_validate_policy_and_rule_type(self):
        for line, message in (
            ("DOMAIN,example.com,MATCH", "policy"),
            ("UNKNOWN,example.com,DIRECT", "unsupported"),
        ):
            with self.subTest(line=line), tempfile.TemporaryDirectory() as directory:
                source = Path(directory)
                (source / "bad.txt").write_text(line + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ConversionError, message):
                    convert_fixed_rules(source)

    def test_fixed_rules_omit_user_agent_and_count_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "mine.txt").write_text(
                "USER-AGENT,Shadowrocket,DIRECT\nDOMAIN,example.com,DIRECT\n",
                encoding="utf-8",
            )
            converted, skipped = convert_fixed_rules(source)

        self.assertEqual(converted, {"DIRECT": ["DOMAIN,example.com"]})
        self.assertEqual(skipped, 1)

    def test_writes_fixed_outputs_and_removes_disappeared_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            stale_proxy = output_dir / "fixed-proxy.txt"
            stale_reject = output_dir / "fixed-reject.txt"
            stale_proxy.write_text("DOMAIN,old.example\n", encoding="utf-8")
            stale_reject.write_text("DOMAIN,old.example\n", encoding="utf-8")

            states = write_fixed_rule_outputs(
                {"DIRECT": ["DOMAIN,new.example"], "PROXY": []}, output_dir
            )

            self.assertEqual(
                (output_dir / "fixed-direct.txt").read_text(encoding="utf-8"),
                "DOMAIN,new.example\n",
            )
            self.assertFalse(stale_proxy.exists())
            self.assertFalse(stale_reject.exists())
            self.assertEqual(
                states,
                {"DIRECT": "updated", "PROXY": "removed", "REJECT": "removed"},
            )

    def test_updates_script_to_reference_only_present_fixed_outputs(self):
        script = """before
// BEGIN GENERATED FIXED PROVIDERS
old
// END GENERATED FIXED PROVIDERS
after
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "script.js"
            path.write_text(script, encoding="utf-8")

            update_fixed_providers_in_script(path, {"DIRECT", "REJECT"})
            updated = path.read_text(encoding="utf-8")

        self.assertIn('"fixed-direct": "fixed-direct.txt"', updated)
        self.assertIn('"fixed-reject": "fixed-reject.txt"', updated)
        self.assertNotIn("fixed-proxy", updated)


if __name__ == "__main__":
    unittest.main()
