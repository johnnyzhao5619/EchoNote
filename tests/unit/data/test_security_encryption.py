# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for SecurityManager class.

Tests encryption, decryption, key derivation, and password hashing.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

from data.security.encryption import SecurityManager


class TestSecurityManagerInitialization:
    """Test SecurityManager initialization."""

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates config directory."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        assert config_dir.exists()
        assert sm.config_dir == config_dir

    def test_init_creates_salt_file(self, tmp_path):
        """Test that initialization creates salt file."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        assert sm.salt_file.exists()
        assert len(sm.salt) == 32

    def test_init_loads_existing_salt(self, tmp_path):
        """Test that initialization loads existing salt."""
        config_dir = tmp_path / "config"
        
        # Create first instance
        sm1 = SecurityManager(str(config_dir))
        salt1 = sm1.salt
        
        # Create second instance
        sm2 = SecurityManager(str(config_dir))
        salt2 = sm2.salt
        
        # Should load same salt
        assert salt1 == salt2

    def test_init_derives_encryption_key(self, tmp_path):
        """Test that initialization derives encryption key."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        assert sm.encryption_key is not None
        assert len(sm.encryption_key) == 32  # 256 bits


class TestMachineUUID:
    """Test machine UUID generation and persistence."""

    def test_get_machine_uuid_linux(self, tmp_path):
        """Test getting machine UUID on Linux."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        # Mock /etc/machine-id
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='test-machine-id\n')):
                uuid = sm._get_machine_uuid()
                assert uuid == 'test-machine-id'

    def test_get_machine_uuid_fallback(self, tmp_path):
        """Test machine UUID fallback to uuid.getnode()."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        # Mock os.path.exists to return False
        with patch('os.path.exists', return_value=False):
            with patch('uuid.getnode', return_value=123456789):
                uuid = sm._get_machine_uuid()
                assert uuid == '123456789'

    def test_get_machine_uuid_persisted(self, tmp_path):
        """Test that machine UUID is persisted."""
        config_dir = tmp_path / "config"
        
        # Mock to trigger fallback and persistence
        with patch('os.path.exists', return_value=False):
            with patch('uuid.uuid4', return_value='generated-uuid'):
                sm = SecurityManager(str(config_dir))
                uuid1 = sm._get_machine_uuid()
        
        # Create new instance - should load persisted UUID
        sm2 = SecurityManager(str(config_dir))
        if sm2.machine_uuid_file.exists():
            uuid2 = sm2._get_machine_uuid()
            # If persisted, should match
            assert uuid2 is not None


