# Releasing TeslaCam Telemetry

Releases are published from version tags. The release workflow builds the package, runs tests, checks package metadata, and attaches the built distributions to a GitHub Release.

## Current release target

- Package version: `0.1.0`
- First tag: `v0.1.0`

## Release checklist

1. Confirm `main` is clean and CI is passing.
2. Confirm `pyproject.toml` has the intended version.
3. Confirm `CHANGELOG.md` has notes for the release.
4. Create and push the version tag:

   ```bash
   git switch main
   git pull --ff-only origin main
   git tag v0.1.0
   git push origin v0.1.0
   ```

5. Watch the `Release` GitHub Actions workflow.
6. Confirm the GitHub Release exists and includes package artifacts from `dist/`.

## Notes

- This does not publish to PyPI yet.
- For now, users install from the repository with `python -m pip install .`.
- A future release stage can add PyPI publishing or Windows executable builds.
