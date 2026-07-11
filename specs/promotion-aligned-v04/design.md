# Design

## Compatibility strategy

The report schema remains `pptlint-report/v2`. New producers always write the added top-level fields, while the schema keeps them optional so committed and third-party v2 reports remain valid. Comparison readers continue to accept older v2 reports. CLI defaults do not change.

## Delivery checklist

`build_report` derives four deterministic checklist entries from finding categories and rule families. Each entry has an id, status (`pass`, `review`, or `fix`), label, summary, and finding count. High-confidence blocker findings produce `fix`; other findings produce `review`; absence produces `pass`.

The privacy entry covers notes, hidden slides, comments, metadata, and external relationships. Editability covers flattened full-slide images. Presentation covers readability and accessibility. File integrity covers package integrity.

## Localization

Language is an output concern, not a rule concern. Findings preserve stable rule IDs and technical evidence. `readiness` supplies localized user impact and repair steps. HTML and terminal labels use a compact bilingual message table. English remains the default to preserve scripts and tests.

## Proof command

The CLI extracts a shared `_check_file` operation. `proof` invokes it twice, writes reports under `<output>-before` and `<output>-after`, then feeds those in-memory reports to the existing comparison builder. This avoids reparsing JSON and guarantees the same settings on both sides.

The comparison JSON keeps `decklint-comparison/v1` for compatibility. It adds no claims beyond the existing matching algorithm: findings are paired by rule and slide, so “resolved” means the corresponding reported item no longer appears under that matching rule.

## Failure behavior

- Invalid PPTX or rendering failure exits 2 and explains which side failed.
- A failed regression gate exits 1 after still writing all reports.
- `check` remains blocked when a high-confidence delivery blocker exists.
