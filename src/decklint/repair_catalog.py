from __future__ import annotations

from dataclasses import dataclass


REPAIR_MODES = ("cleanup-copy", "guided-powerpoint", "agent-rebuild", "human-decision")
REPAIR_RISKS = ("low", "medium", "high")
EXECUTORS = ("pptlint", "powerpoint", "generic-agent", "ultimate-ppt-master", "powerpoint-copilot")


@dataclass(frozen=True)
class RepairRecipe:
    mode: str
    risk: str
    executors: tuple[str, ...]


def _recipe(mode: str, risk: str, *executors: str) -> RepairRecipe:
    if mode not in REPAIR_MODES or risk not in REPAIR_RISKS:
        raise ValueError("Invalid repair recipe")
    if not executors or any(executor not in EXECUTORS for executor in executors):
        raise ValueError("Invalid repair executor")
    return RepairRecipe(mode=mode, risk=risk, executors=tuple(executors))


# Every built-in rule has an explicit repair disposition. Unknown or plugin rules
# deliberately fall back to human-decision instead of receiving invented advice.
REPAIR_CATALOG: dict[str, RepairRecipe] = {
    "accessibility.missing-alt-text": _recipe(
        "guided-powerpoint", "medium", "powerpoint", "generic-agent", "powerpoint-copilot"
    ),
    "accessibility.missing-title": _recipe(
        "guided-powerpoint", "medium", "powerpoint", "generic-agent", "powerpoint-copilot"
    ),
    "accessibility.reading-order-risk": _recipe(
        "human-decision", "medium", "powerpoint", "generic-agent"
    ),
    "consistency.font-outlier": _recipe(
        "guided-powerpoint", "medium", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "consistency.repeated-layout": _recipe(
        "human-decision", "low", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "editability.full-slide-image": _recipe(
        "agent-rebuild", "high", "generic-agent", "ultimate-ppt-master", "powerpoint-copilot"
    ),
    "editability.media-portability-risk": _recipe(
        "human-decision", "high", "powerpoint", "generic-agent"
    ),
    "integrity.broken-relationship": _recipe(
        "agent-rebuild", "high", "generic-agent", "ultimate-ppt-master"
    ),
    "integrity.duplicate-media": _recipe(
        "agent-rebuild", "medium", "generic-agent", "ultimate-ppt-master"
    ),
    "integrity.empty-deck": _recipe(
        "human-decision", "high", "powerpoint", "generic-agent"
    ),
    "integrity.large-package": _recipe(
        "agent-rebuild", "medium", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "integrity.missing-content-type": _recipe(
        "agent-rebuild", "high", "generic-agent", "ultimate-ppt-master"
    ),
    "integrity.notes-relationship": _recipe(
        "agent-rebuild", "high", "generic-agent", "ultimate-ppt-master"
    ),
    "integrity.orphan-slide-part": _recipe(
        "agent-rebuild", "high", "generic-agent", "ultimate-ppt-master"
    ),
    "policy.alt-text-required": _recipe(
        "guided-powerpoint", "medium", "powerpoint", "generic-agent", "powerpoint-copilot"
    ),
    "policy.color-not-allowed": _recipe(
        "guided-powerpoint", "medium", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "policy.external-link-forbidden": _recipe(
        "human-decision", "high", "powerpoint", "generic-agent"
    ),
    "policy.font-not-allowed": _recipe(
        "guided-powerpoint", "medium", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "policy.font-size-below-minimum": _recipe(
        "guided-powerpoint", "medium", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "policy.hidden-slide-forbidden": _recipe(
        "human-decision", "high", "powerpoint", "generic-agent"
    ),
    "policy.notes-forbidden": _recipe(
        "cleanup-copy", "low", "pptlint", "powerpoint", "generic-agent"
    ),
    "privacy.comments": _recipe("cleanup-copy", "low", "pptlint", "powerpoint"),
    "privacy.external-relationship": _recipe(
        "human-decision", "high", "powerpoint", "generic-agent"
    ),
    "privacy.hidden-slide": _recipe(
        "human-decision", "high", "powerpoint", "generic-agent"
    ),
    "privacy.personal-metadata": _recipe("cleanup-copy", "low", "pptlint", "powerpoint"),
    "privacy.speaker-notes": _recipe("cleanup-copy", "low", "pptlint", "powerpoint"),
    "readability.blank-slide": _recipe(
        "human-decision", "medium", "powerpoint", "generic-agent"
    ),
    "readability.dense-text": _recipe(
        "agent-rebuild", "medium", "generic-agent", "ultimate-ppt-master", "powerpoint-copilot"
    ),
    "readability.font-portability-risk": _recipe(
        "guided-powerpoint", "medium", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "readability.low-contrast": _recipe(
        "guided-powerpoint", "medium", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "readability.motion-portability-risk": _recipe(
        "human-decision", "high", "powerpoint", "generic-agent"
    ),
    "readability.off-canvas-text": _recipe(
        "agent-rebuild", "high", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "readability.small-font": _recipe(
        "guided-powerpoint", "medium", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "readability.text-clipping-risk": _recipe(
        "agent-rebuild", "high", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "readability.text-overlap": _recipe(
        "agent-rebuild", "high", "powerpoint", "generic-agent", "ultimate-ppt-master"
    ),
    "readability.unusual-aspect-ratio": _recipe(
        "human-decision", "high", "powerpoint", "generic-agent"
    ),
}


UNKNOWN_RECIPE = _recipe("human-decision", "high", "powerpoint", "generic-agent")


def recipe_for(rule_id: str) -> RepairRecipe:
    return REPAIR_CATALOG.get(rule_id, UNKNOWN_RECIPE)
