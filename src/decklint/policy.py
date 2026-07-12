from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from .model import DeckModel
from .schema import Finding


MAX_POLICY_BYTES = 1024 * 1024


@dataclass(frozen=True)
class DeliveryPolicy:
    name: str
    allowed_fonts: frozenset[str]
    allowed_colors: frozenset[str]
    minimum_font_size: float | None
    forbid_external_links: bool
    forbid_notes: bool
    forbid_hidden_slides: bool
    require_alt_text: bool
    exceptions: tuple["PolicyException", ...]


@dataclass(frozen=True)
class PolicyException:
    rule_id: str
    slides: frozenset[int]
    reason: str
    expires: date | None


def _string_set(value: object, field: str) -> frozenset[str]:
    if value is None:
        return frozenset()
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"Policy field {field} must be a list of non-empty strings")
    return frozenset(item.strip().casefold() for item in value)


def load_policy(path: Path) -> DeliveryPolicy:
    path = Path(path).expanduser()
    if not path.is_file():
        raise ValueError(f"Policy file not found: {path}")
    if path.stat().st_size > MAX_POLICY_BYTES:
        raise ValueError("Policy file exceeds the 1 MiB safety limit")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Policy root must be a mapping")
    unknown = set(payload) - {
        "version",
        "name",
        "allowedFonts",
        "allowedColors",
        "minimumFontSize",
        "forbidExternalLinks",
        "forbidNotes",
        "forbidHiddenSlides",
        "requireAltText",
        "exceptions",
    }
    if unknown:
        raise ValueError(f"Unsupported policy fields: {', '.join(sorted(unknown))}")
    if payload.get("version", 1) != 1:
        raise ValueError("Policy version must be 1")
    minimum = payload.get("minimumFontSize")
    if minimum is not None and (not isinstance(minimum, (int, float)) or not 6 <= minimum <= 72):
        raise ValueError("minimumFontSize must be between 6 and 72")
    raw_exceptions = payload.get("exceptions", [])
    if not isinstance(raw_exceptions, list):
        raise ValueError("Policy field exceptions must be a list")
    exceptions: list[PolicyException] = []
    for index, item in enumerate(raw_exceptions, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Policy exception {index} must be a mapping")
        unknown_exception = set(item) - {"ruleId", "slides", "reason", "expires"}
        if unknown_exception:
            raise ValueError(
                f"Unsupported exception fields: {', '.join(sorted(unknown_exception))}"
            )
        rule_id = item.get("ruleId")
        reason = item.get("reason")
        slides = item.get("slides", [])
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ValueError(f"Policy exception {index} requires ruleId")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"Policy exception {index} requires a reason")
        if not isinstance(slides, list) or not all(
            isinstance(value, int) and value >= 1 for value in slides
        ):
            raise ValueError(f"Policy exception {index} slides must be positive integers")
        expires_value = item.get("expires")
        try:
            expires = date.fromisoformat(str(expires_value)) if expires_value else None
        except ValueError as exc:
            raise ValueError(f"Policy exception {index} expires must be YYYY-MM-DD") from exc
        exceptions.append(
            PolicyException(rule_id.strip(), frozenset(slides), reason.strip(), expires)
        )
    return DeliveryPolicy(
        name=str(payload.get("name") or path.stem),
        allowed_fonts=_string_set(payload.get("allowedFonts"), "allowedFonts"),
        allowed_colors=frozenset(
            value.removeprefix("#").upper()
            for value in _string_set(payload.get("allowedColors"), "allowedColors")
        ),
        minimum_font_size=float(minimum) if minimum is not None else None,
        forbid_external_links=bool(payload.get("forbidExternalLinks", False)),
        forbid_notes=bool(payload.get("forbidNotes", False)),
        forbid_hidden_slides=bool(payload.get("forbidHiddenSlides", False)),
        require_alt_text=bool(payload.get("requireAltText", False)),
        exceptions=tuple(exceptions),
    )


def apply_exceptions(
    findings: list[Finding], policy: DeliveryPolicy, *, today: date | None = None
) -> tuple[list[Finding], list[dict[str, object]]]:
    current = today or date.today()
    remaining: list[Finding] = []
    counts = [0 for _ in policy.exceptions]
    for finding in findings:
        matched = False
        for index, exception in enumerate(policy.exceptions):
            if exception.expires is not None and exception.expires < current:
                continue
            if finding.rule_id != exception.rule_id:
                continue
            if exception.slides and finding.slide_index not in exception.slides:
                continue
            counts[index] += 1
            matched = True
            break
        if not matched:
            remaining.append(finding)
    records = [
        {
            "ruleId": exception.rule_id,
            "slides": sorted(exception.slides),
            "reason": exception.reason,
            "expires": exception.expires.isoformat() if exception.expires else "",
            "matchedCount": counts[index],
            "active": exception.expires is None or exception.expires >= current,
        }
        for index, exception in enumerate(policy.exceptions)
    ]
    return remaining, records


