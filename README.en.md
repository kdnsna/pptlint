# PPTLint

**Do not send a finished PowerPoint until you have checked the actual file.** A deck that looks fine on your computer can fail on a client machine or in a meeting room.

[Product](https://kdnsna.github.io/pptlint/) · [Case Lab](https://kdnsna.github.io/pptlint/lab/) · [Proof Loop](https://kdnsna.github.io/pptlint/proof-loop/comparison.html) · [中文](README.md)

![PPTLint PowerPoint delivery preflight](site/assets/readme-hero.svg)

PPTLint is a local `.pptx` delivery preflight tool. It checks the file without uploading it or calling a model, produces offline HTML and JSON reports, creates complete repair tasks, can clean a separate copy only after explicit authorization, and verifies the edited copy afterward.

## Quick start

```bash
uvx pptlint check output.pptx --scenario present
```

### What is `uvx`? What if it is not installed?

`uvx` is **not a protocol or a PPTLint command**. It is the tool runner included with [Astral uv](https://docs.astral.sh/uv/guides/tools/). It downloads and runs PPTLint in a temporary isolated environment, so a machine without `uv` will not have `uvx`. The first run requires network access.

Run `uvx --version` to check. If the command is missing, either [install uv](https://docs.astral.sh/uv/getting-started/installation/) or use an existing Python 3.10+ environment:

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pptlint
pptlint check output.pptx --scenario present
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pptlint
pptlint check output.pptx --scenario present
```

With the Python installation, replace `uvx pptlint` with `pptlint` in the commands below, and replace `uvx --refresh pptlint app` with `pptlint app`.

For the local drag-and-drop workflow:

```bash
uvx --refresh pptlint app
```

The app binds only to a random `127.0.0.1` port, makes no external requests, stores files in a restricted temporary directory, and deletes that directory when the session closes.

## What it catches

- text that may clip, overlap, or become unreadable during presentation;
- font and linked-content portability risks;
- image-only slides that are hard to edit or hand off;
- speaker notes, comments, hidden slides, author metadata, and external links;
- damaged package relationships, large files, duplicate media, and policy violations.

PPTLint does not score aesthetics, verify facts, or automatically redesign slides.

## Current public proof

The same editable nine-slide deck currently measures:

| Metric | Result |
|---|---:|
| Score | **83 → 100** |
| Resolved high-confidence findings | **103** |
| Persistent low-confidence reminders | **21** |
| New low-confidence reminders | **3** |
| New high-confidence findings | **0** |

The edited deck still has a **review** result: the score is 100 because no high-confidence scoring issue remains, not because the file has zero reminders or zero risk.

- [Open the complete Proof Loop](https://kdnsna.github.io/pptlint/proof-loop/comparison.html)
- [Browse 12 delivery-risk cases](https://kdnsna.github.io/pptlint/lab/)
- [Download the before deck](examples/proof-loop/before.pptx)
- [Download the after deck](examples/proof-loop/after.pptx)

The Case Lab also tracks 33 fixed-source public PPTX samples across 4 project families and 383 slides. All current samples complete successfully and repair-plan coverage is 100%. This is a compatibility check, not an aesthetic ranking.

## Repair and verification workflow

```bash
pptlint plan pptlint-report.json --format json --output repair-plan.json
pptlint plan pptlint-report.json --adapter generic-agent --output repair-brief.md

pptlint fix input.pptx \
  --output input.delivery.pptx \
  --apply clear-personal-metadata \
  --apply remove-comments \
  --apply remove-speaker-notes

pptlint proof before.pptx after.pptx --output comparison
```

Complex layout, hidden-slide, external-link, and image-only-slide decisions remain with a person, PowerPoint, or an editing Agent. PPTLint never overwrites the source file.

## GitHub Action

```yaml
- uses: kdnsna/pptlint@v1
  with:
    path: output.pptx
    scenario: present
    lang: en
    policy: pptlint-policy.yml
    artifact-name: pptlint-report
```

Use a full tag such as `kdnsna/pptlint@v1.3.1` when you need an immutable version reference.

## Security boundary

- `.pptx` only; legacy `.ppt` is not supported.
- Read-only by default; cleanup requires explicit operations and always writes a new file.
- No upload, model call, telemetry, external font, or analytics request.
- Full reports may contain slide previews, text, and document properties. Protect them like the source deck or generate a `--report-mode shareable` report.

The deprecated `decklint` command remains as a compatibility alias. New workflows should use `pptlint`.

[Issues](https://github.com/kdnsna/pptlint/issues) · [Migration guide](docs/migration-from-decklint.md) · [Changelog](CHANGELOG.md)

MIT License
