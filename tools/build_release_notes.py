from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ValueError(f"Not a complete semantic version: {value}")
    return tuple(int(part) for part in match.groups())


def _published_notes(version: str) -> str:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(
        rf"^### {re.escape(version)}\s+—[^\n]*\n\n(?P<body>.*?)(?=^### |^## |\Z)",
        changelog,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"Published CHANGELOG section not found for {version}")
    return match.group("body").strip()


def _previous_tag(version: str) -> str | None:
    current = _version_tuple(version)
    output = subprocess.check_output(
        ["git", "tag", "--list"], cwd=ROOT, text=True, encoding="utf-8"
    )
    versions: list[tuple[tuple[int, int, int], str]] = []
    for line in output.splitlines():
        match = VERSION_RE.fullmatch(line.strip())
        if not match:
            continue
        value = tuple(int(part) for part in match.groups())
        if value < current:
            versions.append((value, f"v{'.'.join(str(part) for part in value)}"))
    return max(versions, default=(None, None))[1]


def build_release_notes(version: str) -> str:
    version = version.removeprefix("v")
    _version_tuple(version)
    tag = f"v{version}"
    previous = _previous_tag(version)
    lines = [_published_notes(version)]
    if previous:
        lines.extend(
            [
                "",
                f"**Full comparison:** https://github.com/kdnsna/pptlint/compare/{previous}...{tag}",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build release notes from a published CHANGELOG section.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    content = build_release_notes(args.version)
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
