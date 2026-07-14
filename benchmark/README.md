# PPTLint Open AI PowerPoint Check

This directory defines a reproducible, cooperative comparison of the PowerPoint files produced by five open-source AI presentation projects.

It does not rank visual taste and does not name an overall winner. It records whether the final `.pptx` opens, renders, stays editable, keeps private information out, and avoids high-confidence delivery problems.

## Fixed method

- Five projects pinned to exact commits in `benchmark.json`.
- Three public tasks in `tasks/`.
- Three independent runs per project and task: 45 runs in total.
- Each project uses its documented recommended configuration and model.
- Every completed run records the model, provider, environment, time, PPTX hash, report hash, and derived metrics.
- Maintainers can reproduce, challenge, or replace a result through a pull request.

Generate the 45-run plan:

```bash
PYTHONPATH=src python tools/benchmark.py plan
```

After a project creates a PPTX, check it with real rendering and record the evidence:

```bash
pptlint check output.pptx --profile ai-generated --renderer libreoffice --output report
PYTHONPATH=src python tools/benchmark.py record ppt-master--qbr-cn--01 \
  --pptx output.pptx --report report.json \
  --model "documented model" --provider "documented provider" \
  --duration 120 --notes "documented recommended configuration"
```

Results are not published until the run manifest, hashes, report and PPTX have been reviewed. Pending runs are not counted as evidence.

## Real-world editing evaluation

The generation comparison above does not answer whether a tool can safely improve an existing business deck. The separate [`editing/`](editing/) suite covers fixed-source local edits, screenshot and native-table repairs, privacy cleanup, source-grounded authoring, and second-round revision.

Its private business inputs are never committed. Cases bind to anonymized source aliases and hashes, and the evaluator blocks unexpected changes to non-target slides instead of rewarding whole-deck regeneration.
