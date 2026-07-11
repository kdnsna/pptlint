from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

from pptlint.benchmark import build_run_plan, metrics_from_report, summarize_runs, validate_run


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plan_command(args: argparse.Namespace) -> int:
    config = read_json(args.config)
    if not isinstance(config, dict):
        raise ValueError("Benchmark config must be a JSON object")
    write_json(args.output, {"schemaVersion": "pptlint-benchmark-plan/v1", "runs": build_run_plan(config)})
    return 0


def record_command(args: argparse.Namespace) -> int:
    payload = read_json(args.plan)
    report = read_json(args.report)
    if not isinstance(payload, dict) or not isinstance(payload.get("runs"), list):
        raise ValueError("Benchmark plan is invalid")
    if not isinstance(report, dict):
        raise ValueError("PPTLint report must be a JSON object")
    run = next((item for item in payload["runs"] if item.get("runId") == args.run_id), None)
    if not isinstance(run, dict):
        raise ValueError(f"Benchmark run not found: {args.run_id}")
    run.update(
        {
            "status": "complete",
            "model": args.model,
            "provider": args.provider,
            "environment": {
                "os": platform.platform(),
                "python": platform.python_version(),
                "notes": args.notes,
            },
            "durationSeconds": args.duration,
            "outputPptx": {"path": str(args.pptx), "sha256": sha256(args.pptx)},
            "reportJson": {"path": str(args.report), "sha256": sha256(args.report)},
            "metrics": metrics_from_report(report),
        }
    )
    validate_run(run)
    write_json(args.plan, payload)
    return 0


def summary_command(args: argparse.Namespace) -> int:
    payload = read_json(args.plan)
    if not isinstance(payload, dict) or not isinstance(payload.get("runs"), list):
        raise ValueError("Benchmark plan is invalid")
    write_json(args.output, summarize_runs(payload["runs"]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and record reproducible PPTLint benchmark runs.")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--config", type=Path, default=Path("benchmark/benchmark.json"))
    plan.add_argument("--output", type=Path, default=Path("benchmark/run-plan.json"))
    plan.set_defaults(handler=plan_command)
    record = commands.add_parser("record")
    record.add_argument("run_id")
    record.add_argument("--plan", type=Path, default=Path("benchmark/run-plan.json"))
    record.add_argument("--pptx", type=Path, required=True)
    record.add_argument("--report", type=Path, required=True)
    record.add_argument("--model", required=True)
    record.add_argument("--provider", required=True)
    record.add_argument("--duration", type=float, required=True)
    record.add_argument("--notes", default="")
    record.set_defaults(handler=record_command)
    summary = commands.add_parser("summary")
    summary.add_argument("--plan", type=Path, default=Path("benchmark/run-plan.json"))
    summary.add_argument("--output", type=Path, default=Path("benchmark/summary.json"))
    summary.set_defaults(handler=summary_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return args.handler(args)
    except (OSError, ValueError) as exc:
        print(f"Benchmark command failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
