from __future__ import annotations

import argparse
import json
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from decklint import __version__
from decklint.model import load_deck
from decklint.render import RenderResult
from decklint.repair_plan import build_repair_plan
from decklint.report import build_report
from decklint.rules import audit_deck
from decklint.scoring import score_findings


ROOT = Path(__file__).resolve().parents[1]
MAX_DOWNLOAD_BYTES = 150 * 1024 * 1024


def _samples(manifest: dict[str, object]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    families = manifest.get("families")
    if not isinstance(families, list):
        raise ValueError("Public sample manifest has no families")
    for family in families:
        if not isinstance(family, dict):
            continue
        family_id = str(family.get("id", ""))
        project = str(family.get("project", family_id))
        repository = str(family.get("repository", ""))
        raw_base = str(family.get("rawBase", ""))
        paths = family.get("paths", [])
        if isinstance(paths, list):
            result.extend(
                {
                    "family": family_id,
                    "project": project,
                    "repository": repository,
                    "name": Path(str(path)).name,
                    "url": raw_base + str(path),
                }
                for path in paths
            )
        urls = family.get("urls", [])
        if isinstance(urls, list):
            result.extend(
                {
                    "family": family_id,
                    "project": project,
                    "repository": repository,
                    "name": str(item.get("name", "sample.pptx")),
                    "url": str(item.get("url", "")),
                }
                for item in urls
                if isinstance(item, dict)
            )
    return result


def _download(url: str, output: Path) -> int:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": f"PPTLint/{__version__}"})
            with urllib.request.urlopen(request, timeout=90) as response, output.open("wb") as stream:
                declared = int(response.headers.get("Content-Length", "0") or 0)
                if declared > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Public sample exceeds the 150 MiB validation limit")
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise ValueError("Public sample exceeds the 150 MiB validation limit")
                    stream.write(chunk)
                return total
        except (OSError, urllib.error.URLError, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    raise ValueError(f"Download failed: {last_error}")


def _audit(sample: dict[str, str], directory: Path, index: int) -> dict[str, object]:
    path = directory / f"{index:02d}-{sample['name']}"
    size = _download(sample["url"], path)
    deck = load_deck(path)
    findings = audit_deck(deck, profile="ai-generated", scenario="present")
    report = build_report(
        deck,
        findings,
        score_findings(findings),
        RenderResult(
            requested="wireframe",
            used="wireframe",
            status="ok",
            detail="public-sample-validation-without-previews",
            previews=[""] * len(deck.slides),
        ),
        profile="ai-generated",
        language="en",
        scenario="present",
        report_mode="shareable",
    )
    plan = build_repair_plan(report)
    tasks = plan["tasks"]
    assert isinstance(tasks, list)
    mode_counts = Counter(str(task.get("repairMode", "")) for task in tasks if isinstance(task, dict))
    readiness = report["readiness"]
    scores = report["scores"]
    assert isinstance(readiness, dict) and isinstance(scores, dict)
    return {
        **sample,
        "bytes": size,
        "sha256": deck.sha256,
        "slides": len(deck.slides),
        "readiness": readiness["status"],
        "score": scores["overall"],
        "findingCount": len(findings),
        "repairTaskCount": len(tasks),
        "repairCoverage": len(tasks) == len(findings),
        "repairModes": dict(sorted(mode_counts.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit pinned public AI-PPT samples without committing them")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "validation" / "public-sample-sources.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "validation" / "public-sample-validation.json",
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    samples = _samples(manifest)
    minimum = int(manifest.get("minimumSamples", 30))
    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="pptlint-public-samples-") as temporary:
        directory = Path(temporary)
        for index, sample in enumerate(samples, 1):
            print(f"[{index}/{len(samples)}] {sample['project']} / {sample['name']}", flush=True)
            try:
                results.append(_audit(sample, directory, index))
            except Exception as exc:
                failures.append({**sample, "error": str(exc)})
    families = Counter(str(item["family"]) for item in results)
    coverage = sum(int(bool(item["repairCoverage"])) for item in results)
    payload = {
        "schemaVersion": "pptlint-public-sample-validation/v1",
        "toolVersion": __version__,
        "manifest": args.manifest.name,
        "summary": {
            "declaredSamples": len(samples),
            "auditedSamples": len(results),
            "failedSamples": len(failures),
            "families": dict(sorted(families.items())),
            "repairPlanCoveragePercent": round(100 * coverage / len(results), 2) if results else 0,
            "minimumSamplesMet": len(results) >= minimum,
        },
        "results": results,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0 if not failures and len(results) >= minimum and coverage == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
