"""
Security and encryption management for EchoNote application.

Provides AES-256-GCM encryption for sensitive data with machine-specific key derivation.
"""

import base64
import binascii
import hashlib
import hmac
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from config.app_config import get_app_dir


logger = logging.getLogger('echonote.security')


class SecurityManager:
    """
    Manages encryption and decryption of sensitive data.

    Uses AES-256-GCM for authenticated encryption with machine-specific
    key derivation for additional security.
    """

    PASSWORD_SALT_SIZE = 16
    PASSWORD_HASH_LENGTH = 32
    PASSWORD_HASH_ITERATIONS = 200_000

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize security manager.

        Args:
            config_dir: Directory for storing security configuration.
                       Defaults to ~/.echonote
        """
        if config_dir is None:
            self.config_dir = get_app_dir()
        else:
            self.config_dir = Path(config_dir).expanduser()
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # File to store the salt
        self.salt_file = self.config_dir / ".salt"
        
        # Initialize or load salt
        self.salt = self._get_or_create_salt()
        
        # Derive encryption key from machine UUID
        self.encryption_key = self._derive_key()
        
        logger.info("Security manager initialized")
    
    def _get_machine_uuid(self) -> str:
        """
        Get a unique identifier for this machine.

        Returns:
            Machine-specific UUID string
        """
        try:
            # Try to get machine UUID from various sources
            if os.path.exists('/etc/machine-id'):
                # Linux
                with open('/etc/machine-id', 'r') as f:
                    return f.read().strip()
            elif os.path.exists('/var/lib/dbus/machine-id'):
                # Linux alternative
                with open('/var/lib/dbus/machine-id', 'r') as f:
                    return f.read().strip()
            else:
                # macOS/Windows - use uuid.getnode() which returns MAC address
                mac = uuid.getnode()
                return str(mac)
        except Exception as e:
            logger.warning(f"Could not get machine UUID: {e}")
            # Fallback to a generated UUID (less secure but functional)
            return str(uuid.uuid4())
    
    def _get_or_create_salt(self) -> bytes:
        """
        Get existing salt or create a new one.

        Returns:
            32-byte salt
        """
        if self.salt_file.exists():
            try:
                with open(self.salt_file, 'rb') as f:
                    salt = f.read()
                if len(salt) == 32:
                    logger.debug("Loaded existing salt")
                    return salt
            except Exception as e:
                logger.warning(f"Could not read salt file: {e}")
        
        # Create new salt
        salt = os.urandom(32)
        
        try:
            # Save salt with restricted permissions
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
            
            # Set file permissions (owner read/write only)
            os.chmod(self.salt_file, 0o600)
            
            logger.info("Created new salt")
        except Exception as e:
            logger.error(f"Could not save salt file: {e}")
            raise
        
        return salt
    
    def _derive_key(self) -> bytes:
        """
        Derive encryption key from machine UUID and salt.

        Returns:
            32-byte encryption key for AES-256
        """
        machine_uuid = self._get_machine_uuid()
        
        # Use PBKDF2 to derive key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256
            salt=self.salt,
            iterations=100000,  # OWASP recommended minimum
        )
        
        key = kdf.derive(machine_uuid.encode('utf-8'))
        logger.debug("Derived encryption key")
        
        return key
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using AES-256-GCM.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted data (nonce + ciphertext + tag)
        """
        if not plaintext:
            return ""
        
        try:
            # Generate random nonce (12 bytes for GCM)
            nonce = os.urandom(12)
            
            # Create AESGCM cipher
            aesgcm = AESGCM(self.encryption_key)
            
            # Encrypt (returns ciphertext + authentication tag)
            ciphertext = aesgcm.encrypt(
                nonce,
                plaintext.encode('utf-8'),
                None  # No additional authenticated data
            )
            
            # Combine nonce + ciphertext for storage
            encrypted_data = nonce + ciphertext
            
            # Encode as base64 for safe storage
            encoded = base64.b64encode(encrypted_data).decode('utf-8')
            
            logger.debug("Data encrypted successfully")
            return encoded
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt data encrypted with AES-256-GCM.

        Args:
            encrypted_data: Base64-encoded encrypted data

        Returns:
            Decrypted plaintext string
        """
        if not encrypted_data:
            return ""
        
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            
            # Extract nonce (first 12 bytes)
            nonce = encrypted_bytes[:12]
            
            # Extract ciphertext + tag (remaining bytes)
            ciphertext = encrypted_bytes[12:]
            
            # Create AESGCM cipher
            aesgcm = AESGCM(self.encryption_key)
            
            # Decrypt and verify authentication tag
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            
            plaintext = plaintext_bytes.decode('utf-8')
            
            logger.debug("Data decrypted successfully")
            return plaintext
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def encrypt_dict(self, data: dict) -> dict:
        """
        Encrypt all string values in a dictionary.

        Args:
            data: Dictionary with string values

        Returns:
            Dictionary with encrypted values
        """
        encrypted = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                encrypted[key] = self.encrypt(value)
            elif isinstance(value, dict):
                encrypted[key] = self.encrypt_dict(value)
            else:
                encrypted[key] = value
        
        return encrypted
    
    def decrypt_dict(self, encrypted_data: dict) -> dict:
        """
        Decrypt all encrypted string values in a dictionary.

        Args:
            encrypted_data: Dictionary with encrypted values

        Returns:
            Dictionary with decrypted values
        """
        decrypted = {}
        
        for key, value in encrypted_data.items():
            if isinstance(value, str):
                try:
                    decrypted[key] = self.decrypt(value)
                except Exception:
                    # If decryption fails, keep original value
                    decrypted[key] = value
            elif isinstance(value, dict):
                decrypted[key] = self.decrypt_dict(value)
            else:
                decrypted[key] = value
        
        return decrypted
    
    def _hash_with_pbkdf2(self, password: str, salt: bytes) -> bytes:
        """Derive a password hash using PBKDF2-HMAC(SHA-256)."""

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.PASSWORD_HASH_LENGTH,
            salt=salt,
            iterations=self.PASSWORD_HASH_ITERATIONS,
        )
        return kdf.derive(password.encode("utf-8"))

    def _legacy_hash_password(self, password: str) -> str:
        """Replicate the legacy SHA-256(salt||password) hashing scheme."""

        hash_obj = hashlib.sha256()
        hash_obj.update(password.encode("utf-8"))
        hash_obj.update(self.salt)
        return base64.b64encode(hash_obj.digest()).decode("utf-8")

    def hash_password(self, password: str) -> str:
        """
        Create a secure hash of a password using per-password salt.

        Args:
            password: Password to hash

        Returns:
            Encoded string containing salt and hash in the form salt$hash
        """

        salt = os.urandom(self.PASSWORD_SALT_SIZE)
        derived = self._hash_with_pbkdf2(password, salt)

        encoded_salt = base64.b64encode(salt).decode("utf-8")
        encoded_hash = base64.b64encode(derived).decode("utf-8")
        return f"{encoded_salt}${encoded_hash}"

    def verify_password(
        self,
        password: str,
        hashed: str,
        *,
        return_new_hash: bool = False,
    ):
        """
        Verify a password against its stored hash.

        Args:
            password: Password to verify
            hashed: Stored hash value (either new or legacy format)
            return_new_hash: When True, return a tuple of (is_valid, migrated_hash)

        Returns:
            True if password matches hash. When ``return_new_hash`` is True,
            returns a tuple where the second value contains a migrated hash for
            legacy entries.
        """

        if "$" in hashed:
            try:
                encoded_salt, encoded_hash = hashed.split("$", 1)
                salt = base64.b64decode(encoded_salt)
                expected_hash = base64.b64decode(encoded_hash)
            except (ValueError, binascii.Error) as exc:
                logger.error("Invalid password hash format: %s", exc)
                result = False
                if return_new_hash:
                    return result, None
                return result

            derived = self._hash_with_pbkdf2(password, salt)
            result = hmac.compare_digest(derived, expected_hash)
            if return_new_hash:
                return result, None
            return result

        legacy_hash = self._legacy_hash_password(password)
        result = hmac.compare_digest(legacy_hash.encode("utf-8"), hashed.encode("utf-8"))
        migrated_hash = self.hash_password(password) if result else None

        if return_new_hash:
            return result, migrated_hash
        return result
    
    def reset_encryption_key(self):
        """
        Reset the encryption key by generating a new salt.
        
        WARNING: This will make all previously encrypted data unrecoverable!
        """
        logger.warning("Resetting encryption key - all encrypted data will be lost!")
        
        # Delete old salt file
        if self.salt_file.exists():
            self.salt_file.unlink()
        
        # Generate new salt and key
        self.salt = self._get_or_create_salt()
        self.encryption_key = self._derive_key()
        
        logger.info("Encryption key reset complete")
