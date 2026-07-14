from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Mapping

from decklint.model import DeckModel, Slide, load_deck
from decklint.render import render_deck
from decklint.repair_plan import build_repair_plan
from decklint.report import build_report
from decklint.rules import audit_deck
from decklint.scoring import score_findings


class EditEvalError(ValueError):
    """Raised when an editing-evaluation definition or run is invalid."""


SUPPORTED_MODES = {"edit", "source-grounded-authoring", "source-grounded-revision"}
GUIDANCE_REVIEW_TERMS = ("检查", "查看", "确认", "再运行", "重新打开", "放映", "100%", "播放")
MANUAL_REPAIR_MODES = {"guided-powerpoint", "agent-rebuild", "human-decision"}


def read_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EditEvalError(f"Expected a JSON object: {path}")
    return payload


def source_map(sources: dict[str, object]) -> dict[str, dict[str, object]]:
    items = sources.get("sources")
    if not isinstance(items, list):
        raise EditEvalError("Source registry requires a sources array")
    mapped: dict[str, dict[str, object]] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise EditEvalError("Every source requires a string id")
        source_id = item["id"]
        if source_id in mapped:
            raise EditEvalError(f"Duplicate source id: {source_id}")
        mapped[source_id] = item
    return mapped


def validate_suite(suite: dict[str, object], sources: dict[str, object]) -> None:
    if suite.get("schemaVersion") != "pptlint-edit-eval/v1":
        raise EditEvalError("Unsupported editing evaluation schemaVersion")
    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EditEvalError("Editing evaluation requires at least one case")
    known_sources = source_map(sources)
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise EditEvalError("Every case must be an object")
        case_id = case.get("id")
        mode = case.get("mode")
        if not isinstance(case_id, str) or not case_id:
            raise EditEvalError("Every case requires a string id")
        if case_id in case_ids:
            raise EditEvalError(f"Duplicate case id: {case_id}")
        case_ids.add(case_id)
        if mode not in SUPPORTED_MODES:
            raise EditEvalError(f"Unsupported mode for {case_id}: {mode}")
        source_id = case.get("sourceId")
        if isinstance(source_id, str) and source_id not in known_sources:
            raise EditEvalError(f"Unknown source for {case_id}: {source_id}")
        if mode in {"edit", "source-grounded-authoring"} and not isinstance(source_id, str):
            raise EditEvalError(f"{case_id} requires sourceId")
        if mode == "source-grounded-revision" and not isinstance(case.get("dependsOn"), str):
            raise EditEvalError(f"{case_id} requires dependsOn")
        acceptance = case.get("acceptance")
        if not isinstance(acceptance, dict):
            raise EditEvalError(f"{case_id} requires acceptance criteria")
        if mode == "edit":
            allowed = acceptance.get("allowedSlideChanges")
            if not isinstance(allowed, list) or not all(
                isinstance(index, int) and index > 0 for index in allowed
            ):
                raise EditEvalError(f"{case_id} requires positive allowedSlideChanges")

    for case in cases:
        if isinstance(case, dict) and isinstance(case.get("dependsOn"), str):
            if case["dependsOn"] not in case_ids:
                raise EditEvalError(f"Unknown dependency for {case['id']}: {case['dependsOn']}")


