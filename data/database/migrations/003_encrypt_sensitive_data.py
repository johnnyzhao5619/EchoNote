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
Migration script to encrypt sensitive data in existing database.

This migration encrypts the sync_token field in calendar_sync_status table.
"""

import logging
from typing import Optional

from data.security.encryption import SecurityManager
from data.database.encryption_helper import DatabaseEncryptionHelper


logger = logging.getLogger("echonote.migrations")


def migrate_up(db_connection, security_manager: Optional[SecurityManager] = None):
    """
    Encrypt sensitive data in the database.

    Args:
        db_connection: Database connection
        security_manager: SecurityManager instance for encryption
    """
    if security_manager is None:
        logger.warning("No security manager provided, skipping encryption migration")
        return

    logger.info("Starting migration: encrypt sensitive data")

    # Initialize encryption helper
    encryption_helper = DatabaseEncryptionHelper(security_manager)

    # Migrate calendar_sync_status table
    _migrate_calendar_sync_status(db_connection, encryption_helper)

    logger.info("Migration completed: encrypt sensitive data")


def _migrate_calendar_sync_status(db_connection, encryption_helper):
    """
    Encrypt sync_token field in calendar_sync_status table.

    Args:
        db_connection: Database connection
        encryption_helper: DatabaseEncryptionHelper instance
    """
    logger.info("Migrating calendar_sync_status table")

    # Get all sync status records
    query = "SELECT id, sync_token FROM calendar_sync_status WHERE sync_token IS NOT NULL"
    rows = db_connection.execute(query)

    if not rows:
        logger.info("No sync status records to migrate")
        return

    migrated_count = 0
    skipped_count = 0

    for row in rows:
        sync_status_id = row["id"]
        sync_token = row["sync_token"]

        # Check if already encrypted
        if encryption_helper.is_encrypted(sync_token):
            logger.debug(f"Sync token for {sync_status_id} is already encrypted, skipping")
            skipped_count += 1
            continue

        # Encrypt the sync token
        try:
            encrypted_token = encryption_helper.encrypt_field(sync_token)

            # Update the record
            update_query = """
                UPDATE calendar_sync_status
                SET sync_token = ?
                WHERE id = ?
            """
            db_connection.execute(update_query, (encrypted_token, sync_status_id), commit=True)

            logger.debug(f"Encrypted sync token for sync status: {sync_status_id}")
            migrated_count += 1

        except Exception as e:
            logger.error(f"Failed to encrypt sync token for {sync_status_id}: {e}")
            raise

    logger.info(
        f"Calendar sync status migration complete: "
        f"{migrated_count} encrypted, {skipped_count} skipped"
    )


def migrate_down(db_connection, security_manager: Optional[SecurityManager] = None):
    """
    Decrypt sensitive data in the database (rollback).

    Args:
        db_connection: Database connection
        security_manager: SecurityManager instance for decryption
    """
    if security_manager is None:
        logger.warning("No security manager provided, skipping decryption migration")
        return

    logger.info("Starting rollback: decrypt sensitive data")

    # Initialize encryption helper
    encryption_helper = DatabaseEncryptionHelper(security_manager)

    # Rollback calendar_sync_status table
    _rollback_calendar_sync_status(db_connection, encryption_helper)

    logger.info("Rollback completed: decrypt sensitive data")


def _rollback_calendar_sync_status(db_connection, encryption_helper):
    """
    Decrypt sync_token field in calendar_sync_status table.

    Args:
        db_connection: Database connection
        encryption_helper: DatabaseEncryptionHelper instance
    """
    logger.info("Rolling back calendar_sync_status table")

    # Get all sync status records
    query = "SELECT id, sync_token FROM calendar_sync_status WHERE sync_token IS NOT NULL"
    rows = db_connection.execute(query)

    if not rows:
        logger.info("No sync status records to rollback")
        return

    decrypted_count = 0
    skipped_count = 0

    for row in rows:
        sync_status_id = row["id"]
        sync_token = row["sync_token"]

        # Check if encrypted
        if not encryption_helper.is_encrypted(sync_token):
            logger.debug(f"Sync token for {sync_status_id} is not encrypted, skipping")
            skipped_count += 1
            continue

        # Decrypt the sync token
        try:
            decrypted_token = encryption_helper.decrypt_field(sync_token)

            # Update the record
            update_query = """
                UPDATE calendar_sync_status
                SET sync_token = ?
                WHERE id = ?
            """
            db_connection.execute(update_query, (decrypted_token, sync_status_id), commit=True)

            logger.debug(f"Decrypted sync token for sync status: {sync_status_id}")
            decrypted_count += 1

        except Exception as e:
            logger.error(f"Failed to decrypt sync token for {sync_status_id}: {e}")
            raise

    logger.info(
        f"Calendar sync status rollback complete: "
        f"{decrypted_count} decrypted, {skipped_count} skipped"
    )
