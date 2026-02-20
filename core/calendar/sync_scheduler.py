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
Calendar Sync Scheduler for EchoNote.

Manages automatic periodic synchronization of external calendars.
"""

import logging
from typing import Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from utils.time_utils import now_utc

logger = logging.getLogger("echonote.calendar.sync_scheduler")


class SyncScheduler:
    """
    Manages automatic periodic synchronization of external calendars.

    Uses APScheduler to run sync tasks at regular intervals.
    Implements exponential backoff retry logic for failed syncs.
    """

    def __init__(self, calendar_manager, interval_minutes: int = 15):
        """
        Initialize the sync scheduler.

        Args:
            calendar_manager: CalendarManager instance
            interval_minutes: Sync interval in minutes (default: 15)
        """
        self.calendar_manager = calendar_manager
        self.interval_minutes = interval_minutes
        self.scheduler = BackgroundScheduler()
        self.is_running = False

        # Track retry attempts for each provider
        # Format: {provider: {'attempts': int}}
        self.retry_state: Dict[str, Dict] = {}

        logger.info(f"SyncScheduler initialized with {interval_minutes}min interval")

    def start(self):
        """
        Start the automatic sync scheduler.
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        try:
            # Add sync job with interval trigger
            self.scheduler.add_job(
                func=self._sync_all,
                trigger=IntervalTrigger(minutes=self.interval_minutes),
                id="calendar_sync",
                name="Calendar Sync Job",
                replace_existing=True,
                max_instances=1,  # Prevent overlapping syncs
            )

            self.scheduler.start()
            self.is_running = True
            logger.info("Sync scheduler started")

        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    def stop(self):
        """
        Stop the automatic sync scheduler.
        """
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Sync scheduler stopped")

        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            raise

    def sync_now(self):
        """
        Trigger an immediate sync (in addition to scheduled syncs).

        This method can be called manually to force a sync without
        waiting for the next scheduled interval.
        """
        if not self.is_running:
            logger.warning("Scheduler is not running, cannot trigger manual sync")
            return

        try:
            # Add a one-time job
            self.scheduler.add_job(
                func=self._sync_all,
                id="calendar_sync_manual",
                name="Manual Calendar Sync",
                replace_existing=True,
            )
            logger.info("Manual sync triggered")

        except Exception as e:
            logger.error(f"Failed to trigger manual sync: {e}")

    def _sync_all(self):
        """
        Synchronize all connected external calendars.

        This method is called by the scheduler at regular intervals.
        Implements error handling and retry logic with exponential
        backoff.
        """
        try:
            logger.info("Starting scheduled calendar sync")

            # Get all active sync adapters
            from data.database.models import CalendarSyncStatus

            active_syncs = CalendarSyncStatus.get_all_active(self.calendar_manager.db)

            if not active_syncs:
                logger.info("No active calendar syncs configured")
                return

            # Sync each provider
            success_count = 0
            error_count = 0

            for sync_status in active_syncs:
                provider = sync_status.provider

                try:
                    logger.info(f"Syncing {provider} calendar...")
                    self.calendar_manager.sync_external_calendar(provider)
                    success_count += 1
                    logger.info(f"Successfully synced {provider}")

                    # Clear retry state on success
                    if provider in self.retry_state:
                        logger.info(
                            f"Clearing retry state for {provider} " f"after successful sync"
                        )
                        del self.retry_state[provider]

                except Exception as e:
                    error_count += 1
                    logger.error(f"Failed to sync {provider}: {e}")

                    # Implement retry logic with exponential backoff
                    self._handle_sync_failure(provider)

            logger.info(f"Sync completed: {success_count} succeeded, " f"{error_count} failed")

        except Exception as e:
            logger.error(f"Error in sync_all: {e}")
            # Don't raise - we don't want to stop the scheduler

    def _handle_sync_failure(self, provider: str):
        """
        Handle sync failure with exponential backoff retry logic.

        Implements retry with exponential backoff (1min, 2min, 4min).
        Maximum of 3 retry attempts before giving up.

        Args:
            provider: Provider name that failed
        """
        # Initialize retry state if not exists
        if provider not in self.retry_state:
            self.retry_state[provider] = {"attempts": 0}

        # Increment retry attempts
        self.retry_state[provider]["attempts"] += 1
        attempts = self.retry_state[provider]["attempts"]

        # Maximum 3 retry attempts
        if attempts > 3:
            logger.error(
                f"Maximum retry attempts (3) reached for {provider}. "
                f"Giving up until next scheduled sync."
            )
            # Reset retry state so next scheduled sync will try again
            del self.retry_state[provider]
            return

        # Calculate exponential backoff delay: 1min, 2min, 4min
        delay_minutes = 2 ** (attempts - 1)  # 2^0=1, 2^1=2, 2^2=4

        try:
            # Schedule retry with exponential backoff
            run_time = now_utc() + timedelta(minutes=delay_minutes)

            self.scheduler.add_job(
                func=self._retry_sync,
                args=[provider],
                trigger="date",
                run_date=run_time,
                id=f"calendar_sync_retry_{provider}",
                name=f"Retry Sync for {provider} (attempt {attempts}/3)",
                replace_existing=True,
            )

            logger.info(
                f"Scheduled retry {attempts}/3 for {provider} "
                f"in {delay_minutes} minute(s) at "
                f"{run_time.strftime('%H:%M:%S')}"
            )

        except Exception as e:
            logger.error(f"Failed to schedule retry for {provider}: {e}")

    def _retry_sync(self, provider: str):
        """
        Retry syncing a specific provider.

        This method is called by the scheduler after a failed sync
        attempt.

        Args:
            provider: Provider name to retry
        """
        try:
            attempts = self.retry_state.get(provider, {}).get("attempts", 0)
            logger.info(f"Retrying sync for {provider} (attempt {attempts}/3)")

            self.calendar_manager.sync_external_calendar(provider)
            logger.info(f"Retry successful for {provider}")

            # Clear retry state on success
            if provider in self.retry_state:
                del self.retry_state[provider]

            # Remove the retry job after success
            try:
                self.scheduler.remove_job(f"calendar_sync_retry_{provider}")
            except Exception:
                pass  # Job might have already been removed

        except Exception as e:
            logger.error(f"Retry failed for {provider}: {e}")

            # Handle failure - will schedule another retry if under limit
            self._handle_sync_failure(provider)

    def get_next_sync_time(self) -> Optional[str]:
        """
        Get the next scheduled sync time.

        Returns:
            ISO format timestamp of next sync, or None if not scheduled
        """
        if not self.is_running:
            return None

        try:
            job = self.scheduler.get_job("calendar_sync")
            if job and job.next_run_time:
                return job.next_run_time.isoformat()
            return None

        except Exception as e:
            logger.error(f"Failed to get next sync time: {e}")
            return None

    def get_status(self) -> dict:
        """
        Get the current status of the scheduler.

        Returns:
            Dictionary with scheduler status information
        """
        return {
            "is_running": self.is_running,
            "interval_minutes": self.interval_minutes,
            "next_sync_time": self.get_next_sync_time(),
            "active_jobs": len(self.scheduler.get_jobs()),
        }
