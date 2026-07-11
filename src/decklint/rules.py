from __future__ import annotations

from collections import Counter

from .model import DeckModel, Shape, Slide
from .schema import Finding


PORTABLE_FONTS = {
    "aptos",
    "arial",
    "calibri",
    "courier new",
    "georgia",
    "microsoft yahei",
    "noto sans",
    "noto serif",
    "pingfang sc",
    "simsun",
    "simhei",
    "tahoma",
    "times new roman",
    "trebuchet ms",
    "verdana",
}


def _finding(
    rule_id: str,
    category: str,
    severity: str,
    confidence: str,
    message: str,
    evidence: str,
    remediation: str,
    *,
    slide: Slide | None = None,
    shape: Shape | None = None,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        message=message,
        evidence=evidence,
        remediation=remediation,
        slide_index=slide.index if slide else None,
        shape_id=shape.shape_id if shape else None,
        bbox=shape.bbox if shape else None,
    )


def _relative_luminance(hex_color: str) -> float:
    rgb = [int(hex_color[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _layout_fingerprint(slide: Slide, width: int, height: int) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            shape.kind,
            round(shape.bbox.x / width, 1),
            round(shape.bbox.y / height, 1),
            round(shape.bbox.w / width, 1),
            round(shape.bbox.h / height, 1),
            bool(shape.text),
        )
        for shape in slide.shapes
    )


def _semantic_title_shape(slide: Slide, width: int, height: int) -> Shape | None:
    candidates = [
        shape
        for shape in slide.shapes
        if shape.text.strip()
        and len(shape.text.strip()) <= 160
        and shape.bbox.y < height * 0.25
        and shape.bbox.w >= width * 0.20
        and shape.font_sizes
        and max(shape.font_sizes) >= 24
    ]
    return min(
        candidates,
        key=lambda shape: (shape.bbox.y, shape.bbox.x, shape.shape_id),
        default=None,
    )


def _overlap_ratio(first: Shape, second: Shape) -> float:
    left = max(first.bbox.x, second.bbox.x)
    top = max(first.bbox.y, second.bbox.y)
    right = min(first.bbox.x + first.bbox.w, second.bbox.x + second.bbox.w)
    bottom = min(first.bbox.y + first.bbox.h, second.bbox.y + second.bbox.h)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    smaller = min(first.bbox.w * first.bbox.h, second.bbox.w * second.bbox.h)
    return intersection / max(1, smaller)


def audit_deck(deck: DeckModel, *, profile: str = "baseline") -> list[Finding]:
    if profile not in {"baseline", "ai-generated"}:
        raise ValueError(f"Unsupported profile: {profile}")
    findings: list[Finding] = []

    if not deck.slides:
        findings.append(
            _finding(
                "integrity.empty-deck",
                "integrity",
                "critical",
                "high",
                "The presentation contains no slides.",
                "ppt/presentation.xml has an empty slide list",
                "Restore at least one valid slide before delivery.",
            )
        )
    for part_name in deck.orphan_slide_parts:
        findings.append(
            _finding(
                "integrity.orphan-slide-part",
                "integrity",
                "medium",
                "high",
                "The package contains a slide part that is not referenced by the presentation slide list.",
                part_name,
                "Remove the orphan part or restore its presentation relationship.",
            )
        )
    for relationship in deck.broken_relationships:
        findings.append(
            _finding(
                "integrity.broken-relationship",
                "integrity",
                "critical",
                "high",
                "A PPTX relationship points to a missing package part.",
                f"{relationship.source}#{relationship.relationship_id} -> {relationship.target}",
                "Restore the missing media or remove the dangling relationship.",
            )
        )
    for part_name in deck.missing_content_types:
        findings.append(
            _finding(
                "integrity.missing-content-type",
                "integrity",
                "critical",
                "high",
                "A package part has no declared OOXML content type.",
                part_name,
                "Declare the part in [Content_Types].xml or recreate the affected media in PowerPoint.",
            )
        )

    aspect_ratio = max(deck.width, deck.height) / min(deck.width, deck.height)
    if aspect_ratio > 2.0 or aspect_ratio < 1.25:
        findings.append(
            _finding(
                "readability.unusual-aspect-ratio",
                "readability",
                "medium",
                "low",
                "The slide aspect ratio is unusual for a projected presentation.",
                f"canvas={deck.width}x{deck.height}; ratio={aspect_ratio:.3f}",
                "Confirm the intended output device and page size before delivery.",
            )
        )

    small_high = 14 if profile == "ai-generated" else 12
    small_medium = 18 if profile == "ai-generated" else 14
    for slide in deck.slides:
        if not any(
            shape.text.strip() or shape.kind in {"picture", "graphic-frame"} for shape in slide.shapes
        ):
            findings.append(
                _finding(
                    "readability.blank-slide",
                    "readability",
                    "medium",
                    "high",
                    "The slide has no audience-visible content.",
                    f"Slide {slide.index} contains no text, picture, table, or chart object",
                    "Remove the slide or restore the missing audience-visible content.",
                    slide=slide,
                )
            )
        title_shapes = [
            shape for shape in slide.shapes if shape.placeholder_type in {"title", "ctrTitle"} and shape.text
        ]
        semantic_title = (
            _semantic_title_shape(slide, deck.width, deck.height)
            if profile == "ai-generated" and not title_shapes
            else None
        )
        if title_shapes:
            slide.title_source = "placeholder"
        elif semantic_title is not None:
            slide.title = semantic_title.text
            slide.title_source = "inferred"
        else:
            slide.title_source = "none"
            findings.append(
                _finding(
                    "accessibility.missing-title",
                    "accessibility",
                    "medium",
                    "high",
                    "The slide has no populated title placeholder.",
                    f"Slide {slide.index} has no title or centered-title placeholder text",
                    "Add a unique slide title using the title placeholder.",
                    slide=slide,
                )
            )
        for shape in slide.shapes:
            if shape.text:
                minimum_size = min(shape.font_sizes) if shape.font_sizes else None
                if minimum_size is not None and minimum_size < small_medium:
                    severity = "high" if minimum_size < small_high else "medium"
                    findings.append(
                        _finding(
                            "readability.small-font",
                            "readability",
                            severity,
                            "high",
                            f"Text uses {minimum_size:g} pt type, below the {small_medium} pt profile threshold.",
                            f"{shape.name}: minimum explicit font size {minimum_size:g} pt",
                            "Increase the font size or split dense content across slides.",
                            slide=slide,
                            shape=shape,
                        )
                    )
                right = shape.bbox.x + shape.bbox.w
                bottom = shape.bbox.y + shape.bbox.h
                if shape.bbox.x < 0 or shape.bbox.y < 0 or right > deck.width or bottom > deck.height:
                    findings.append(
                        _finding(
                            "readability.off-canvas-text",
                            "readability",
                            "high",
                            "high",
                            "A text box extends beyond the slide canvas.",
                            f"bbox={shape.bbox}; canvas={deck.width}x{deck.height}",
                            "Move or resize the text box so it remains inside the slide bounds.",
                            slide=slide,
                            shape=shape,
                        )
                    )
                if shape.fill_color and shape.text_colors:
                    ratio = min(_contrast_ratio(shape.fill_color, color) for color in shape.text_colors)
                    if ratio < 3.0:
                        findings.append(
                            _finding(
                                "readability.low-contrast",
                                "readability",
                                "high",
                                "high",
                                f"Explicit text and fill colors have a contrast ratio of {ratio:.2f}:1.",
                                f"text={shape.text_colors}; fill={shape.fill_color}",
                                "Use text and background colors with at least 3:1 contrast for large type.",
                                slide=slide,
                                shape=shape,
                            )
                        )
                character_count = len(shape.text.replace(" ", ""))
                if character_count > 600:
                    findings.append(
                        _finding(
                            "readability.dense-text",
                            "readability",
                            "medium",
                            "low",
                            "A text box may be too dense for presentation viewing.",
                            f"{shape.name} contains {character_count} non-space characters",
                            "Move detail to speaker notes or split the content.",
                            slide=slide,
                            shape=shape,
                        )
                    )
                if (
                    shape.text_vertical_overflow == "clip"
                    and character_count > 120
                    and (shape.bbox.w * shape.bbox.h) < deck.width * deck.height * 0.12
                ):
                    findings.append(
                        _finding(
                            "readability.text-clipping-risk",
                            "readability",
                            "high",
                            "low",
                            "A dense text box explicitly clips vertical overflow.",
                            f"{shape.name}: vertOverflow=clip; characters={character_count}",
                            "Open the slide in PowerPoint, inspect the final line, and resize or split the text box.",
                            slide=slide,
                            shape=shape,
                        )
                    )
            if shape.kind == "picture" and not shape.alt_text.strip():
                findings.append(
                    _finding(
                        "accessibility.missing-alt-text",
                        "accessibility",
                        "medium",
                        "high",
                        "An image has no alternative text.",
                        f"{shape.name} has an empty descr/title attribute",
                        "Add concise alt text or mark the image as decorative in PowerPoint.",
                        slide=slide,
                        shape=shape,
                    )
                )

        pictures = [shape for shape in slide.shapes if shape.kind == "picture"]
        text_shapes = [shape for shape in slide.shapes if shape.text]
        for picture in pictures:
            coverage = (picture.bbox.w * picture.bbox.h) / max(1, deck.width * deck.height)
            if coverage >= 0.9 and len(text_shapes) <= 2:
                findings.append(
                    _finding(
                        "editability.full-slide-image",
                        "editability",
                        "high" if profile == "ai-generated" else "medium",
                        "high",
                        "The slide is dominated by a full-canvas image and has little native text.",
                        f"image coverage={coverage:.1%}; native text boxes={len(text_shapes)}",
                        "Keep body text, charts, and key labels as native PowerPoint objects.",
                        slide=slide,
                        shape=picture,
                    )
                )
                break

        text_shapes = [
            shape for shape in slide.shapes if shape.text.strip() and shape.bbox.w > 0 and shape.bbox.h > 0
        ]
        for first_index, first in enumerate(text_shapes):
            for second in text_shapes[first_index + 1 :]:
                if first.placeholder_type in {"title", "ctrTitle"} or second.placeholder_type in {
                    "title",
                    "ctrTitle",
                }:
                    continue
                first_area = first.bbox.w * first.bbox.h
                second_area = second.bbox.w * second.bbox.h
                if max(first_area, second_area) > min(first_area, second_area) * 4:
                    continue
                ratio = _overlap_ratio(first, second)
                if ratio >= 0.25:
                    findings.append(
                        _finding(
                            "readability.text-overlap",
                            "readability",
                            "high",
                            "low",
                            "Two native text boxes substantially overlap.",
                            f"{first.name} overlaps {second.name}; smaller-box overlap={ratio:.1%}",
                            "Separate or resize the text boxes, then inspect the slide at presentation size.",
                            slide=slide,
                            shape=second,
                        )
                    )

        visual_order = [
            shape.shape_id for shape in sorted(slide.shapes, key=lambda item: (item.bbox.y, item.bbox.x))
        ]
        z_order = [shape.shape_id for shape in slide.shapes]
        if len(z_order) >= 4 and visual_order != z_order:
            findings.append(
                _finding(
                    "accessibility.reading-order-risk",
                    "accessibility",
                    "medium",
                    "low",
                    "Shape order differs from the top-to-bottom visual order.",
                    f"visual={visual_order}; z-order={z_order}",
                    "Review the Selection Pane reading order for screen readers.",
                    slide=slide,
                )
            )
        if slide.hidden:
            findings.append(
                _finding(
                    "privacy.hidden-slide",
                    "privacy",
                    "low",
                    "high",
                    "The file contains a hidden slide.",
                    f"Slide {slide.index} has show=0",
                    "Confirm that hidden content is safe to share or remove it.",
                    slide=slide,
                )
            )
        if slide.notes_text:
            findings.append(
                _finding(
                    "privacy.speaker-notes",
                    "privacy",
                    "medium",
                    "high",
                    "The slide contains speaker notes.",
                    f"Slide {slide.index} contains {len(slide.notes_text)} note characters",
                    "Review speaker notes and remove information that should not be shared.",
                    slide=slide,
                )
            )

    font_counts = Counter(
        font for slide in deck.slides for shape in slide.shapes for font in shape.font_families
    )
    for font in sorted(font_counts):
        if font.casefold() not in PORTABLE_FONTS:
            findings.append(
                _finding(
                    "readability.font-portability-risk",
                    "readability",
                    "medium",
                    "low",
                    "A font may be substituted on another computer.",
                    f"font={font}; explicit declarations={font_counts[font]}",
                    "Confirm the font on the delivery computer, embed it when licensing permits, or use an approved portable font.",
                )
            )
    if len(font_counts) >= 3:
        total = sum(font_counts.values())
        for font, count in sorted(font_counts.items()):
            if count / total < 0.1:
                findings.append(
                    _finding(
                        "consistency.font-outlier",
                        "consistency",
                        "medium",
                        "low",
                        "A rarely used font may be an accidental style drift.",
                        f"{font}: {count}/{total} explicit font declarations",
                        "Confirm the font is intentional or replace it with the deck type system.",
                    )
                )

    if len(deck.slides) >= 3:
        fingerprints = [_layout_fingerprint(slide, deck.width, deck.height) for slide in deck.slides]
        for index in range(2, len(fingerprints)):
            if fingerprints[index] == fingerprints[index - 1] == fingerprints[index - 2]:
                findings.append(
                    _finding(
                        "consistency.repeated-layout",
                        "consistency",
                        "high",
                        "low",
                        "Three consecutive slides share the same structural layout fingerprint.",
                        f"slides {index - 1}, {index}, {index + 1}",
                        "Confirm the repetition is deliberate or vary the page role and dominant visual.",
                        slide=deck.slides[index],
                    )
                )
                break

    if deck.metadata:
        findings.append(
            _finding(
                "privacy.personal-metadata",
                "privacy",
                "medium",
                "high",
                "The PPTX contains author or last-editor metadata.",
                "; ".join(f"{key}={value}" for key, value in sorted(deck.metadata.items())),
                "Remove personal document properties before external delivery.",
            )
        )
    if deck.comments_count:
        findings.append(
            _finding(
                "privacy.comments",
                "privacy",
                "medium",
                "high",
                "The PPTX contains comments.",
                f"comment parts={deck.comments_count}",
                "Review and remove comments that should not leave the organization.",
            )
        )
    for target in deck.external_relationships:
        findings.append(
            _finding(
                "privacy.external-relationship",
                "privacy",
                "high",
                "high",
                "The PPTX contains an external relationship.",
                target,
                "Confirm the external URL or file reference is safe and intentional.",
            )
        )
    return sorted(findings, key=lambda item: (item.slide_index or 0, item.rule_id, item.shape_id or ""))
