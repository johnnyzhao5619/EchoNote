"""
Input validation utilities for EchoNote application.

Provides validation functions for various input types with clear error
messages.
"""

import os
import re
from pathlib import Path
from typing import Tuple


def validate_concurrent_tasks(value: int) -> Tuple[bool, str]:
    """
    Validate concurrent tasks count.

    Args:
        value: Number of concurrent tasks

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(value, int):
        return False, "Concurrent tasks must be an integer"

    if not (1 <= value <= 5):
        return False, "Concurrent tasks must be between 1 and 5"

    return True, ""


def validate_file_path(path: str) -> Tuple[bool, str]:
    """
    Validate file path.

    Args:
        path: File path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(path, str):
        return False, "File path must be a string"

    if not path.strip():
        return False, "File path cannot be empty"

    # Expand user home directory
    expanded_path = os.path.expanduser(path)

    # Check if path exists
    if not os.path.exists(expanded_path):
        return False, f"File does not exist: {path}"

    # Check if it's a file (not a directory)
    if not os.path.isfile(expanded_path):
        return False, f"Path is not a file: {path}"

    return True, ""


def validate_directory_path(path: str) -> Tuple[bool, str]:
    """
    Validate directory path.

    Args:
        path: Directory path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(path, str):
        return False, "Directory path must be a string"

    if not path.strip():
        return False, "Directory path cannot be empty"

    # Expand user home directory
    expanded_path = os.path.expanduser(path)

    # Check if path exists
    if not os.path.exists(expanded_path):
        # Check if parent directory exists (path might not exist yet)
        parent = Path(expanded_path).parent
        if not parent.exists():
            return False, f"Parent directory does not exist: {parent}"
        return True, ""  # Path doesn't exist but can be created

    # Check if it's a directory
    if not os.path.isdir(expanded_path):
        return False, f"Path is not a directory: {path}"

    return True, ""


def validate_api_key(key: str, provider: str) -> Tuple[bool, str]:
    """
    Validate API key format.

    Args:
        key: API key to validate
        provider: Provider name (openai, google, azure)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(key, str):
        return False, "API key must be a string"

    if not key.strip():
        return False, "API key cannot be empty"

    provider = provider.lower()

    # Provider-specific validation
    if provider == "openai":
        # OpenAI keys start with "sk-"
        if not key.startswith("sk-"):
            return False, "OpenAI API key must start with 'sk-'"
        if len(key) < 20:
            return False, "OpenAI API key is too short"

    elif provider == "google":
        # Google API keys are typically 39 characters
        if len(key) < 20:
            return False, "Google API key is too short"

    elif provider == "azure":
        # Azure keys are typically 32 characters hex
        if len(key) != 32:
            return False, "Azure API key must be 32 characters"
        if not re.match(r'^[a-fA-F0-9]{32}$', key):
            return False, "Azure API key must be hexadecimal"

    else:
        # Generic validation for unknown providers
        if len(key) < 10:
            return False, f"API key for {provider} is too short"

    return True, ""


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(email, str):
        return False, "Email must be a string"

    if not email.strip():
        return False, "Email cannot be empty"

    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(pattern, email):
        return False, "Invalid email format"

    return True, ""


def validate_url(url: str) -> Tuple[bool, str]:
    """
    Validate URL format.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(url, str):
        return False, "URL must be a string"

    if not url.strip():
        return False, "URL cannot be empty"

    # URL regex pattern
    pattern = (
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'
        r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$'
    )

    if not re.match(pattern, url, re.IGNORECASE):
        return (
            False,
            "Invalid URL format (must start with http:// or https://)"
        )

    return True, ""


def validate_language_code(code: str) -> Tuple[bool, str]:
    """
    Validate language code.

    Args:
        code: Language code to validate (e.g., zh_CN, en_US, fr_FR)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(code, str):
        return False, "Language code must be a string"

    if not code.strip():
        return False, "Language code cannot be empty"

    # Valid language codes for EchoNote
    valid_codes = ["zh_CN", "en_US", "fr_FR"]

    if code not in valid_codes:
        return (
            False,
            f"Invalid language code. Must be one of: {', '.join(valid_codes)}"
        )

    return True, ""


# Convenience functions that return only boolean

def is_valid_concurrent_tasks(value: int) -> bool:
    """Check if concurrent tasks value is valid."""
    return validate_concurrent_tasks(value)[0]


def is_valid_file_path(path: str) -> bool:
    """Check if file path is valid."""
    return validate_file_path(path)[0]


def is_valid_directory_path(path: str) -> bool:
    """Check if directory path is valid."""
    return validate_directory_path(path)[0]


def is_valid_api_key(key: str, provider: str) -> bool:
    """Check if API key is valid."""
    return validate_api_key(key, provider)[0]


def is_valid_email(email: str) -> bool:
    """Check if email is valid."""
    return validate_email(email)[0]


def is_valid_url(url: str) -> bool:
    """Check if URL is valid."""
    return validate_url(url)[0]


def is_valid_language_code(code: str) -> bool:
    """Check if language code is valid."""
    return validate_language_code(code)[0]
