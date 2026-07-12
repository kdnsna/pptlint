# PPTLint Verified Delivery Requirements

## Goal

Turn PPTLint from a read-only checker into a local, source-preserving delivery workflow that can describe every repair task, perform only explicitly approved privacy cleanup in a copy, and independently verify the result.

## User stories

1. As an agent-assisted creator, I want a complete machine-readable repair plan so my chosen agent can act without inventing scope.
2. As a nontechnical PowerPoint user, I want exact next actions and a local drag-and-drop flow so I can finish delivery without understanding the CLI.
3. As a privacy-conscious user, I want to approve each cleanup operation and keep the source unchanged.
4. As a generator maintainer, I want a stable verification contract and GitHub Action inputs so delivery checks can run in CI.

## Acceptance requirements

- When public proof files are generated, the repository shall derive every public score and count from the checked-in current-version comparison JSON.
- When a user runs `pptlint plan`, PPTLint shall cover every issue group and shall classify unknown rules as human decisions.
- When a repair plan is generated, it shall contain stable task IDs, targets, repair mode, risk, executors, and machine-checkable acceptance criteria without source text or absolute paths.
- When a user requests cleanup, PPTLint shall require one or more explicit operations and shall write only to a new output path.
- When cleanup completes, PPTLint shall verify the output before atomic publication and shall emit a receipt and repair verification.
- When a user runs `pptlint app`, the app shall bind only to loopback, use a session token, keep files in a private temporary directory, make no external requests, and remove temporary files on shutdown.
- While an issue needs layout, semantic, hidden-slide, external-link, font, color, relationship, or media judgment, PPTLint shall not modify it automatically.
- Existing `pptlint-report/v2` and comparison interfaces shall remain readable and valid.

## Non-goals

- A cloud upload service, model calls, telemetry, aesthetic scoring, automatic slide design, or source-file overwrite.
- A PowerPoint add-in or packaged desktop installer in the first local-app release.
