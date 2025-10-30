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
Post-initialization tasks for the application.

Contains tasks that run after the main window is shown, such as
FFmpeg checks, model validation, and first-run setup.
"""

import logging

logger = logging.getLogger("echonote.post_init")


def check_ffmpeg_availability(config, i18n, main_window):
    """Check FFmpeg availability and show installation dialog if needed."""
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


def check_model_availability(config, model_manager, i18n, main_window):
    """Check model availability and show recommendation dialog if needed."""
    logger.info("Checking if model recommendation is needed...")
    from utils.first_run_setup import FirstRunSetup

    downloaded_models = model_manager.get_downloaded_models()

    # Only show dialog if NO models are downloaded at all
    if not downloaded_models:
        logger.info("No models downloaded, showing recommendation dialog...")

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
        logger.info(f"Found {len(downloaded_models)} downloaded model(s), skipping dialog")
        # Note: If configured model is not available, the engine will automatically
        # use a fallback model (implemented in FasterWhisperEngine)


def start_background_services(managers, config, db, logger):
    """Start background services like sync scheduler and auto task scheduler."""
    logger.info("Background initialization complete")

    # Start schedulers
    if "sync_scheduler" in managers and managers["sync_scheduler"]:
        # Check if there are any connected external calendars
        try:
            sync_status = db.execute(
                "SELECT COUNT(*) as count FROM calendar_sync_status WHERE is_active = 1"
            )
            if sync_status and sync_status[0]["count"] > 0:
                logger.info("Starting sync scheduler...")
                managers["sync_scheduler"].start()
                logger.info("Sync scheduler started")
            else:
                logger.info("No external calendars connected, sync scheduler not started")
        except Exception as e:
            logger.warning(f"Could not start sync scheduler: {e}")

    if "auto_task_scheduler" in managers and managers["auto_task_scheduler"]:
        try:
            logger.info("Starting auto task scheduler...")
            managers["auto_task_scheduler"].start()
            logger.info("Auto task scheduler started")
        except Exception as e:
            logger.error(f"Could not start auto task scheduler: {e}")

    logger.info("Background services started")
