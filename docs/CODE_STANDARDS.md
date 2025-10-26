# EchoNote Code Standards

**Version**: 1.0.0  
**Last Updated**: October 2025

---

## Table of Contents

1. [Python Style Guide](#python-style-guide)
2. [Project Structure](#project-structure)
3. [Naming Conventions](#naming-conventions)
4. [Documentation Standards](#documentation-standards)
5. [Error Handling](#error-handling)
6. [Testing Standards](#testing-standards)
7. [Git Workflow](#git-workflow)
8. [Code Review Guidelines](#code-review-guidelines)

---

## Python Style Guide

### General Principles

We follow [PEP 8](https://pep8.org/) with the following modifications:

- **Line Length**: 100 characters (not 79)
- **Docstring Length**: 72 characters
- **String Quotes**: Double quotes preferred
- **Indentation**: 4 spaces (never tabs)

### Formatting

#### Automatic Formatting

Use `black` with custom configuration:

```bash
# Format all files
black echonote/

# Check without modifying
black --check echonote/
```

Configuration (`.black.toml`):

```toml
[tool.black]
line-length = 100
target-version = ['py38', 'py39', 'py310', 'py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''
```

#### Line Length

```python
# Good
result = some_function(
    parameter1="value1",
    parameter2="value2",
    parameter3="value3"
)

# Bad
result = some_function(parameter1="value1", parameter2="value2", parameter3="value3", parameter4="value4")
```

#### Indentation

```python
# Good
def long_function_name(
    var_one: str,
    var_two: int,
    var_three: dict = None
) -> bool:
    """Function with proper indentation."""
    if var_three is None:
        var_three = {}

    return True

# Bad
def long_function_name(var_one: str, var_two: int,
    var_three: dict = None) -> bool:
    """Function with improper indentation."""
    if var_three is None: var_three = {}
    return True
```

### Imports

#### Import Order

1. Standard library imports
2. Third-party imports
3. Local application imports

```python
# Standard library
import os
import sys
from datetime import datetime
from typing import Optional, List, Dict

# Third-party
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
import numpy as np
import httpx

# Local
from core.transcription.manager import TranscriptionManager
from engines.speech.base import SpeechEngine
from utils.logger import setup_logging
```

#### Import Style

```python
# Good - Explicit imports
from core.transcription.manager import TranscriptionManager
from engines.speech.base import SpeechEngine

# Acceptable - Module import for many items
from PySide6 import QtWidgets, QtCore, QtGui

# Bad - Wildcard imports
from core.transcription.manager import *
```

### Whitespace

#### Around Operators

```python
# Good
x = 1
y = 2
z = x + y

# Bad
x=1
y=2
z=x+y
```

#### In Function Calls

```python
# Good
function(arg1, arg2, kwarg1=value1)

# Bad
function( arg1 , arg2 , kwarg1 = value1 )
```

#### In Collections

```python
# Good
my_list = [1, 2, 3, 4]
my_dict = {"key": "value", "key2": "value2"}

# Bad
my_list = [ 1,2,3,4 ]
my_dict = { "key" : "value" , "key2" : "value2" }
```

---

## Project Structure

### Module Organization

```
module/
├── __init__.py          # Module initialization
├── base.py              # Base classes/interfaces
├── manager.py           # Main manager class
├── models.py            # Data models
├── utils.py             # Utility functions
└── constants.py         # Constants
```

### File Size

- Keep files under **500 lines**
- Split large files into logical modules
- Use subdirectories for related functionality

### Circular Imports

Avoid circular imports:

```python
# Bad - Circular import
# file_a.py
from file_b import ClassB

class ClassA:
    def method(self):
        return ClassB()

# file_b.py
from file_a import ClassA

class ClassB:
    def method(self):
        return ClassA()

# Good - Use TYPE_CHECKING
# file_a.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from file_b import ClassB

class ClassA:
    def method(self) -> 'ClassB':
        from file_b import ClassB
        return ClassB()
```

---

## Naming Conventions

### Classes

Use `PascalCase`:

```python
class TranscriptionManager:
    pass

class SpeechEngine:
    pass

class CalendarEvent:
    pass
```

### Functions and Methods

Use `snake_case`:

```python
def process_audio_file(file_path: str) -> dict:
    pass

def get_task_status(task_id: str) -> dict:
    pass

def create_calendar_event(event_data: dict) -> str:
    pass
```

### Variables

Use `snake_case`:

```python
# Good
task_id = "abc-123"
file_path = "/path/to/file"
max_retries = 3

# Bad
taskId = "abc-123"
filePath = "/path/to/file"
MaxRetries = 3
```

### Constants

Use `UPPER_SNAKE_CASE`:

```python
MAX_CONCURRENT_TASKS = 5
DEFAULT_LANGUAGE = "en"
SUPPORTED_FORMATS = [".mp3", ".wav", ".m4a"]
API_TIMEOUT_SECONDS = 30
```

### Private Members

Prefix with single underscore:

```python
class MyClass:
    def __init__(self):
        self._internal_state = {}
        self.public_attribute = "value"

    def _internal_helper(self):
        """Private helper method."""
        pass

    def public_method(self):
        """Public method."""
        return self._internal_helper()
```

### Protected Members

Use single underscore (convention only):

```python
class BaseClass:
    def __init__(self):
        self._protected_attribute = "value"

    def _protected_method(self):
        """Protected method for subclasses."""
        pass
```

### Boolean Variables

Use descriptive names with `is_`, `has_`, `can_`, `should_`:

```python
# Good
is_active = True
has_permission = False
can_edit = True
should_retry = False

# Bad
active = True
permission = False
edit = True
retry = False
```

---

## Documentation Standards

### Module Docstrings

```python
"""
Module for managing transcription tasks.

This module provides the TranscriptionManager class which handles
batch transcription of audio files using various speech recognition
engines.

Example:
    >>> from core.transcription.manager import TranscriptionManager
    >>> manager = TranscriptionManager(db, engine, config)
    >>> task_id = await manager.add_task("/path/to/audio.mp3")
"""
```

### Class Docstrings

```python
class TranscriptionManager:
    """
    Manages batch transcription tasks.

    This class handles the lifecycle of transcription tasks including
    queueing, processing, progress tracking, and result storage.

    Attributes:
        task_queue: Queue of pending tasks
        speech_engine: Speech recognition engine
        db: Database connection

    Example:
        >>> manager = TranscriptionManager(db, engine, config)
        >>> task_id = await manager.add_task("/path/to/audio.mp3")
        >>> await manager.start_processing()
    """
```

### Function Docstrings

Use Google-style docstrings:

```python
def transcribe_file(
    audio_path: str,
    language: str = "en",
    options: dict = None
) -> dict:
    """
    Transcribe an audio file to text.

    This function processes an audio file using the configured speech
    recognition engine and returns the transcription result with
    timestamps.

    Args:
        audio_path: Path to the audio file. Supported formats: MP3,
            WAV, M4A, FLAC, OGG.
        language: Language code (ISO 639-1). If None, auto-detect.
            Examples: 'en', 'zh', 'fr'.
        options: Optional processing options:
            - beam_size (int): Beam size for decoding (default: 5)
            - temperature (float): Sampling temperature (default: 0.0)
            - vad_filter (bool): Enable VAD filtering (default: True)

    Returns:
        Dictionary containing transcription result:
            - segments (list): List of transcription segments
                - start (float): Start time in seconds
                - end (float): End time in seconds
                - text (str): Transcribed text
            - language (str): Detected/used language code
            - duration (float): Audio duration in seconds

    Raises:
        FileNotFoundError: If audio file doesn't exist
        ValueError: If audio format is not supported
        RuntimeError: If transcription engine fails

    Example:
        >>> result = transcribe_file("/path/to/audio.mp3", "en")
        >>> for segment in result["segments"]:
        ...     print(f"{segment['start']:.2f}s: {segment['text']}")
        0.00s: Hello world
        2.50s: This is a test

    Note:
        Large files (>100MB) may take several minutes to process.
        Consider using streaming mode for real-time transcription.
    """
    pass
```

### Inline Comments

```python
# Good - Explain why, not what
# Use exponential backoff to avoid overwhelming the API
retry_delay = 2 ** attempt

# Bad - Obvious comment
# Increment counter by 1
counter += 1
```

### TODO Comments

```python
# TODO(username): Add support for MP4 video files
# FIXME(username): Memory leak in audio buffer
# HACK(username): Temporary workaround for Qt bug
# NOTE(username): This assumes UTF-8 encoding
```

---

## Error Handling

### Exception Types

Use specific exception types:

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
except PermissionError as e:
    logger.error(f"Permission denied: {path}")
    raise

# Bad
try:
    result = process_file(path)
except Exception as e:
    logger.error(f"Error: {e}")
    return None
```

### Custom Exceptions

```python
class TranscriptionError(Exception):
    """Base exception for transcription errors."""
    pass

class UnsupportedFormatError(TranscriptionError):
    """Raised when audio format is not supported."""
    pass

class ModelNotAvailableError(TranscriptionError):
    """Raised when speech recognition model is not available."""
    pass

# Usage
if not is_format_supported(file_path):
    raise UnsupportedFormatError(
        f"Format {ext} is not supported. "
        f"Supported formats: {SUPPORTED_FORMATS}"
    )
```

### Error Messages

```python
# Good - Descriptive and actionable
raise ValueError(
    f"Invalid language code: '{language}'. "
    f"Supported languages: {', '.join(SUPPORTED_LANGUAGES)}"
)

# Bad - Vague
raise ValueError("Invalid language")
```

### Logging Errors

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = process_file(path)
except FileNotFoundError:
    logger.error(
        f"File not found: {path}",
        exc_info=True  # Include traceback
    )
    raise
except Exception as e:
    logger.exception(
        f"Unexpected error processing {path}: {e}"
    )
    raise
```

---

## Testing Standards

### Test Organization

```
tests/
├── unit/                    # Unit tests
│   ├── test_transcription_manager.py
│   ├── test_speech_engine.py
│   └── test_calendar_manager.py
├── integration/             # Integration tests
│   ├── test_transcription_workflow.py
│   └── test_calendar_sync.py
├── fixtures/                # Test fixtures
│   ├── audio/
│   └── data/
└── conftest.py             # Shared fixtures
```

### Test Naming

```python
# Good - Descriptive test names
def test_add_task_with_valid_file():
    pass

def test_add_task_with_invalid_format_raises_error():
    pass

def test_cancel_task_updates_status():
    pass

# Bad - Vague test names
def test_add_task():
    pass

def test_error():
    pass
```

### Test Structure

Use Arrange-Act-Assert pattern:

```python
def test_transcribe_file_success():
    # Arrange
    manager = TranscriptionManager(mock_db, mock_engine, mock_config)
    file_path = "/path/to/audio.mp3"
    expected_result = {"segments": [...]}

    # Act
    result = await manager.transcribe_file(file_path)

    # Assert
    assert result == expected_result
    assert len(result["segments"]) > 0
```

### Fixtures

```python
import pytest

@pytest.fixture
def db_connection(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(str(db_path))
    db.initialize_schema()
    yield db
    db.close_all()

@pytest.fixture
def transcription_manager(db_connection, mock_engine, mock_config):
    """Create a TranscriptionManager for testing."""
    return TranscriptionManager(db_connection, mock_engine, mock_config)
```

### Mocking

```python
from unittest.mock import Mock, patch, MagicMock

def test_api_call_with_mock():
    # Mock external API
    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value.json.return_value = {"result": "success"}

        # Test code that calls the API
        result = await call_external_api()

        # Verify
        assert result == {"result": "success"}
        mock_post.assert_called_once()
```

### Test Coverage

- Aim for **80%+ coverage**
- Focus on critical paths
- Test edge cases and error conditions

```bash
# Run with coverage
pytest --cov=echonote --cov-report=html tests/

# View report
open htmlcov/index.html
```

---

## Git Workflow

### Commit Messages

Use conventional commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Tests
- `chore`: Maintenance

**Examples:**

```
feat(transcription): add support for MP4 video files

- Add MP4 to supported formats list
- Update file validation logic
- Add tests for MP4 transcription

Closes #123
```

```
fix(calendar): resolve sync token expiration issue

The sync token was not being refreshed properly, causing
sync failures after 1 hour. Now we check token expiration
and refresh before each sync operation.

Fixes #456
```

### Branch Naming

```
feature/add-azure-speech-engine
fix/transcription-progress-bar
docs/update-api-reference
refactor/simplify-audio-buffer
test/add-calendar-manager-tests
chore/update-dependencies
```

### Pull Requests

- Keep PRs focused and small
- Include tests
- Update documentation
- Link related issues
- Request review from maintainers

---

## Code Review Guidelines

### For Authors

**Before Submitting:**

- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Self-review completed
- [ ] No debug code or comments
- [ ] CHANGELOG updated

**During Review:**

- Respond to all comments
- Ask for clarification if needed
- Make requested changes promptly
- Request re-review after changes

### For Reviewers

**What to Check:**

- [ ] Code correctness
- [ ] Test coverage
- [ ] Documentation quality
- [ ] Performance implications
- [ ] Security considerations
- [ ] Error handling
- [ ] Code style compliance

**Review Comments:**

````
# Good - Specific and constructive
"Consider using a context manager here to ensure the file is closed:
```python
with open(file_path) as f:
    data = f.read()
````

This prevents resource leaks if an exception occurs."

# Bad - Vague

"This doesn't look right."

````

**Approval Criteria:**
- All automated checks passing
- No unresolved comments
- Code meets quality standards
- Documentation complete

---

## Additional Guidelines

### Performance

- Profile before optimizing
- Use appropriate data structures
- Avoid premature optimization
- Document performance-critical code

### Security

- Never commit secrets or API keys
- Validate all user input
- Use parameterized queries
- Encrypt sensitive data

### Accessibility

- Support keyboard navigation
- Provide text alternatives
- Use semantic HTML/Qt widgets
- Test with screen readers

### Internationalization

- Use translation keys, not hardcoded strings
- Support RTL languages
- Format dates/numbers appropriately
- Test with different locales

---

## Tools and Automation

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
````

Configuration (`.pre-commit-config.yaml`):

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black

  - repo: https://github.com/PyCQA/pylint
    rev: v3.0.0
    hooks:
      - id: pylint

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

### CI/CD

GitHub Actions workflow runs:

- Code style checks
- Unit tests
- Integration tests
- Coverage report
- Documentation build

---

## Questions?

If you have questions about code standards:

- Check the [Developer Guide](DEVELOPER_GUIDE.md)
- Ask in GitHub Discussions
- Contact the maintainers

---

**Last Updated**: October 2025  
**Version**: 1.0.0
