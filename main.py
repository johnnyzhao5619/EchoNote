#!/usr/bin/env python3
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
EchoNote - Intelligent Voice Transcription and Calendar Management Application

Main entry point for the application.
"""

import asyncio
import inspect
import sys
import traceback

from config.app_config import ConfigManager
from utils.error_handler import ErrorHandler
from utils.first_run_setup import FirstRunSetup
from utils.logger import setup_logging
from utils.resource_cleanup import close_lazy_loaded_engine

# Global logger for exception hook
_logger = None


def _create_sync_scheduler(calendar_manager, sync_interval):
    """Create sync scheduler (for background initialization)."""
    from core.calendar.sync_scheduler import SyncScheduler

    return SyncScheduler(calendar_manager, sync_interval)


def _create_auto_task_scheduler(
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


def _create_resource_monitor_handlers(transcription_manager, i18n, logger):
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


def exception_hook(exctype, value, tb):
    """
    Global exception handler for uncaught exceptions.

    This function is called for all uncaught exceptions. It logs the error
    and displays a user-friendly error dialog.

    Args:
        exctype: Exception type
        value: Exception value
        tb: Traceback object
    """
    # Format the full traceback
    error_msg = "".join(traceback.format_exception(exctype, value, tb))

    # Log the error
    if _logger:
        _logger.critical(
            f"Uncaught exception: {exctype.__name__}: {value}",
            exc_info=(exctype, value, tb),
        )
    else:
        # Fallback if logger not initialized
        print(f"CRITICAL ERROR: {error_msg}", file=sys.stderr)

    # Try to show error dialog if PySide6 is available
    try:
        from PySide6.QtWidgets import QApplication

        from ui.common.error_dialog import show_error_dialog

        # Check if QApplication exists
        app = QApplication.instance()
        if app:
            # Get error info from error handler
            error_info = ErrorHandler.handle_error(value)

            # Show error dialog
            show_error_dialog(
                title="应用程序错误 / Application Error",
                message=error_info["user_message"],
                details=error_msg,
                i18n=None,  # No i18n available in crash scenario
                parent=None,
            )
    except Exception as dialog_error:
        # If dialog fails, just print to stderr
        print(f"Failed to show error dialog: {dialog_error}", file=sys.stderr)
        print(f"Original error:\n{error_msg}", file=sys.stderr)


def main():
    """Application entry point."""
    global _logger

    try:
        speech_engine_loader = None
        translation_engine_loader = None

        # Initialize logging system
        logger = setup_logging()
        _logger = logger  # Set global logger for exception hook

        logger.info("=" * 60)
        logger.info("EchoNote Application Starting")
        logger.info("=" * 60)

        # Create startup timer
        from utils.startup_optimizer import StartupTimer

        timer = StartupTimer()
        timer.checkpoint("logging_initialized")

        # Install global exception hook
        sys.excepthook = exception_hook
        logger.info("Global exception handler installed")

        # Initialize PySide6 application FIRST (needed for splash screen)
        logger.info("Initializing PySide6 application...")
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        # Enable high DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        app = QApplication(sys.argv)
        app.setApplicationName("EchoNote")
        app.setOrganizationName("EchoNote")
        app.setOrganizationDomain("echonote.app")

        logger.info("PySide6 application initialized")
        timer.checkpoint("qt_initialized")

        # Load configuration early to display accurate version on splash screen
        logger.info("Loading configuration...")
        config = ConfigManager()
        app_version = config.get("version", "") or ""

        # Show splash screen
        from ui.common.splash_screen import SplashScreen

        splash = SplashScreen(version=app_version)
        splash.show()
        splash.show_progress("Initializing...", 0)
        app.processEvents()  # Process events to show splash

        # Check first run and perform setup
        splash.show_progress("Checking first run...", 5)
        app.processEvents()

        is_first_run = FirstRunSetup.is_first_run()
        if is_first_run:
            logger.info("First run detected, performing basic setup...")
            FirstRunSetup.setup()
            logger.info("First run basic setup completed")

        timer.checkpoint("first_run_checked")

        # Load configuration (already loaded above; update splash for user feedback)
        splash.show_progress("Loading configuration...", 10)
        app.processEvents()

        logger.info("Configuration loaded successfully (version: %s)", app_version or "unknown")
        timer.checkpoint("config_loaded")

        # Early FFmpeg check - detect system and log status
        splash.show_progress("Checking system dependencies...", 15)
        app.processEvents()

        logger.info("Performing early system check...")
        import platform

        system_name = platform.system()
        logger.info(f"Detected operating system: {system_name}")

        from utils.ffmpeg_checker import get_ffmpeg_checker

        ffmpeg_checker = get_ffmpeg_checker()
        ffmpeg_available = ffmpeg_checker.check_and_log()

        if not ffmpeg_available:
            logger.warning(
                "FFmpeg is not installed. Video format support will be limited. "
                "User will be prompted to install after application starts."
            )
            # Get platform-specific installation hint for logs
            title, instructions = ffmpeg_checker.get_installation_instructions()
            logger.info(f"Installation guide available: {title}")
        else:
            logger.info("FFmpeg is available - full format support enabled")

        timer.checkpoint("ffmpeg_checked")

        # Initialize database connection
        splash.show_progress("Initializing database...", 20)
        app.processEvents()

        logger.info("Initializing database connection...")
        from data.database.connection import DatabaseConnection
        from data.security.encryption import SecurityManager
        from data.security.secrets_manager import SecretsManager

        security_manager = SecurityManager()

        from data.database.encryption_helper import initialize_encryption_helper

        initialize_encryption_helper(security_manager)
        secrets_manager = SecretsManager(security_manager=security_manager)

        db_path = config.get("database.path")
        encryption_enabled = config.get("database.encryption_enabled", True)

        if encryption_enabled:
            # Use first 32 chars of encrypted key as database encryption key
            db_encryption_key = security_manager.encryption_key[:32].hex()
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

        timer.checkpoint("database_initialized")

        # Initialize internationalization
        splash.show_progress("Loading language resources...", 30)
        app.processEvents()

        logger.info("Initializing internationalization...")
        from utils.i18n import I18nQtManager

        language = config.get("ui.language", "zh_CN")
        i18n = I18nQtManager(default_language=language)
        logger.info(f"Internationalization initialized (language: {language})")
        timer.checkpoint("i18n_initialized")

        # Initialize all managers
        splash.show_progress("Initializing core managers...", 40)
        app.processEvents()

        logger.info("Initializing managers...")
        managers = {}

        # Store database connection and security managers in managers
        managers["db_connection"] = db
        managers["security_manager"] = security_manager
        managers["secrets_manager"] = secrets_manager

        # Initialize file manager
        logger.info("Initializing file manager...")
        from data.storage.file_manager import FileManager

        recordings_path = config.get(
            "realtime.recording_save_path", "~/Documents/EchoNote/Recordings"
        )
        file_manager = FileManager(recordings_path)
        managers["file_manager"] = file_manager
        logger.info("File manager initialized")

        # Initialize settings manager
        logger.info("Initializing settings manager...")
        from core.settings.manager import SettingsManager

        settings_manager = SettingsManager(config)
        managers["settings_manager"] = settings_manager
        logger.info("Settings manager initialized")

        # Initialize usage tracker
        logger.info("Initializing usage tracker...")
        from engines.speech.usage_tracker import UsageTracker

        usage_tracker = UsageTracker(db)
        managers["usage_tracker"] = usage_tracker
        logger.info("Usage tracker initialized")

        # Initialize model manager (must be before speech engine)
        logger.info("Initializing model manager...")
        from core.models.manager import ModelManager

        model_manager = ModelManager(config, db)
        managers["model_manager"] = model_manager
        logger.info("Model manager initialized")

        # Initialize speech engine with lazy loading
        splash.show_progress("Preparing speech engine...", 50)
        app.processEvents()

        logger.info("Setting up speech engine (lazy loading)...")
        from engines.speech.faster_whisper_engine import FasterWhisperEngine
        from utils.startup_optimizer import LazyLoader

        model_size = config.get("transcription.faster_whisper.model_size", "base")
        device = config.get("transcription.faster_whisper.device", "auto")
        compute_type = config.get("transcription.faster_whisper.compute_type", "int8")

        # Use lazy loading for speech engine (heavy model loading)
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
        managers["speech_engine_loader"] = speech_engine_loader

        # For backward compatibility, provide direct access
        # The engine will be loaded on first access
        class SpeechEngineProxy:
            def __getattr__(self, name):
                return getattr(speech_engine_loader.get(), name)

        managers["speech_engine"] = SpeechEngineProxy()
        logger.info("Speech engine configured (will load on first use)")

        # Initialize transcription manager
        splash.show_progress("Initializing transcription manager...", 55)
        app.processEvents()

        logger.info("Initializing transcription manager...")
        from core.transcription.manager import TranscriptionManager

        transcription_manager = TranscriptionManager(
            db, managers["speech_engine"], config.get("transcription", {})
        )
        managers["transcription_manager"] = transcription_manager
        logger.info("Transcription manager initialized")

        # Initialize resource monitor
        splash.show_progress("Initializing resource monitor...", 60)
        app.processEvents()

        logger.info("Initializing resource monitor...")
        from utils.resource_monitor import get_resource_monitor

        resource_monitor = get_resource_monitor()
        managers["resource_monitor"] = resource_monitor

        # Connect resource monitor signals to transcription manager
        on_low_memory, on_resources_recovered = _create_resource_monitor_handlers(
            transcription_manager,
            i18n,
            logger,
        )

        # Connect signals
        resource_monitor.low_memory_warning.connect(on_low_memory)
        resource_monitor.resources_recovered.connect(on_resources_recovered)

        # Start monitoring
        resource_monitor.start()
        logger.info("Resource monitoring started")
        timer.checkpoint("resource_monitor_initialized")

        # Initialize audio capture
        logger.info("Initializing audio capture...")
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
            logger.warning(
                "Install PyAudio with 'pip install pyaudio' to enable microphone capture."
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Audio capture unavailable due to runtime error. Real-time recording will be disabled."
            )
            logger.warning("Audio capture initialization error: %s", exc, exc_info=True)

        managers["audio_capture"] = audio_capture

        # Initialize translation engine (optional) with lazy loading
        logger.info("Setting up translation engine (lazy loading)...")

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
        managers["translation_engine_loader"] = translation_engine_loader

        # For backward compatibility
        class TranslationEngineProxy:
            def __getattr__(self, name):
                engine = translation_engine_loader.get()
                if engine is None:
                    raise AttributeError(f"Translation engine not available")
                return getattr(engine, name)

            def __bool__(self):
                return translation_engine_loader.get() is not None

        managers["translation_engine"] = TranslationEngineProxy()
        logger.info("Translation engine configured (will load on first use)")

        # Initialize realtime recorder
        splash.show_progress("Initializing realtime recorder...", 65)
        app.processEvents()

        logger.info("Initializing realtime recorder...")
        from core.realtime.recorder import RealtimeRecorder

        realtime_recorder = RealtimeRecorder(
            audio_capture=audio_capture,
            speech_engine=managers["speech_engine"],
            translation_engine=managers["translation_engine"],
            db_connection=db,
            file_manager=file_manager,
            i18n=i18n,
        )
        managers["realtime_recorder"] = realtime_recorder
        logger.info("Realtime recorder initialized")

        # Initialize OAuth manager
        logger.info("Initializing OAuth manager...")
        from data.security.oauth_manager import OAuthManager

        oauth_manager = OAuthManager(security_manager)
        managers["oauth_manager"] = oauth_manager
        logger.info("OAuth manager initialized")

        # Initialize calendar sync adapters
        logger.info("Initializing calendar sync adapters...")
        sync_adapters = {}

        # Get OAuth configuration
        oauth_config = config.get("calendar", {}).get("oauth", {})
        redirect_uri = oauth_config.get("redirect_uri", "http://localhost:8080/callback")

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

        managers["sync_adapters"] = sync_adapters

        # Initialize calendar manager
        splash.show_progress("Initializing calendar manager...", 70)
        app.processEvents()

        logger.info("Initializing calendar manager...")
        from core.calendar.manager import CalendarManager

        calendar_manager = CalendarManager(db, sync_adapters, oauth_manager=oauth_manager)
        managers["calendar_manager"] = calendar_manager
        logger.info("Calendar manager initialized")

        # Initialize timeline manager
        logger.info("Initializing timeline manager...")
        from core.timeline.manager import TimelineManager

        timeline_manager = TimelineManager(
            calendar_manager,
            db,
            i18n=i18n,
        )
        managers["timeline_manager"] = timeline_manager
        logger.info("Timeline manager initialized")
        timer.checkpoint("critical_managers_initialized")

        logger.info("All critical managers initialized successfully")

        # Create and show main window
        splash.show_progress("Creating main window...", 80)
        app.processEvents()

        logger.info("Creating main window...")
        from ui.main_window import MainWindow

        main_window = MainWindow(managers, i18n)
        timer.checkpoint("main_window_created")

        splash.show_progress("Starting application...", 90)
        app.processEvents()

        main_window.show()
        logger.info("Main window created and shown")

        # Close splash screen with delay
        splash.finish_with_delay(main_window, delay_ms=500)
        timer.checkpoint("splash_closed")

        # Show first run wizard if this is the first run
        if is_first_run:
            logger.info("Showing first run wizard...")
            from utils.first_run_setup import FirstRunWizard

            wizard_completed = FirstRunWizard.show_wizard(config, model_manager, i18n, main_window)

            if wizard_completed:
                logger.info("First run wizard completed successfully")
                # Apply theme from wizard selection
                theme = config.get("ui.theme", "light")
                main_window.apply_theme(theme)
            else:
                logger.info("First run wizard was skipped or cancelled")

        # Background initialization for non-critical components
        logger.info("Starting background initialization...")
        from utils.startup_optimizer import BackgroundInitializer

        # Get reminder time and sync interval from config
        reminder_minutes = config.get("timeline.reminder_minutes", 5)
        sync_interval = config.get("calendar.sync_interval_minutes", 15)

        bg_init_functions = [
            (
                "sync_scheduler",
                lambda: _create_sync_scheduler(calendar_manager, sync_interval),
            ),
            (
                "auto_task_scheduler",
                lambda: _create_auto_task_scheduler(
                    timeline_manager,
                    realtime_recorder,
                    db,
                    file_manager,
                    reminder_minutes,
                    settings_manager,
                    i18n,
                ),
            ),
        ]

        bg_init = BackgroundInitializer(bg_init_functions)

        def on_background_init_complete(results):
            """Handle background initialization completion."""
            logger.info("Background initialization complete")

            # Update managers with background-initialized components
            for name, component in results.items():
                managers[name] = component
                logger.info(f"Background component ready: {name}")

            # Start schedulers
            if "sync_scheduler" in results and results["sync_scheduler"]:
                # Check if there are any connected external calendars
                try:
                    sync_status = db.execute(
                        "SELECT COUNT(*) as count FROM calendar_sync_status WHERE is_active = 1"
                    )
                    if sync_status and sync_status[0]["count"] > 0:
                        logger.info("Starting sync scheduler...")
                        results["sync_scheduler"].start()
                        logger.info("Sync scheduler started")
                    else:
                        logger.info("No external calendars connected, sync scheduler not started")
                except Exception as e:
                    logger.warning(f"Could not start sync scheduler: {e}")

            if "auto_task_scheduler" in results and results["auto_task_scheduler"]:
                try:
                    logger.info("Starting auto task scheduler...")
                    results["auto_task_scheduler"].start()
                    logger.info("Auto task scheduler started")
                except Exception as e:
                    logger.error(f"Could not start auto task scheduler: {e}")

            logger.info("Background services started")

        bg_init.finished.connect(on_background_init_complete)
        bg_init.start()
        logger.info("Background initialization started")

        # Check FFmpeg availability and show installation dialog if needed
        logger.info("Checking FFmpeg availability...")
        from utils.ffmpeg_checker import get_ffmpeg_checker

        ffmpeg_checker = get_ffmpeg_checker()
        if not ffmpeg_checker.check_and_log():
            # FFmpeg not available, check if we should show dialog
            show_ffmpeg_dialog = config.get("ui.show_ffmpeg_install_dialog", True)

            if show_ffmpeg_dialog:
                logger.info("Showing FFmpeg installation dialog...")
                from ui.dialogs.ffmpeg_install_dialog import FFmpegInstallDialog

                title, instructions = ffmpeg_checker.get_installation_instructions(i18n)
                dialog = FFmpegInstallDialog(title, instructions, i18n, main_window)
                dialog.exec()

                # Save preference if user chose not to show again
                if not dialog.should_show_again():
                    config.set("ui.show_ffmpeg_install_dialog", False)
                    config.save()
                    logger.info("User chose not to show FFmpeg dialog again")
        else:
            logger.info("FFmpeg is available")

        # Show model recommendation dialog if no models are available
        logger.info("Checking if model recommendation is needed...")
        downloaded_models = model_manager.get_downloaded_models()

        # Check if configured model is available (without loading the engine)
        configured_model_available = model_manager.is_model_downloaded(model_size)

        if not downloaded_models or not configured_model_available:
            if not downloaded_models:
                logger.info("No models downloaded, showing recommendation dialog...")
            else:
                logger.warning(
                    f"Configured model '{model_size}' is not available, "
                    f"showing recommendation dialog..."
                )

            user_downloaded = FirstRunSetup.show_model_recommendation_dialog(
                model_manager, i18n, main_window
            )

            # If user chose to download later, show a reminder in the main window
            if not user_downloaded:
                logger.info("User chose to download later, showing reminder...")
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    main_window,
                    i18n.t("settings.model_management.reminder_title"),
                    i18n.t("settings.model_management.reminder_message"),
                    QMessageBox.StandardButton.Ok,
                )
        else:
            logger.info(f"Found {len(downloaded_models)} downloaded model(s)")

        # Start model validation (after Qt event loop is running)
        logger.info("Starting model validation...")
        model_manager.start_validation()

        logger.info("Application initialization complete")
        logger.info("=" * 60)

        # Log startup performance summary
        timer.log_summary()

        # Start application event loop
        exit_code = app.exec()

        logger.info("Application event loop exited")

        # Cleanup
        logger.info("Performing cleanup...")

        close_lazy_loaded_engine("speech engine", speech_engine_loader, logger)
        close_lazy_loaded_engine("translation engine", translation_engine_loader, logger)

        db.close_all()
        logger.info("Cleanup complete")

        return exit_code

    except Exception as e:
        print(f"Fatal error during application startup: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
