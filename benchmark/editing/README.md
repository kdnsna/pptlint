# PPTLint Real-World Editing Evaluation

This suite measures whether a tool can improve a real presentation without making the rest of the file slower, flatter, or less reliable. It is deliberately separate from the existing generation benchmark.

The first version contains 24 cases:

- 20 fixed-source editing cases across six anonymized business decks (111 slides total).
- 2 paper-to-deck cases: create a research briefing, then revise it for executives.
- 2 article-to-deck cases: create a public-service briefing, then revise it into an opportunity brief.

The six business inputs are private and are never committed. `sources.json` stores only aliases, hashes, slide counts, and environment-variable locators. The public source cases store URLs and fact anchors, not copied articles or papers.

## What this evaluation rewards

For fixed-source editing, the machine score is 85 points and the visual review is 15 points.

| Dimension | Points | Evidence |
| --- | ---: | --- |
| Correct source and valid output | 15 | Input hash, parseable PPTX, slide count, canvas |
| Requested change is actually complete | 25 | Text assertions and/or targeted PPTLint rule reduction |
| No unintended changes | 25 | Semantic fingerprints of every non-target slide |
| No new high-confidence delivery issue | 10 | Before/after rule multiset |
| Editability is preserved | 5 | Native-object ratio does not materially fall |
| Time remains practical | 5 | Per-case time budget |
| Visual result is genuinely better | 15 | Readability, hierarchy, alignment, brand continuity |

A run is blocked regardless of total score when the output is invalid, the source hash is wrong, slide count or canvas changes unexpectedly, the requested change is not evidenced, or a non-target slide changes.

To prevent a safe but unchanged file from looking successful, the machine score is capped at 40 when the requested edit is not completed. Invalid output is capped at 0, unexpected slide-count or canvas changes at 25, and out-of-scope slide changes at 55. The uncapped value remains in `rawMachine` for diagnosis.

The source-grounded track is reported separately. It evaluates content fidelity, information selection, citation, visual communication, and the quality of a second-round revision. Its score must not be averaged into the fixed-source editing score.

The latest representative current-product baseline is in [`results/`](results/).

## Manual and one-click paths

Every case contains both:

- `manualAdjustment`: steps a customer can perform in PowerPoint or WPS today.
- `productAction`: the desired single scoped outcome used to test a product, not a claim that the current PPTLint release can execute it.

The product action is not permission to redesign the whole deck. The allowed slides and hard acceptance criteria still apply.

For current-product guidance research, the 20 business cases are intentionally split into 14 lint-detectable delivery problems and 6 instruction-only content changes such as replacing a cover date or visible contact. Instruction-only changes are outside the current checker contract and are not counted as missed lint findings.

## Run the suite

Validate definitions and create a path-free run plan:

```bash
PYTHONPATH=src python tools/edit_eval.py validate
PYTHONPATH=src python tools/edit_eval.py plan
```

Verify private inputs without recording their paths in Git:

```bash
PYTHONPATH=src python tools/edit_eval.py validate \
  --source business-01=/absolute/path/to/source-01.pptx \
  --source business-02=/absolute/path/to/source-02.pptx
```

Alternatively set the `locatorEnv` variables declared in `sources.json` in the local run environment.

Audit whether the current product detects the 14 in-scope problems, selects a safe route, provides actionable manual steps, includes a recheck, and avoids false automation promises:

```bash
PYTHONPATH=src python tools/edit_eval.py guidance \
  --source business-01=/absolute/path/to/source-01.pptx \
  --source business-02=/absolute/path/to/source-02.pptx \
  --source business-03=/absolute/path/to/source-03.pptx \
  --source business-04=/absolute/path/to/source-04.pptx \
  --source business-05=/absolute/path/to/source-05.pptx \
  --source business-06=/absolute/path/to/source-06.pptx
```

The guidance result contains aliases, hashes, counts, routes and timings only. It never records local source paths or extracted business text.

Score a fixed-source editing output:

```bash
PYTHONPATH=src python tools/edit_eval.py evaluate business-01-cover-date \
  --source /absolute/path/to/source.pptx \
  --output-pptx /absolute/path/to/output.pptx \
  --duration 42 \
  --result /absolute/path/to/result.json
```

Add `--human-score 0..15` only after reviewing before/after renders at full-slide and 100% detail. Keep the source read-only and always save the result as a new file.

## Human visual review (15 points)

- Readability (0-5): the target content can be read at normal presentation distance; no clipping or illegible compression.
- Visual hierarchy (0-5): the key message, supporting evidence, and action are distinguishable within three seconds.
- Continuity (0-5): the change still looks like the same deck; alignment, spacing, colors, and object style remain coherent.

For source-grounded cases, use the case-specific rubric in addition to PPTLint's delivery checks. A polished slide with an unsupported fact is not a pass.

## Privacy boundary

- Do not commit private PPTX files, rendered slides, extracted text, speaker notes, contacts, or local paths.
- Public reports may use only the anonymized inventory in `baseline/source-inventory.json` and aggregate results.
- If a private source changes, update its hash and inventory only after reviewing whether the case still tests the same behavior.
