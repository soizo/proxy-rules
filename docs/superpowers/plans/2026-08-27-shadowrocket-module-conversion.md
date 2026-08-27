# Shadowrocket Module Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert three public Shadowrocket routing modules into daily-updated Mihomo classical rule providers and provide a subscription-independent Clash Verge Rev global extension script.

**Architecture:** A dependency-free Python CLI parses and validates each module, converts host-only `URL-REGEX` entries to `DOMAIN-REGEX`, and writes deterministic text providers. GitHub Actions runs tests and conversion daily, committing changed providers; Clash Verge Rev loads them through HTTP rule providers configured by one global script.

**Tech Stack:** Python 3 standard library, `unittest`, JavaScript, GitHub Actions YAML

**Spec:** `docs/superpowers/specs/2026-08-27-shadowrocket-module-conversion-design.md`

## Global Constraints

- Use no third-party runtime or test dependencies.
- Accept only the `[Rule]` section and known Mihomo-compatible rule types.
- Convert only canonical host-only `URL-REGEX`; reject path-aware URL expressions.
- Fail on unknown types and policy mismatches.
- Run daily and by manual dispatch.
- Do not create, commit, push, or publish a GitHub repository without explicit user approval.

---

### Task 1: Converter parser and URL-regex conversion

**Files:**

- Create: `test_convert.py`
- Create: `convert.py`

**Interfaces:**

- Produces: `convert_module(text: str, expected_policy: str) -> str`
- Produces: `convert_url_regex(expression: str) -> str`
- Produces: `main() -> int`

- [ ] **Step 1: Write failing parser tests**

Create `test_convert.py` using `unittest`. Cover:

```python
from convert import ConversionError, convert_module, convert_url_regex


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
```

Also cover ignoring metadata/comments/non-rule sections, quoted regex commas, missing `[Rule]`, and deterministic trailing newline.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
cd /Users/soizoktantas/Local/Projects/Repo/proxy-rules
python3 -m unittest -v
```

Expected: import failure because `convert.py` does not exist.

- [ ] **Step 3: Implement the minimum converter**

Create `convert.py` with:

- `ConversionError(ValueError)`.
- A fixed set of accepted classical types observed in the sources and supported by Mihomo.
- CSV parsing via `csv.reader`, preserving commas inside quoted regexes.
- `[Rule]` section detection.
- Exact expected-policy validation.
- Canonical URL-regex extraction from `^https?:\/\/<host>.*$`, rejecting any `\/` remaining in `<host>`.
- `urllib.request.urlopen` download with a bounded timeout.
- Atomic output replacement using a temporary sibling file and `os.replace`, skipped when bytes are unchanged.
- Three fixed source definitions mapping to `rules/direct.txt`, `rules/proxy.txt`, and `rules/reject.txt`.

The CLI exits nonzero and prints a concise source-specific error when conversion fails.

- [ ] **Step 4: Run tests and verify GREEN**

```bash
python3 -m unittest -v
```

Expected: all tests pass with no warnings.

- [ ] **Step 5: Run live integration conversion**

```bash
python3 convert.py
```

Expected: three provider files are written and each reports its converted rule count.

Check invariants:

```bash
! grep -R -E '^#!|^\[|,(DIRECT|PROXY|REJECT)$' rules
find rules -type f -name '*.txt' -size +0
```

Expected: both commands exit 0.

### Task 2: Clash Verge Rev global extension

**Files:**

- Create: `clash-verge-script.js`
- Create: `test_clash_verge_script.js`

**Interfaces:**

- Produces: `main(config, profileName)` for Clash Verge Rev.
- Produces: `findProxyGroup(config)`.

- [ ] **Step 1: Write failing JavaScript self-check**

Create `test_clash_verge_script.js` using Node's built-in `assert` and `vm`. Load `clash-verge-script.js`, call `main`, and assert:

- Three HTTP providers use `behavior: "classical"`, `format: "text"`, and one-day intervals.
- Rules are prepended in direct, proxy, reject order.
- An existing `节点选择` group is selected for proxy rules.
- Existing subscription rules remain after the three provider rules.
- Missing `rules` and `rule-providers` are handled.

- [ ] **Step 2: Run self-check and verify RED**

```bash
node test_clash_verge_script.js
```

Expected: failure because `clash-verge-script.js` does not exist.

- [ ] **Step 3: Implement the minimum global script**

Create `clash-verge-script.js` with fixed raw GitHub URLs rooted at `https://raw.githubusercontent.com/soizo/proxy-rules/main/rules/`. Preserve the approved proxy-group selection order:

```javascript
["Proxy", "PROXY", "proxy", "节点选择", "🚀 节点选择"]
```

Register providers named `module-direct`, `module-proxy`, and `module-reject`, then prepend:

```javascript
RULE-SET,module-direct,DIRECT
RULE-SET,module-proxy,<selected group>
RULE-SET,module-reject,REJECT
```

- [ ] **Step 4: Run self-check and verify GREEN**

```bash
node test_clash_verge_script.js
```

Expected: prints a single success line and exits 0.

### Task 3: Daily automation and operator documentation

**Files:**

- Create: `.github/workflows/update-rules.yml`
- Create: `README.md`
- Create: `.gitignore`

**Interfaces:**

- Consumes: `python3 convert.py`, `python3 -m unittest -v`, generated `rules/*.txt`.
- Produces: daily UTC workflow and setup instructions.

- [ ] **Step 1: Add the daily workflow**

Configure:

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "17 3 * * *"
```

Grant only `contents: write`, use `actions/checkout`, `actions/setup-python`, run tests before conversion, and commit only `rules/` when changed. Use the repository-provided GitHub Actions bot identity.

- [ ] **Step 2: Add concise documentation**

Document:

- What is converted and what is intentionally unsupported.
- Local test and conversion commands.
- The three generated raw URLs.
- The expected public repository name `soizo/proxy-rules` used by `clash-verge-script.js`.
- Where to paste the script in Clash Verge Rev: Profiles → Global Extend Script.
- Daily update time and manual workflow trigger.

Add a minimal `.gitignore` for `__pycache__/` and `*.pyc`.

- [ ] **Step 3: Run complete verification**

```bash
python3 -m unittest -v
node test_clash_verge_script.js
python3 convert.py
! grep -R -E '^#!|^\[|,(DIRECT|PROXY|REJECT)$' rules
python3 - <<'PY'
from pathlib import Path
for path in sorted(Path('rules').glob('*.txt')):
    data = path.read_text()
    assert data and data.endswith('\n'), path
    print(path, len(data.splitlines()))
PY
git diff --check
```

Expected: all tests and invariants pass; generated rule counts are nonzero; `git diff --check` reports nothing.

- [ ] **Step 4: Review diagnostics and repository state**

Run `lens_diagnostics` with `mode=all`, inspect `git status --short`, and verify that no credentials, caches, or unrelated files are present.

- [ ] **Step 5: Stop before remote side effects**

Report local verification evidence and ask for explicit authorization to create the public `soizo/proxy-rules` GitHub repository, commit, and push.
