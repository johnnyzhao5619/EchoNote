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
Tests for enhanced i18n functionality including complex dynamic strings,
conditional text, and performance optimizations.
"""

import pytest
import tempfile
import json
from pathlib import Path
from utils.i18n import I18nManager

class TestI18nEnhanced:
    """Test enhanced i18n functionality."""

    @pytest.fixture
    def temp_translations_dir(self):
        """Create temporary translations directory with test data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            translations_dir = Path(temp_dir)

            # Create test translation files
            zh_translations = {
                "simple": {
                    "message": "简单消息",
                    "with_param": "参数: {value}",
                    "multiple_params": "用户 {name} 有 {count} 个文件",
                    "conditional": "状态: {status|活跃|非活跃}",
                    "complex": "处理了 {total} 个项目，{success} 个成功",
                    "complex_with_errors": (
                        "处理了 {total} 个项目，{success} 个成功，{errors} 个失败"
                    ),
                    "plural_test": "文件",
                    "plural_test_plural": "文件",
                }
            }

            en_translations = {
                "simple": {
                    "message": "Simple message",
                    "with_param": "Parameter: {value}",
                    "multiple_params": "User {name} has {count} files",
                    "conditional": "Status: {status|Active|Inactive}",
                    "complex": "Processed {total} items, {success} successful",
                    "complex_with_errors": (
                        "Processed {total} items, {success} successful, {errors} failed"
                    ),
                    "plural_test": "file",
                    "plural_test_plural": "files",
                }
            }

            # Write translation files
            with open(translations_dir / "zh_CN.json", "w", encoding="utf-8") as f:
                json.dump(zh_translations, f, ensure_ascii=False, indent=2)

            with open(translations_dir / "en_US.json", "w", encoding="utf-8") as f:
                json.dump(en_translations, f, ensure_ascii=False, indent=2)

            yield translations_dir

    @pytest.fixture
    def i18n_manager(self, temp_translations_dir):
        """Create I18nManager instance with test data."""
        return I18nManager(str(temp_translations_dir), "zh_CN")

    def test_simple_translation(self, i18n_manager):
        """Test basic translation functionality."""
        result = i18n_manager.t("simple.message")
        assert result == "简单消息"

    def test_parameter_substitution(self, i18n_manager):
        """Test basic parameter substitution."""
        result = i18n_manager.t("simple.with_param", value="测试值")
        assert result == "参数: 测试值"

    def test_multiple_parameters(self, i18n_manager):
        """Test multiple parameter substitution."""
        result = i18n_manager.t("simple.multiple_params", name="张三", count=5)
        assert result == "用户 张三 有 5 个文件"

    def test_conditional_text_true(self, i18n_manager):
        """Test conditional text when condition is True."""
        result = i18n_manager.t("simple.conditional", condition=True, status=True)
        assert result == "状态: 活跃"

    def test_conditional_text_false(self, i18n_manager):
        """Test conditional text when condition is False."""
        result = i18n_manager.t("simple.conditional", condition=False, status=False)
        assert result == "状态: 非活跃"

    def test_complex_dynamic_string(self, i18n_manager):
        """Test complex dynamic string with multiple parameters."""
        # Test without errors
        result = i18n_manager.t("simple.complex", total=10, success=8)
        assert result == "处理了 10 个项目，8 个成功"

        # Test with errors
        result = i18n_manager.t("simple.complex_with_errors", total=10, success=6, errors=4)
        assert result == "处理了 10 个项目，6 个成功，4 个失败"

    def test_plural_forms(self, i18n_manager):
        """Test basic plural form handling."""
        # Singular
        result = i18n_manager.t("simple.plural_test", count=1)
        assert result == "文件"

        # Plural
        result = i18n_manager.t("simple.plural_test", count=5)
        assert result == "文件"  # Chinese doesn't change for plural

    def test_fallback_parameter(self, i18n_manager):
        """Test fallback parameter for missing keys."""
        result = i18n_manager.t("nonexistent.key", fallback="默认文本")
        assert result == "默认文本"

    def test_missing_parameter_handling(self, i18n_manager):
        """Test handling of missing parameters."""
        result = i18n_manager.t("simple.with_param")  # Missing 'value' parameter
        assert "参数:" in result  # Should still contain the base text

    def test_parameter_validation(self, i18n_manager):
        """Test parameter validation functionality."""
        validation = i18n_manager.validate_parameters(
            "simple.multiple_params", name="test", count=5
        )
        assert validation["valid"] is True
        assert "name" in validation["expected_parameters"]
        assert "count" in validation["expected_parameters"]

        # Test missing parameters
        validation = i18n_manager.validate_parameters("simple.multiple_params", name="test")
        assert validation["valid"] is False
        assert "count" in validation["missing_parameters"]

    def test_parameter_info(self, i18n_manager):
        """Test parameter information extraction."""
        info = i18n_manager.get_parameter_info("simple.multiple_params")
        assert "name" in info["parameters"]
        assert "count" in info["parameters"]

    def test_language_switching(self, i18n_manager):
        """Test language switching with cache clearing."""
        # Test Chinese
        result = i18n_manager.t("simple.message")
        assert result == "简单消息"

        # Switch to English
        i18n_manager.change_language("en_US")
        result = i18n_manager.t("simple.message")
        assert result == "Simple message"

        # Test parameters in English
        result = i18n_manager.t("simple.with_param", value="test value")
        assert result == "Parameter: test value"

    def test_template_caching(self, i18n_manager):
        """Test template caching functionality."""
        # First call should create cache entry
        result1 = i18n_manager.t("simple.multiple_params", name="test", count=1)

        # Second call should use cached template
        result2 = i18n_manager.t("simple.multiple_params", name="test", count=1)

        assert result1 == result2

        # Check cache stats
        stats = i18n_manager.get_cache_stats()
        assert stats["parameter_cache_size"] > 0

    def test_precompile_templates(self, i18n_manager):
        """Test template precompilation."""
        i18n_manager.precompile_templates()

        stats = i18n_manager.get_cache_stats()
        assert stats["template_cache_size"] >= 0
        assert stats["parameter_cache_size"] > 0

    def test_cache_clearing(self, i18n_manager):
        """Test cache clearing functionality."""
        # Generate some cache entries
        i18n_manager.t("simple.with_param", value="test")
        i18n_manager.get_parameter_info("simple.multiple_params")

        # Clear caches
        i18n_manager.clear_caches()

        stats = i18n_manager.get_cache_stats()
        assert stats["template_cache_size"] == 0
        assert stats["parameter_cache_size"] == 0

    def test_error_handling(self, i18n_manager):
        """Test error handling in dynamic strings."""
        # Test with invalid template syntax (should not crash)
        result = i18n_manager.t("simple.with_param", invalid_param="test")
        assert isinstance(result, str)  # Should return some string, not crash

    def test_cache_performance(self, i18n_manager):
        """Test caching improves performance."""
        # Multiple calls should use cached results
        key = "simple.multiple_params"
        params = {"name": "test", "count": 5}

        result1 = i18n_manager.t(key, **params)
        result2 = i18n_manager.t(key, **params)

        assert result1 == result2
        # Parameter info should be cached
        assert key in i18n_manager._parameter_cache

    def test_complex_parameter_detection(self, i18n_manager):
        """Test complex parameter pattern detection."""
        # Simple parameters should not be detected as complex
        assert not i18n_manager._has_complex_parameters("Simple {param}")

        # Conditional patterns should be detected as complex
        assert i18n_manager._has_complex_parameters("Status: {status|Active|Inactive}")

    def test_conditional_text_handling(self, i18n_manager):
        """Test conditional text pattern handling."""
        text = "Status: {status|Active|Inactive}"

        result_true = i18n_manager._handle_conditional_text(text, True, {"status": True})
        assert result_true == "Status: Active"

        result_false = i18n_manager._handle_conditional_text(text, False, {"status": False})
        assert result_false == "Status: Inactive"
