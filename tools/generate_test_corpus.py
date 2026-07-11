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

    for index, size in enumerate(range(1800, 3800, 100), 1):
        add(f"clean-{index:02d}", "clean native deck", "", slides=[slide_xml(body_size=size)])
    for index, size in enumerate(range(400, 1400, 100), 1):
        add(
            f"small-font-{index:02d}",
            "explicit small text",
            "readability.small-font",
            slides=[slide_xml(body_size=size)],
        )
    for index in range(1, 11):
        add(
            f"flattened-{index:02d}",
            "full-slide raster",
            "editability.full-slide-image",
            include_picture=True,
            slides=[slide_xml(title=None, include_picture=True, picture_alt="")],
        )
    for index in range(1, 6):
        add(
            f"untitled-{index:02d}",
            "missing title placeholder",
            "accessibility.missing-title",
            slides=[slide_xml(title=None)],
        )
    for index, color in enumerate(("F8F8F8", "F4F4F4", "EEEEEE", "E8E8E8", "E0E0E0"), 1):
        add(
            f"low-contrast-{index:02d}",
            "explicit low contrast",
            "readability.low-contrast",
            slides=[slide_xml(body_fill="FFFFFF", body_text_color=color)],
        )
    for index in range(1, 6):
        add(
            f"privacy-{index:02d}",
            "personal metadata",
            "privacy.personal-metadata",
            creator=f"Fixture Author {index}",
        )
        add(f"comments-{index:02d}", "comments", "privacy.comments", include_comments=True)
        add(
            f"hidden-{index:02d}",
            "hidden slide",
            "privacy.hidden-slide",
            slides=[slide_xml(hidden=True, body_size=1700 + index * 100)],
        )
        add(
            f"repeated-layout-{index:02d}",
            "three repeated layouts",
            "consistency.repeated-layout",
            slides=[slide_xml(body_size=1700 + index * 100)] * 3,
        )
        add(
            f"off-canvas-{index:02d}",
            "text outside canvas",
            "readability.off-canvas-text",
            slides=[slide_xml(body_x=11_300_000 + index * 40_000, body_w=2_000_000)],
        )
        add(
            f"missing-content-type-{index:02d}",
            "media content type missing",
            "integrity.missing-content-type",
            include_picture=True,
            omit_picture_content_type=True,
        )
        add(
            f"blank-{index:02d}",
            "blank slide",
            "readability.blank-slide",
            slides=[slide_xml(title=None, body_text=None)],
        )
        add(
            f"overlap-{index:02d}",
            "substantial text overlap",
            "readability.text-overlap",
            slides=[slide_xml(second_body=True, body_size=1700 + index * 100)],
        )
        add(
            f"clipping-{index:02d}",
            "explicit text clipping risk",
            "readability.text-clipping-risk",
            slides=[
                slide_xml(
                    body_overflow="clip",
                    body_text="A" * (650 + index * 10),
                    body_w=1_000_000,
                    body_h=300_000,
                )
            ],
        )
        add(
            f"aspect-{index:02d}",
            "unusual slide aspect ratio",
            "readability.unusual-aspect-ratio",
            slide_width=str(17_000_000 + index * 500_000),
            slide_height="6858000",
        )
    (OUTPUT / "manifest.json").write_text(
        json.dumps({"schemaVersion": "decklint-fixture-corpus/v1", "cases": cases}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
