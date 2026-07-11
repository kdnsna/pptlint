# PPTLint promotion-aligned v0.4 requirements

## Goal

Make the public product experience match the launch promise without claiming that a rule-based checker can guarantee visual perfection, predict every edit, or repair the source file.

## Version 0.3.2 — delivery check people can understand

1. `pptlint check` keeps its current English output by default and accepts `--lang zh-CN`.
2. The terminal and HTML report lead with the delivery consequence and next action, not rule IDs or the score.
3. The report groups the supported checks into four questions:
   - Can the file open reliably?
   - Can people read and present it?
   - Can the next person edit it?
   - Is hidden or linked information leaving with it?
4. All promoted checks receive a concrete impact and a practical three-step review path.
5. The JSON contract exposes the selected language and the four delivery checks while retaining `pptlint-report/v2` compatibility.
6. A score of 100 is described only as the rule score for this run.

## Version 0.4.0 — one-command proof loop

1. Add `pptlint proof BEFORE.pptx AFTER.pptx`.
2. The command checks both decks with the same profile and renderer, then creates:
   - before HTML and JSON reports;
   - after HTML and JSON reports;
   - one comparison HTML and JSON report.
3. The terminal states score change, resolved count, remaining count, new count, and regression result.
4. `--lang zh-CN` produces Chinese terminal guidance and a Chinese action-first comparison report.
5. The command remains local and read-only; input files are never modified or uploaded.
6. Existing `check`, `audit`, `compare`, and `decklint` compatibility continue to work.

## Truth boundaries

- Text clipping, overlap, font portability, and contrast findings are risk signals, not guarantees of how every computer or projector will render.
- A future edit shifting the layout cannot be predicted; PPTLint reports current structural risks.
- A score of 100 is neither an aesthetic grade nor a zero-risk guarantee.
- PPTLint does not repair the deck.

## Acceptance

- Full pytest suite, Ruff, source/wheel build, schema validation, and public-contract tests pass.
- `proof` is exercised on real PPTX fixtures and its four artifacts are readable.
- HTML has no horizontal overflow at 390 px and stays usable at 1280 px.
- Documentation uses `pptlint`, with `decklint` identified only as a compatibility command.
