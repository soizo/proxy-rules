from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class ConversionError(ValueError):
    pass


SUPPORTED_CLASSICAL_RULE_TYPES = {
    "DOMAIN",
    "DOMAIN-KEYWORD",
    "DOMAIN-SUFFIX",
    "IP-CIDR",
    "URL-REGEX",
    "USER-AGENT",
}

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
    if not expression.startswith(URL_REGEX_PREFIX) or not expression.endswith(URL_REGEX_SUFFIX):
        raise ConversionError(f"unsupported URL-REGEX expression: {expression}")
    host_regex = expression[len(URL_REGEX_PREFIX) : -len(URL_REGEX_SUFFIX)]
    if r"\/" in host_regex:
        raise ConversionError("path matching in URL-REGEX is unsupported")
    if not host_regex:
        raise ConversionError("unsupported URL-REGEX expression: empty host")
    return f"DOMAIN-REGEX,^{host_regex}$"


def convert_module(text: str, expected_policy: str) -> str:
    rules: list[str] = []
    in_rule_section = False
    saw_rule_section = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#!", "#")):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_rule_section = line == "[Rule]"
            saw_rule_section = saw_rule_section or in_rule_section
            continue
        if not in_rule_section:
            continue

        fields = next(csv.reader([line], skipinitialspace=True))
        if len(fields) < 3:
            raise ConversionError(f"unsupported rule line: {line}")

        rule_type = fields[0].strip()
        policy = fields[-1].strip()
        if policy != expected_policy:
            raise ConversionError(f"unexpected policy {policy!r}; expected {expected_policy}")

        if rule_type == "URL-REGEX":
            rules.append(convert_url_regex(fields[1].strip()))
            continue
        if rule_type not in SUPPORTED_CLASSICAL_RULE_TYPES:
            raise ConversionError(f"unsupported rule type: {rule_type}")

        rules.append(f"{rule_type},{','.join(field.strip() for field in fields[1:-1])}")

    if not saw_rule_section:
        raise ConversionError("missing [Rule] section")

    return "\n".join(rules) + ("\n" if rules else "")


def _download_text(url: str) -> str:
    if urlsplit(url).scheme != "https":
        raise ConversionError(f"unsupported download URL: {url}")
    try:
        with urlopen(Request(url), timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8")
    except Exception as exc:  # pragma: no cover - surfaced in CLI only
        raise ConversionError(f"download failed: {exc}") from exc


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


def main() -> int:
    for label, expected_policy, url, output_path in SOURCE_DEFINITIONS:
        try:
            module_text = _download_text(url)
            converted = convert_module(module_text, expected_policy)
            rule_count = 0 if not converted else len(converted.splitlines())
            changed = _write_text_if_changed(output_path, converted)
            state = "updated" if changed else "unchanged"
            print(f"{label}: {rule_count} rules ({state}) -> {output_path}")
        except ConversionError as exc:
            print(f"{label}: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
