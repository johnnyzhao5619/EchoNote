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
Application-wide constants for EchoNote.

This module contains constants used across multiple modules to avoid
hardcoded values throughout the codebase.
"""

# ============================================================================
# Application Constants
# ============================================================================

# Startup and Initialization
SPLASH_SCREEN_DELAY_MS = 500
STARTUP_PROGRESS_STEPS = {
    "configuration": 10,
    "dependencies": 15,
    "database": 20,
    "i18n": 30,
    "managers": 40,
    "speech_engine": 50,
    "transcription": 55,
    "resource_monitor": 60,
    "realtime_recorder": 65,
    "calendar": 70,
    "main_window": 80,
    "final": 90,
}

# Database and Security
DATABASE_ENCRYPTION_KEY_LENGTH = 32  # bytes
LOG_SEPARATOR_LENGTH = 60  # characters for "=" * 60

# Default Configuration Values
DEFAULT_REMINDER_MINUTES = 5
DEFAULT_SYNC_INTERVAL_MINUTES = 15
DEFAULT_OAUTH_REDIRECT_PORT = 8080

# ============================================================================
# Audio Processing Constants
# ============================================================================

# Audio Capture Defaults
DEFAULT_SAMPLE_RATE_HZ = 16000  # 16 kHz (Whisper baseline)
DEFAULT_AUDIO_CHANNELS = 1  # Mono
DEFAULT_CHUNK_SIZE_SAMPLES = 512  # ~32ms at 16kHz
DEFAULT_AUDIO_GAIN = 1.0

# Audio Gain Limits
MIN_AUDIO_GAIN = 0.0
MAX_AUDIO_GAIN = 10.0

# Audio Format Constants
AUDIO_NORMALIZATION_DIVISOR = 32768.0  # For int16 to float32 conversion

# ============================================================================
# Timeline and Calendar Constants
# ============================================================================

# Timeline Search and Filtering
DEFAULT_TRANSCRIPT_CANDIDATE_WINDOW_DAYS = 30
MAX_TRANSCRIPT_CANDIDATES = 200

# Date Range Defaults (for timeline filtering)
TIMELINE_MIN_YEAR = 1970
TIMELINE_MIN_MONTH = 1
TIMELINE_MIN_DAY = 1
TIMELINE_MAX_YEAR = 2099
TIMELINE_MAX_MONTH = 12
TIMELINE_MAX_DAY = 31
TIMELINE_MAX_HOUR = 23
TIMELINE_MAX_MINUTE = 59
TIMELINE_MAX_SECOND = 59

# ============================================================================
# Network and API Constants
# ============================================================================

# HTTP Timeouts (seconds)
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
CALENDAR_API_TIMEOUT_SECONDS = 30.0

# API Pagination
GOOGLE_CALENDAR_MAX_RESULTS = 250
OUTLOOK_CALENDAR_MAX_PAGE_SIZE = 250

# OAuth and Security
OAUTH_STATE_TOKEN_LENGTH = 16  # bytes for secrets.token_urlsafe()
OAUTH_CODE_VERIFIER_LENGTH = 64  # bytes for secrets.token_urlsafe()
OAUTH_CODE_VERIFIER_MIN_LENGTH = 43  # PKCE minimum
OAUTH_CODE_VERIFIER_MAX_LENGTH = 128  # PKCE maximum
OAUTH_CODE_VERIFIER_PADDING_LENGTH = 32  # bytes for padding

# Token Expiration
DEFAULT_TOKEN_EXPIRES_IN_SECONDS = 3600  # 1 hour

# ============================================================================
# Resource Monitoring Constants
# ============================================================================

# Resource Monitor Thresholds
LOW_MEMORY_THRESHOLD_MB = 500  # Warn if available memory < 500MB
HIGH_CPU_THRESHOLD_PERCENT = 90  # Warn if CPU usage > 90%
RESOURCE_CHECK_INTERVAL_MS = 30000  # Check every 30 seconds

# Memory Thresholds for Configuration
MIN_MEMORY_THRESHOLD_MB = 64.0
MAX_MEMORY_THRESHOLD_MB = 1048576.0  # 1TB
MIN_CPU_THRESHOLD_PERCENT = 1.0
MAX_CPU_THRESHOLD_PERCENT = 100.0

# Unit Conversion
BYTES_TO_MB_DIVISOR = 1024 * 1024
MB_TO_GB_THRESHOLD = 1024

# ============================================================================
# Validation Constants
# ============================================================================

# API Key Validation
MIN_OPENAI_API_KEY_LENGTH = 20
MIN_GOOGLE_API_KEY_LENGTH = 20
AZURE_API_KEY_LENGTH = 32  # Exact length required
MIN_GENERIC_API_KEY_LENGTH = 10

# URL Validation
URL_DOMAIN_MAX_LABEL_LENGTH = 61
URL_TLD_MIN_LENGTH = 2
URL_TLD_MAX_LENGTH = 6

# ============================================================================
# Time and Date Format Constants
# ============================================================================

# Time Calculations
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60
MILLISECONDS_PER_SECOND = 1000

# Format Strings
SRT_TIMESTAMP_FORMAT = "{:02d}:{:02d}:{:02d},{:03d}"
MARKDOWN_TIMESTAMP_FORMAT = "{:02d}:{:02d}:{:02d}"

# Timezone Handling
UTC_OFFSET_MINUTES_PER_HOUR = 60
TIMEZONE_SUFFIX_START = "T00:00:00"
TIMEZONE_SUFFIX_END = "T23:59:59"

# ============================================================================
# File and Data Constants
# ============================================================================

# File Size Formatting
FILE_SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"]
FILE_SIZE_THRESHOLD = 1024.0

# User Feedback
DEFAULT_RECENT_OPERATIONS_COUNT = 10


# Default Paths (platform-aware)
def get_default_recordings_path() -> str:
    """Get the default recordings path based on the platform."""
    from pathlib import Path

    return str(Path.home() / "Documents" / "EchoNote" / "Recordings")


DEFAULT_RECORDINGS_PATH = get_default_recordings_path()

# ============================================================================
# Accessibility Constants
# ============================================================================

# Screen Reader Announcements
ACCESSIBILITY_ANNOUNCEMENT_DELAY_MS = 100

# ============================================================================
# Date Parsing Constants
# ============================================================================

# ISO 8601 Date Handling
ISO_DATE_ONLY_LENGTH = 10  # YYYY-MM-DD
UTC_TIMEZONE_SUFFIX = "Z"
UTC_TIMEZONE_OFFSET = "+00:00"

# ============================================================================
# Magic Numbers - Extracted from Codebase
# ============================================================================

# File System Permissions
FILE_PERMISSION_OWNER_RW = 0o600  # Owner read/write only
DIRECTORY_PERMISSION_OWNER_RWX = 0o700  # Owner read/write/execute only

# Time Calculations (seconds)
SECONDS_PER_DAY = 86400  # 24 * 60 * 60
DEFAULT_TOKEN_BUFFER_SECONDS = 300  # 5 minutes buffer for token/OAuth expiration

# Audio Processing Defaults
DEFAULT_AUDIO_BUFFER_DURATION_SECONDS = 60  # 1 minute audio buffer
DEFAULT_WHISPER_SAMPLE_RATE = 16000  # 16 kHz for Whisper models

# Database Configuration
DATABASE_CONNECTION_TIMEOUT_SECONDS = 30.0  # SQLite connection timeout

# Logging Configuration
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB log file size
LOG_FILE_BACKUP_COUNT = 5  # Number of backup log files
DEFAULT_LOG_LINES_TO_READ = 100  # Default number of recent log lines

# Cryptographic Constants
SALT_SIZE_BYTES = 32  # 256-bit salt for key derivation
ENCRYPTION_KEY_SIZE_BYTES = 32  # 256-bit key for AES-256
PASSWORD_SALT_SIZE_BYTES = 16  # 128-bit salt for password hashing
PASSWORD_HASH_LENGTH_BYTES = 32  # 256-bit password hash
PASSWORD_HASH_ITERATIONS = 200_000  # PBKDF2 iterations for password hashing

# Text Search and Context
SEARCH_CONTEXT_CHARS_BEFORE = 30  # Characters before search match
SEARCH_CONTEXT_CHARS_AFTER = 30  # Characters after search match

# Timeline and Scheduling
MIN_REMINDER_WINDOW_MINUTES = 5  # Minimum past window for reminders
REMINDER_FUTURE_WINDOW_OFFSET_MINUTES = 10  # Additional minutes for future window
MIN_FUTURE_WINDOW_MINUTES = 15  # Minimum future window for reminders

# Audio Format Constants
AUDIO_CHUNK_MEMORY_BYTES_PER_SAMPLE = 4  # float32 samples use 4 bytes each

# Numeric Conversion
PERCENTAGE_MULTIPLIER = 100  # For converting ratios to percentages