def apply_policy(deck: DeckModel, policy: DeliveryPolicy) -> list[Finding]:
    findings: list[Finding] = []
    for slide in deck.slides:
        if policy.forbid_notes and slide.notes_text:
            findings.append(
                Finding(
                    "policy.notes-forbidden",
                    "privacy",
                    "high",
                    "high",
                    "The delivery policy does not allow speaker notes.",
                    f"Slide {slide.index} contains notes; policy={policy.name}",
                    "Remove notes from the delivery copy or change the approved policy.",
                    slide_index=slide.index,
                )
            )
        if policy.forbid_hidden_slides and slide.hidden:
            findings.append(
                Finding(
                    "policy.hidden-slide-forbidden",
                    "privacy",
                    "high",
                    "high",
                    "The delivery policy does not allow hidden slides.",
                    f"Slide {slide.index} is hidden; policy={policy.name}",
                    "Remove the hidden slide from the delivery copy or make it visible and approved.",
                    slide_index=slide.index,
                )
            )
        for shape in slide.shapes:
            for font in shape.font_families:
                if policy.allowed_fonts and font.casefold() not in policy.allowed_fonts:
                    findings.append(
                        Finding(
                            "policy.font-not-allowed",
                            "consistency",
                            "medium",
                            "high",
                            "A font is outside the approved delivery policy.",
                            f"font={font}; policy={policy.name}",
                            "Replace the font with one listed in the approved policy.",
                            slide_index=slide.index,
                            shape_id=shape.shape_id,
                            bbox=shape.bbox,
                        )
                    )
            if (
                policy.minimum_font_size is not None
                and shape.font_sizes
                and min(shape.font_sizes) < policy.minimum_font_size
            ):
                findings.append(
                    Finding(
                        "policy.font-size-below-minimum",
                        "readability",
                        "high",
                        "high",
                        "Text is smaller than the approved delivery policy.",
                        f"minimum={min(shape.font_sizes):g} pt; policy minimum={policy.minimum_font_size:g} pt",
                        "Increase the text size or approve a documented exception.",
                        slide_index=slide.index,
                        shape_id=shape.shape_id,
                        bbox=shape.bbox,
                    )
                )
            colors = [value for value in [shape.fill_color, *shape.text_colors] if value]
            for color in colors:
                if policy.allowed_colors and color.upper() not in policy.allowed_colors:
                    findings.append(
                        Finding(
                            "policy.color-not-allowed",
                            "consistency",
                            "medium",
                            "high",
                            "A color is outside the approved delivery policy.",
                            f"color=#{color}; policy={policy.name}",
                            "Replace the color with an approved brand color or document the exception.",
                            slide_index=slide.index,
                            shape_id=shape.shape_id,
                            bbox=shape.bbox,
                        )
                    )
            if policy.require_alt_text and shape.kind == "picture" and not shape.alt_text.strip():
                findings.append(
                    Finding(
                        "policy.alt-text-required",
                        "accessibility",
                        "high",
                        "high",
                        "The delivery policy requires alternative text for every image.",
                        f"{shape.name} has no alternative text; policy={policy.name}",
                        "Add meaningful alternative text or mark the image decorative.",
                        slide_index=slide.index,
                        shape_id=shape.shape_id,
                        bbox=shape.bbox,
                    )
                )
    if policy.forbid_external_links:
        for target in deck.external_relationships:
            findings.append(
                Finding(
                    "policy.external-link-forbidden",
                    "privacy",
                    "high",
                    "high",
                    "The delivery policy does not allow external links or files.",
                    f"target={target}; policy={policy.name}",
                    "Remove or embed the external content in the delivery copy.",
                )
            )
    return findings


POLICY_TEMPLATE = """version: 1
name: Example delivery policy
allowedFonts:
  - Microsoft YaHei
  - Arial
allowedColors:
  - '#17324D'
  - '#E7763C'
  - '#FFFFFF'
minimumFontSize: 18
forbidExternalLinks: true
forbidNotes: true
forbidHiddenSlides: true
requireAltText: true
exceptions:
  - ruleId: readability.small-font
    slides: [12]
    reason: Legal disclaimer approved by the presentation owner
    expires: 2026-12-31
"""