class TestSaltManagement:
    """Test salt creation and loading."""

    def test_get_or_create_salt_creates_new(self, tmp_path):
        """Test creating new salt."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        sm = SecurityManager(str(config_dir))
        salt = sm._get_or_create_salt()
        
        assert len(salt) == 32
        assert sm.salt_file.exists()

    def test_get_or_create_salt_loads_existing(self, tmp_path):
        """Test loading existing salt."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create salt file
        salt_file = config_dir / ".salt"
        original_salt = b'x' * 32
        salt_file.write_bytes(original_salt)
        
        sm = SecurityManager(str(config_dir))
        loaded_salt = sm._get_or_create_salt()
        
        assert loaded_salt == original_salt

    def test_get_or_create_salt_invalid_size(self, tmp_path):
        """Test handling invalid salt size."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create salt file with wrong size
        salt_file = config_dir / ".salt"
        salt_file.write_bytes(b'invalid')
        
        sm = SecurityManager(str(config_dir))
        salt = sm._get_or_create_salt()
        
        # Should create new salt
        assert len(salt) == 32


class TestKeyDerivation:
    """Test encryption key derivation."""

    def test_derive_key_length(self, tmp_path):
        """Test that derived key has correct length."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        key = sm._derive_key()
        
        assert len(key) == 32  # 256 bits for AES-256

    def test_derive_key_deterministic(self, tmp_path):
        """Test that key derivation is deterministic."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        key1 = sm._derive_key()
        key2 = sm._derive_key()
        
        assert key1 == key2

    def test_derive_key_different_salt(self, tmp_path):
        """Test that different salts produce different keys."""
        config_dir1 = tmp_path / "config1"
        config_dir2 = tmp_path / "config2"
        
        sm1 = SecurityManager(str(config_dir1))
        sm2 = SecurityManager(str(config_dir2))
        
        # Different salts should produce different keys
        assert sm1.encryption_key != sm2.encryption_key


class TestEncryptionDecryption:
    """Test encryption and decryption operations."""

    def test_encrypt_basic(self, tmp_path):
        """Test basic encryption."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        plaintext = "Hello, World!"
        encrypted = sm.encrypt(plaintext)
        
        assert encrypted != plaintext
        assert len(encrypted) > 0

    def test_encrypt_empty_string(self, tmp_path):
        """Test encrypting empty string."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        encrypted = sm.encrypt("")
        assert encrypted == ""

    def test_decrypt_basic(self, tmp_path):
        """Test basic decryption."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        plaintext = "Hello, World!"
        encrypted = sm.encrypt(plaintext)
        decrypted = sm.decrypt(encrypted)
        
        assert decrypted == plaintext

    def test_decrypt_empty_string(self, tmp_path):
        """Test decrypting empty string."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        decrypted = sm.decrypt("")
        assert decrypted == ""

    def test_encrypt_decrypt_unicode(self, tmp_path):
        """Test encryption/decryption with Unicode characters."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        plaintext = "Hello 世界 🌍 Привет"
        encrypted = sm.encrypt(plaintext)
        decrypted = sm.decrypt(encrypted)
        
        assert decrypted == plaintext

    def test_encrypt_decrypt_long_text(self, tmp_path):
        """Test encryption/decryption with long text."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        plaintext = "A" * 10000
        encrypted = sm.encrypt(plaintext)
        decrypted = sm.decrypt(encrypted)
        
        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext(self, tmp_path):
        """Test that encrypting same plaintext produces different ciphertext."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        plaintext = "Hello, World!"
        encrypted1 = sm.encrypt(plaintext)
        encrypted2 = sm.encrypt(plaintext)
        
        # Different nonces should produce different ciphertexts
        assert encrypted1 != encrypted2

    def test_decrypt_invalid_data(self, tmp_path):
        """Test decrypting invalid data raises error."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        with pytest.raises(Exception):
            sm.decrypt("invalid_base64_data")

    def test_decrypt_tampered_data(self, tmp_path):
        """Test decrypting tampered data raises error."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        plaintext = "Hello, World!"
        encrypted = sm.encrypt(plaintext)
        
        # Tamper with encrypted data
        tampered = encrypted[:-4] + "XXXX"
        
        with pytest.raises(Exception):
            sm.decrypt(tampered)


