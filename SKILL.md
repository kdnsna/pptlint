---
name: decklint
description: Audit a PowerPoint PPTX for integrity, readability, editability, consistency, accessibility, and privacy risks without modifying the source file.
---

# DeckLint

Use DeckLint when a user asks to inspect, audit, lint, QA, validate, or review a `.pptx` file.

## Run

Prefer the installed command:

```bash
decklint audit input.pptx --output decklint-report
```

If DeckLint is not installed and `uvx` is available:

```bash
uvx decklint audit input.pptx --output decklint-report
```

Use `--profile ai-generated` when the presentation is expected to contain native editable objects and varied generated layouts. Use `--renderer wireframe` in restricted CI environments; use `auto` locally.

## Interpret

- Exit `0`: no high-confidence finding reached the configured threshold.
- Exit `1`: a quality finding or minimum-score gate failed.
- Exit `2`: the file could not be audited.
- Read `decklint-report.json` for automation and `decklint-report.html` for human review.
- Low-confidence findings are advisory and do not reduce the score or fail CI.

## Safety

Do not upload the presentation or report unless the user explicitly asks.
Do not modify the source PPTX. DeckLint v0.1 is report-only.
Do not claim that heuristic warnings prove poor design; report their confidence and evidence.

