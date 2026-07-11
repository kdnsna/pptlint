# PPTLint

> **Check an AI-generated PowerPoint before you send or present it.**

[简体中文](README.zh-CN.md) · [Live example](https://kdnsna.github.io/pptlint/) · [Before/after report](https://kdnsna.github.io/pptlint/proof-loop/comparison.html)

[![CI](https://github.com/kdnsna/pptlint/actions/workflows/ci.yml/badge.svg)](https://github.com/kdnsna/pptlint/actions/workflows/ci.yml)
[![Pages](https://github.com/kdnsna/pptlint/actions/workflows/pages.yml/badge.svg)](https://kdnsna.github.io/pptlint/)
[![License: MIT](https://img.shields.io/badge/license-MIT-10233f.svg)](LICENSE)

[![A risky AI-generated PowerPoint beside the repaired delivery-ready deck](site/assets/pptlint-before-after-hero.png)](https://kdnsna.github.io/pptlint/proof-loop/comparison.html)

AI tools can make a PowerPoint quickly. They can also leave behind missing files, clipped text, overlapping text boxes, unreadable type, flattened slides, speaker notes, comments, and personal information.

PPTLint checks the `.pptx` on your computer and answers three questions:

- **Ready to send** — no high-confidence delivery problem was found.
- **Check before sending** — open the named slides and confirm the highlighted items.
- **Fix before sending** — fix the listed problem before sending the file.

PPTLint does not upload the presentation, call an AI model, or change the source file.

Need to create or repair the presentation first? Use [Ultimate PPT Master](https://github.com/kdnsna/ultimate-ppt-master-skill), then run PPTLint as the independent delivery check.

## Ask your coding agent

Copy this into Codex, Claude Code, or another coding agent:

```text
Install PPTLint and check whether this AI-generated PowerPoint is ready to send.
Show me the slides I must fix first and the exact PowerPoint steps for each one.
```

## Run it yourself

Install from PyPI and run:

```bash
uvx pptlint check output.pptx --profile ai-generated
```

PPTLint writes two files:

- `pptlint-report.html` — an offline report for people;
- `pptlint-report.json` — the same result for agents and automation.

The first screen shows whether the file is ready and the three most important actions. The numerical score is secondary and is intended only for comparing the same presentation before and after changes.

## See real examples

- [Ready example](examples/reports/good-deck.html)
- [Problem example](examples/reports/bad-deck.html)
- [Real editable PowerPoint improvement: 49 → 100](https://kdnsna.github.io/pptlint/proof-loop/comparison.html)
- [Before PPTX](examples/proof-loop/before.pptx) and [after PPTX](examples/proof-loop/after.pptx)
- [Open method for checking five AI PowerPoint projects](https://kdnsna.github.io/pptlint/benchmark/)

## Check changes

Keep the original file, check a separate edited copy, and compare the two reports:

```bash
pptlint check before.pptx --output before
pptlint check after.pptx --output after
pptlint compare before.json after.json --output comparison
```

The comparison separates problems that were fixed, problems that remain, and problems introduced by the edit.

## Use it in GitHub Actions

```yaml
- uses: kdnsna/pptlint@v0
  with:
    path: output.pptx
    profile: ai-generated
    renderer: wireframe
```

The reports are uploaded even when the check fails.

## What PPTLint checks

| User concern | Checks |
|---|---|
| Will it open correctly? | PPTX package, relationships, content types, media, slide list, real rendering |
| Will it fail on screen? | Off-slide text, substantial text overlap, explicit clipping risk, small type, low contrast, unusual page size |
| Can someone edit it later? | Full-slide images and native text, table, chart, shape coverage |
| Is it safe to send? | Notes, comments, hidden slides, author information, external files and links |

Low-confidence hints never block delivery. PPTLint does not judge whether a presentation is beautiful, persuasive, or factually correct.

## Stable interfaces

- Current report: [`pptlint-report/v2`](schema/pptlint-report-v2.schema.json)
- Previous report: [`decklint-report/v1`](schema/decklint-report-v1.schema.json)
- Comparison format: [`decklint-comparison/v1`](schema/decklint-comparison-v1.schema.json)
- Exit code `0`: completed; `1`: changes required; `2`: file or runtime error.

The previous `decklint` command remains available through v0.4. Existing v1 reports can still be compared.

## Development

```bash
uv venv --python 3.13
uv pip install -e '.[dev]'
PYTHONPATH=src .venv/bin/python -m pytest
.venv/bin/ruff check src tests tools
```

PPTLint is local, read-only, model-free, telemetry-free, and MIT licensed.
