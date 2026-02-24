# Release Process

This document describes the release process for Botanu SDK.

## Versioning

Botanu SDK follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Breaking changes to public API
- **MINOR** (0.2.0): New features, backwards compatible
- **PATCH** (0.1.1): Bug fixes, backwards compatible

Pre-release versions use suffixes:
- `-alpha.N`: Early development, unstable
- `-beta.N`: Feature complete, testing
- `-rc.N`: Release candidate, final testing

## Prerequisites

Before releasing, ensure:

1. All CI checks pass on `main` branch
2. CHANGELOG.md is updated with release notes
3. Documentation is up to date
4. Test coverage meets threshold (70%+)

## Release Workflow

### 1. Prepare the Release

```bash
# Ensure you're on main with latest changes
git checkout main
git pull origin main

# Update CHANGELOG.md
# - Move items from [Unreleased] to new version section
# - Add release date
# - Update comparison links at bottom

# Commit changelog
git add CHANGELOG.md
git commit -s -m "docs: prepare release v0.1.0"
git push origin main
```

### 2. Create a Release Tag

```bash
# For production release
git tag -a v0.1.0 -m "Release v0.1.0"

# For pre-release
git tag -a v0.1.0-alpha.1 -m "Release v0.1.0-alpha.1"

# Push tag
git push origin v0.1.0
```

### 3. Automated Publishing

When a tag is pushed:

- **Pre-release tags** (`v*-alpha*`, `v*-beta*`, `v*-rc*`) → TestPyPI
- **Release tags** (`v*` without suffix) → PyPI + GitHub Release

The workflow uses [Trusted Publishing (OIDC)](https://docs.pypi.org/trusted-publishers/) — no API tokens needed.

### 4. Manual Publishing (if needed)

You can manually trigger publishing from the Actions tab:

1. Go to Actions → "Release to PyPI"
2. Click "Run workflow"
3. Select target: `testpypi` or `pypi`
4. Click "Run workflow"

## TestPyPI Verification

After publishing to TestPyPI, verify installation:

```bash
# Create a test environment
python -m venv test-env
source test-env/bin/activate  # or test-env\Scripts\activate on Windows

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    botanu

# Verify import
python -c "import botanu; print(botanu.__version__)"

# Run quick test
python -c "
from botanu import enable, botanu_workflow
enable(service_name='test')
print('Botanu SDK loaded successfully!')
"
```

## PyPI Trusted Publishing Setup

### Initial Setup (One-time)

1. **Create PyPI project** (if not exists):
   - Go to https://pypi.org/manage/projects/
   - Create new project named `botanu`

2. **Configure Trusted Publisher on PyPI**:
   - Go to https://pypi.org/manage/project/botanu/settings/publishing/
   - Add new publisher:
     - Owner: `botanu-ai`
     - Repository: `botanu-sdk-python`
     - Workflow: `release.yml`
     - Environment: `pypi`

3. **Configure Trusted Publisher on TestPyPI**:
   - Go to https://test.pypi.org/manage/project/botanu/settings/publishing/
   - Add new publisher with same settings, environment: `testpypi`

4. **Create GitHub Environments**:
   - Go to repo Settings → Environments
   - Create `pypi` environment (for production)
   - Create `testpypi` environment (for testing)
   - Optionally add protection rules (required reviewers, etc.)

## Local Build Verification

Before releasing, verify the build locally:

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Check the package
twine check dist/*

# List contents
tar -tvf dist/botanu-*.tar.gz
unzip -l dist/botanu-*.whl

# Test installation from local wheel
pip install dist/botanu-*.whl
python -c "import botanu; print(botanu.__version__)"
```

## Version Determination

The version is determined by `hatch-vcs` from git tags:

- Tagged commit: `0.1.0`
- Commits after tag: `0.1.1.dev3+g1234567`
- No tags: `0.0.0.dev0`

To see what version will be used:

```bash
pip install hatch-vcs
python -c "from setuptools_scm import get_version; print(get_version())"
```

## Rollback Procedure

If a release has issues:

1. **Yank from PyPI** (hides from install, but doesn't delete):
   ```bash
   # Via web UI: PyPI project → Release history → Yank
   # Or via API (requires token)
   ```

2. **Delete GitHub Release** (if needed):
   ```bash
   gh release delete v0.1.0 --yes
   git push origin --delete v0.1.0
   ```

3. **Fix and re-release** with a new patch version (e.g., `v0.1.1`)

## Release Checklist

- [ ] All CI checks pass
- [ ] CHANGELOG.md updated
- [ ] Documentation updated
- [ ] Version tag follows semver
- [ ] Tag pushed to origin
- [ ] TestPyPI verification passed (for major releases)
- [ ] PyPI package visible
- [ ] GitHub Release created
- [ ] Announcement posted (if applicable)

## Maintainers

See [MAINTAINERS.md](./MAINTAINERS.md) for the list of release maintainers.
