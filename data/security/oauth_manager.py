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
OAuth token management for EchoNote application.

Handles secure storage, retrieval, and refresh of OAuth tokens.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from config.app_config import get_app_dir
from data.security.encryption import SecurityManager

logger = logging.getLogger("echonote.security.oauth")


class OAuthManager:
    """
    Manages OAuth tokens with encrypted storage and automatic refresh.

    Stores tokens securely using the SecurityManager and handles
    token expiration detection and refresh logic.
    """

    def __init__(self, security_manager: SecurityManager, config_dir: Optional[str] = None):
        """
        Initialize OAuth manager.

        Args:
            security_manager: SecurityManager instance for encryption
            config_dir: Directory for storing OAuth tokens.
                       Defaults to ~/.echonote
        """
        self.security_manager = security_manager

        if config_dir is None:
            self.config_dir = get_app_dir()
        else:
            self.config_dir = Path(config_dir).expanduser()

        self.config_dir.mkdir(parents=True, exist_ok=True)

        # File to store encrypted tokens
        self.tokens_file = self.config_dir / "oauth_tokens.enc"

        # In-memory cache of tokens
        self._tokens_cache: Dict[str, Dict[str, Any]] = {}

        # Load existing tokens
        self._load_tokens()

        logger.info("OAuth manager initialized")

    def _load_tokens(self):
        """Load tokens from encrypted storage."""
        if not self.tokens_file.exists():
            logger.debug("No existing OAuth tokens file")
            self._tokens_cache = {}
            return

        try:
            with open(self.tokens_file, "r", encoding="utf-8") as f:
                encrypted_data = json.load(f)

            # Decrypt the tokens
            self._tokens_cache = self.security_manager.decrypt_dict(encrypted_data)

            logger.info(f"Loaded {len(self._tokens_cache)} OAuth token(s)")

        except Exception as e:
            logger.error(f"Failed to load OAuth tokens: {e}")
            self._tokens_cache = {}

    def _save_tokens(self):
        """Save tokens to encrypted storage."""
        try:
            # Encrypt the tokens
            encrypted_data = self.security_manager.encrypt_dict(self._tokens_cache)

            # Save to file
            with open(self.tokens_file, "w", encoding="utf-8") as f:
                json.dump(encrypted_data, f, indent=2)

            # Set file permissions (owner read/write only)
            import os

            from config.constants import FILE_PERMISSION_OWNER_RW

            os.chmod(self.tokens_file, FILE_PERMISSION_OWNER_RW)

            logger.debug("OAuth tokens saved successfully")

        except Exception as e:
            logger.error(f"Failed to save OAuth tokens: {e}")
            raise

    def store_token(
        self,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        token_type: str = "Bearer",
        scope: Optional[str] = None,
        **extra_data,
    ):
        """
        Store OAuth token for a provider.

        Args:
            provider: Provider name (e.g., 'google', 'outlook')
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            expires_in: Token expiration time in seconds (optional)
            token_type: Token type (default: 'Bearer')
            scope: Token scope (optional)
            **extra_data: Additional provider-specific data
        """
        # Calculate expiration time and record storage timestamp
        now = datetime.now()
        expires_at = None
        if expires_in is not None:
            expires_at = (now + timedelta(seconds=expires_in)).isoformat()

        existing_data = self._tokens_cache.get(provider, {})
        merged_data = dict(existing_data)

        # Preserve refresh token unless a new non-empty value is provided
        if refresh_token:
            merged_data["refresh_token"] = refresh_token

        # Update optional metadata only when explicitly provided to avoid dropping
        # previously stored values.
        if scope is not None:
            merged_data["scope"] = scope

        if token_type is not None:
            merged_data["token_type"] = token_type
        elif "token_type" not in merged_data:
            merged_data["token_type"] = "Bearer"

        for key, value in extra_data.items():
            if value is not None or key not in merged_data:
                merged_data[key] = value

        # Required fields are always refreshed
        merged_data["access_token"] = access_token
        merged_data["expires_in"] = expires_in
        merged_data["expires_at"] = expires_at
        merged_data["stored_at"] = now.isoformat()

        self._tokens_cache[provider] = merged_data
        self._save_tokens()

        logger.info(f"Stored OAuth token for provider: {provider}")
        logger.debug(
            "Provider %s token persisted with expires_in=%s (expires_at=%s)",
            provider,
            expires_in,
            expires_at,
        )

    def get_token(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get OAuth token for a provider.

        Args:
            provider: Provider name (e.g., 'google', 'outlook')

        Returns:
            Token data dictionary or None if not found
        """
        token_data = self._tokens_cache.get(provider)

        if token_data:
            logger.debug(f"Retrieved OAuth token for provider: {provider}")
        else:
            logger.debug(f"No OAuth token found for provider: {provider}")

        return token_data

    def get_access_token(self, provider: str) -> Optional[str]:
        """
        Get access token for a provider.

        Args:
            provider: Provider name

        Returns:
            Access token string or None if not found
        """
        token_data = self.get_token(provider)
        return token_data.get("access_token") if token_data else None

    def get_refresh_token(self, provider: str) -> Optional[str]:
        """
        Get refresh token for a provider.

        Args:
            provider: Provider name

        Returns:
            Refresh token string or None if not found
        """
        token_data = self.get_token(provider)
        return token_data.get("refresh_token") if token_data else None

    def is_token_expired(self, provider: str, buffer_seconds: int = None) -> bool:
        """
        Check if a token is expired or will expire soon.

        Args:
            provider: Provider name
            buffer_seconds: Consider token expired if it expires within
                          this many seconds (default: DEFAULT_TOKEN_BUFFER_SECONDS)

        Returns:
            True if token is expired or will expire soon
        """
        if buffer_seconds is None:
            from config.constants import DEFAULT_TOKEN_BUFFER_SECONDS

            buffer_seconds = DEFAULT_TOKEN_BUFFER_SECONDS
        token_data = self.get_token(provider)

        if not token_data:
            return True

        expires_at = token_data.get("expires_at")
        if not expires_at:
            # No expiration time set, assume token is valid
            return False

        try:
            expiration = datetime.fromisoformat(expires_at)
            now = datetime.now()

            # Check if expired or will expire within buffer time
            is_expired = (expiration - now).total_seconds() <= buffer_seconds

            if is_expired:
                logger.debug(f"Token for {provider} is expired or expiring soon")

            return is_expired

        except Exception as e:
            logger.error(f"Error checking token expiration: {e}")
            return True

    def update_access_token(
        self,
        provider: str,
        access_token: str,
        expires_in: Optional[int] = None,
        *,
        token_type: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_at: Optional[str] = None,
    ):
        """
        Update only the access token (e.g., after refresh).

        Args:
            provider: Provider name
            access_token: New access token
            expires_in: Token expiration time in seconds (optional)
        """
        token_data = self._tokens_cache.get(provider)

        if not token_data:
            logger.warning(f"Cannot update token for {provider}: no existing token")
            return

        # Update access token
        token_data["access_token"] = access_token

        # Update expiration time
        if expires_in is not None:
            computed_expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
            token_data["expires_at"] = computed_expires_at
            token_data["expires_in"] = expires_in
        elif expires_at is not None:
            token_data["expires_at"] = expires_at

        if token_type:
            token_data["token_type"] = token_type

        if refresh_token:
            token_data["refresh_token"] = refresh_token

        # Update stored_at timestamp
        token_data["stored_at"] = datetime.now().isoformat()

        self._tokens_cache[provider] = token_data
        self._save_tokens()

        logger.info(f"Updated access token for provider: {provider}")
        logger.debug(
            "Provider %s token updated with expires_in=%s (expires_at=%s)",
            provider,
            token_data.get("expires_in"),
            token_data.get("expires_at"),
        )

    def delete_token(self, provider: str):
        """
        Delete OAuth token for a provider.

        Args:
            provider: Provider name
        """
        if provider in self._tokens_cache:
            del self._tokens_cache[provider]
            self._save_tokens()
            logger.info(f"Deleted OAuth token for provider: {provider}")
        else:
            logger.debug(f"No token to delete for provider: {provider}")

    def has_token(self, provider: str) -> bool:
        """
        Check if a token exists for a provider.

        Args:
            provider: Provider name

        Returns:
            True if token exists
        """
        return provider in self._tokens_cache

    def list_providers(self) -> list:
        """
        Get list of providers with stored tokens.

        Returns:
            List of provider names
        """
        return list(self._tokens_cache.keys())

    def clear_all_tokens(self):
        """
        Delete all stored OAuth tokens.

        WARNING: This will require re-authentication for all providers!
        """
        logger.warning("Clearing all OAuth tokens")

        self._tokens_cache = {}
        self._save_tokens()

        logger.info("All OAuth tokens cleared")

    def refresh_token_if_needed(
        self, provider: str, refresh_callback, buffer_seconds: int = None
    ) -> Dict[str, Any]:
        """
        Check if token is expired and refresh if needed.

        Args:
            provider: Provider name
            refresh_callback: Function to call for token refresh.
                            Should accept refresh_token and return dict with
                            'access_token' and optionally 'expires_in',
                            'token_type', 'refresh_token', or 'expires_at'
            buffer_seconds: Consider token expired if it expires within
                          this many seconds (default: DEFAULT_TOKEN_BUFFER_SECONDS)

        Returns:
            Current (possibly refreshed) token data

        Raises:
            ValueError: If no token or refresh token exists
            Exception: If token refresh fails

        Example:
            def my_refresh_callback(refresh_token):
                # Call provider API to refresh token
                response = requests.post(...)
                return {
                    'access_token': response['access_token'],
                    'expires_in': response['expires_in']
                }

            token = oauth_manager.refresh_token_if_needed(
                'google',
                my_refresh_callback
            )
        """
        if buffer_seconds is None:
            from config.constants import DEFAULT_TOKEN_BUFFER_SECONDS

            buffer_seconds = DEFAULT_TOKEN_BUFFER_SECONDS

        # Check if token exists
        if not self.has_token(provider):
            raise ValueError(f"No token found for provider: {provider}")

        # Check if token is expired or will expire soon
        if not self.is_token_expired(provider, buffer_seconds):
            logger.debug(f"Token for {provider} is still valid, no refresh needed")
            return self.get_token(provider)

        # Token is expired or expiring soon, try to refresh
        refresh_token = self.get_refresh_token(provider)
        if not refresh_token:
            raise ValueError(f"No refresh token available for {provider}")

        logger.info(f"Refreshing token for {provider}")

        try:
            # Call the refresh callback
            new_token_data = refresh_callback(refresh_token)

            if not new_token_data or "access_token" not in new_token_data:
                raise ValueError("Refresh callback did not return valid token data")

            # Update the access token
            self.update_access_token(
                provider,
                new_token_data["access_token"],
                new_token_data.get("expires_in"),
                token_type=new_token_data.get("token_type"),
                refresh_token=new_token_data.get("refresh_token"),
                expires_at=new_token_data.get("expires_at"),
            )

            logger.info(f"Successfully refreshed token for {provider}")
            return self.get_token(provider)

        except Exception as e:
            logger.error(f"Failed to refresh token for {provider}: {e}")
            raise

    def get_token_info(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get non-sensitive information about a token.

        Args:
            provider: Provider name

        Returns:
            Dictionary with token metadata (no actual tokens)
        """
        token_data = self.get_token(provider)

        if not token_data:
            return None

        return {
            "provider": provider,
            "token_type": token_data.get("token_type"),
            "scope": token_data.get("scope"),
            "expires_at": token_data.get("expires_at"),
            "stored_at": token_data.get("stored_at"),
            "has_refresh_token": bool(token_data.get("refresh_token")),
            "is_expired": self.is_token_expired(provider),
        }
