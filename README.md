# PPTLint

> **Do not send the PowerPoint yet.** Problems that stay invisible on your laptop often appear on your client's computer or in the meeting room.

[简体中文](README.zh-CN.md) · [Product site](https://kdnsna.github.io/pptlint/) · [12 before/after cases](https://kdnsna.github.io/pptlint/lab/) · [Current 83 → 100 proof](https://kdnsna.github.io/pptlint/proof-loop/comparison.html)

[![CI](https://github.com/kdnsna/pptlint/actions/workflows/ci.yml/badge.svg)](https://github.com/kdnsna/pptlint/actions/workflows/ci.yml)
[![Pages](https://github.com/kdnsna/pptlint/actions/workflows/pages.yml/badge.svg)](https://kdnsna.github.io/pptlint/)
[![PyPI](https://img.shields.io/pypi/v/pptlint.svg)](https://pypi.org/project/pptlint/)
[![License: MIT](https://img.shields.io/badge/license-MIT-10233f.svg)](LICENSE)

[![The same editable PowerPoint under the current rules, from 83 to 100](site/assets/pptlint-before-after-hero.png)](https://kdnsna.github.io/pptlint/lab/)

## Not “is it beautiful?” — “is it safe to send?”

A deck can look finished and still fail at handoff:

- a substituted font wraps the title and clips the final line;
- two text boxes overlap only on another computer;
- the entire slide is one image, so a recipient cannot edit one number;
- notes, hidden slides, comments, author data, or local file links leave with the deck;
- a missing package part triggers a PowerPoint repair warning;
- duplicated media turns nine slides into an 86 MB file.

PPTLint runs locally, reads the `.pptx`, and writes offline HTML and JSON reports. It **does not upload the deck, call a model, modify the source, or collect telemetry**.

## Start in one minute

Give this to Codex, Claude Code, or another coding agent:

```text
Install PPTLint and check whether this PowerPoint is ready to send to a client.
Separate must-fix items from human-review suggestions, name the affected slides,
and give me the exact PowerPoint steps. Do not modify the source file.
```

Or run it directly:

```bash
uvx pptlint check output.pptx --scenario present
```

`present` is the default meeting-room scenario. Use `screen` for close screen reading or `document` for report-like decks.

Each run writes:

- `pptlint-report.html` — an offline human report that explains consequences and next steps;
- `pptlint-report.json` — stable evidence for agents, CI, and integrations.

## Inspect the evidence first

- [12 delivery-risk before/after cases](https://kdnsna.github.io/pptlint/lab/);
- [real editable deck: 83 → 100](https://kdnsna.github.io/pptlint/proof-loop/comparison.html), with both PPTX files and full reports;
- [before PPTX](examples/proof-loop/before.pptx) and [after PPTX](examples/proof-loop/after.pptx);
- [evaluation-method archive](https://kdnsna.github.io/pptlint/benchmark/).

In the published nine-slide Proof Loop, 103 items are no longer reported, 21 still need review, three new low-confidence reminders appear, and no new high-confidence problem appears. **A score of 100 is a scoring result, not an aesthetic grade or a zero-risk guarantee.**

## Three outcomes people can act on

| Result | What to do |
|---|---|
| Ready to send | No high-confidence delivery problem was found; still perform the final human preview |
| Check before sending | Open the named slides and confirm suggestions that need context or human judgment |
| Fix before sending | Resolve the listed blocker, save a separate delivery copy, and check again |

Repeated object-level findings are grouped in HTML so 200 instances of one root cause do not become 200 noisy tasks. Full evidence remains in JSON.

## Prove the edit

Keep the original and edit a separate copy:

```bash
uvx pptlint proof before.pptx after.pptx \
  --scenario present --output comparison
```

The proof pack separates resolved, remaining, and newly introduced findings.

Create a repair brief for a coding agent:

```bash
uvx pptlint plan pptlint-report.json --output repair-brief.md
```

The brief tells the agent to preserve the source and not damage an existing design merely to raise a score.

## Team delivery policy

```bash
uvx pptlint policy init pptlint-policy.yml
uvx pptlint check output.pptx --policy pptlint-policy.yml
```

Policies can define approved fonts and colors, minimum type size, and rules for external links, notes, hidden slides, and alt text. Unknown policy fields fail explicitly instead of being ignored.

## Scope and boundaries

| Delivery question | What PPTLint checks |
|---|---|
| Will the file open? | PPTX package structure, relationships, content types, media, slide list, and real rendering |
| Will people see it? | Off-canvas text, substantial overlap, clipping risk, type size, contrast, and aspect ratio |
| Will it survive another computer? | Fonts, external files, motion, transitions, audio, video, and notes relationships |
| Can someone edit it? | Native text, tables, charts, shapes, and full-slide image coverage |
| Is it safe to send? | Notes, comments, hidden slides, author data, local files, and external links |
| Is handoff practical? | Package size, duplicated media, embedded fonts, and dynamic-content facts |

PPTLint does not judge aesthetics, persuasion, or factual accuracy. Low-confidence hints never block delivery. Need to create or repair the deck first? Use [Ultimate PPT Master](https://github.com/kdnsna/ultimate-ppt-master-skill), then run PPTLint as the independent check.

## GitHub Actions

```yaml
- uses: kdnsna/pptlint@v0
  with:
    path: output.pptx
    profile: ai-generated
    renderer: wireframe
```

Reports are uploaded even when the check fails.

## Stable interfaces and development

- Current report: [`pptlint-report/v2`](schema/pptlint-report-v2.schema.json)
- Previous report: [`decklint-report/v1`](schema/decklint-report-v1.schema.json)
- Comparison: [`decklint-comparison/v1`](schema/decklint-comparison-v1.schema.json)
- Exit code `0`: completed; `1`: changes required; `2`: file or runtime error.

```bash
uv venv --python 3.13
uv pip install -e '.[dev]'
PYTHONPATH=src .venv/bin/python -m pytest
.venv/bin/ruff check src tests tools
```

`decklint` remains as a compatibility alias. All new documentation and commands use `pptlint`.

MIT · Local · Read-only · No upload · No model · No telemetry
