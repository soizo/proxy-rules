# proxy-rules

Mihomo rule providers converted from three upstream Shadowrocket modules and personal rules under `fixed-rules/` for Clash Verge Rev.

## What is converted

- `DIRECT`, `PROXY`, and `REJECT` routing rules from the upstream modules.
- Personal `.module` files and plain Shadowrocket rule files found recursively under `fixed-rules/`; files may mix policies.
- Supported Mihomo classical rules are preserved as text providers under `rules/`.
- Canonical host-only `URL-REGEX` entries are converted to `DOMAIN-REGEX`.
- Duplicate personal rules are removed while preserving deterministic file and rule order.

## What is intentionally unsupported

- Shadowrocket rewrite, MITM, and script sections.
- Non-`[Rule]` sections, unknown rule types, and policy mismatches.
- Shadowrocket `USER-AGENT` rules are omitted with a deterministic CLI warning because Mihomo classical providers cannot represent them.
- Path-aware `URL-REGEX` rules that cannot be represented as Mihomo routing rules.

## Local commands

```bash
python3 -m unittest -v
node test_clash_verge_script.js
python3 convert.py
git diff --check
```

## Personal fixed rules

Add non-hidden files anywhere under `fixed-rules/`. Files containing `[Rule]` use only that section; files without it are read as plain rule lists. Generated personal providers are loaded before the upstream modules in this order: `fixed-direct`, `fixed-proxy`, `fixed-reject`.

Only policies with at least one rule produce a provider file. Current generated URLs are:

- `https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/fixed-direct.txt`
- `https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/fixed-proxy.txt`

## Upstream generated URLs

- `https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/direct.txt`
- `https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/proxy.txt`
- `https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/reject.txt`

## Clash Verge Rev setup

Paste `clash-verge-script.js` into **Profiles → Global Extend Script**.
It loads the providers from the public repository `soizo/proxy-rules`.

## Automation

- Runs daily at **03:17 UTC**.
- Runs after changes to `fixed-rules/**` or `convert.py` reach `main`.
- Also runs manually through **workflow_dispatch** in GitHub Actions.
