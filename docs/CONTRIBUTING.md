# Contributing to EchoNote

Thank you for your interest in contributing to EchoNote! This document provides guidelines and instructions for contributing to the project.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Coding Standards](#coding-standards)
5. [Testing Guidelines](#testing-guidelines)
6. [Documentation](#documentation)
7. [Pull Request Process](#pull-request-process)
8. [Issue Guidelines](#issue-guidelines)
9. [Community](#community)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of experience level, gender, gender identity and expression, sexual orientation, disability, personal appearance, body size, race, ethnicity, age, religion, or nationality.

### Our Standards

**Positive behaviors include:**

- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behaviors include:**

- Trolling, insulting/derogatory comments, and personal or political attacks
- Public or private harassment
- Publishing others' private information without explicit permission
- Other conduct which could reasonably be considered inappropriate

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported by contacting the project team. All complaints will be reviewed and investigated promptly and fairly.

---

## Getting Started

### Prerequisites

Before you begin, ensure you have:

- Python 3.8 or higher
- Git
- A GitHub account
- Basic knowledge of Python and PyQt6

### Setting Up Your Development Environment

1. **Fork the Repository**

   - Visit https://github.com/johnnyzhao5619/echonote
   - Click the "Fork" button in the top right

2. **Clone Your Fork**

   ```bash
   git clone https://github.com/johnnyzhao5619/echonote.git
   cd echonote
   ```

3. **Add Upstream Remote**

   ```bash
   git remote add upstream https://github.com/johnnyzhao5619/echonote.git
   ```

4. **Create Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

5. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

6. **Verify Installation**
   ```bash
   python main.py
   ```

---

## Development Workflow

### 1. Create a Feature Branch

Always create a new branch for your work:

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a new branch
git checkout -b feature/your-feature-name
```

**Branch Naming Conventions:**

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions or modifications
- `chore/` - Maintenance tasks

**Examples:**

- `feature/add-azure-speech-engine`
- `fix/transcription-progress-bar`
- `docs/update-api-reference`

### 2. Make Your Changes

- Write clean, readable code
- Follow the coding standards (see below)
- Add tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

### 3. Commit Your Changes

Use conventional commit messages:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

**Examples:**

```bash
git commit -m "feat(transcription): add support for MP4 video files"
git commit -m "fix(calendar): resolve sync token expiration issue"
git commit -m "docs(api): update TranscriptionManager documentation"
```

### 4. Keep Your Branch Updated

Regularly sync with upstream:

```bash
git fetch upstream
git rebase upstream/main
```

### 5. Push Your Changes

```bash
git push origin feature/your-feature-name
```

### 6. Create a Pull Request

1. Go to your fork on GitHub
2. Click "New Pull Request"
3. Select your feature branch
4. Fill out the PR template
5. Submit the PR

---

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

#### Line Length

- Maximum line length: **100 characters** (not 79)
- For docstrings and comments: **72 characters**

#### Indentation

- Use **4 spaces** per indentation level
- Never use tabs

#### Quotes

- Use **double quotes** for strings: `"hello"`
- Use single quotes for dict keys when appropriate: `{'key': 'value'}`

#### Imports

Group imports in the following order:

1. Standard library imports
2. Third-party imports
3. Local application imports

```python
# Standard library
import os
import sys
from datetime import datetime

# Third-party
from PyQt6.QtWidgets import QWidget
import numpy as np

# Local
from core.transcription.manager import TranscriptionManager
from utils.logger import setup_logging
```

#### Naming Conventions

- **Classes**: `PascalCase`

  ```python
  class TranscriptionManager:
      pass
  ```

- **Functions and Methods**: `snake_case`

  ```python
  def process_audio_file(file_path):
      pass
  ```

- **Constants**: `UPPER_SNAKE_CASE`

  ```python
  MAX_CONCURRENT_TASKS = 5
  DEFAULT_LANGUAGE = "en"
  ```

- **Private Methods**: Prefix with single underscore
  ```python
  def _internal_helper(self):
      pass
  ```

#### Type Hints

Always use type hints for function signatures:

```python
def transcribe_file(
    audio_path: str,
    language: str = "en",
    options: dict = None
) -> dict:
    """Transcribe an audio file."""
    pass
```

#### Docstrings

Use Google-style docstrings:

```python
def process_task(task_id: str, options: dict = None) -> bool:
    """
    Process a transcription task.

    This function processes a single transcription task from the queue.
    It handles audio loading, transcription, and result saving.

    Args:
        task_id: Unique identifier for the task
        options: Optional processing options
            - language (str): Language code
            - output_format (str): Output format

    Returns:
        True if processing succeeded, False otherwise.

    Raises:
        FileNotFoundError: If audio file doesn't exist
        ValueError: If task_id is invalid

    Example:
        >>> success = process_task("abc-123", {"language": "en"})
        >>> if success:
        ...     print("Task completed")
    """
    pass
```

### Code Formatting

Use `black` for automatic formatting:

```bash
# Format all files
black echonote/

# Format specific file
black echonote/core/transcription/manager.py

# Check without modifying
black --check echonote/
```

### Linting

Use `pylint` for code quality:

```bash
# Lint all files
pylint echonote/

# Lint specific file
pylint echonote/core/transcription/manager.py
```

### Error Handling

Always use specific exception types:

```python
# Good
try:
    result = process_file(path)
except FileNotFoundError as e:
    logger.error(f"File not found: {path}")
    raise
except ValueError as e:
    logger.error(f"Invalid file format: {e}")
    return None

# Bad
try:
    result = process_file(path)
except Exception as e:
    logger.error(f"Error: {e}")
    return None
```

### Logging

Use the application logger:

```python
import logging

logger = logging.getLogger(__name__)

# Log levels
logger.debug("Detailed information for debugging")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error")

# Include context
logger.info(f"Processing task {task_id} with language {language}")
```

---

## Testing Guidelines

### Writing Tests

#### Unit Tests

Place unit tests in `tests/unit/`:

```python
import pytest
from core.transcription.manager import TranscriptionManager

class TestTranscriptionManager:
    @pytest.fixture
    def manager(self, mock_db, mock_engine, mock_config):
        """Create a TranscriptionManager instance for testing."""
        return TranscriptionManager(mock_db, mock_engine, mock_config)

    def test_add_task_success(self, manager):
        """Test successfully adding a task."""
        task_id = manager.add_task("/path/to/audio.mp3", {})
        assert task_id is not None
        assert len(task_id) == 36  # UUID length

    def test_add_task_invalid_format(self, manager):
        """Test adding task with invalid file format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            manager.add_task("/path/to/file.xyz", {})

    def test_cancel_task(self, manager):
        """Test canceling a task."""
        task_id = manager.add_task("/path/to/audio.mp3", {})
        manager.cancel_task(task_id)
        status = manager.get_task_status(task_id)
        assert status["status"] == "cancelled"
```

#### Integration Tests

Place integration tests in `tests/integration/`:

```python
import pytest
from data.database.connection import DatabaseConnection
from core.transcription.manager import TranscriptionManager

class TestTranscriptionIntegration:
    @pytest.fixture
    def db(self, tmp_path):
        """Create a temporary database."""
        db_path = tmp_path / "test.db"
        db = DatabaseConnection(str(db_path))
        db.initialize_schema()
        yield db
        db.close_all()

    @pytest.mark.asyncio
    async def test_full_workflow(self, db, speech_engine, config):
        """Test complete transcription workflow."""
        manager = TranscriptionManager(db, speech_engine, config)

        # Add task
        task_id = await manager.add_task("/path/to/audio.mp3", {})

        # Process task
        await manager.process_task(task_id)

        # Verify result
        status = manager.get_task_status(task_id)
        assert status["status"] == "completed"
        assert status["progress"] == 100
        assert os.path.exists(status["output_path"])
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/unit/test_transcription_manager.py

# Run specific test
pytest tests/unit/test_transcription_manager.py::TestTranscriptionManager::test_add_task_success

# Run with coverage
pytest --cov=echonote --cov-report=html tests/

# Run with verbose output
pytest -v tests/

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/
```

### Test Coverage

- Aim for at least **80% code coverage**
- All new features must include tests
- Bug fixes should include regression tests

View coverage report:

```bash
pytest --cov=echonote --cov-report=html tests/
open htmlcov/index.html
```

---

## Documentation

### Code Documentation

- All public classes, methods, and functions must have docstrings
- Use Google-style docstrings
- Include examples for complex functionality
- Document parameters, return values, and exceptions

### User Documentation

When adding new features, update:

- `docs/user-guide/` - User-facing documentation
- `docs/quick-start/` - Quick start guides (if applicable)
- `docs/FAQ.md` - Frequently asked questions (if applicable)

### Developer Documentation

When making architectural changes, update:

- `docs/DEVELOPER_GUIDE.md` - Developer guide
- `docs/API_REFERENCE.md` - API reference
- `.kiro/specs/echonote-core/design.md` - Design document

### README Updates

Update `README.md` if you:

- Add a major feature
- Change system requirements
- Modify installation instructions

---

## Pull Request Process

### Before Submitting

1. **Run Tests**

   ```bash
   pytest tests/
   ```

2. **Check Code Style**

   ```bash
   black --check echonote/
   pylint echonote/
   ```

3. **Update Documentation**

   - Add/update docstrings
   - Update relevant documentation files

4. **Update CHANGELOG**
   - Add entry to `CHANGELOG.md` under "Unreleased"

### PR Template

When creating a PR, include:

```markdown
## Description

Brief description of changes

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally
- [ ] CHANGELOG updated

## Related Issues

Closes #123
```

### Review Process

1. **Automated Checks**

   - CI/CD pipeline runs tests
   - Code style checks
   - Coverage report generated

2. **Code Review**

   - At least one maintainer review required
   - Address all review comments
   - Request re-review after changes

3. **Approval and Merge**
   - PR approved by maintainer
   - All checks passing
   - Squash and merge (default)

---

## Issue Guidelines

### Reporting Bugs

Use the bug report template:

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:

1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**

- OS: [e.g., Windows 11, macOS 14]
- Python version: [e.g., 3.11]
- EchoNote version: [e.g., 1.0.0]

**Additional context**
Any other relevant information.
```

### Requesting Features

Use the feature request template:

```markdown
**Is your feature request related to a problem?**
A clear description of the problem.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Alternative solutions or features you've considered.

**Additional context**
Any other context or screenshots.
```

### Issue Labels

- `bug` - Something isn't working
- `enhancement` - New feature or request
- `documentation` - Documentation improvements
- `good first issue` - Good for newcomers
- `help wanted` - Extra attention needed
- `question` - Further information requested
- `wontfix` - This will not be worked on

---

## Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **Discord**: Real-time chat (link TBD)

### Getting Help

If you need help:

1. Check the [User Guide](USER_GUIDE.md)
2. Search existing [GitHub Issues](https://github.com/johnnyzhao5619/echonote/issues)
3. Ask in [GitHub Discussions](https://github.com/johnnyzhao5619/echonote/discussions)
4. Join our Discord community

### Recognition

Contributors are recognized in:

- `CONTRIBUTORS.md` file
- Release notes
- Project README

---

## License

By contributing to EchoNote, you agree that your contributions will be licensed under the MIT License.

---

## Questions?

If you have questions about contributing, please:

- Open a discussion on GitHub
- Contact the maintainers
- Join our Discord community

Thank you for contributing to EchoNote! 🎉

---

**Last Updated**: October 2025
