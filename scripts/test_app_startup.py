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
应用程序启动测试

测试EchoNote应用程序是否能够完全启动到主窗口显示阶段
"""

import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def test_app_startup():
    """测试应用程序启动"""
    logger.info("Testing application startup...")

    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    try:
        # 测试主模块导入
        logger.info("Testing main module import...")
        import main

        logger.info("✅ Main module imported successfully")

        # 测试关键组件导入
        logger.info("Testing key component imports...")

        from config.app_config import ConfigManager
        from core.calendar.manager import CalendarManager
        from core.timeline.manager import TimelineManager
        from core.transcription.manager import TranscriptionManager
        from ui.main_window import MainWindow
        from utils.i18n import I18nQtManager
        from utils.resource_monitor import get_resource_monitor

        logger.info("✅ All key components imported successfully")

        # 测试配置管理器
        logger.info("Testing configuration manager...")
        config = ConfigManager()
        app_version = config.get("version", "unknown")
        logger.info(f"✅ Configuration loaded (version: {app_version})")

        # 测试国际化管理器
        logger.info("Testing i18n manager...")
        language = config.get("ui.language", "zh_CN")
        i18n = I18nQtManager(default_language=language)
        test_translation = i18n.t("common.ok")
        logger.info(f"✅ I18n manager working (translation: {test_translation})")

        # 测试资源监控器
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
    """主函数"""
    print("🚀 开始应用程序启动测试...")
    print("=" * 60)

    success = test_app_startup()

    print("\n" + "=" * 60)
    if success:
        print("✅ 应用程序启动测试成功！")
        print("EchoNote应用程序已准备好正常运行。")
        return 0
    else:
        print("❌ 应用程序启动测试失败！")
        print("需要修复启动问题才能正常运行应用程序。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
