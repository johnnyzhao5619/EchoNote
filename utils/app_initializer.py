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
Application initialization utilities.

Extracted from main.py to reduce its size and improve separation of concerns.
Contains helper functions for initializing various application components.
"""

import logging

logger = logging.getLogger("echonote.app_initializer")


def create_sync_scheduler(calendar_manager, sync_interval):
    """Create sync scheduler (for background initialization)."""
    from core.calendar.sync_scheduler import SyncScheduler

    return SyncScheduler(calendar_manager, sync_interval)


def create_auto_task_scheduler(
    timeline_manager,
    realtime_recorder,
    db,
    file_manager,
    reminder_minutes,
    settings_manager,
    i18n_manager=None,
):
    """Create auto task scheduler (for background initialization)."""
    from core.timeline.auto_task_scheduler import AutoTaskScheduler

    return AutoTaskScheduler(
        timeline_manager=timeline_manager,
        realtime_recorder=realtime_recorder,
        db_connection=db,
        file_manager=file_manager,
        reminder_minutes=reminder_minutes,
        settings_manager=settings_manager,
        i18n_manager=i18n_manager,
    )


def create_resource_monitor_handlers(transcription_manager, i18n, logger):
    """Create handlers for resource monitor signals."""
    notification_manager = None

    def _get_notification_manager():
        nonlocal notification_manager
        if notification_manager is None:
            from ui.common.notification import get_notification_manager

            notification_manager = get_notification_manager()
        return notification_manager

    def on_low_memory(available_mb):
        """Handle low memory warning."""
        logger.warning(
            f"Low memory detected: {available_mb:.1f}MB available. " f"Pausing transcription tasks."
        )

        if getattr(transcription_manager, "_running", False):
            transcription_manager.pause_processing()

        _get_notification_manager().send_warning(
            title=i18n.t("notification.low_memory.title"),
            message=i18n.t("notification.low_memory.message", memory=f"{available_mb:.0f}MB"),
        )

    def on_resources_recovered():
        """Handle resources recovered."""
        logger.info("System resources recovered. Resuming transcription tasks.")

        if getattr(transcription_manager, "_running", False) and transcription_manager.is_paused():
            transcription_manager.resume_processing()

        _get_notification_manager().send_info(
            title=i18n.t("notification.resources_recovered.title"),
            message=i18n.t("notification.resources_recovered.message"),
        )

    return on_low_memory, on_resources_recovered


def initialize_database(config, security_manager):
    """Initialize database connection with encryption if enabled."""
    from data.database.connection import DatabaseConnection
    from data.database.encryption_helper import initialize_encryption_helper

    initialize_encryption_helper(security_manager)

    db_path = config.get("database.path")
    encryption_enabled = config.get("database.encryption_enabled", True)

    if encryption_enabled:
        from config.constants import DATABASE_ENCRYPTION_KEY_LENGTH

        # Use first N chars of encrypted key as database encryption key
        db_encryption_key = security_manager.encryption_key[:DATABASE_ENCRYPTION_KEY_LENGTH].hex()
        db = DatabaseConnection(db_path, encryption_key=db_encryption_key)
    else:
        db = DatabaseConnection(db_path)

    logger.info("Database connection initialized")

    # Check if schema needs initialization
    schema_version = db.get_version()
    if schema_version == 0:
        logger.info("Initializing database schema...")
        db.initialize_schema()
        db.set_version(1)
        logger.info("Database schema initialized")
    else:
        logger.info(f"Database schema version: {schema_version}")

    return db


def initialize_speech_engine(config, model_manager):
    """Initialize speech engine with lazy loading."""
    from engines.speech.faster_whisper_engine import FasterWhisperEngine
    from utils.startup_optimizer import LazyLoader

    model_size = config.get("transcription.faster_whisper.model_size", "base")
    device = config.get("transcription.faster_whisper.device", "auto")
    compute_type = config.get("transcription.faster_whisper.compute_type", "int8")

    def create_speech_engine():
        logger.info(f"Loading speech engine (model: {model_size}, device: {device})...")
        engine = FasterWhisperEngine(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            model_manager=model_manager,
        )

        # Check if model is available
        if not engine.is_model_available():
            logger.warning(
                f"Speech engine initialized but model '{model_size}' is not available. "
                f"Transcription features will be disabled until model is downloaded."
            )
        else:
            logger.info(f"Speech engine loaded successfully (model: {model_size})")

        return engine

    speech_engine_loader = LazyLoader("speech_engine", create_speech_engine)
    logger.info("Speech engine configured (will load on first use)")

    return speech_engine_loader


def initialize_translation_engine(config):
    """Initialize translation engine with lazy loading."""
    from utils.startup_optimizer import LazyLoader

    def create_translation_engine():
        try:
            logger.info("Loading translation engine...")
            from engines.translation.google_translate import GoogleTranslateEngine

            # Check if API key is configured
            api_key = config.get("translation.google.api_key")
            if api_key:
                engine = GoogleTranslateEngine(api_key)
                logger.info("Translation engine loaded successfully")
                return engine
            else:
                logger.info("Translation engine not configured (no API key)")
                return None
        except Exception as e:
            logger.warning(f"Could not initialize translation engine: {e}")
            return None

    translation_engine_loader = LazyLoader("translation_engine", create_translation_engine)
    logger.info("Translation engine configured (will load on first use)")

    return translation_engine_loader


def initialize_calendar_adapters(config, oauth_manager):
    """Initialize calendar sync adapters."""
    sync_adapters = {}

    # Get OAuth configuration
    oauth_config = config.get("calendar", {}).get("oauth", {})
    from config.constants import DEFAULT_OAUTH_REDIRECT_PORT

    redirect_uri = oauth_config.get(
        "redirect_uri", f"http://localhost:{DEFAULT_OAUTH_REDIRECT_PORT}/callback"
    )

    def inject_cached_tokens(provider_key: str, adapter):
        token_data = oauth_manager.get_token(provider_key)
        if not token_data:
            logger.info("No cached OAuth token found for %s calendar adapter", provider_key)
            return

        adapter.access_token = token_data.get("access_token")
        adapter.refresh_token = token_data.get("refresh_token")
        adapter.expires_at = token_data.get("expires_at")

        if adapter.refresh_token:
            logger.info(
                "Restored OAuth token for %s calendar adapter (expires_at=%s)",
                provider_key,
                adapter.expires_at,
            )
        else:
            logger.warning(
                "Cached OAuth token for %s adapter lacks refresh_token; refresh disabled",
                provider_key,
            )
            return

    # Initialize Google Calendar adapter
    try:
        from engines.calendar_sync.google_calendar import GoogleCalendarAdapter

        google_config = oauth_config.get("google", {})
        google_client_id = google_config.get("client_id", "")
        google_client_secret = google_config.get("client_secret", "")

        if google_client_id and google_client_secret:
            google_adapter = GoogleCalendarAdapter(
                client_id=google_client_id,
                client_secret=google_client_secret,
                redirect_uri=redirect_uri,
            )
            inject_cached_tokens("google", google_adapter)
            sync_adapters["google"] = google_adapter
            logger.info("Google Calendar adapter initialized")
        else:
            logger.warning("Google Calendar OAuth credentials not configured")
    except Exception as e:
        logger.warning(f"Could not initialize Google Calendar adapter: {e}")

    # Initialize Outlook Calendar adapter
    try:
        from engines.calendar_sync.outlook_calendar import OutlookCalendarAdapter

        outlook_config = oauth_config.get("outlook", {})
        outlook_client_id = outlook_config.get("client_id", "")
        outlook_client_secret = outlook_config.get("client_secret", "")

        if outlook_client_id and outlook_client_secret:
            outlook_adapter = OutlookCalendarAdapter(
                client_id=outlook_client_id,
                client_secret=outlook_client_secret,
                redirect_uri=redirect_uri,
            )
            inject_cached_tokens("outlook", outlook_adapter)
            sync_adapters["outlook"] = outlook_adapter
            logger.info("Outlook Calendar adapter initialized")
        else:
            logger.warning("Outlook Calendar OAuth credentials not configured")
    except Exception as e:
        logger.warning(f"Could not initialize Outlook Calendar adapter: {e}")

    return sync_adapters


def initialize_audio_capture():
    """Initialize audio capture with error handling."""
    from engines.audio.capture import AudioCapture

    audio_capture = None
    try:
        audio_capture = AudioCapture()
        logger.info("Audio capture initialized")
    except ImportError as exc:
        logger.warning(
            "PyAudio not available; real-time recording disabled until installation. %s",
            exc,
        )
        logger.warning("Install PyAudio with 'pip install pyaudio' to enable microphone capture.")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Audio capture unavailable due to runtime error. "
            "Real-time recording will be disabled."
        )
        logger.warning("Audio capture initialization error: %s", exc, exc_info=True)

    return audio_capture


class EngineProxy:
    """Proxy class for lazy-loaded engines."""

    def __init__(self, loader):
        self._loader = loader

    def __getattr__(self, name):
        return getattr(self._loader.get(), name)

    def __bool__(self):
        try:
            return self._loader.get() is not None
        except Exception:
            return False


class TranslationEngineProxy(EngineProxy):
    """Proxy class specifically for translation engine."""

    def __getattr__(self, name):
        engine = self._loader.get()
        if engine is None:
            raise AttributeError("Translation engine not available")
        return getattr(engine, name)
