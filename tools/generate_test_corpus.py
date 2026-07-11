from __future__ import annotations

import json
from pathlib import Path

from tests.pptx_factory import slide_xml, write_pptx


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests/fixtures/corpus"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, str]] = []

    def add(name: str, label: str, expected_rule: str, **kwargs) -> None:
        filename = f"{name}.pptx"
        write_pptx(OUTPUT / filename, **kwargs)
        cases.append({"file": filename, "label": label, "expectedRule": expected_rule})

    for index, size in enumerate(range(1800, 2800, 100), 1):
        add(f"clean-{index:02d}", "clean native deck", "", slides=[slide_xml(body_size=size)])
    for index, size in enumerate((700, 800, 900, 1000, 1100), 1):
        add(
            f"small-font-{index:02d}",
            "explicit small text",
            "readability.small-font",
            slides=[slide_xml(body_size=size)],
        )
    for index in range(1, 6):
        add(
            f"flattened-{index:02d}",
            "full-slide raster",
            "editability.full-slide-image",
            include_picture=True,
            slides=[slide_xml(title=None, include_picture=True, picture_alt="")],
        )
    for index in range(1, 4):
        add(
            f"untitled-{index:02d}",
            "missing title placeholder",
            "accessibility.missing-title",
            slides=[slide_xml(title=None)],
        )
    for index, color in enumerate(("F8F8F8", "EEEEEE"), 1):
        add(
            f"low-contrast-{index:02d}",
            "explicit low contrast",
            "readability.low-contrast",
            slides=[slide_xml(body_fill="FFFFFF", body_text_color=color)],
        )
    add("privacy-01", "personal metadata", "privacy.personal-metadata", creator="Fixture Author")
    add("privacy-02", "comments", "privacy.comments", include_comments=True)
    add("hidden-01", "hidden slide", "privacy.hidden-slide", slides=[slide_xml(hidden=True)])
    add(
        "repeated-layout-01",
        "three repeated layouts",
        "consistency.repeated-layout",
        slides=[slide_xml(), slide_xml(), slide_xml()],
    )
    add(
        "off-canvas-01",
        "text outside canvas",
        "readability.off-canvas-text",
        slides=[slide_xml(body_x=11_500_000, body_w=2_000_000)],
    )
    (OUTPUT / "manifest.json").write_text(
        json.dumps({"schemaVersion": "decklint-fixture-corpus/v1", "cases": cases}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

