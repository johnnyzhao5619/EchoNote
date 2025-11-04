# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Common validation utilities for EchoNote application.

Provides reusable validation functions to reduce code duplication
across different modules.
"""

import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from config.constants import (
    AZURE_API_KEY_LENGTH,
    MIN_GENERIC_API_KEY_LENGTH,
    MIN_GOOGLE_API_KEY_LENGTH,
    MIN_OPENAI_API_KEY_LENGTH,
)

logger = logging.getLogger(__name__)


def validate_api_key(key: str, provider: str) -> Tuple[bool, str]:
    """
    Validate an API key for a specific provider.

    Args:
        key: The API key to validate
        provider: The provider name (openai, google, azure, etc.)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not key or not key.strip():
        return False, "API key cannot be empty"

    key = key.strip()

    if provider.lower() == "openai":
        if len(key) < MIN_OPENAI_API_KEY_LENGTH:
            return False, f"OpenAI API key must be at least {MIN_OPENAI_API_KEY_LENGTH} characters"
        if not key.startswith("sk-"):
            return False, "OpenAI API key must start with 'sk-'"

    elif provider.lower() == "google":
        if len(key) < MIN_GOOGLE_API_KEY_LENGTH:
            return False, f"Google API key must be at least {MIN_GOOGLE_API_KEY_LENGTH} characters"

    elif provider.lower() == "azure":
        if len(key) != AZURE_API_KEY_LENGTH:
            return False, f"Azure API key must be exactly {AZURE_API_KEY_LENGTH} characters"

    else:
        # Generic validation for other providers
        if len(key) < MIN_GENERIC_API_KEY_LENGTH:
            return False, f"API key must be at least {MIN_GENERIC_API_KEY_LENGTH} characters"

    return True, ""


def validate_file_path(
    path: Union[str, Path], must_exist: bool = False, create_if_missing: bool = False
) -> Tuple[bool, str]:
    """
    Validate a file path.

    Args:
        path: The path to validate
        must_exist: Whether the path must already exist
        create_if_missing: Whether to create the directory if it doesn't exist

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Path cannot be empty"

    try:
        path_obj = Path(path).expanduser().resolve()

        if must_exist and not path_obj.exists():
            return False, f"Path does not exist: {path_obj}"

        if create_if_missing and not path_obj.exists():
            try:
                path_obj.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return False, f"Cannot create directory: {e}"

        # Check if parent directory exists and is writable
        parent = path_obj.parent
        if not parent.exists():
            if create_if_missing:
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    return False, f"Cannot create parent directory: {e}"
            else:
                return False, f"Parent directory does not exist: {parent}"

        # Check write permissions
        if not parent.is_dir():
            return False, f"Parent is not a directory: {parent}"

        return True, ""

    except Exception as e:
        return False, f"Invalid path: {e}"


def validate_numeric_range(
    value: Any,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    value_type: type = float,
) -> Tuple[bool, str]:
    """
    Validate that a numeric value is within a specified range.

    Args:
        value: The value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        value_type: Expected type (int or float)

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Convert to the expected type
        if value_type == int:
            converted_value = int(value)
        else:
            converted_value = float(value)

        if min_val is not None and converted_value < min_val:
            return False, f"Value must be at least {min_val}"

        if max_val is not None and converted_value > max_val:
            return False, f"Value must be at most {max_val}"

        return True, ""

    except (ValueError, TypeError):
        return False, f"Value must be a valid {value_type.__name__}"


def validate_choice(value: Any, valid_choices: List[Any]) -> Tuple[bool, str]:
    """
    Validate that a value is one of the allowed choices.

    Args:
        value: The value to validate
        valid_choices: List of valid choices

    Returns:
        Tuple of (is_valid, error_message)
    """
    if value not in valid_choices:
        return False, f"Value must be one of: {', '.join(map(str, valid_choices))}"

    return True, ""


def validate_non_empty_string(value: Any, field_name: str = "Value") -> Tuple[bool, str]:
    """
    Validate that a value is a non-empty string.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"

    if not value.strip():
        return False, f"{field_name} cannot be empty"

    return True, ""
