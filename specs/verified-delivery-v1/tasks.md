# Implementation Plan

- [x] 1. Restore release and proof consistency
  - Regenerate current proof, replace stale public metrics, localize reports, expand Action inputs, and publish v0.7.1.
  - _Requirements: 1, 7_
- [x] 2. Add the open repair-plan contract
  - Build the catalog, schemas, complete plan generator, adapters, report actions, and Action artifact.
  - _Requirements: 2, 3, 7, 8_
- [x] 3. Add explicit cleanup copies
  - Implement three approved operations, atomic output, receipt, proof mapping, and failure semantics.
  - _Requirements: 4, 5, 7_
- [ ] 4. Add the local app
  - Implement loopback service, drag/drop audit, cleanup selection, agent instructions, repaired-copy verification, and downloads.
  - _Requirements: 6, 7_
- [ ] 5. Complete release validation
  - Run unit, contract, packaging, real-sample, browser, offline, and published-package smoke tests.
  - _Requirements: 1-8_
