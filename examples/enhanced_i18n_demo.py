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
Enhanced I18n Demo - Demonstrates the new dynamic string capabilities.

This example shows how to use the enhanced i18n features in a real application context.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.i18n import I18nManager

class TranscriptionStatusDemo:
    """Demo class showing enhanced i18n usage in a transcription context."""

    def __init__(self):
        self.i18n = I18nManager()
        # Precompile templates for better performance
        self.i18n.precompile_templates()

    def show_file_processing_status(self, processed: int, successful: int, failed: int):
        """Show file processing status with dynamic strings."""
        print("=== File Processing Status ===")

        # Use complex parameterized string
        status = self.i18n.t(
            "common.complex_status", processed=processed, success=successful, failed=failed
        )
        print(f"Status: {status}")

        # Show individual file counts with proper pluralization
        if processed == 1:
            file_msg = self.i18n.t("common.file_count", count=processed)
        else:
            file_msg = self.i18n.t("common.file_count", count=processed)
        print(f"Files: {file_msg}")

    def show_task_status(self, task_name: str, is_completed: bool):
        """Show task status with conditional text."""
        print(f"\n=== Task Status: {task_name} ===")

        # Use conditional text based on completion status
        status = self.i18n.t(
            "common.task_status",
            name=task_name,
            condition=True,  # Enable conditional processing
            status=is_completed,
        )
        print(f"Status: {status}")

    def show_error_handling(self, has_error: bool, error_message: str = None):
        """Demonstrate error handling with conditional messages."""
        print(f"\n=== Error Handling Demo ===")

        if has_error and error_message:
            result = self.i18n.t(
                "common.conditional_message", condition=True, has_error=True, error=error_message
            )
        else:
            result = self.i18n.t("common.conditional_message", condition=False, has_error=False)

        print(f"Result: {result}")

    def demonstrate_parameter_validation(self):
        """Demonstrate parameter validation features."""
        print(f"\n=== Parameter Validation Demo ===")

        # Validate parameters before use
        validation = self.i18n.validate_parameters(
            "common.complex_status", processed=10, success=8, failed=2
        )

        print(f"Validation result: {'✓' if validation['valid'] else '✗'}")
        if not validation["valid"]:
            print(f"Missing parameters: {validation['missing_parameters']}")

        # Show parameter info
        info = self.i18n.get_parameter_info("common.complex_status")
        print(f"Expected parameters: {info['parameters']}")

    def demonstrate_multilingual_support(self):
        """Demonstrate multilingual support with dynamic strings."""
        print(f"\n=== Multilingual Support Demo ===")

        languages = ["zh_CN", "en_US", "fr_FR"]

        for lang in languages:
            self.i18n.change_language(lang)
            print(f"\n{lang}:")

            # Show file count
            file_count = self.i18n.t("common.file_count", count=5)
            print(f"  File count: {file_count}")

            # Show complex status
            status = self.i18n.t("common.complex_status", processed=10, success=8, failed=2)
            print(f"  Status: {status}")

    def show_performance_stats(self):
        """Show performance statistics."""
        print(f"\n=== Performance Statistics ===")

        stats = self.i18n.get_cache_stats()
        print(f"Template cache size: {stats['template_cache_size']}")
        print(f"Parameter cache size: {stats['parameter_cache_size']}")

        # Demonstrate performance with cached templates
        import time

        start_time = time.time()
        for i in range(1000):
            self.i18n.t("common.complex_status", processed=i, success=i - 1, failed=1)
        end_time = time.time()

        print(f"Time for 1000 translations: {end_time - start_time:.4f} seconds")

def main():
    """Main demo function."""
    print("Enhanced I18n Demo - EchoNote Dynamic Strings")
    print("=" * 50)

    demo = TranscriptionStatusDemo()

    # Demonstrate various features
    demo.show_file_processing_status(processed=15, successful=12, failed=3)
    demo.show_task_status("语音转录", is_completed=True)
    demo.show_task_status("文件导出", is_completed=False)
    demo.show_error_handling(has_error=False)
    demo.show_error_handling(has_error=True, error_message="文件权限不足")
    demo.demonstrate_parameter_validation()
    demo.demonstrate_multilingual_support()
    demo.show_performance_stats()

    print(f"\n✓ Enhanced I18n demo completed successfully!")

if __name__ == "__main__":
    main()
