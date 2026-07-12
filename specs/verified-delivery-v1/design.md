# PPTLint Verified Delivery Design

## Architecture

The existing audit engine remains the source of truth. New modules sit downstream:

1. `repair_catalog` maps every rule to a deterministic repair classification.
2. `repair_plan` groups all findings and emits `pptlint-repair-plan/v1` plus adapter-specific Markdown.
3. `cleanup` applies only approved privacy operations to an atomic copy and emits `pptlint-repair-receipt/v1`.
4. `repair_verification` maps before/after comparison evidence back to planned tasks.
5. `local_app` exposes the same services through a loopback-only browser flow.

The audit report v2 remains unchanged. Repair plans, receipts, and verification are separate versioned documents.

## Repair modes

- `cleanup-copy`: explicit deterministic copy cleanup.
- `guided-powerpoint`: exact manual PowerPoint steps.
- `agent-rebuild`: layout or semantic reconstruction by an external executor.
- `human-decision`: uncertain or destructive work that requires approval first.

Only `clear-personal-metadata`, `remove-comments`, and `remove-speaker-notes` are executable by PPTLint v0.9.

## Local application

`pptlint app` uses a small optional local HTTP service and static HTML/JS. It binds to `127.0.0.1` with port `0`, authenticates mutating requests with a random bearer token, writes uploads to a mode-0700 temporary directory, and returns generated artifacts as downloads. No hosted backend or external asset is used.

## Compatibility and rollout

- v0.7.1 restores public proof and package consistency.
- v0.8 adds repair-plan generation without changing report v2.
- v0.9 adds cleanup, receipt, and verification.
- v1.0 adds the optional local app.
- Each version is independently committed, tested, and released only after previous-version smoke tests pass.
