# Publishing

## GitHub release

1. Run the full verification commands from `CONTRIBUTING.md`.
2. Tag the verified main commit with the exact version from `pyproject.toml` and update the floating composite-action tag `v0` to the same commit.
3. Create a GitHub release using the matching changelog section and attach the wheel and source archive from `dist/`.

## PyPI trusted publishing

PPTLint does not store a PyPI token in GitHub.

Before the first publish, create the `pptlint` project or a pending trusted publisher in PyPI and authorize:

- Owner: `kdnsna`
- Repository: `pptlint`
- Workflow: `publish-pypi.yml`
- Environment: `pypi`

Then run the **Publish to PyPI** workflow manually and enter the exact version from `pyproject.toml`. The workflow checks the version, builds in a clean job, and publishes through GitHub OIDC. A manual trigger prevents an unconfigured or accidental GitHub release from attempting a package upload.