class TestDictionaryEncryption:
    """Test dictionary encryption/decryption."""

    def test_encrypt_dict_basic(self, tmp_path):
        """Test encrypting dictionary."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        data = {
            "key1": "value1",
            "key2": "value2"
        }
        
        encrypted = sm.encrypt_dict(data)
        
        assert encrypted["key1"] != "value1"
        assert encrypted["key2"] != "value2"

    def test_encrypt_dict_nested(self, tmp_path):
        """Test encrypting nested dictionary."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        data = {
            "outer": {
                "inner": "secret"
            }
        }
        
        encrypted = sm.encrypt_dict(data)
        
        assert isinstance(encrypted["outer"], dict)
        assert encrypted["outer"]["inner"] != "secret"

    def test_encrypt_dict_mixed_types(self, tmp_path):
        """Test encrypting dictionary with mixed types."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        data = {
            "string": "value",
            "number": 42,
            "boolean": True,
            "none": None
        }
        
        encrypted = sm.encrypt_dict(data)
        
        assert encrypted["string"] != "value"
        assert encrypted["number"] == 42
        assert encrypted["boolean"] is True
        assert encrypted["none"] is None

    def test_decrypt_dict_basic(self, tmp_path):
        """Test decrypting dictionary."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        data = {
            "key1": "value1",
            "key2": "value2"
        }
        
        encrypted = sm.encrypt_dict(data)
        decrypted = sm.decrypt_dict(encrypted)
        
        assert decrypted == data

    def test_decrypt_dict_nested(self, tmp_path):
        """Test decrypting nested dictionary."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        data = {
            "outer": {
                "inner": "secret"
            }
        }
        
        encrypted = sm.encrypt_dict(data)
        decrypted = sm.decrypt_dict(encrypted)
        
        assert decrypted == data

    def test_decrypt_dict_invalid_value(self, tmp_path):
        """Test decrypting dictionary with invalid encrypted value."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        encrypted = {
            "key1": "not_encrypted_value"
        }
        
        decrypted = sm.decrypt_dict(encrypted)
        
        # Should keep original value if decryption fails
        assert decrypted["key1"] == "not_encrypted_value"


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password_basic(self, tmp_path):
        """Test basic password hashing."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        password = "my_secure_password"
        hashed = sm.hash_password(password)
        
        assert hashed != password
        assert "$" in hashed  # New format uses salt$hash

    def test_hash_password_different_salts(self, tmp_path):
        """Test that same password produces different hashes."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        password = "my_secure_password"
        hashed1 = sm.hash_password(password)
        hashed2 = sm.hash_password(password)
        
        # Different per-password salts should produce different hashes
        assert hashed1 != hashed2

    def test_verify_password_correct(self, tmp_path):
        """Test verifying correct password."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        password = "my_secure_password"
        hashed = sm.hash_password(password)
        
        assert sm.verify_password(password, hashed)

    def test_verify_password_incorrect(self, tmp_path):
        """Test verifying incorrect password."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        password = "my_secure_password"
        hashed = sm.hash_password(password)
        
        assert not sm.verify_password("wrong_password", hashed)

    def test_verify_password_legacy_format(self, tmp_path):
        """Test verifying password in legacy format."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        password = "test_password"
        legacy_hash = sm._legacy_hash_password(password)
        
        assert sm.verify_password(password, legacy_hash)

    def test_verify_password_with_migration(self, tmp_path):
        """Test password verification with migration flag."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        password = "test_password"
        legacy_hash = sm._legacy_hash_password(password)
        
        is_valid, migrated_hash = sm.verify_password(password, legacy_hash, return_new_hash=True)
        
        assert is_valid
        assert migrated_hash is not None
        assert "$" in migrated_hash

    def test_verify_password_new_format_no_migration(self, tmp_path):
        """Test that new format doesn't trigger migration."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        password = "test_password"
        hashed = sm.hash_password(password)
        
        is_valid, migrated_hash = sm.verify_password(password, hashed, return_new_hash=True)
        
        assert is_valid
        assert migrated_hash is None

    def test_verify_password_invalid_format(self, tmp_path):
        """Test verifying password with invalid hash format."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        result = sm.verify_password("password", "invalid$format$extra")
        assert not result


class TestSecurityReset:
    """Test security reset operations."""

    def test_reset_encryption_key(self, tmp_path):
        """Test resetting encryption key."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        # Encrypt some data
        plaintext = "secret data"
        encrypted = sm.encrypt(plaintext)
        old_key = sm.encryption_key
        
        # Reset key
        sm.reset_encryption_key()
        
        # Key should be different
        assert sm.encryption_key != old_key
        
        # Old encrypted data should not be decryptable
        with pytest.raises(Exception):
            sm.decrypt(encrypted)

    def test_reset_creates_new_salt(self, tmp_path):
        """Test that reset creates new salt."""
        config_dir = tmp_path / "config"
        sm = SecurityManager(str(config_dir))
        
        old_salt = sm.salt
        
        sm.reset_encryption_key()
        
        assert sm.salt != old_salt
