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
Unit tests for CalendarIntegration.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.realtime.integration import CalendarIntegration


class TestCalendarIntegration:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_i18n(self):
        i18n = Mock()
        i18n.t.side_effect = lambda key, **kwargs: key
        return i18n

    @pytest.fixture
    def calendar_integration(self, mock_db, mock_i18n):
        return CalendarIntegration(mock_db, mock_i18n)

    @pytest.mark.asyncio
    async def test_create_event_success(self, calendar_integration, mock_db):
        """Test successful event creation."""
        # Create mocks for the models
        mock_models = MagicMock()
        mock_event_cls = MagicMock()
        mock_event_instance = MagicMock()
        mock_event_instance.id = "test_event_123"
        mock_event_cls.return_value = mock_event_instance

        mock_attachment_cls = MagicMock()
        mock_attachment_cls.upsert_for_event_type = MagicMock()

        mock_models.CalendarEvent = mock_event_cls
        mock_models.EventAttachment = mock_attachment_cls

        # Mock datetime to ensure stable timestamps if needed,
        # but here we just need the import to work.

        result_data = {
            "start_time": "2023-01-01T12:00:00",
            "end_time": "2023-01-01T13:00:00",
            "duration": 3600.0,
            "transcript_path": "/path/to/transcript.txt",
            "translation_path": "/path/to/translation.txt",
            "recording_path": "/path/to/audio.wav",
        }

        # Patch sys.modules to inject our mock models
        with patch.dict("sys.modules", {"data.database.models": mock_models}):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1024):
                    event_id = await calendar_integration.create_event(result_data)

        assert event_id == "test_event_123"

        # Verify Event creation
        mock_event_cls.assert_called_once()
        call_kwargs = mock_event_cls.call_args[1]
        assert call_kwargs["start_time"] == "2023-01-01T12:00:00"
        assert call_kwargs["end_time"] == "2023-01-01T13:00:00"

        # Verify Event save
        mock_event_instance.save.assert_called_once_with(mock_db)

        # Verify Attachments
        # We expect 3 upsert calls (recording, transcript, translation)
        assert mock_attachment_cls.upsert_for_event_type.call_count == 3

    @pytest.mark.asyncio
    async def test_create_event_db_failure(self, calendar_integration, mock_db):
        """Test failure handling."""
        mock_models = MagicMock()
        mock_event_cls = MagicMock()
        mock_event_instance = MagicMock()
        mock_event_instance.save.side_effect = Exception("DB Error")
        mock_event_cls.return_value = mock_event_instance
        mock_models.CalendarEvent = mock_event_cls

        with patch.dict("sys.modules", {"data.database.models": mock_models}):
            event_id = await calendar_integration.create_event(
                {"start_time": "2023-01-01T12:00:00"}
            )

        assert event_id == ""
