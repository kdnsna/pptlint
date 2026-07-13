# Moving from DeckLint to PPTLint

DeckLint v0.2 has moved to PPTLint v0.3. The old project remains available so existing GitHub Actions do not stop unexpectedly.

## Commands

Replace:

```bash
decklint audit slides.pptx --output report
```

with:

```bash
pptlint check slides.pptx --output report
```

The old `decklint` command remains as a deprecated compatibility alias and prints a migration reminder. New workflows should use `pptlint` directly.

## GitHub Actions

New workflows should use:

```yaml
- uses: kdnsna/pptlint@v0
```

The archived `kdnsna/decklint@v0` action stays pinned to the v0.2 behavior. GitHub does not redirect Action calls when a repository is renamed, so the two repositories coexist during migration.

## Reports

PPTLint writes `pptlint-report/v2`. It adds a delivery result, up to three priority actions, practical impact, and PowerPoint repair steps. `pptlint compare` continues to read existing `decklint-report/v1` files.
