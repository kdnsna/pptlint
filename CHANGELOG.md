# Changelog

## 0.3.1 — 2026-07-11

- Put the plain-language delivery result first in the terminal and HTML report.
- Print the three most important slide-level actions directly in the terminal.
- Move scores, rule identifiers, renderer names, and other technical details behind optional sections.
- Make the coding-agent instruction the first action on the public homepage.

## 0.3.0 — 2026-07-11

- Rename the primary product and package to PPTLint while keeping the previous command available through v0.4.
- Add `pptlint check`, `pptlint-report/v2`, plain-language delivery results, and three priority actions.
- Add content-type, blank-slide, substantial text-overlap, clipping-risk, font-portability, aspect-ratio, and editability checks.
- Replace the score-first report and homepage with a ready, review, or blocked result for ordinary PowerPoint users.

## 0.2.0 — 2026-07-11

- Add deterministic before/after comparison with resolved, persistent, and new findings.
- Add `decklint-comparison/v1`, a Chinese-first offline comparison report, and regression gates.
- Infer semantic titles for editable AI-generated slides without weakening the baseline profile.
- Add the documented Ultimate PPT Master repair loop while keeping DeckLint read-only.
- Publish a reproducible Proof Loop case study: 49→100, 103 findings resolved, and zero new findings.
- Add an offline GitHub Pages product surface with downloadable PPTX, JSON, and HTML evidence.

## 0.1.0 — 2026-07-11

- Add deterministic local PPTX parsing with package safety limits.
- Add integrity, readability, editability, consistency, accessibility, and privacy findings.
- Add transparent weighted scoring and the `decklint-report/v1` JSON Schema.
- Publish category weights, scoring policy, per-finding deductions, caps, and calculation state in JSON and HTML.
- Add self-contained HTML reports with wireframe and optional LibreOffice previews.
- Add CLI, Agent Skill, composite GitHub Action, 30-case synthetic corpus, and good/bad proof reports.
