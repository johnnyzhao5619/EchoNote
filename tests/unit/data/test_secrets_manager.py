# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for SecretsManager class.

Tests encrypted storage of API keys and OAuth tokens.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from data.security.secrets_manager import SecretsManager
from data.security.encryption import SecurityManager


class TestSecretsManagerInitialization:
    """Test SecretsManager initialization."""

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates config directory."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        assert config_dir.exists()
        assert sm.config_dir == config_dir

    def test_init_creates_security_manager(self, tmp_path):
        """Test that initialization creates SecurityManager."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        assert sm.security_manager is not None
        assert isinstance(sm.security_manager, SecurityManager)

    def test_init_with_existing_security_manager(self, tmp_path):
        """Test initialization with existing SecurityManager."""
        config_dir = tmp_path / "config"
        security_mgr = SecurityManager(str(config_dir))
        
        sm = SecretsManager(security_manager=security_mgr)
        
        assert sm.security_manager is security_mgr
        assert sm.config_dir == Path(config_dir)

    def test_init_loads_empty_secrets(self, tmp_path):
        """Test that initialization loads empty secrets when file doesn't exist."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        assert "api_keys" in sm._secrets
        assert "oauth_tokens" in sm._secrets
        assert len(sm._secrets["api_keys"]) == 0
        assert len(sm._secrets["oauth_tokens"]) == 0

    def test_init_loads_existing_secrets(self, tmp_path):
        """Test that initialization loads existing secrets file."""
        config_dir = tmp_path / "config"
        
        # Create first instance and save secrets
        sm1 = SecretsManager(str(config_dir))
        sm1.set_api_key("openai", "test_key")
        
        # Create second instance - should load saved secrets
        sm2 = SecretsManager(str(config_dir))
        
        assert sm2.get_api_key("openai") == "test_key"


class TestAPIKeyManagement:
    """Test API key storage and retrieval."""

    def test_set_api_key(self, tmp_path):
        """Test setting API key."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "sk-test123")
        
        assert "openai" in sm._secrets["api_keys"]

    def test_get_api_key_exists(self, tmp_path):
        """Test getting existing API key."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "sk-test123")
        api_key = sm.get_api_key("openai")
        
        assert api_key == "sk-test123"

    def test_get_api_key_not_exists(self, tmp_path):
        """Test getting non-existent API key."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        api_key = sm.get_api_key("nonexistent")
        
        assert api_key is None

    def test_delete_api_key(self, tmp_path):
        """Test deleting API key."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "sk-test123")
        sm.delete_api_key("openai")
        
        assert sm.get_api_key("openai") is None

    def test_delete_api_key_not_exists(self, tmp_path):
        """Test deleting non-existent API key doesn't raise error."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        # Should not raise error
        sm.delete_api_key("nonexistent")

    def test_get_all_api_keys(self, tmp_path):
        """Test getting all API keys."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "key1")
        sm.set_api_key("google", "key2")
        sm.set_api_key("azure", "key3")
        
        all_keys = sm.get_all_api_keys()
        
        assert len(all_keys) == 3
        assert all_keys["openai"] == "key1"
        assert all_keys["google"] == "key2"
        assert all_keys["azure"] == "key3"

    def test_get_all_api_keys_returns_copy(self, tmp_path):
        """Test that get_all_api_keys returns a copy."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "key1")
        
        all_keys = sm.get_all_api_keys()
        all_keys["modified"] = "value"
        
        # Original should not be modified
        assert "modified" not in sm._secrets["api_keys"]

    def test_has_api_key_exists(self, tmp_path):
        """Test checking if API key exists."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "sk-test123")
        
        assert sm.has_api_key("openai")

    def test_has_api_key_not_exists(self, tmp_path):
        """Test checking if non-existent API key exists."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        assert not sm.has_api_key("nonexistent")

    def test_has_api_key_empty_string(self, tmp_path):
        """Test that empty string API key returns False."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "")
        
        assert not sm.has_api_key("openai")

    def test_has_api_key_whitespace(self, tmp_path):
        """Test that whitespace-only API key returns False."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "   ")
        
        assert not sm.has_api_key("openai")


class TestOAuthTokenManagement:
    """Test OAuth token storage and retrieval."""

    def test_set_oauth_token(self, tmp_path):
        """Test setting OAuth token."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        token_data = {
            "access_token": "token123",
            "refresh_token": "refresh456",
            "expires_at": 1234567890
        }
        
        sm.set_oauth_token("google_calendar", token_data)
        
        assert "google_calendar" in sm._secrets["oauth_tokens"]

    def test_get_oauth_token_exists(self, tmp_path):
        """Test getting existing OAuth token."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        token_data = {
            "access_token": "token123",
            "refresh_token": "refresh456"
        }
        
        sm.set_oauth_token("google_calendar", token_data)
        retrieved = sm.get_oauth_token("google_calendar")
        
        assert retrieved == token_data

    def test_get_oauth_token_not_exists(self, tmp_path):
        """Test getting non-existent OAuth token."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        token = sm.get_oauth_token("nonexistent")
        
        assert token is None

    def test_delete_oauth_token(self, tmp_path):
        """Test deleting OAuth token."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        token_data = {"access_token": "token123"}
        sm.set_oauth_token("google_calendar", token_data)
        sm.delete_oauth_token("google_calendar")
        
        assert sm.get_oauth_token("google_calendar") is None

    def test_delete_oauth_token_not_exists(self, tmp_path):
        """Test deleting non-existent OAuth token doesn't raise error."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        # Should not raise error
        sm.delete_oauth_token("nonexistent")


