# Roadmap

DeckLint stays narrow: inspect presentations before delivery. New features require evidence from public issues or integrations.

## v0.1 — report-only foundation

- Local CLI, deterministic JSON, offline HTML, quality scoring, GitHub Action.
- No model calls, uploads, source modification, cloud service, or automatic repair.

## Candidate v0.2 work

- `.decklint.yml` policy overrides.
- SARIF and pull-request annotations.
- Brand-specific font/color policies.
- Additional renderers only where cross-platform fixtures prove fidelity.

Only the most requested and testable items should ship. DeckLint may become an optional pinned quality gate for Ultimate PPT Master after the report schema is stable; existing Ultimate PPT Master audit commands should retain compatibility wrappers for two minor releases.

PyPI release operations use tokenless trusted publishing; see `docs/publishing.md`.

## Candidate v0.3 work

Safe repair copies or Agent-assisted remediation may be explored only after high-confidence false-positive rates remain below 5% on real, shareable decks. The original PPTX must remain untouched.
