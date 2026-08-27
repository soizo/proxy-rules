# proxy-rules

Daily-updated Mihomo rule providers converted from three Shadowrocket modules for Clash Verge Rev.

## What is converted

- `DIRECT`, proxy, and `REJECT` routing rules from the source modules.
- Supported Mihomo classical rules are preserved as text providers under `rules/`.
- Canonical host-only `URL-REGEX` entries are converted to `DOMAIN-REGEX`.

## What is intentionally unsupported

- Shadowrocket rewrite, MITM, and script sections.
- Non-`[Rule]` sections, unknown rule types, and policy mismatches.
- Path-aware `URL-REGEX` rules that cannot be represented as Mihomo routing rules.

## Local commands

```bash
python3 -m unittest -v
node test_clash_verge_script.js
python3 convert.py
git diff --check
```

## Generated raw URLs

- `https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/direct.txt`
- `https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/proxy.txt`
- `https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/reject.txt`

## Clash Verge Rev setup

Paste `clash-verge-script.js` into **Profiles → Global Extend Script**.
It loads the providers from the public repository `soizo/proxy-rules`.

## Automation

- Runs daily at **03:17 UTC**.
- Also runs manually through **workflow_dispatch** in GitHub Actions.
