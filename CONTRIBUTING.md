# Contributing

DeckLint accepts narrowly scoped rules with reproducible PPTX fixtures.

1. Open an issue describing the observable defect and why it can be judged deterministically.
2. Add a synthetic or openly licensed fixture; never commit private presentations.
3. Add a failing test that proves the rule's positive, negative, and boundary behavior.
4. Keep low-confidence visual heuristics advisory: they must not deduct points or fail CI.
5. Run `pytest`, `ruff check src tests tools`, `python -m build`, and `git diff --check`.

Every finding must include evidence and a concrete remediation. Rules that judge taste, factual truth, or business strategy are out of scope.

