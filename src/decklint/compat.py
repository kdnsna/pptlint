from __future__ import annotations

import sys

from .cli import main as pptlint_main


def main(argv: list[str] | None = None) -> int:
    print(
        "DeckLint is now PPTLint. The decklint command is deprecated; use `pptlint check` for all new workflows.",
        file=sys.stderr,
    )
    return pptlint_main(argv)
