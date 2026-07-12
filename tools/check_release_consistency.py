from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(project["project"]["version"])
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
