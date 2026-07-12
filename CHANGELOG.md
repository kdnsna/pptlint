# Changelog

## 1.3.0 — 2026-07-12

- Add `pptlint app`, a Chinese drag-and-drop workflow bound only to a random `127.0.0.1` port with a per-session token.
- Keep uploads and artifacts in a permission-restricted temporary session directory and delete it when the app closes.
- Support local check, explicit cleanup selection, complete Agent brief copy, repaired-copy verification, and Proof Pack download without external requests or telemetry.
- Generate `pptlint-verified/v1` JSON and a linked SVG badge only when every repair task is verified and no high-confidence regression appears.
- Validate the complete workflow at desktop and 390 px mobile widths with no horizontal overflow.

## 1.2.0 — 2026-07-12

- Add `pptlint fix` for three explicitly authorized operations: clear author metadata, remove comments, and remove speaker-note text.
- Always write a new output file through a reserved path and validated temporary PPTX; never overwrite the source or an existing output.
- Generate `pptlint-repair-receipt/v1`, before/after reports, and a comparison report for every successful cleanup copy.
- Add `pptlint proof --plan` and `pptlint-repair-verification/v1` to classify completed, remaining, unconfirmed, and regressed repair tasks.
- Return `1` when a requested operation did not apply, the output remains blocked, or repair verification fails; reserve `2` for file and runtime errors.

## 1.1.0 — 2026-07-12

- Add the complete `pptlint-repair-plan/v1` protocol with stable task IDs, source identity, locations, repair modes, risk, executors, and machine-verifiable acceptance criteria.
- Cover every built-in rule through a central repair catalog; unknown rules fail safe to `human-decision`.
- Generate complete briefs for generic agents, Ultimate PPT Master, PowerPoint Copilot, and manual PowerPoint work instead of limiting plans to three priority items.
- Show the safe repair path beside each report finding and upload the machine-readable repair plan from the GitHub Action.

## 1.0.1 — 2026-07-12

- Restore a verifiable release path after the parallel 1.0 merge and keep the public package, source version, and generated proof in sync.
- Make CI fail when committed Proof Loop metrics or public claims no longer match the current comparison JSON.
- Publish immutable package artifacts and advance the matching major Action tag only after the public package passes smoke tests.

## 1.0.0 — 2026-07-12

- Add `pptlint start` to check a deck and open its offline report in one command.
- Add `pptlint doctor` and `pptlint --version` for supportable local diagnostics.
- Add documented policy exceptions with page scope, business reason, expiry, and matched counts.
- Exercise the installed CLI, diagnostics, generated public assets, and documentation contracts in CI.

## 0.8.0 — 2026-07-12

- Make Chinese reports consistently Chinese, including messages, impact labels, scores, run details, and page summaries.
- Add sticky page navigation and action filters for must-fix, review, and advisory findings.
- Warn that full reports are as sensitive as the source presentation.
- Add `--report-mode shareable` to redact filenames, slide titles, previews, and object-level evidence.

## 0.7.1 — 2026-07-12

- Align the package description, release instructions, public tests, and generated case pages.
- Replace invalid case-lab `--rule` examples with a command supported by the published CLI contract.
- Emit one valid HTML document for the case lab and verify public commands in tests.
- Regenerate the public Proof Loop with the current Chinese report contract.

## 0.7.0 — 2026-07-12

- Launch the Delivery Lab with 12 complete before/after risk demonstrations.
- Separate controlled demonstrations from attributed audits of four public AI PowerPoint samples.
- Add individual evidence pages for readability, portability, privacy, editability, package integrity, file size, and team policy cases.
- Link the product homepage directly to the case lab and verify generated pages in CI and Pages deployment.

## 0.6.0 — 2026-07-12

- Add package, media, animation, transition, audio, video, chart, and table handoff facts.
- Flag large packages, duplicated media, and motion or media portability risks without judging aesthetics.
- Add optional YAML delivery policies for approved fonts, colors, minimum type, privacy, links, and alt text.
- Add `pptlint policy init` and `pptlint plan` for a safe policy template and an agent-ready repair brief.

## 0.5.0 — 2026-07-12

- Add `--scenario present|screen|document` so readability checks match the real delivery setting.
- Ignore sub-pixel canvas rounding instead of blocking an otherwise valid deck.
- Treat missing notes-only relationships as review items rather than broken-slide blockers.
- Group repeated occurrences by rule in JSON and HTML so one root cause does not flood the report.

## 0.4.0 — 2026-07-12

- Add `pptlint proof BEFORE.pptx AFTER.pptx` for a complete local before/after evidence pack.
- Check both files with identical settings and write the two source reports plus one comparison report.
- Summarize score change, resolved reminders, remaining reminders, new reminders, and new high-confidence problems in the terminal.
- Keep the source presentations unchanged and state the score boundary in every proof run.

## 0.3.2 — 2026-07-12

- Add `--lang zh-CN` for plain Chinese terminal guidance and action-first HTML reports.
- Add four delivery questions covering file integrity, presentation, editability, and hidden information.
- Add concrete consequences and practical review steps for the checks used in public launch examples.
- State explicitly that 100 is a rule-check score, not an aesthetic grade or a zero-risk guarantee.

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
