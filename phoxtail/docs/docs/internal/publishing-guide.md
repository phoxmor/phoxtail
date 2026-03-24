# Publishing a New Version to PyPI

Step-by-step process for releasing a new version of `phoxtail`.

## Tooling decisions

- **uv** is the single tool for environment management and publishing. No twine needed.
- **`.venv/`** is the persistent development environment, created once with `uv venv`. You do not recreate it for each release — it's for running lint, tests, and the build command.
- **`python -m build`** creates its own isolated build environment internally, so the build is clean regardless of what's in `.venv/`.
- The **throwaway venv** in step 6 is the real isolation check — it simulates a fresh user install.

## Prerequisites

- uv installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- PyPI account with API token configured in `~/.pypirc` (permissions `600`)
- Dev environment set up: `uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"`
- `build` installed in the dev environment: `uv pip install build`

## Step 1: Prepare the release

### Update the version number

The version must be updated in **two** places — they must match:

```
phoxtail/__init__.py  →  __version__ = "0.2.0"
pyproject.toml        →  version = "0.2.0"
```

Version format follows semver at `0.x.y`:
- `0.x.0` — new features (e.g., deploy commands)
- `0.x.y` — bug fixes and patches

### Update README.md if needed

If new commands were added, update the commands table in `README.md`.

## Step 2: Activate the dev environment and run checks

```bash
source .venv/bin/activate
ruff check phoxtail/
ruff format phoxtail/ --check
pytest
```

All must pass. Do not proceed if anything fails.

## Step 3: Clean previous build artifacts

Old artifacts in `dist/` will cause upload conflicts or publish the wrong version.
Stale `.egg-info/` can cause phantom files to appear in the wheel.
Always start clean.

```bash
rm -rf build/ dist/ phoxtail.egg-info/
```

## Step 4: Build the package

This produces two files in `dist/`:
- `phoxtail-X.Y.Z.tar.gz` — the source distribution (sdist)
- `phoxtail-X.Y.Z-py3-none-any.whl` — the wheel (what pip installs)

```bash
python -m build
```

Note: `python -m build` creates its own temporary venv for the build process.
Your `.venv/` does not affect the build output.

## Step 5: Inspect the build

Never publish without checking what's inside.

### Check the wheel contents (what users install)

```bash
unzip -l dist/phoxtail-*.whl
```

Verify:
- `phoxtail/cli/` — all command modules, utilities, and templates present
- No `phoxtail/cli/tests/` directory
- No `phoxtail/core/` directory (excluded until v0.2.0)
- No `phoxtail/design/` directory (excluded until v0.2.0)
- No `phoxtail/streams/` directory (excluded until v0.2.0)
- No `phoxtail/project_template/` directory (excluded until v0.2.0)
- No `phoxtail/docs/` directory
- No `CLAUDE.md`
- No `uv.lock`
- No `.env` files

### Check the sdist contents

```bash
tar tzf dist/phoxtail-*.tar.gz | head -40
```

## Step 6: Test install locally

Install from the built wheel into a throwaway environment and verify the CLI works.
This catches issues that lint and tests cannot — missing package data, broken entry points, import errors.

```bash
# Create a throwaway venv (not your dev .venv)
python3 -m venv /tmp/phoxtail-release-test

# Install the wheel
/tmp/phoxtail-release-test/bin/pip install dist/phoxtail-*.whl

# Verify
/tmp/phoxtail-release-test/bin/phoxtail version
/tmp/phoxtail-release-test/bin/phoxtail --help

# Clean up
rm -rf /tmp/phoxtail-release-test
```

## Step 7: Push the commit

Push the release commit **before** publishing to PyPI. This order matters.

If you publish first and the push fails (merge conflict, hook rejection, permissions), you've got a released package on PyPI with no matching commit on the remote. PyPI does not allow re-uploading the same version — you'd be forced to bump to a new patch version for what should have been this release.

If you push first and the publish fails, no harm done — fix the issue and publish again.

```bash
git push
```

## Step 8: Publish to PyPI

```bash
uv publish dist/* --token <your-pypi-token>
```

The token is stored in `~/.pypirc` under the `[pypi]` password field. Copy it from there.
Note: `uv publish` does not read `~/.pypirc` automatically — the `--token` flag is required.

Alternatively, install and use twine which does read `~/.pypirc`:

```bash
pip install twine
twine upload dist/*
```

## Step 9: Verify the published package

```bash
# Wait a minute for PyPI to index, then:
pip install --upgrade phoxtail
phoxtail version
```

Also check the PyPI page: https://pypi.org/project/phoxtail/

## Step 10: Tag the release

Tag **after** a successful publish — the tag marks "this version was released", which should only be true once PyPI actually has it.

```bash
git tag v0.2.0
git push --tags
```

## Step 11: Post-publish token rotation (first release only)

After the first publish, the initial token has "Entire account" scope. Replace it:

1. Go to pypi.org → Account settings → API tokens
2. Delete the `phoxtail-publish-initial` token
3. Create a new token scoped to the `phoxtail` project only, name it `phoxtail-publish`
4. Update `~/.pypirc` with the new token

## Quick reference (copy-paste)

For subsequent releases after the first, the condensed flow:

```bash
source .venv/bin/activate

# 1. Update version in phoxtail/__init__.py and pyproject.toml

# 2. Lint, format, test
ruff check phoxtail/ && ruff format phoxtail/ --check && pytest

# 3. Clean, build, inspect
rm -rf build/ dist/ phoxtail.egg-info/
python -m build
unzip -l dist/phoxtail-*.whl

# 4. Test install
python3 -m venv /tmp/phoxtail-release-test
/tmp/phoxtail-release-test/bin/pip install dist/phoxtail-*.whl
/tmp/phoxtail-release-test/bin/phoxtail version
rm -rf /tmp/phoxtail-release-test

# 5. Push, publish, tag (this order matters — see steps 7-10)
git push
uv publish dist/* --token <your-pypi-token>
git tag vX.Y.Z && git push --tags
```

## Troubleshooting

### "File already exists" error
PyPI does not allow overwriting a published version. If 0.2.0 has a problem, fix it and publish 0.2.1.

### "Invalid or non-existent authentication" error
Check `~/.pypirc` — the password must include the `pypi-` prefix. Username must be literally `__token__`.

### Tests or lint fail
Do not publish. Fix the issues first. There is no undo on PyPI — a broken version is permanent.

### Wrong files in the wheel
Check `MANIFEST.in` and `[tool.setuptools.packages.find]` in `pyproject.toml`. Clean artifacts (`rm -rf build/ dist/ phoxtail.egg-info/`) and rebuild. Stale `.egg-info/` is a common cause of phantom files appearing in the wheel.
