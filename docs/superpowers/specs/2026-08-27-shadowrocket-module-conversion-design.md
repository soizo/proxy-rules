# Shadowrocket Module Conversion Design

## Goal

Maintain three independent Shadowrocket rule modules as automatically updated, public Mihomo rule providers for Clash Verge Rev.

## Inputs

| Policy | Source |
| --- | --- |
| `DIRECT` | `https://raw.githubusercontent.com/GMOogway/shadowrocket-rules/refs/heads/master/sr_direct_list.module` |
| Proxy group | `https://raw.githubusercontent.com/GMOogway/shadowrocket-rules/refs/heads/master/sr_proxy_list.module` |
| `REJECT` | `https://cdn.jsdelivr.net/gh/GMOogway/shadowrocket-rules@master/sr_reject_list.module` |

## Architecture

A dependency-free Python converter downloads each module, reads only its `[Rule]` section, validates the expected policy, and writes Mihomo `classical` text providers under `rules/`. A scheduled GitHub Actions workflow runs once daily and on manual dispatch, then commits changed generated files to `main`.

Clash Verge Rev uses one Global Extend Script. The script registers the three generated files as HTTP rule providers and prepends their `RULE-SET` entries to every selected subscription, keeping these rules independent of subscription updates.

## Conversion Rules

- Ignore module metadata, blank lines, comments, and non-rule sections.
- Strip the final `DIRECT`, `PROXY`, or `REJECT` policy from supported rules because the enclosing `RULE-SET` supplies the policy.
- Preserve Mihomo-compatible classical rule types and their operands.
- Convert canonical host-only Shadowrocket rules of the form `URL-REGEX,"^https?:\\/\\/<host-regex>.*$",POLICY` to `DOMAIN-REGEX,^<host-regex>$`.
- Reject URL regexes containing path matching because they cannot be represented by Mihomo routing rules.
- Fail on unknown rule types or a rule whose policy differs from the module's expected policy.
- Write deterministic UTF-8 output with one rule per line and a trailing newline.
- Do not rewrite generated files when their content is unchanged.

## Generated Providers and Priority

Rules are prepended in this order:

1. Direct provider → `DIRECT`
2. Proxy provider → selected proxy group
3. Reject provider → `REJECT`
4. Existing subscription rules

The proxy target is selected from common names (`Proxy`, `PROXY`, `proxy`, `节点选择`, `🚀 节点选择`), then the first `select` group, then the first available group, with `GLOBAL` as the last fallback.

## Repository Layout

```text
proxy-rules/
├── .github/workflows/update-rules.yml
├── docs/superpowers/specs/2026-08-27-shadowrocket-module-conversion-design.md
├── rules/
│   ├── direct.txt
│   ├── proxy.txt
│   └── reject.txt
├── clash-verge-script.js
├── convert.py
├── test_convert.py
└── README.md
```

## Automation

The workflow:

1. Checks out `main`.
2. Runs the standard-library test suite.
3. Runs the converter against the three upstream URLs.
4. Commits and pushes only when `rules/` changed.

The repository must be public so Clash Verge Rev can fetch raw provider URLs without credentials. Repository creation and pushing require separate explicit approval.

## Verification

- Unit tests cover section parsing, policy stripping, URL-to-domain regex conversion, rejection of path URL regexes, policy mismatch, and unknown rule types.
- A local integration run downloads all three live modules and generates all providers.
- Generated output contains no module headers, section names, or policy suffixes.
- The resulting JavaScript is syntax-checked with Node when available.
- The workflow YAML and documented raw URLs are reviewed against the final GitHub owner/repository name before publishing.

## Deliberate Omissions

- No web service, package dependency, database, release pipeline, or GitHub Pages deployment.
- No support for Shadowrocket rewrite, MITM, or script sections; the selected sources are used only as routing-rule inputs.
- No private-repository authentication flow.
