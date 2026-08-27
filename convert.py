from __future__ import annotations

import csv
import http.client
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit


class ConversionError(ValueError):
    pass


SUPPORTED_CLASSICAL_RULE_TYPES = {
    "DOMAIN",
    "DOMAIN-KEYWORD",
    "DOMAIN-SUFFIX",
    "IP-CIDR",
    "URL-REGEX",
}

UNREPRESENTABLE_RULE_TYPES = {"USER-AGENT"}
FIXED_POLICIES = ("DIRECT", "PROXY", "REJECT")
FIXED_SOURCE_DIR = Path("fixed-rules")
FIXED_OUTPUT_DIR = Path("rules")
CLASH_VERGE_SCRIPT_PATH = Path("clash-verge-script.js")
FIXED_PROVIDER_START = "// BEGIN GENERATED FIXED PROVIDERS"
FIXED_PROVIDER_END = "// END GENERATED FIXED PROVIDERS"

URL_REGEX_PREFIX = r"^https?:\/\/"
URL_REGEX_SUFFIX = r".*$"
DOWNLOAD_TIMEOUT_SECONDS = 15
SOURCE_DEFINITIONS = (
    (
        "direct",
        "DIRECT",
        "https://raw.githubusercontent.com/GMOogway/shadowrocket-rules/refs/heads/master/sr_direct_list.module",
        Path("rules/direct.txt"),
    ),
    (
        "proxy",
        "PROXY",
        "https://raw.githubusercontent.com/GMOogway/shadowrocket-rules/refs/heads/master/sr_proxy_list.module",
        Path("rules/proxy.txt"),
    ),
    (
        "reject",
        "REJECT",
        "https://cdn.jsdelivr.net/gh/GMOogway/shadowrocket-rules@master/sr_reject_list.module",
        Path("rules/reject.txt"),
    ),
)


def convert_url_regex(expression: str) -> str:
    if not expression.startswith(URL_REGEX_PREFIX) or not expression.endswith(
        URL_REGEX_SUFFIX
    ):
        raise ConversionError(f"unsupported URL-REGEX expression: {expression}")
    host_regex = expression[len(URL_REGEX_PREFIX) : -len(URL_REGEX_SUFFIX)]
    if not host_regex:
        raise ConversionError("unsupported URL-REGEX expression: empty host")
    if "/" in host_regex:
        raise ConversionError("path matching in URL-REGEX is unsupported")
    if any(marker in host_regex for marker in (":", r"\?", r"\#")):
        raise ConversionError("non-canonical URL-REGEX expression")
    return f"DOMAIN-REGEX,^{host_regex}$"


def _convert_rule_line(
    line: str, expected_policy: str | None = None
) -> tuple[str, str | None]:
    fields = next(csv.reader([line], skipinitialspace=True))
    if len(fields) < 3:
        raise ConversionError(f"unsupported rule line: {line}")

    rule_type = fields[0].strip()
    policy = fields[-1].strip()
    if expected_policy is not None and policy != expected_policy:
        raise ConversionError(f"unexpected policy {policy!r}; expected {expected_policy}")
    if policy not in FIXED_POLICIES:
        raise ConversionError(f"unsupported policy: {policy!r}")

    if rule_type in UNREPRESENTABLE_RULE_TYPES:
        return policy, None
    if rule_type == "URL-REGEX":
        return policy, convert_url_regex(fields[1].strip())
    if rule_type not in SUPPORTED_CLASSICAL_RULE_TYPES:
        raise ConversionError(f"unsupported rule type: {rule_type}")

    return policy, f"{rule_type},{','.join(field.strip() for field in fields[1:-1])}"


def _iter_rule_lines(text: str, require_rule_section: bool) -> tuple[list[str], bool]:
    saw_rule_section = any(line.strip() == "[Rule]" for line in text.splitlines())
    in_rule_section = not saw_rule_section
    lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_rule_section = line == "[Rule]"
            continue
        if in_rule_section:
            lines.append(line)

    if require_rule_section and not saw_rule_section:
        raise ConversionError("missing [Rule] section")
    return lines, saw_rule_section


def _convert_module_with_stats(text: str, expected_policy: str) -> tuple[str, int]:
    rules: list[str] = []
    skipped_user_agent_rules = 0

    for line in _iter_rule_lines(text, require_rule_section=True)[0]:
        _, converted = _convert_rule_line(line, expected_policy)
        if converted is None:
            skipped_user_agent_rules += 1
        else:
            rules.append(converted)

    if not rules:
        raise ConversionError("zero rules converted")

    return "\n".join(rules) + "\n", skipped_user_agent_rules


