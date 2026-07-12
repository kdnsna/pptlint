from __future__ import annotations

import json
from pathlib import Path

from decklint import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_public_ai_ppt_validation_covers_thirty_real_files_and_all_families() -> None:
    payload = json.loads(
        (ROOT / "validation/public-sample-validation.json").read_text(encoding="utf-8")
    )
    summary = payload["summary"]

    assert payload["schemaVersion"] == "pptlint-public-sample-validation/v1"
    assert payload["toolVersion"] == __version__
    assert summary["auditedSamples"] >= 30
    assert summary["failedSamples"] == 0
    assert summary["repairPlanCoveragePercent"] == 100.0
    assert set(summary["families"]) == {
        "ppt-master",
        "pptagent",
        "presenton",
        "ultimate-ppt-master",
    }
    assert len(payload["results"]) == summary["auditedSamples"]
    assert all(item["findingCount"] == item["repairTaskCount"] for item in payload["results"])
    assert all(item["repairCoverage"] is True for item in payload["results"])
    assert all(str(item["url"]).startswith("https://") for item in payload["results"])
    assert "/Users/" not in json.dumps(payload)
