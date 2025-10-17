"""
Secrets manager for storing API keys and sensitive configuration.

Provides encrypted storage for API keys and other sensitive data.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any

from data.security.encryption import SecurityManager
from config.app_config import get_app_dir


logger = logging.getLogger('echonote.security.secrets')


class SecretsManager:
    """
    Manages encrypted storage of API keys and sensitive configuration.
    
    Stores secrets in ~/.echonote/secrets.enc as encrypted JSON.
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize secrets manager.
        
        Args:
            config_dir: Directory for storing secrets file.
                       Defaults to ~/.echonote
        """
        if config_dir is None:
            self.config_dir = get_app_dir()
        else:
            self.config_dir = Path(config_dir).expanduser()
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Secrets file path
        self.secrets_file = self.config_dir / "secrets.enc"
        
        # Initialize security manager for encryption
        self.security_manager = SecurityManager(config_dir)
        
        # Load secrets
        self._secrets = self._load_secrets()
        
        logger.info("Secrets manager initialized")
    
    def _load_secrets(self) -> Dict[str, Any]:
        """
        Load secrets from encrypted file.
        
        Returns:
            Dictionary of secrets
        """
        if not self.secrets_file.exists():
            logger.info("No secrets file found, starting with empty secrets")
            return {
                "api_keys": {},
                "oauth_tokens": {}
            }
        
        try:
            # Read encrypted file
            with open(self.secrets_file, 'r', encoding='utf-8') as f:
                encrypted_data = f.read()
            
            # Decrypt
            decrypted_json = self.security_manager.decrypt(encrypted_data)
            
            # Parse JSON
            secrets = json.loads(decrypted_json)
            
            logger.info("Secrets loaded successfully")
            return secrets
            
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
            # Return empty secrets on error
            return {
                "api_keys": {},
                "oauth_tokens": {}
            }
    
    def _save_secrets(self):
        """Save secrets to encrypted file."""
        try:
            # Convert to JSON
            secrets_json = json.dumps(self._secrets, indent=2)
            
            # Encrypt
            encrypted_data = self.security_manager.encrypt(secrets_json)
            
            # Write to file
            with open(self.secrets_file, 'w', encoding='utf-8') as f:
                f.write(encrypted_data)
            
            # Set file permissions (owner read/write only)
            import os
            os.chmod(self.secrets_file, 0o600)
            
            logger.info("Secrets saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            raise
    
    def set_api_key(self, provider: str, api_key: str):
        """
        Set API key for a provider.
        
        Args:
            provider: Provider name (openai/google/azure)
            api_key: API key to store
        """
        if "api_keys" not in self._secrets:
            self._secrets["api_keys"] = {}
        
        self._secrets["api_keys"][provider] = api_key
        self._save_secrets()
        
        logger.info(f"API key set for provider: {provider}")
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key for a provider.
        
        Args:
            provider: Provider name (openai/google/azure)
            
        Returns:
            API key or None if not found
        """
        return self._secrets.get("api_keys", {}).get(provider)
    
    def delete_api_key(self, provider: str):
        """
        Delete API key for a provider.
        
        Args:
            provider: Provider name (openai/google/azure)
        """
        if "api_keys" in self._secrets and provider in self._secrets["api_keys"]:
            del self._secrets["api_keys"][provider]
            self._save_secrets()
            logger.info(f"API key deleted for provider: {provider}")
    
    def get_all_api_keys(self) -> Dict[str, str]:
        """
        Get all API keys.
        
        Returns:
            Dictionary of provider -> API key
        """
        return self._secrets.get("api_keys", {}).copy()
    
    def set_oauth_token(self, provider: str, token_data: Dict[str, Any]):
        """
        Set OAuth token for a provider.
        
        Args:
            provider: Provider name (google_calendar/outlook_calendar)
            token_data: Token data dictionary
        """
        if "oauth_tokens" not in self._secrets:
            self._secrets["oauth_tokens"] = {}
        
        self._secrets["oauth_tokens"][provider] = token_data
        self._save_secrets()
        
        logger.info(f"OAuth token set for provider: {provider}")
    
    def get_oauth_token(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get OAuth token for a provider.
        
        Args:
            provider: Provider name (google_calendar/outlook_calendar)
            
        Returns:
            Token data dictionary or None if not found
        """
        return self._secrets.get("oauth_tokens", {}).get(provider)
    
    def delete_oauth_token(self, provider: str):
        """
        Delete OAuth token for a provider.
        
        Args:
            provider: Provider name (google_calendar/outlook_calendar)
        """
        if "oauth_tokens" in self._secrets and provider in self._secrets["oauth_tokens"]:
            del self._secrets["oauth_tokens"][provider]
            self._save_secrets()
            logger.info(f"OAuth token deleted for provider: {provider}")
    
    def set_secret(self, key: str, value: Any):
        """
        Set a custom secret value.
        
        Args:
            key: Secret key
            value: Secret value
        """
        self._secrets[key] = value
        self._save_secrets()
        logger.info(f"Secret set: {key}")
    
    def get_secret(self, key: str) -> Optional[Any]:
        """
        Get a custom secret value.
        
        Args:
            key: Secret key
            
        Returns:
            Secret value or None if not found
        """
        return self._secrets.get(key)
    
    def delete_secret(self, key: str):
        """
        Delete a custom secret.
        
        Args:
            key: Secret key
        """
        if key in self._secrets:
            del self._secrets[key]
            self._save_secrets()
            logger.info(f"Secret deleted: {key}")
    
    def clear_all_secrets(self):
        """Clear all secrets (use with caution!)."""
        self._secrets = {
            "api_keys": {},
            "oauth_tokens": {}
        }
        self._save_secrets()
        logger.warning("All secrets cleared")
    
    def has_api_key(self, provider: str) -> bool:
        """
        Check if API key exists for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            True if API key exists
        """
        api_key = self.get_api_key(provider)
        return api_key is not None and api_key.strip() != ""