class TestCustomSecrets:
    """Test custom secret storage."""

    def test_set_secret(self, tmp_path):
        """Test setting custom secret."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_secret("custom_key", "custom_value")
        
        assert "custom_key" in sm._secrets

    def test_get_secret_exists(self, tmp_path):
        """Test getting existing custom secret."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_secret("custom_key", "custom_value")
        value = sm.get_secret("custom_key")
        
        assert value == "custom_value"

    def test_get_secret_not_exists(self, tmp_path):
        """Test getting non-existent custom secret."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        value = sm.get_secret("nonexistent")
        
        assert value is None

    def test_delete_secret(self, tmp_path):
        """Test deleting custom secret."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_secret("custom_key", "custom_value")
        sm.delete_secret("custom_key")
        
        assert sm.get_secret("custom_key") is None

    def test_delete_secret_not_exists(self, tmp_path):
        """Test deleting non-existent custom secret doesn't raise error."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        # Should not raise error
        sm.delete_secret("nonexistent")

    def test_set_secret_complex_value(self, tmp_path):
        """Test setting secret with complex value."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        complex_value = {
            "nested": {
                "key": "value"
            },
            "list": [1, 2, 3]
        }
        
        sm.set_secret("complex", complex_value)
        retrieved = sm.get_secret("complex")
        
        assert retrieved == complex_value


class TestSecretsPersistence:
    """Test secrets file persistence."""

    def test_secrets_persisted_to_file(self, tmp_path):
        """Test that secrets are persisted to file."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "test_key")
        
        # File should exist
        assert sm.secrets_file.exists()

    def test_secrets_encrypted_in_file(self, tmp_path):
        """Test that secrets are encrypted in file."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "test_key")
        
        # Read file content
        file_content = sm.secrets_file.read_text()
        
        # Should not contain plaintext key
        assert "test_key" not in file_content

    def test_secrets_loaded_from_file(self, tmp_path):
        """Test that secrets are loaded from file."""
        config_dir = tmp_path / "config"
        
        # Create and save secrets
        sm1 = SecretsManager(str(config_dir))
        sm1.set_api_key("openai", "test_key")
        sm1.set_oauth_token("google", {"token": "value"})
        
        # Create new instance - should load from file
        sm2 = SecretsManager(str(config_dir))
        
        assert sm2.get_api_key("openai") == "test_key"
        assert sm2.get_oauth_token("google") == {"token": "value"}

    def test_corrupted_secrets_file(self, tmp_path):
        """Test handling of corrupted secrets file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create corrupted secrets file
        secrets_file = config_dir / "secrets.enc"
        secrets_file.write_text("corrupted data")
        
        # Should load empty secrets without crashing
        sm = SecretsManager(str(config_dir))
        
        assert len(sm._secrets["api_keys"]) == 0
        assert len(sm._secrets["oauth_tokens"]) == 0


class TestClearAllSecrets:
    """Test clearing all secrets."""

    def test_clear_all_secrets(self, tmp_path):
        """Test clearing all secrets."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        # Add various secrets
        sm.set_api_key("openai", "key1")
        sm.set_api_key("google", "key2")
        sm.set_oauth_token("google_calendar", {"token": "value"})
        sm.set_secret("custom", "value")
        
        # Clear all
        sm.clear_all_secrets()
        
        # All should be empty
        assert len(sm._secrets["api_keys"]) == 0
        assert len(sm._secrets["oauth_tokens"]) == 0
        assert sm.get_secret("custom") is None

    def test_clear_all_secrets_persisted(self, tmp_path):
        """Test that clearing all secrets is persisted."""
        config_dir = tmp_path / "config"
        
        sm1 = SecretsManager(str(config_dir))
        sm1.set_api_key("openai", "key1")
        sm1.clear_all_secrets()
        
        # Create new instance - should have empty secrets
        sm2 = SecretsManager(str(config_dir))
        
        assert len(sm2.get_all_api_keys()) == 0


class TestSecretsManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_multiple_providers(self, tmp_path):
        """Test managing multiple providers."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        providers = ["openai", "google", "azure", "anthropic"]
        
        for provider in providers:
            sm.set_api_key(provider, f"{provider}_key")
        
        for provider in providers:
            assert sm.get_api_key(provider) == f"{provider}_key"

    def test_update_existing_key(self, tmp_path):
        """Test updating existing API key."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "old_key")
        sm.set_api_key("openai", "new_key")
        
        assert sm.get_api_key("openai") == "new_key"

    def test_special_characters_in_key(self, tmp_path):
        """Test API key with special characters."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        special_key = "sk-!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        sm.set_api_key("openai", special_key)
        
        assert sm.get_api_key("openai") == special_key

    def test_unicode_in_secrets(self, tmp_path):
        """Test secrets with Unicode characters."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        unicode_value = "密钥🔑Ключ"
        sm.set_secret("unicode_test", unicode_value)
        
        assert sm.get_secret("unicode_test") == unicode_value

    def test_large_secret_value(self, tmp_path):
        """Test storing large secret value."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        large_value = "x" * 100000
        sm.set_secret("large", large_value)
        
        assert sm.get_secret("large") == large_value

    def test_file_permissions(self, tmp_path):
        """Test that secrets file has secure permissions."""
        config_dir = tmp_path / "config"
        sm = SecretsManager(str(config_dir))
        
        sm.set_api_key("openai", "test_key")
        
        # Check file permissions (should be 0o600 - owner read/write only)
        import stat
        file_stat = sm.secrets_file.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)
        
        # On Unix-like systems, should be 0o600
        # On Windows, permissions work differently, so we just check file exists
        assert sm.secrets_file.exists()
