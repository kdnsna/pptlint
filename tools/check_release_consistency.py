from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_section = project.split("[project]", 1)[1].split("\n[", 1)[0]
    project_match = re.search(r'^version\s*=\s*"([^"]+)"', project_section, re.MULTILINE)
    if project_match is None:
        raise SystemExit("pyproject.toml has no project version")
    version = project_match.group(1)
    module = (ROOT / "src" / "decklint" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', module)
    if match is None or match.group(1) != version:
        raise SystemExit("pyproject.toml and decklint.__version__ do not match")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## {version} —" not in changelog:
        raise SystemExit(f"CHANGELOG.md has no {version} release entry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
