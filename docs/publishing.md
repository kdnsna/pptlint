# Publishing

## GitHub release

1. Run the full verification commands from `CONTRIBUTING.md`.
2. Tag the verified main commit as `v0.3.0` and update the floating composite-action tag `v0` to the same commit.
3. Create a GitHub release using the matching changelog section and attach the wheel and source archive from `dist/`.

## PyPI trusted publishing

PPTLint does not store a PyPI token in GitHub.

Before the first publish, create the `pptlint` project or a pending trusted publisher in PyPI and authorize:

- Owner: `kdnsna`
- Repository: `pptlint`
- Workflow: `publish-pypi.yml`
- Environment: `pypi`

Then run the **Publish to PyPI** workflow manually and enter the exact version from `pyproject.toml`. The workflow checks the version, builds and smoke-tests a clean wheel, publishes through GitHub OIDC, verifies the public PyPI package, creates the immutable GitHub Release, and finally advances the floating `v0` Action tag. A manual trigger prevents an accidental package upload.
