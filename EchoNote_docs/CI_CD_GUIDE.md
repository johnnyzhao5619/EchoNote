# CI/CD Guide

This document describes the Continuous Integration and Continuous Deployment (CI/CD) setup for EchoNote.

## Overview

EchoNote uses GitHub Actions for automated testing, code quality checks, building, and releasing. The CI/CD pipeline ensures code quality and reliability across multiple platforms and Python versions.

## Workflows

### 1. Test Suite (`.github/workflows/ci.yml`)

**Triggers:**

- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Matrix:**

- **Operating Systems:** Ubuntu, Windows, macOS
- **Python Versions:** 3.10, 3.11, 3.12

**Steps:**

1. Checkout code
2. Set up Python with pip caching
3. Install system dependencies (platform-specific)
4. Install Python dependencies
5. Verify PySide6 installation
6. Run tests with coverage
7. Upload coverage to Codecov

**Coverage:**

- Modules: `core`, `engines`, `data`, `utils`, `ui`
- Format: XML (for Codecov) + terminal output
- Target: 70%+

### 2. Code Quality (`.github/workflows/quality-check.yml`)

**Triggers:**

- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Jobs:**

#### Lint

- **Black:** Code formatting check
- **isort:** Import sorting check
- **flake8:** Linting
- **mypy:** Type checking (continue-on-error)
- **bandit:** Security scanning (continue-on-error)

#### Security

- **Bandit:** Security vulnerability scanning
- **Safety:** Dependency vulnerability check

### 3. Build (`.github/workflows/build.yml`)

**Triggers:**

- Push tags matching `v*` (e.g., `v1.2.0`)
- Manual workflow dispatch

**Matrix:**

- **Ubuntu:** Builds Linux executable
- **Windows:** Builds Windows executable
- **macOS:** Builds macOS app bundle + DMG

**Steps:**

1. Validate release (run tests + quality checks)
2. Build for each platform using PyInstaller
3. Upload artifacts (30-day retention)
4. Create GitHub Release (if triggered by tag)

**Artifacts:**

- `echonote-linux`: Linux executable
- `echonote-windows`: Windows executable
- `echonote-macos`: macOS app bundle + DMG

### 4. Release (`.github/workflows/release.yml`)

**Triggers:**

- Push tags matching `v*.*.*` (semantic versioning)
- Manual workflow dispatch with version input

**Steps:**

1. **Validate:** Run full test suite and quality checks
2. **Build:** Build for all platforms (Linux, Windows, macOS)
3. **Release:** Create GitHub Release with:
   - All platform artifacts
   - Auto-generated release notes from git history
   - Custom release notes from `RELEASE_NOTES_v*.md` (if exists)
   - Prerelease flag for alpha/beta/rc versions

## Setup Instructions

### 1. Codecov Integration

1. Sign up at [codecov.io](https://codecov.io)
2. Add your repository
3. Get the `CODECOV_TOKEN`
4. Add it to GitHub repository secrets:
   - Go to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `CODECOV_TOKEN`
   - Value: Your token from Codecov

### 2. Update README Badges

Replace `YOUR_USERNAME` in `README.md` with your GitHub username:

```markdown
[![CI Status](https://github.com/YOUR_USERNAME/EchoNote/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/EchoNote/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/YOUR_USERNAME/EchoNote/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/EchoNote)
```

### 3. Release Process

#### Automatic Release (Recommended)

1. Update version in relevant files
2. Create release notes file (optional): `RELEASE_NOTES_v1.2.0.md`
3. Commit changes
4. Create and push a tag:
   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```
5. GitHub Actions will automatically:
   - Run tests
   - Build for all platforms
   - Create GitHub Release
   - Upload artifacts

#### Manual Release

1. Go to Actions → Release workflow
2. Click "Run workflow"
3. Enter version (e.g., `v1.2.0`)
4. Click "Run workflow"

### 4. Pre-release Versions

For alpha, beta, or release candidate versions:

```bash
git tag v1.2.0-alpha.1
git tag v1.2.0-beta.1
git tag v1.2.0-rc.1
```

These will be automatically marked as "pre-release" on GitHub.

## Local Testing

### Run Tests Locally

```bash
# All tests
pytest tests/

# With coverage
pytest tests/ --cov=core --cov=engines --cov=data --cov=utils --cov=ui --cov-report=term-missing

# Specific test file
pytest tests/unit/core/test_transcription_manager.py -v
```

### Run Quality Checks Locally

```bash
# Format check
black --check .

# Import sorting check
isort --check .

# Linting
flake8 .

# Type checking
mypy .

# Security scan
bandit -c pyproject.toml -r .
```

### Run All Pre-commit Hooks

```bash
pre-commit run --all-files
```

## Build Locally

### Linux

```bash
python scripts/build_linux.py --clean
```

### Windows

```bash
python scripts/build_windows.py --clean
```

### macOS

```bash
python scripts/build_macos.py --clean --dmg
```

## Troubleshooting

### Tests Fail on CI but Pass Locally

1. **Platform differences:** Check if the failure is platform-specific
2. **Python version:** Ensure you're testing with the same Python version
3. **Dependencies:** Check if all dependencies are installed correctly
4. **Environment variables:** Some tests may depend on environment setup

### Coverage Upload Fails

1. Verify `CODECOV_TOKEN` is set correctly in repository secrets
2. Check Codecov service status
3. Ensure `coverage.xml` is generated correctly

### Build Fails

1. Check build script logs in GitHub Actions
2. Verify all system dependencies are installed
3. Test build locally on the same platform
4. Check PyInstaller compatibility with dependencies

### Release Creation Fails

1. Ensure you have `contents: write` permission
2. Verify tag format matches `v*.*.*`
3. Check if release notes file exists (if referenced)
4. Verify all artifacts were uploaded successfully

## Best Practices

1. **Always run tests locally** before pushing
2. **Use pre-commit hooks** to catch issues early
3. **Write meaningful commit messages** (they appear in release notes)
4. **Tag releases properly** using semantic versioning
5. **Test builds locally** before creating a release
6. **Monitor CI/CD runs** and fix failures promptly
7. **Keep dependencies updated** to avoid security issues

## Monitoring

### GitHub Actions

- View workflow runs: Repository → Actions
- Check test results, coverage, and build artifacts
- Download artifacts for testing

### Codecov

- View coverage reports: [codecov.io/gh/YOUR_USERNAME/EchoNote](https://codecov.io/gh/YOUR_USERNAME/EchoNote)
- Track coverage trends over time
- Review coverage by file and function

## Future Improvements

- [ ] Add performance benchmarking to CI
- [ ] Implement automatic dependency updates (Dependabot)
- [ ] Add Docker image builds
- [ ] Implement automatic changelog generation
- [ ] Add deployment to package registries (PyPI, Homebrew, etc.)
- [ ] Implement automatic documentation deployment
