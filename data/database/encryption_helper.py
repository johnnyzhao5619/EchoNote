"""
Database encryption helper for EchoNote application.

Provides utilities for encrypting/decrypting sensitive database fields.
"""

import logging
from typing import Optional
from data.security.encryption import SecurityManager


logger = logging.getLogger('echonote.database.encryption')


class DatabaseEncryptionHelper:
    """
    Helper class for encrypting/decrypting sensitive database fields.
    
    Uses SecurityManager for encryption and provides convenience methods
    for model classes to encrypt/decrypt specific fields.
    """

    def __init__(self, security_manager: SecurityManager):
        """
        Initialize database encryption helper.

        Args:
            security_manager: SecurityManager instance for encryption
        """
        self.security_manager = security_manager
        logger.info("Database encryption helper initialized")
    
    def encrypt_field(self, value: Optional[str]) -> Optional[str]:
        """
        Encrypt a field value.

        Args:
            value: Plain text value to encrypt

        Returns:
            Encrypted value or None if input is None
        """
        if value is None or value == "":
            return value
        
        try:
            encrypted = self.security_manager.encrypt(value)
            logger.debug("Field encrypted successfully")
            return encrypted
        except Exception as e:
            logger.error(f"Failed to encrypt field: {e}")
            raise
    
    def decrypt_field(self, encrypted_value: Optional[str]) -> Optional[str]:
        """
        Decrypt a field value.

        Args:
            encrypted_value: Encrypted value to decrypt

        Returns:
            Decrypted plain text value or None if input is None
        """
        if encrypted_value is None or encrypted_value == "":
            return encrypted_value
        
        try:
            decrypted = self.security_manager.decrypt(encrypted_value)
            logger.debug("Field decrypted successfully")
            return decrypted
        except Exception as e:
            logger.warning(f"Failed to decrypt field (may be unencrypted): {e}")
            # Return original value if decryption fails (backward compatibility)
            return encrypted_value
    
    def is_encrypted(self, value: Optional[str]) -> bool:
        """
        Check if a value appears to be encrypted.

        Args:
            value: Value to check

        Returns:
            True if value appears to be encrypted (base64 format)
        """
        if not value:
            return False
        
        try:
            # Try to decrypt - if it works, it's encrypted
            self.security_manager.decrypt(value)
            return True
        except Exception:
            return False


# Global instance (will be initialized by main.py)
_encryption_helper: Optional[DatabaseEncryptionHelper] = None


def initialize_encryption_helper(security_manager: SecurityManager):
    """
    Initialize the global encryption helper instance.

    Args:
        security_manager: SecurityManager instance
    """
    global _encryption_helper
    _encryption_helper = DatabaseEncryptionHelper(security_manager)
    logger.info("Global database encryption helper initialized")


def get_encryption_helper() -> Optional[DatabaseEncryptionHelper]:
    """
    Get the global encryption helper instance.

    Returns:
        DatabaseEncryptionHelper instance or None if not initialized
    """
    return _encryption_helper


def encrypt_sensitive_field(value: Optional[str]) -> Optional[str]:
    """
    Convenience function to encrypt a sensitive field.

    Args:
        value: Plain text value to encrypt

    Returns:
        Encrypted value or original value if encryption is not available
    """
    helper = get_encryption_helper()
    if helper:
        return helper.encrypt_field(value)
    else:
        logger.warning("Encryption helper not initialized, returning plain value")
        return value


def decrypt_sensitive_field(encrypted_value: Optional[str]) -> Optional[str]:
    """
    Convenience function to decrypt a sensitive field.

    Args:
        encrypted_value: Encrypted value to decrypt

    Returns:
        Decrypted value or original value if decryption is not available
    """
    helper = get_encryption_helper()
    if helper:
        return helper.decrypt_field(encrypted_value)
    else:
        logger.warning("Encryption helper not initialized, returning original value")
        return encrypted_value
