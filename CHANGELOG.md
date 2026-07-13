# Changelog

This file separates versions that were actually published from internal development milestones that never had a PyPI release or Git tag.

## Unreleased

- Ignore explicit ZIP directory entries when validating OOXML content types; older PowerPoint files can contain these harmless entries and must not be capped as critically damaged.
- Keep one-click Ultimate repair limited to page-scoped visual tasks, show selected page and task counts, and leave accessibility, metadata, external-link, and deck-level decisions on the manual path.
- Turn every local-app finding into a visible outcome plus concrete PowerPoint desktop steps instead of hiding the useful guidance in downloaded reports.
- Let users choose between manual adjustment and targeted Ultimate PPT Master repair while locking exact text, numbers, slide count, order, and all unselected slides.
- Reuse the existing loopback Ultimate Bridge and Agent launch contracts; fall back to a copyable command when the Bridge or auto-launch is unavailable.
- Improve desktop/mobile hierarchy and report wrapping without changing checking rules, CLI commands, or published JSON schemas.

## Published releases

### 1.3.1 — 2026-07-13

- Reconcile the homepage, Case Lab, Proof Loop, README files, package metadata, and release notes with current behavior and evidence.
- Publish the complete `83 → 100 / 103 resolved / 21 persistent / 3 new low-confidence / 0 new high-confidence` Proof Loop without implying that 100 means zero reminders.
- Regenerate the 33 fixed-source public-sample validation and derive featured-sample claims from its JSON instead of hand-maintained values.
- Correct Chinese report text, DeckLint deprecation guidance, mobile navigation, keyboard focus, filter state, sharing metadata, sitemap coverage, and site contracts.
- Add Python 3.14 classification and CI coverage without changing the CLI, JSON schemas, repair modes, or checking rules.

### 1.3.0 — 2026-07-12

- Add `pptlint app`, a local Chinese drag-and-drop workflow bound only to a random `127.0.0.1` port with a per-session token.
- Keep uploads and artifacts in a permission-restricted temporary session directory and delete it when the app closes.
- Support local check, explicit cleanup selection, complete Agent brief copy, repaired-copy verification, and Proof Pack download without external requests or telemetry.
- Generate `pptlint-verified/v1` JSON and a linked SVG badge only when every repair task is verified and no high-confidence regression appears.

### 1.2.0 — 2026-07-12

- Add `pptlint fix` for explicitly authorized author-metadata, comment, and speaker-note cleanup.
- Always write a new output file through a validated temporary PPTX; never overwrite the source or an existing output.
- Generate a repair receipt, before/after reports, and repair verification for every cleanup copy.

### 1.1.0 — 2026-07-12

- Add the complete `pptlint-repair-plan/v1` protocol with stable task IDs, repair modes, risks, executors, and acceptance criteria.
- Cover every built-in rule through a central repair catalog; unknown rules fail safe to `human-decision`.
- Generate complete briefs for generic Agents, Ultimate PPT Master, PowerPoint Copilot, and manual PowerPoint work.

### 1.0.1 — 2026-07-12

- Restore a verifiable release path after parallel 1.0 development and keep the public package, source version, and generated proof in sync.
- Make CI fail when committed Proof Loop metrics or public claims no longer match the current comparison JSON.
- Publish package artifacts and advance the matching major Action tag only after the public package passes smoke tests.

### 0.7.1 — 2026-07-12

- Align package description, release instructions, public tests, and generated case pages.
- Replace invalid Case Lab command examples and regenerate the public Proof Loop with the current Chinese report contract.

### 0.3.1 — 2026-07-11

- Put the plain-language delivery result first in terminal and HTML reports.
- Print the three most important slide-level actions directly in the terminal.
- Move scores, rule identifiers, renderer names, and other technical details behind optional sections.

### 0.3.0 — 2026-07-11

- Rename the primary product and package to PPTLint while keeping `decklint` as a deprecated compatibility alias.
- Add `pptlint check`, `pptlint-report/v2`, plain-language delivery results, and three priority actions.
- Add content-type, blank-slide, overlap, clipping-risk, font-portability, aspect-ratio, and editability checks.

## Internal milestones — not published or tagged

The following versions were development checkpoints only. Their capabilities were included in later published releases; they must not be treated as historical PyPI versions or Git tags.

### 1.0.0 — internal milestone

- Added `pptlint start`, `pptlint doctor`, policy exceptions, and installed-CLI contract checks.

### 0.8.0 — internal milestone

- Added consistent Chinese reports, action filters, shareable-report redaction, and report sensitivity guidance.

### 0.7.0 — internal milestone

- Added the Delivery Lab, controlled demonstrations, and attributed public-sample audits.

### 0.6.0 — internal milestone

- Added package, media, motion, chart, table, policy, and initial repair-plan facts.

### 0.5.0 — internal milestone

- Added presentation scenarios, grouped repeated findings, and safer package interpretation.

### 0.4.0 — internal milestone

- Added local before/after Proof reports and regression gates.

### 0.3.2 — internal milestone

- Added Chinese terminal/report guidance and the explicit score boundary.

### 0.2.0 — internal milestone

- Added deterministic comparison and the first public Proof Loop.

### 0.1.0 — internal milestone

- Added local PPTX parsing, core findings, scoring, JSON schema, reports, CLI, Agent Skill, GitHub Action, and the synthetic corpus.
