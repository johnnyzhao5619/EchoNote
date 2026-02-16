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

import sys

from config.app_config import ConfigManager
from utils.exception_handler import install_exception_hook
from utils.first_run_setup import FirstRunSetup
from utils.logger import setup_logging
from utils.resource_cleanup import close_lazy_loaded_engine


def main():
    """Application entry point."""
    global _logger

    try:
        speech_engine_loader = None
        translation_engine_loader = None

        # Initialize logging system
        logger = setup_logging()
        _logger = logger  # Set global logger for exception hook

        from config.constants import LOG_SEPARATOR_LENGTH

        logger.info("=" * LOG_SEPARATOR_LENGTH)
        logger.info("EchoNote Application Starting")
        logger.info("=" * LOG_SEPARATOR_LENGTH)

        # Create startup timer
        from utils.startup_optimizer import StartupTimer

        timer = StartupTimer()
        timer.checkpoint("logging_initialized")

        # Install global exception hook
        install_exception_hook(logger)
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

        # Set application icon
        from PySide6.QtGui import QIcon
        import os

        icon_path = os.path.join("resources", "icons", "echonote.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        logger.info("PySide6 application initialized")
        timer.checkpoint("qt_initialized")

        # Load configuration early to display accurate version on splash screen
        logger.info("Loading configuration...")
        config = ConfigManager()

        # Get version directly from version module for consistency
        from config import get_display_version

        app_version = get_display_version()

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

        from config.constants import STARTUP_PROGRESS_STEPS

        # Load configuration (already loaded above; update splash for user feedback)
        splash.show_progress("Loading configuration...", STARTUP_PROGRESS_STEPS["configuration"])
        app.processEvents()

        logger.info("Configuration loaded successfully (version: %s)", app_version)
        timer.checkpoint("config_loaded")

        # Early FFmpeg check - detect system and log status
        splash.show_progress(
            "Checking system dependencies...", STARTUP_PROGRESS_STEPS["dependencies"]
        )
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
        splash.show_progress("Initializing database...", STARTUP_PROGRESS_STEPS["database"])
        app.processEvents()

        logger.info("Initializing database connection...")
        from data.security.encryption import SecurityManager
        from data.security.secrets_manager import SecretsManager
        from utils.app_initializer import initialize_database

        security_manager = SecurityManager()
        secrets_manager = SecretsManager(security_manager=security_manager)
        db = initialize_database(config, security_manager)
        # Initialize internationalization
        splash.show_progress("Loading language resources...", STARTUP_PROGRESS_STEPS["i18n"])
        app.processEvents()

        logger.info("Initializing internationalization...")
        from utils.i18n import I18nQtManager

        language = config.get("ui.language", "en_US")
        i18n = I18nQtManager(default_language=language)
        logger.info(f"Internationalization initialized (language: {language})")
        timer.checkpoint("i18n_initialized")

        # Initialize all managers
        splash.show_progress("Initializing core managers...", STARTUP_PROGRESS_STEPS["managers"])
        app.processEvents()

        logger.info("Initializing managers...")
        managers = {}

        # Store database connection and security managers in managers
        managers["db_connection"] = db
        managers["security_manager"] = security_manager
        managers["secrets_manager"] = secrets_manager

        # Initialize file manager
        logger.info("Initializing file manager...")
        from pathlib import Path

        from config.constants import DEFAULT_RECORDINGS_PATH
        from data.storage.file_manager import FileManager

        recordings_path = config.get("realtime.recording_save_path", DEFAULT_RECORDINGS_PATH)
        default_base_dir = str(Path(DEFAULT_RECORDINGS_PATH).expanduser().parent)
        file_manager = FileManager(base_dir=default_base_dir, recordings_dir=recordings_path)
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
        splash.show_progress("Preparing speech engine...", STARTUP_PROGRESS_STEPS["speech_engine"])
        app.processEvents()

        logger.info("Setting up speech engine (lazy loading)...")
        from utils.app_initializer import EngineProxy, initialize_speech_engine

        speech_engine_loader = initialize_speech_engine(
            config,
            model_manager,
            managers.get("secrets_manager"),
            db,
        )
        managers["speech_engine_loader"] = speech_engine_loader
        managers["speech_engine"] = EngineProxy(speech_engine_loader)

        # Initialize transcription manager
        splash.show_progress(
            "Initializing transcription manager...", STARTUP_PROGRESS_STEPS["transcription"]
        )
        app.processEvents()

        logger.info("Initializing transcription manager...")
        from core.transcription.manager import TranscriptionManager

        transcription_manager = TranscriptionManager(
            db, managers["speech_engine"], config.get("transcription", {})
        )
        managers["transcription_manager"] = transcription_manager
        logger.info("Transcription manager initialized")

        # Initialize resource monitor
        splash.show_progress(
            "Initializing resource monitor...", STARTUP_PROGRESS_STEPS["resource_monitor"]
        )
        app.processEvents()

        logger.info("Initializing resource monitor...")
        from utils.resource_monitor import get_resource_monitor

        resource_monitor = get_resource_monitor()
        managers["resource_monitor"] = resource_monitor

        # Connect resource monitor signals to transcription manager
        from utils.app_initializer import create_resource_monitor_handlers

        on_low_memory, on_resources_recovered = create_resource_monitor_handlers(
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
        from utils.app_initializer import initialize_audio_capture

        audio_capture = initialize_audio_capture()
        managers["audio_capture"] = audio_capture

        # Initialize translation engine (optional) with lazy loading
        logger.info("Setting up translation engine (lazy loading)...")
        from utils.app_initializer import TranslationEngineProxy, initialize_translation_engine

        translation_engine_loader = initialize_translation_engine(config)
        managers["translation_engine_loader"] = translation_engine_loader
        managers["translation_engine"] = TranslationEngineProxy(translation_engine_loader)

        # Initialize realtime recorder
        splash.show_progress(
            "Initializing realtime recorder...", STARTUP_PROGRESS_STEPS["realtime_recorder"]
        )
        app.processEvents()

        logger.info("Initializing realtime recorder...")
        from core.realtime.config import RealtimeConfig
        from core.realtime.recorder import RealtimeRecorder

        realtime_preferences = settings_manager.get_realtime_preferences()
        realtime_config = RealtimeConfig(
            vad_threshold=float(realtime_preferences.get("vad_threshold", 0.5)),
            silence_duration_ms=int(realtime_preferences.get("silence_duration_ms", 2000)),
            min_audio_duration=float(realtime_preferences.get("min_audio_duration", 3.0)),
        )

        realtime_recorder = RealtimeRecorder(
            audio_capture=audio_capture,
            speech_engine=managers["speech_engine"],
            translation_engine=managers["translation_engine"],
            db_connection=db,
            file_manager=file_manager,
            i18n=i18n,
            config=realtime_config,
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
        from utils.app_initializer import initialize_calendar_adapters

        sync_adapters = initialize_calendar_adapters(config, oauth_manager)
        managers["sync_adapters"] = sync_adapters

        # Initialize calendar manager
        splash.show_progress("Initializing calendar manager...", STARTUP_PROGRESS_STEPS["calendar"])
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
        splash.show_progress("Creating main window...", STARTUP_PROGRESS_STEPS["main_window"])
        app.processEvents()

        logger.info("Creating main window...")
        from ui.main_window import MainWindow

        main_window = MainWindow(managers, i18n)
        timer.checkpoint("main_window_created")

        splash.show_progress("Starting application...", STARTUP_PROGRESS_STEPS["final"])
        app.processEvents()

        main_window.show()
        logger.info("Main window created and shown")

        from config.constants import SPLASH_SCREEN_DELAY_MS

        # Close splash screen with delay
        splash.finish_with_delay(main_window, delay_ms=SPLASH_SCREEN_DELAY_MS)
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
        from config.constants import DEFAULT_REMINDER_MINUTES, DEFAULT_SYNC_INTERVAL_MINUTES
        from utils.startup_optimizer import BackgroundInitializer

        # Get reminder time and sync interval from config
        reminder_minutes = config.get("timeline.reminder_minutes", DEFAULT_REMINDER_MINUTES)
        sync_interval = config.get("calendar.sync_interval_minutes", DEFAULT_SYNC_INTERVAL_MINUTES)

        from utils.app_initializer import create_auto_task_scheduler, create_sync_scheduler

        bg_init_functions = [
            (
                "sync_scheduler",
                lambda: create_sync_scheduler(calendar_manager, sync_interval),
            ),
            (
                "auto_task_scheduler",
                lambda: create_auto_task_scheduler(
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
            # Update managers with background-initialized components
            for name, component in results.items():
                managers[name] = component
                logger.info(f"Background component ready: {name}")

            from utils.post_init_tasks import start_background_services

            start_background_services(results, config, db, logger)

        bg_init.finished.connect(on_background_init_complete)
        bg_init.start()
        logger.info("Background initialization started")

        # Check FFmpeg availability and show installation dialog if needed
        from utils.post_init_tasks import check_ffmpeg_availability, check_model_availability

        check_ffmpeg_availability(config, i18n, main_window)

        # Validate local models before prompting download recommendations.
        logger.info("Starting model validation...")
        model_manager.start_validation(deferred=False)
        check_model_availability(config, model_manager, i18n, main_window)

        logger.info("Application initialization complete")
        logger.info("=" * LOG_SEPARATOR_LENGTH)

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
