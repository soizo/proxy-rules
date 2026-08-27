import unittest

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
            convert_url_regex(r'^https?:\/\/(.*\.)?example\.com.*$'),
            r'DOMAIN-REGEX,^(.*\.)?example\.com$',
        )

    def test_rejects_path_url_regex(self):
        with self.assertRaisesRegex(ConversionError, "path"):
            convert_url_regex(r'^https?:\/\/example\.com\/private.*$')

    def test_rejects_policy_mismatch(self):
        with self.assertRaisesRegex(ConversionError, "expected DIRECT"):
            convert_module("[Rule]\nDOMAIN,example.com,PROXY\n", "DIRECT")

    def test_rejects_unknown_rule_type(self):
        with self.assertRaisesRegex(ConversionError, "unsupported"):
            convert_module("[Rule]\nUNKNOWN,example.com,DIRECT\n", "DIRECT")

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

    def test_keeps_trailing_newline_deterministic(self):
        self.assertTrue(convert_module("[Rule]\nDOMAIN,example.com,DIRECT\n", "DIRECT").endswith("\n"))


if __name__ == "__main__":
    unittest.main()