def build_run_plan(suite: dict[str, object]) -> dict[str, object]:
    cases = suite.get("cases")
    if not isinstance(cases, list):
        raise EditEvalError("Editing evaluation requires a cases array")
    runs: list[dict[str, object]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise EditEvalError("Every case must be an object")
        run = {
            "runId": case["id"],
            "caseId": case["id"],
            "track": case["track"],
            "mode": case["mode"],
            "status": "pending",
        }
        for field in ("sourceId", "dependsOn"):
            if field in case:
                run[field] = case[field]
        runs.append(run)
    return {"schemaVersion": "pptlint-edit-eval-plan/v1", "runs": runs}


def resolve_private_source(
    source: dict[str, object],
    *,
    overrides: Mapping[str, Path] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    source_id = str(source.get("id", ""))
    if source.get("type") != "private-pptx":
        raise EditEvalError(f"Source is not a private PPTX: {source_id}")
    if overrides and source_id in overrides:
        return overrides[source_id]
    variable = source.get("locatorEnv")
    env = os.environ if environ is None else environ
    if isinstance(variable, str) and env.get(variable):
        return Path(env[variable]).expanduser()
    raise EditEvalError(f"No local path supplied for {source_id}; set {variable} or pass an override")


def verify_private_source(source: dict[str, object], path: Path) -> dict[str, object]:
    if not path.is_file():
        raise EditEvalError(f"Source file does not exist: {path}")
    deck = load_deck(path)
    expected_hash = source.get("sha256")
    expected_slides = source.get("slides")
    hash_matches = not isinstance(expected_hash, str) or deck.sha256 == expected_hash
    slides_match = not isinstance(expected_slides, int) or len(deck.slides) == expected_slides
    return {
        "sourceId": source.get("id"),
        "sha256": deck.sha256,
        "slides": len(deck.slides),
        "bytes": path.stat().st_size,
        "hashMatches": hash_matches,
        "slidesMatch": slides_match,
        "passed": hash_matches and slides_match,
    }


def _slide_fingerprint(slide: Slide) -> str:
    shapes = []
    for shape in sorted(slide.shapes, key=lambda item: item.z_order):
        shapes.append(
            {
                "kind": shape.kind,
                "bbox": [shape.bbox.x, shape.bbox.y, shape.bbox.w, shape.bbox.h],
                "text": shape.text,
                "fontSizes": [round(value, 3) for value in shape.font_sizes],
                "fontFamilies": shape.font_families,
                "fillColor": shape.fill_color,
                "textColors": shape.text_colors,
                "altText": shape.alt_text,
                "placeholderType": shape.placeholder_type,
                "textVerticalOverflow": shape.text_vertical_overflow,
            }
        )
    payload = {
        "index": slide.index,
        "title": slide.title,
        "titleSource": slide.title_source,
        "hidden": slide.hidden,
        "notes": slide.notes_text,
        "shapes": shapes,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _deck_text(deck: DeckModel, slide_index: int | None = None) -> str:
    slides = deck.slides if slide_index is None else [deck.slides[slide_index - 1]]
    return "\n".join(shape.text for slide in slides for shape in slide.shapes if shape.text)


def _normalized_text(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _finding_counts(
    deck: DeckModel,
    *,
    rule_id: str | None = None,
    slides: set[int] | None = None,
    high_confidence_only: bool = False,
) -> Counter[tuple[str, int | None]]:
    counts: Counter[tuple[str, int | None]] = Counter()
    for finding in audit_deck(deck):
        if rule_id is not None and finding.rule_id != rule_id:
            continue
        if slides is not None and finding.slide_index not in slides:
            continue
        if high_confidence_only and finding.confidence != "high":
            continue
        counts[(finding.rule_id, finding.slide_index)] += 1
    return counts


def _native_object_ratio(deck: DeckModel) -> float:
    shapes = [shape for slide in deck.slides for shape in slide.shapes]
    native_text = sum(bool(shape.text.strip()) for shape in shapes)
    pictures = sum(shape.kind == "picture" for shape in shapes)
    frames = sum(shape.kind == "graphic-frame" for shape in shapes)
    charts = sum(shape.kind == "chart" for shape in shapes)
    tables = sum(shape.kind == "table" for shape in shapes)
    native = native_text + frames + charts + tables
    return round(native / max(1, native + pictures), 4)


def _case_by_id(suite: dict[str, object], case_id: str) -> dict[str, object]:
    cases = suite.get("cases")
    if not isinstance(cases, list):
        raise EditEvalError("Editing evaluation requires a cases array")
    for case in cases:
        if isinstance(case, dict) and case.get("id") == case_id:
            return case
    raise EditEvalError(f"Unknown case: {case_id}")


def _check_required_text(deck: DeckModel, item: object) -> dict[str, object]:
    if not isinstance(item, dict) or not isinstance(item.get("contains"), str):
        raise EditEvalError("requiredText entries require contains")
    slide = item.get("slide")
    slide_index = slide if isinstance(slide, int) else None
    contains = item["contains"]
    return {
        "kind": "required-text",
        "slide": slide_index,
        "contains": contains,
        "passed": _normalized_text(contains) in _normalized_text(_deck_text(deck, slide_index)),
    }


def _check_forbidden_text(deck: DeckModel, item: object) -> dict[str, object]:
    if not isinstance(item, dict) or not isinstance(item.get("contains"), str):
        raise EditEvalError("forbiddenText entries require contains")
    slide = item.get("slide")
    slide_index = slide if isinstance(slide, int) else None
    contains = item["contains"]
    return {
        "kind": "forbidden-text",
        "slide": slide_index,
        "contains": contains,
        "passed": _normalized_text(contains) not in _normalized_text(_deck_text(deck, slide_index)),
    }


def verify_case_source(case: dict[str, object], source_path: Path) -> dict[str, object]:
    if case.get("mode") != "edit":
        return {"caseId": case.get("id"), "passed": True, "reasons": []}
    acceptance = case.get("acceptance")
    if not isinstance(acceptance, dict):
        raise EditEvalError("Case requires acceptance criteria")
    deck = load_deck(source_path)
    reasons: list[str] = []
    allowed = acceptance.get("allowedSlideChanges", [])
    if any(not isinstance(index, int) or index < 1 or index > len(deck.slides) for index in allowed):
        reasons.append("allowed-slide-out-of-range")
    for item in acceptance.get("mustReduceRules", []):
        if not isinstance(item, dict) or not isinstance(item.get("ruleId"), str):
            reasons.append("invalid-rule-reduction")
            continue
        slides_value = item.get("slides")
        slides = set(slides_value) if isinstance(slides_value, list) else None
        before = sum(_finding_counts(deck, rule_id=item["ruleId"], slides=slides).values())
        if before < int(item.get("minimumReduction", 1)):
            reasons.append(f"missing-baseline-rule:{item['ruleId']}")
    for item in acceptance.get("forbiddenText", []):
        if not isinstance(item, dict) or not isinstance(item.get("contains"), str):
            reasons.append("invalid-forbidden-text")
            continue
        slide = item.get("slide")
        slide_index = slide if isinstance(slide, int) else None
        if _normalized_text(item["contains"]) not in _normalized_text(_deck_text(deck, slide_index)):
            reasons.append("forbidden-text-not-present-in-source")
    return {"caseId": case.get("id"), "passed": not reasons, "reasons": reasons}


def guidance_scope(case: dict[str, object]) -> str:
    acceptance = case.get("acceptance")
    reductions = acceptance.get("mustReduceRules") if isinstance(acceptance, dict) else None
    return "lint-detectable" if isinstance(reductions, list) and reductions else "instruction-only"


def build_guidance_context(source_path: Path) -> tuple[dict[str, object], float]:
    started = perf_counter()
    deck = load_deck(source_path)
    findings = audit_deck(deck, profile="baseline", scenario="present")
    report = build_report(
        deck,
        findings,
        score_findings(findings),
        render_deck(deck, source=source_path, renderer="wireframe"),
        profile="baseline",
        language="zh-CN",
        scenario="present",
        report_mode="full",
    )
    return build_repair_plan(report), round(perf_counter() - started, 4)


def _guidance_target_tasks(
    case: dict[str, object], plan: dict[str, object]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    acceptance = case.get("acceptance")
    reductions = acceptance.get("mustReduceRules", []) if isinstance(acceptance, dict) else []
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        raise EditEvalError("Guidance evaluation requires repair-plan tasks")
    matched: list[dict[str, object]] = []
    checks: list[dict[str, object]] = []
    for reduction in reductions:
        if not isinstance(reduction, dict) or not isinstance(reduction.get("ruleId"), str):
            raise EditEvalError("Guidance rule reductions require ruleId")
        slides_value = reduction.get("slides")
        slides = set(slides_value) if isinstance(slides_value, list) else None
        candidates = []
        for task in tasks:
            if not isinstance(task, dict) or task.get("ruleId") != reduction["ruleId"]:
                continue
            location = task.get("location")
            slide = location.get("slideIndex") if isinstance(location, dict) else None
            if slides is None or slide in slides:
                candidates.append(task)
        minimum = int(reduction.get("minimumReduction", 1))
        checks.append(
            {
                "ruleId": reduction["ruleId"],
                "slides": sorted(slides) if slides is not None else None,
                "minimum": minimum,
                "found": len(candidates),
                "passed": len(candidates) >= minimum,
            }
        )
        matched.extend(candidates)
    unique = {str(task.get("taskId", index)): task for index, task in enumerate(matched)}
    return list(unique.values()), checks


def evaluate_guidance_case(
    case: dict[str, object],
    source: dict[str, object],
    source_path: Path,
    *,
    plan: dict[str, object],
    duration_seconds: float,
) -> dict[str, object]:
    if case.get("mode") != "edit" or case.get("track") != "business-edit":
        raise EditEvalError("Guidance evaluation only accepts business-edit cases")
    source_verification = verify_private_source(source, source_path)
    scope = guidance_scope(case)
    if scope == "instruction-only":
        return {
            "caseId": case["id"],
            "sourceId": case["sourceId"],
            "operationClass": case.get("operationClass"),
            "scopeClass": scope,
            "targetDetected": None,
            "hasLocation": None,
            "hasManualSteps": None,
            "hasVerificationStep": None,
            "routeCorrect": None,
            "falseAutomationPromise": False,
            "durationSeconds": duration_seconds,
            "passed": bool(source_verification["passed"]),
        }

    matched, target_checks = _guidance_target_tasks(case, plan)
    target_detected = bool(target_checks) and all(item["passed"] for item in target_checks)
    has_location = bool(matched) and all(
        isinstance(task.get("location"), dict)
        and (
            isinstance(task["location"].get("slideIndex"), int)
            or task["location"].get("slideIndex") is None
        )
        for task in matched
    )
    has_manual_steps = bool(matched) and all(
        isinstance(task.get("steps"), list)
        and len(task["steps"]) >= 3
        and all(isinstance(step, str) and step.strip() for step in task["steps"])
        for task in matched
    )
    has_verification = bool(matched) and all(
        any(term in " ".join(str(step) for step in task.get("steps", [])) for term in GUIDANCE_REVIEW_TERMS)
        for task in matched
    )
    modes = {str(task.get("repairMode", "")) for task in matched}
    operation_class = str(case.get("operationClass", ""))
    if operation_class == "privacy-cleanup":
        route_correct = modes == {"cleanup-copy"}
    elif operation_class == "package-relationship-cleanup":
        route_correct = modes == {"human-decision"}
    else:
        route_correct = bool(modes) and modes <= MANUAL_REPAIR_MODES
    false_automation = any(
        task.get("repairMode") != "cleanup-copy"
        and "pptlint" in task.get("recommendedExecutors", [])
        for task in matched
    )
    passed = all(
        (
            bool(source_verification["passed"]),
            target_detected,
            has_location,
            has_manual_steps,
            has_verification,
            route_correct,
            not false_automation,
        )
    )
    return {
        "caseId": case["id"],
        "sourceId": case["sourceId"],
        "operationClass": operation_class,
        "scopeClass": scope,
        "targetDetected": target_detected,
        "targetChecks": target_checks,
        "matchedTaskCount": len(matched),
        "repairModes": sorted(modes),
        "hasLocation": has_location,
        "hasManualSteps": has_manual_steps,
        "hasVerificationStep": has_verification,
        "routeCorrect": route_correct,
        "falseAutomationPromise": false_automation,
        "durationSeconds": duration_seconds,
        "passed": passed,
    }


def evaluate_edit_case(
    case: dict[str, object],
    source: dict[str, object],
    source_path: Path,
    output_path: Path,
    *,
    duration_seconds: float,
    human_score: float | None = None,
) -> dict[str, object]:
    if case.get("mode") != "edit":
        raise EditEvalError("evaluate_edit_case only accepts edit cases")
    if human_score is not None and not 0 <= human_score <= 15:
        raise EditEvalError("Human score must be between 0 and 15")
    source_verification = verify_private_source(source, source_path)
    source_deck = load_deck(source_path)
    try:
        output_deck = load_deck(output_path)
        output_error = None
    except (OSError, ValueError) as exc:
        output_deck = None
        output_error = str(exc)

    acceptance = case.get("acceptance")
    if not isinstance(acceptance, dict):
        raise EditEvalError("Case requires acceptance criteria")
    allowed = set(acceptance.get("allowedSlideChanges", []))
    checks: dict[str, object] = {
        "sourceIdentity": source_verification["passed"],
        "outputValid": output_deck is not None,
        "outputError": output_error,
    }
    task_checks: list[dict[str, object]] = []
    changed_slides: list[int] = []
    out_of_scope_slides: list[int] = []
    new_high_confidence: list[dict[str, object]] = []
    native_drop = 1.0

    if output_deck is not None:
        checks["slideCountPreserved"] = (
            len(source_deck.slides) == len(output_deck.slides)
            if acceptance.get("preserveSlideCount", True)
            else True
        )
        checks["canvasPreserved"] = (
            source_deck.width == output_deck.width and source_deck.height == output_deck.height
        )
        for index in range(1, min(len(source_deck.slides), len(output_deck.slides)) + 1):
            if _slide_fingerprint(source_deck.slides[index - 1]) != _slide_fingerprint(
                output_deck.slides[index - 1]
            ):
                changed_slides.append(index)
                if index not in allowed:
                    out_of_scope_slides.append(index)
        checks["untouchedSlidesPreserved"] = (
            not out_of_scope_slides if acceptance.get("preserveUntouchedSlides", True) else True
        )
        package_only = acceptance.get("allowPackageOnlyChange", False)
        if not package_only:
            task_checks.append(
                {
                    "kind": "target-slide-changed",
                    "allowedSlides": sorted(allowed),
                    "passed": bool(allowed.intersection(changed_slides)),
                }
            )
        for item in acceptance.get("requiredText", []):
            task_checks.append(_check_required_text(output_deck, item))
        for item in acceptance.get("forbiddenText", []):
            task_checks.append(_check_forbidden_text(output_deck, item))
        for item in acceptance.get("mustReduceRules", []):
            if not isinstance(item, dict) or not isinstance(item.get("ruleId"), str):
                raise EditEvalError("mustReduceRules entries require ruleId")
            slides_value = item.get("slides")
            slides = set(slides_value) if isinstance(slides_value, list) else None
            before = sum(_finding_counts(source_deck, rule_id=item["ruleId"], slides=slides).values())
            after = sum(_finding_counts(output_deck, rule_id=item["ruleId"], slides=slides).values())
            minimum = int(item.get("minimumReduction", 1))
            task_checks.append(
                {
                    "kind": "rule-reduction",
                    "ruleId": item["ruleId"],
                    "slides": sorted(slides) if slides is not None else None,
                    "before": before,
                    "after": after,
                    "minimumReduction": minimum,
                    "passed": before - after >= minimum,
                }
            )
        before_high = _finding_counts(source_deck, high_confidence_only=True)
        after_high = _finding_counts(output_deck, high_confidence_only=True)
        for key, count in sorted((after_high - before_high).items()):
            new_high_confidence.append({"ruleId": key[0], "slide": key[1], "count": count})
        checks["noNewHighConfidenceFindings"] = (
            not new_high_confidence if acceptance.get("noNewHighConfidenceFindings", True) else True
        )
        source_native = _native_object_ratio(source_deck)
        output_native = _native_object_ratio(output_deck)
        native_drop = round(source_native - output_native, 4)
        maximum_drop = float(acceptance.get("maxNativeObjectRatioDrop", 0.02))
        checks["editabilityPreserved"] = native_drop <= maximum_drop
        checks["nativeObjectRatio"] = {
            "before": source_native,
            "after": output_native,
            "drop": native_drop,
            "maximumDrop": maximum_drop,
        }
    else:
        checks.update(
            {
                "slideCountPreserved": False,
                "canvasPreserved": False,
                "untouchedSlidesPreserved": False,
                "noNewHighConfidenceFindings": False,
                "editabilityPreserved": False,
            }
        )

    max_duration = float(acceptance.get("maxDurationSeconds", 180))
    checks["durationWithinBudget"] = duration_seconds <= max_duration
    checks["taskEvidence"] = bool(task_checks) and all(item["passed"] for item in task_checks)

    machine_score = 0.0
    machine_score += 5 if checks["sourceIdentity"] else 0
    machine_score += 5 if checks["outputValid"] else 0
    machine_score += 3 if checks["slideCountPreserved"] else 0
    machine_score += 2 if checks["canvasPreserved"] else 0
    machine_score += 25 if checks["taskEvidence"] else 0
    machine_score += 25 if checks["untouchedSlidesPreserved"] else 0
    machine_score += 10 if checks["noNewHighConfidenceFindings"] else 0
    machine_score += 5 if checks["editabilityPreserved"] else 0
    machine_score += 5 if checks["durationWithinBudget"] else 0
    raw_machine_score = machine_score
    score_cap = 85.0
    score_cap_reasons: list[str] = []
    if not checks["sourceIdentity"] or not checks["outputValid"]:
        score_cap = 0.0
        score_cap_reasons.append("invalid-source-or-output")
    elif not checks["slideCountPreserved"] or not checks["canvasPreserved"]:
        score_cap = 25.0
        score_cap_reasons.append("presentation-structure-changed")
    elif not checks["taskEvidence"]:
        score_cap = 40.0
        score_cap_reasons.append("requested-edit-not-completed")
    elif not checks["untouchedSlidesPreserved"]:
        score_cap = 55.0
        score_cap_reasons.append("out-of-scope-slide-changed")
    machine_score = min(machine_score, score_cap)
    hard_gate_names = (
        "sourceIdentity",
        "outputValid",
        "slideCountPreserved",
        "canvasPreserved",
        "taskEvidence",
        "untouchedSlidesPreserved",
    )
    hard_gate_passed = all(bool(checks[name]) for name in hard_gate_names)
    total_score = machine_score + (human_score or 0)
    status = "blocked" if not hard_gate_passed else ("complete" if human_score is not None else "review")
    return {
        "schemaVersion": "pptlint-edit-eval-result/v1",
        "caseId": case["id"],
        "sourceId": case["sourceId"],
        "status": status,
        "hardGatePassed": hard_gate_passed,
        "durationSeconds": duration_seconds,
        "changedSlides": changed_slides,
        "outOfScopeSlides": out_of_scope_slides,
        "newHighConfidenceFindings": new_high_confidence,
        "checks": checks,
        "taskChecks": task_checks,
        "score": {
            "machine": round(machine_score, 2),
            "rawMachine": round(raw_machine_score, 2),
            "machineMaximum": 85,
            "cap": round(score_cap, 2),
            "capReasons": score_cap_reasons,
            "human": human_score,
            "humanMaximum": 15,
            "total": round(total_score, 2) if human_score is not None else None,
        },
    }


def evaluate_source_grounded_case(
    case: dict[str, object],
    output_path: Path,
    *,
    duration_seconds: float,
    revision_source_path: Path | None = None,
    human_score: float | None = None,
) -> dict[str, object]:
    if case.get("mode") not in {"source-grounded-authoring", "source-grounded-revision"}:
        raise EditEvalError("Case is not source-grounded")
    if human_score is not None and not 0 <= human_score <= 30:
        raise EditEvalError("Human score must be between 0 and 30")
    acceptance = case.get("acceptance")
    if not isinstance(acceptance, dict):
        raise EditEvalError("Case requires acceptance criteria")
    try:
        output_deck = load_deck(output_path)
        output_error = None
    except (OSError, ValueError) as exc:
        output_deck = None
        output_error = str(exc)

    checks: dict[str, object] = {"outputValid": output_deck is not None, "outputError": output_error}
    fact_checks: list[dict[str, object]] = []
    attribution_checks: list[dict[str, object]] = []
    if output_deck is not None:
        slide_range = acceptance.get("slideRange", {})
        minimum = int(slide_range.get("minimum", 1)) if isinstance(slide_range, dict) else 1
        maximum = int(slide_range.get("maximum", 999)) if isinstance(slide_range, dict) else 999
        checks["slideRange"] = minimum <= len(output_deck.slides) <= maximum
        all_text = _normalized_text(_deck_text(output_deck))
        for fact in acceptance.get("requiredFacts", []):
            passed = isinstance(fact, str) and _normalized_text(fact) in all_text
            fact_checks.append({"fact": fact, "passed": passed})
        for attribution in acceptance.get("requiredAttribution", []):
            passed = isinstance(attribution, str) and _normalized_text(attribution) in all_text
            attribution_checks.append({"attribution": attribution, "passed": passed})
        checks["requiredFacts"] = bool(fact_checks) and all(item["passed"] for item in fact_checks)
        checks["requiredAttribution"] = bool(attribution_checks) and all(
            item["passed"] for item in attribution_checks
        )
        findings = audit_deck(output_deck, profile="ai-generated")
        checks["noCriticalFindings"] = not any(finding.severity == "critical" for finding in findings)
        native_ratio = _native_object_ratio(output_deck)
        checks["editability"] = native_ratio >= 0.6
        checks["nativeObjectRatio"] = native_ratio
    else:
        checks.update(
            {
                "slideRange": False,
                "requiredFacts": False,
                "requiredAttribution": False,
                "noCriticalFindings": False,
                "editability": False,
            }
        )
    if case.get("mode") == "source-grounded-revision":
        if revision_source_path is None:
            checks["revisionSourceValid"] = False
            checks["outputDiffersFromRevisionSource"] = False
        else:
            try:
                revision_source = load_deck(revision_source_path)
                checks["revisionSourceValid"] = True
                checks["outputDiffersFromRevisionSource"] = (
                    output_deck is not None and revision_source.sha256 != output_deck.sha256
                )
            except (OSError, ValueError):
                checks["revisionSourceValid"] = False
                checks["outputDiffersFromRevisionSource"] = False
    max_duration = float(acceptance.get("maxDurationSeconds", 600))
    checks["durationWithinBudget"] = duration_seconds <= max_duration

    machine_score = 0.0
    machine_score += 10 if checks["outputValid"] else 0
    machine_score += 10 if checks["slideRange"] else 0
    machine_score += 25 if checks["requiredFacts"] else 0
    machine_score += 10 if checks["requiredAttribution"] else 0
    machine_score += 5 if checks["noCriticalFindings"] else 0
    machine_score += 5 if checks["editability"] else 0
    machine_score += 5 if checks["durationWithinBudget"] else 0
    hard_gate_names = ["outputValid", "slideRange", "requiredFacts", "requiredAttribution"]
    if case.get("mode") == "source-grounded-revision":
        hard_gate_names.extend(["revisionSourceValid", "outputDiffersFromRevisionSource"])
    hard_gate_passed = all(bool(checks[name]) for name in hard_gate_names)
    raw_machine_score = machine_score
    score_cap = 70.0 if hard_gate_passed else 40.0
    score_cap_reasons = [] if hard_gate_passed else ["source-grounded-hard-gate-failed"]
    machine_score = min(machine_score, score_cap)
    total_score = machine_score + (human_score or 0)
    status = "blocked" if not hard_gate_passed else ("complete" if human_score is not None else "review")
    return {
        "schemaVersion": "pptlint-edit-eval-result/v1",
        "caseId": case["id"],
        "sourceId": case.get("sourceId"),
        "dependsOn": case.get("dependsOn"),
        "status": status,
        "hardGatePassed": hard_gate_passed,
        "durationSeconds": duration_seconds,
        "checks": checks,
        "factChecks": fact_checks,
        "attributionChecks": attribution_checks,
        "score": {
            "machine": round(machine_score, 2),
            "rawMachine": round(raw_machine_score, 2),
            "machineMaximum": 70,
            "cap": round(score_cap, 2),
            "capReasons": score_cap_reasons,
            "human": human_score,
            "humanMaximum": 30,
            "total": round(total_score, 2) if human_score is not None else None,
        },
    }


def evaluate_case_by_id(
    suite: dict[str, object],
    sources: dict[str, object],
    case_id: str,
    source_path: Path | None,
    output_path: Path,
    *,
    duration_seconds: float,
    human_score: float | None = None,
) -> dict[str, object]:
    case = _case_by_id(suite, case_id)
    registered = source_map(sources)
    if case.get("mode") == "edit":
        source_id = case.get("sourceId")
        if not isinstance(source_id, str) or source_id not in registered or source_path is None:
            raise EditEvalError(f"Edit case requires a registered PPTX source: {case_id}")
        return evaluate_edit_case(
            case,
            registered[source_id],
            source_path,
            output_path,
            duration_seconds=duration_seconds,
            human_score=human_score,
        )
    return evaluate_source_grounded_case(
        case,
        output_path,
        duration_seconds=duration_seconds,
        revision_source_path=source_path,
        human_score=human_score,
    )
