# Public AI-PPT compatibility validation

This validation checks whether current PPTLint can safely parse, audit, and create a complete repair plan for pinned public AI-PPT exports. It is not a visual ranking of the generators and does not redistribute their PPTX files.

Current result for PPTLint 1.3.2:

- 33 public PPTX files, 383 slides, 198,731,251 downloaded bytes;
- PPT Master 21, PPTAgent 9, Presenton 1, Ultimate PPT Master 2;
- 33 audits completed and 0 package-load failures;
- 7,464 findings and 7,464 repair tasks, for 100% repair-plan coverage;
- source URL, pinned revision where available, byte size, SHA-256, readiness, score, and repair-mode counts are recorded in [`public-sample-validation.json`](public-sample-validation.json).

The pinned Presenton repository contains no committed PPTX sample, so its entry uses one public export from Presenton's public export host. Ultimate's two samples are public immutable Proof Loop exports produced by Ultimate PPT Master.

Run the validation without retaining third-party files:

```bash
PYTHONPATH=src:. .venv/bin/python tools/validate_public_samples.py
```

The command downloads into a permission-scoped temporary directory and removes every PPTX when it exits. This validates compatibility and repair-plan completeness; it does not claim that an Agent already resolved every task or replace the separate real-user completion study.
