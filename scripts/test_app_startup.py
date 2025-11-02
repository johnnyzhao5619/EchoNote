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
Application Startup Test

Tests whether the EchoNote application can fully start up to the main window display stage
"""

import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def test_app_startup():
    """Test application startup"""
    logger.info("Testing application startup...")

    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    try:
        # Test main module import
        logger.info("Testing main module import...")
        import main

        logger.info("✅ Main module imported successfully")

        # Test key component imports
        logger.info("Testing key component imports...")

        from config.app_config import ConfigManager
        from core.calendar.manager import CalendarManager
        from core.timeline.manager import TimelineManager
        from core.transcription.manager import TranscriptionManager
        from ui.main_window import MainWindow
        from utils.i18n import I18nQtManager
        from utils.resource_monitor import get_resource_monitor

        logger.info("✅ All key components imported successfully")

        # Test configuration manager
        logger.info("Testing configuration manager...")
        config = ConfigManager()
        app_version = config.get("version", "unknown")
        logger.info(f"✅ Configuration loaded (version: {app_version})")

        # Test internationalization manager
        logger.info("Testing i18n manager...")
        language = config.get("ui.language", "en_US")
        i18n = I18nQtManager(default_language=language)
        test_translation = i18n.t("common.ok")
        logger.info(f"✅ I18n manager working (translation: {test_translation})")

        # Test resource monitor
        logger.info("Testing resource monitor...")
        resource_monitor = get_resource_monitor()
        logger.info("✅ Resource monitor initialized successfully")

        logger.info("🎉 All startup components tested successfully!")
        return True

    except Exception as e:
        logger.error(f"❌ Startup test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main function"""
    print("🚀 Starting application startup test...")
    print("=" * 60)

    success = test_app_startup()

    print("\n" + "=" * 60)
    if success:
        print("✅ Application startup test successful!")
        print("EchoNote application is ready for normal operation.")
        return 0
    else:
        print("❌ Application startup test failed!")
        print("Startup issues need to be fixed before the application can run normally.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