def convert_fixed_rules(source_dir: Path) -> tuple[dict[str, list[str]], int]:
    rules_by_policy: dict[str, list[str]] = {policy: [] for policy in FIXED_POLICIES}
    seen_by_policy: dict[str, set[str]] = {policy: set() for policy in FIXED_POLICIES}
    skipped_user_agent_rules = 0
    paths = sorted(
        (
            path
            for path in source_dir.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and not any(part.startswith(".") for part in path.relative_to(source_dir).parts)
        ),
        key=lambda path: path.relative_to(source_dir).as_posix(),
    )

    for path in paths:
        for line in _iter_rule_lines(path.read_text(encoding="utf-8"), False)[0]:
            policy, converted = _convert_rule_line(line)
            if converted is None:
                skipped_user_agent_rules += 1
            elif converted not in seen_by_policy[policy]:
                seen_by_policy[policy].add(converted)
                rules_by_policy[policy].append(converted)

    return (
        {policy: rules for policy, rules in rules_by_policy.items() if rules},
        skipped_user_agent_rules,
    )


def convert_module(text: str, expected_policy: str) -> str:
    converted, _ = _convert_module_with_stats(text, expected_policy)
    return converted


def _download_text(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise ConversionError(f"unsupported download URL: {url}")
    connection = http.client.HTTPSConnection(
        parts.netloc, timeout=DOWNLOAD_TIMEOUT_SECONDS
    )
    try:
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        connection.request("GET", path, headers={"User-Agent": "proxy-rules"})
        response = connection.getresponse()
        if response.status != 200:
            raise ConversionError(f"download failed: HTTP {response.status}")
        return response.read().decode("utf-8")
    except Exception as exc:  # pragma: no cover - surfaced in CLI only
        if isinstance(exc, ConversionError):
            raise
        raise ConversionError(f"download failed: {exc}") from exc
    finally:
        connection.close()


def _write_text_if_changed(path: Path, text: str) -> bool:
    data = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return False

    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        with temp_path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return True


def write_fixed_rule_outputs(
    rules_by_policy: dict[str, list[str]], output_dir: Path
) -> dict[str, str]:
    states: dict[str, str] = {}
    for policy in FIXED_POLICIES:
        output_path = output_dir / f"fixed-{policy.lower()}.txt"
        rules = rules_by_policy.get(policy, [])
        if rules:
            changed = _write_text_if_changed(output_path, "\n".join(rules) + "\n")
            states[policy] = "updated" if changed else "unchanged"
        elif output_path.exists():
            output_path.unlink()
            states[policy] = "removed"
        else:
            states[policy] = "absent"
    return states


def update_fixed_providers_in_script(path: Path, policies: set[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    start = text.find(FIXED_PROVIDER_START)
    end = text.find(FIXED_PROVIDER_END)
    if start < 0 or end < start:
        raise ConversionError("fixed provider markers missing from Clash Verge script")

    entries = "\n".join(
        f'  "fixed-{policy.lower()}": "fixed-{policy.lower()}.txt",'
        for policy in FIXED_POLICIES
        if policy in policies
    )
    generated = f"{FIXED_PROVIDER_START}\nconst FIXED_PROVIDERS = {{\n{entries}\n}};\n"
    updated = text[:start] + generated + text[end:]
    return _write_text_if_changed(path, updated)


def main() -> int:
    try:
        fixed_rules, skipped_fixed_user_agent_rules = convert_fixed_rules(
            FIXED_SOURCE_DIR
        )
        fixed_states = write_fixed_rule_outputs(fixed_rules, FIXED_OUTPUT_DIR)
        script_changed = update_fixed_providers_in_script(
            CLASH_VERGE_SCRIPT_PATH, set(fixed_rules)
        )
        if skipped_fixed_user_agent_rules:
            print(
                "fixed: skipped "
                f"{skipped_fixed_user_agent_rules} USER-AGENT rules",
                file=sys.stderr,
            )
        for policy in FIXED_POLICIES:
            rule_count = len(fixed_rules.get(policy, []))
            print(
                f"fixed-{policy.lower()}: {rule_count} rules "
                f"({fixed_states[policy]})"
            )
        script_state = "updated" if script_changed else "unchanged"
        print(f"fixed providers: {script_state} -> {CLASH_VERGE_SCRIPT_PATH}")
    except (ConversionError, OSError, UnicodeError) as exc:
        print(f"fixed: {exc}", file=sys.stderr)
        return 1

    for label, expected_policy, url, output_path in SOURCE_DEFINITIONS:
        try:
            module_text = _download_text(url)
            converted, skipped_user_agent_rules = _convert_module_with_stats(
                module_text, expected_policy
            )
            if skipped_user_agent_rules:
                print(
                    f"{label}: skipped {skipped_user_agent_rules} USER-AGENT rules",
                    file=sys.stderr,
                )
            rule_count = len(converted.splitlines())
            changed = _write_text_if_changed(output_path, converted)
            state = "updated" if changed else "unchanged"
            print(f"{label}: {rule_count} rules ({state}) -> {output_path}")
        except ConversionError as exc:
            print(f"{label}: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
