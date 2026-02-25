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
Version management for EchoNote application.

This module provides the single source of truth for version information.
All other files should import version from this module to ensure consistency.
"""

# Single source of truth for version information
__version__ = "1.4.3"

# Version metadata
VERSION_INFO = {
    "major": 1,
    "minor": 4,
    "patch": 3,
    "pre_release": None,  # e.g., "alpha", "beta", "rc1"
    "build": None,  # e.g., build number or commit hash
}


def get_version() -> str:
    """
    Get the current application version.

    Returns:
        Version string in semantic versioning format
    """
    return __version__


def get_version_info() -> dict:
    """
    Get detailed version information.

    Returns:
        Dictionary containing version components
    """
    return VERSION_INFO.copy()


def get_display_version() -> str:
    """
    Get formatted version for display in UI.

    Returns:
        Version string with 'v' prefix for display
    """
    version = get_version()
    if not version:
        return ""

    # Add 'v' prefix if not already present
    if not version.lower().startswith("v"):
        return f"v{version}"

    return version


def is_development_version() -> bool:
    """
    Check if this is a development version.

    Returns:
        True if this is a development/pre-release version
    """
    return VERSION_INFO.get("pre_release") is not None


def get_version_tuple() -> tuple:
    """
    Get version as a tuple for comparison.

    Returns:
        Tuple of (major, minor, patch) integers
    """
    return (VERSION_INFO["major"], VERSION_INFO["minor"], VERSION_INFO["patch"])
