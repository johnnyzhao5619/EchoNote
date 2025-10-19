"""
Data models for EchoNote application.

Provides ORM-like classes for database operations.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

from data.database.encryption_helper import (
    encrypt_sensitive_field,
    decrypt_sensitive_field
)


logger = logging.getLogger('echonote.database.models')


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def current_timestamp() -> str:
    """Get current timestamp as ISO format string."""
    return datetime.now().isoformat()


@dataclass
class TranscriptionTask:
    """Model for transcription tasks."""
    
    id: str = field(default_factory=generate_uuid)
    file_path: str = ""
    file_name: str = ""
    file_size: Optional[int] = None
    audio_duration: Optional[float] = None
    status: str = "pending"  # pending/processing/completed/failed
    progress: float = 0.0
    language: Optional[str] = None
    engine: str = "faster-whisper"
    output_format: Optional[str] = None
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = field(default_factory=current_timestamp)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    @classmethod
    def from_db_row(cls, row) -> 'TranscriptionTask':
        """Create instance from database row."""
        return cls(
            id=row['id'],
            file_path=row['file_path'],
            file_name=row['file_name'],
            file_size=row['file_size'],
            audio_duration=row['audio_duration'],
            status=row['status'],
            progress=row['progress'],
            language=row['language'],
            engine=row['engine'],
            output_format=row['output_format'],
            output_path=row['output_path'],
            error_message=row['error_message'],
            created_at=row['created_at'],
            started_at=row['started_at'],
            completed_at=row['completed_at']
        )
    
    def save(self, db_connection):
        """Save or update task in database."""
        query = """
            INSERT OR REPLACE INTO transcription_tasks (
                id, file_path, file_name, file_size, audio_duration,
                status, progress, language, engine, output_format,
                output_path, error_message, created_at, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            self.id, self.file_path, self.file_name, self.file_size,
            self.audio_duration, self.status, self.progress, self.language,
            self.engine, self.output_format, self.output_path,
            self.error_message, self.created_at, self.started_at, self.completed_at
        )
        db_connection.execute(query, params, commit=True)
        logger.debug(f"Saved transcription task: {self.id}")
    
    @staticmethod
    def get_by_id(db_connection, task_id: str) -> Optional['TranscriptionTask']:
        """Get task by ID."""
        query = "SELECT * FROM transcription_tasks WHERE id = ?"
        result = db_connection.execute(query, (task_id,))
        if result:
            return TranscriptionTask.from_db_row(result[0])
        return None
    
    @staticmethod
    def get_all(db_connection, status: Optional[str] = None) -> List['TranscriptionTask']:
        """Get all tasks, optionally filtered by status."""
        if status:
            query = "SELECT * FROM transcription_tasks WHERE status = ? ORDER BY created_at DESC"
            result = db_connection.execute(query, (status,))
        else:
            query = "SELECT * FROM transcription_tasks ORDER BY created_at DESC"
            result = db_connection.execute(query)
        
        return [TranscriptionTask.from_db_row(row) for row in result]
    
    def delete(self, db_connection):
        """Delete task from database."""
        query = "DELETE FROM transcription_tasks WHERE id = ?"
        db_connection.execute(query, (self.id,), commit=True)
        logger.debug(f"Deleted transcription task: {self.id}")


@dataclass
class CalendarEvent:
    """Model for calendar events."""
    
    id: str = field(default_factory=generate_uuid)
    title: str = ""
    event_type: str = "Event"  # Event/Task/Appointment
    start_time: str = ""
    end_time: str = ""
    location: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    description: Optional[str] = None
    reminder_minutes: Optional[int] = None
    recurrence_rule: Optional[str] = None
    source: str = "local"  # local/google/outlook
    external_id: Optional[str] = None
    is_readonly: bool = False
    created_at: str = field(default_factory=current_timestamp)
    updated_at: str = field(default_factory=current_timestamp)
    
    @classmethod
    def from_db_row(cls, row) -> 'CalendarEvent':
        """Create instance from database row."""
        attendees = json.loads(row['attendees']) if row['attendees'] else []
        return cls(
            id=row['id'],
            title=row['title'],
            event_type=row['event_type'],
            start_time=row['start_time'],
            end_time=row['end_time'],
            location=row['location'],
            attendees=attendees,
            description=row['description'],
            reminder_minutes=row['reminder_minutes'],
            recurrence_rule=row['recurrence_rule'],
            source=row['source'],
            external_id=row['external_id'],
            is_readonly=bool(row['is_readonly']),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def save(self, db_connection):
        """Save or update event in database."""
        self.updated_at = current_timestamp()

        def _ensure_iso(value):
            if isinstance(value, datetime):
                return value.isoformat()
            return value

        self.start_time = _ensure_iso(self.start_time)
        self.end_time = _ensure_iso(self.end_time)
        self.created_at = _ensure_iso(self.created_at)
        self.updated_at = _ensure_iso(self.updated_at)

        query = """
            INSERT OR REPLACE INTO calendar_events (
                id, title, event_type, start_time, end_time, location,
                attendees, description, reminder_minutes, recurrence_rule,
                source, external_id, is_readonly, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            self.id, self.title, self.event_type, self.start_time,
            self.end_time, self.location, json.dumps(self.attendees),
            self.description, self.reminder_minutes, self.recurrence_rule,
            self.source, self.external_id, int(self.is_readonly),
            self.created_at, self.updated_at
        )
        db_connection.execute(query, params, commit=True)
        logger.debug(f"Saved calendar event: {self.id}")
    
    @staticmethod
    def get_by_id(db_connection, event_id: str) -> Optional['CalendarEvent']:
        """Get event by ID."""
        query = "SELECT * FROM calendar_events WHERE id = ?"
        result = db_connection.execute(query, (event_id,))
        if result:
            return CalendarEvent.from_db_row(result[0])
        return None
    
    @staticmethod
    def get_by_time_range(
        db_connection,
        start_time: str,
        end_time: str,
        source: Optional[str] = None
    ) -> List['CalendarEvent']:
        """Get events within a time range."""
        if source:
            query = """
                SELECT * FROM calendar_events
                WHERE start_time < ? AND end_time > ? AND source = ?
                ORDER BY start_time
            """
            result = db_connection.execute(query, (end_time, start_time, source))
        else:
            query = """
                SELECT * FROM calendar_events
                WHERE start_time < ? AND end_time > ?
                ORDER BY start_time
            """
            result = db_connection.execute(query, (end_time, start_time))
        
        return [CalendarEvent.from_db_row(row) for row in result]
    
    @staticmethod
    def search(
        db_connection,
        keyword: Optional[str] = None,
        event_type: Optional[str] = None,
        source: Optional[str] = None
    ) -> List['CalendarEvent']:
        """Search events by various criteria."""
        conditions = []
        params = []
        
        if keyword:
            conditions.append("(title LIKE ? OR description LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        
        if source:
            conditions.append("source = ?")
            params.append(source)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT * FROM calendar_events
            WHERE {where_clause}
            ORDER BY start_time DESC
        """
        
        result = db_connection.execute(query, tuple(params))
        return [CalendarEvent.from_db_row(row) for row in result]
    
    def delete(self, db_connection):
        """Delete event from database."""
        query = "DELETE FROM calendar_events WHERE id = ?"
        db_connection.execute(query, (self.id,), commit=True)
        logger.debug(f"Deleted calendar event: {self.id}")


@dataclass
class EventAttachment:
    """Model for event attachments."""
    
    id: str = field(default_factory=generate_uuid)
    event_id: str = ""
    attachment_type: str = ""  # recording/transcript
    file_path: str = ""
    file_size: Optional[int] = None
    created_at: str = field(default_factory=current_timestamp)
    
    @classmethod
    def from_db_row(cls, row) -> 'EventAttachment':
        """Create instance from database row."""
        return cls(
            id=row['id'],
            event_id=row['event_id'],
            attachment_type=row['attachment_type'],
            file_path=row['file_path'],
            file_size=row['file_size'],
            created_at=row['created_at']
        )
    
    def save(self, db_connection):
        """Save attachment in database."""
        query = """
            INSERT OR REPLACE INTO event_attachments (
                id, event_id, attachment_type, file_path, file_size, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            self.id, self.event_id, self.attachment_type,
            self.file_path, self.file_size, self.created_at
        )
        db_connection.execute(query, params, commit=True)
        logger.debug(f"Saved event attachment: {self.id}")
    
    @staticmethod
    def get_by_event_id(db_connection, event_id: str) -> List['EventAttachment']:
        """Get all attachments for an event."""
        query = "SELECT * FROM event_attachments WHERE event_id = ? ORDER BY created_at"
        result = db_connection.execute(query, (event_id,))
        return [EventAttachment.from_db_row(row) for row in result]
    
    def delete(self, db_connection):
        """Delete attachment from database."""
        query = "DELETE FROM event_attachments WHERE id = ?"
        db_connection.execute(query, (self.id,), commit=True)
        logger.debug(f"Deleted event attachment: {self.id}")


@dataclass
class AutoTaskConfig:
    """Model for automatic task configurations."""
    
    id: str = field(default_factory=generate_uuid)
    event_id: str = ""
    enable_transcription: bool = False
    enable_recording: bool = False
    transcription_language: Optional[str] = None
    enable_translation: bool = False
    translation_target_language: Optional[str] = None
    created_at: str = field(default_factory=current_timestamp)
    
    @classmethod
    def from_db_row(cls, row) -> 'AutoTaskConfig':
        """Create instance from database row."""
        return cls(
            id=row['id'],
            event_id=row['event_id'],
            enable_transcription=bool(row['enable_transcription']),
            enable_recording=bool(row['enable_recording']),
            transcription_language=row['transcription_language'],
            enable_translation=bool(row['enable_translation']),
            translation_target_language=row['translation_target_language'],
            created_at=row['created_at']
        )
    
    def save(self, db_connection):
        """Save configuration in database."""
        query = """
            INSERT OR REPLACE INTO auto_task_configs (
                id, event_id, enable_transcription, enable_recording,
                transcription_language, enable_translation,
                translation_target_language, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            self.id, self.event_id, int(self.enable_transcription),
            int(self.enable_recording), self.transcription_language,
            int(self.enable_translation), self.translation_target_language,
            self.created_at
        )
        db_connection.execute(query, params, commit=True)
        logger.debug(f"Saved auto task config: {self.id}")
    
    @staticmethod
    def get_by_event_id(db_connection, event_id: str) -> Optional['AutoTaskConfig']:
        """Get configuration for an event."""
        query = "SELECT * FROM auto_task_configs WHERE event_id = ?"
        result = db_connection.execute(query, (event_id,))
        if result:
            return AutoTaskConfig.from_db_row(result[0])
        return None
    
    def delete(self, db_connection):
        """Delete configuration from database."""
        query = "DELETE FROM auto_task_configs WHERE id = ?"
        db_connection.execute(query, (self.id,), commit=True)
        logger.debug(f"Deleted auto task config: {self.id}")


@dataclass
class CalendarSyncStatus:
    """Model for calendar sync status."""
    
    id: str = field(default_factory=generate_uuid)
    provider: str = ""  # google/outlook
    user_email: Optional[str] = None
    last_sync_time: Optional[str] = None
    sync_token: Optional[str] = None
    is_active: bool = True
    created_at: str = field(default_factory=current_timestamp)
    updated_at: str = field(default_factory=current_timestamp)
    
    @classmethod
    def from_db_row(cls, row) -> 'CalendarSyncStatus':
        """Create instance from database row."""
        # Decrypt sync_token if present
        sync_token = decrypt_sensitive_field(row['sync_token'])
        
        return cls(
            id=row['id'],
            provider=row['provider'],
            user_email=row['user_email'],
            last_sync_time=row['last_sync_time'],
            sync_token=sync_token,
            is_active=bool(row['is_active']),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def save(self, db_connection):
        """Save sync status in database."""
        self.updated_at = current_timestamp()
        
        # Encrypt sync_token before saving
        encrypted_sync_token = encrypt_sensitive_field(self.sync_token)
        
        query = """
            INSERT OR REPLACE INTO calendar_sync_status (
                id, provider, user_email, last_sync_time, sync_token,
                is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            self.id, self.provider, self.user_email, self.last_sync_time,
            encrypted_sync_token, int(self.is_active), self.created_at, self.updated_at
        )
        db_connection.execute(query, params, commit=True)
        logger.debug(f"Saved calendar sync status: {self.id}")
    
    @staticmethod
    def get_by_provider(db_connection, provider: str) -> Optional['CalendarSyncStatus']:
        """Get sync status for a provider."""
        query = "SELECT * FROM calendar_sync_status WHERE provider = ? AND is_active = 1"
        result = db_connection.execute(query, (provider,))
        if result:
            return CalendarSyncStatus.from_db_row(result[0])
        return None
    
    @staticmethod
    def get_all_active(db_connection) -> List['CalendarSyncStatus']:
        """Get all active sync statuses."""
        query = "SELECT * FROM calendar_sync_status WHERE is_active = 1"
        result = db_connection.execute(query)
        return [CalendarSyncStatus.from_db_row(row) for row in result]
    
    def delete(self, db_connection):
        """Delete sync status from database."""
        query = "DELETE FROM calendar_sync_status WHERE id = ?"
        db_connection.execute(query, (self.id,), commit=True)
        logger.debug(f"Deleted calendar sync status: {self.id}")


@dataclass
class APIUsage:
    """Model for API usage tracking."""
    
    id: str = field(default_factory=generate_uuid)
    engine: str = ""  # openai/google/azure
    duration_seconds: float = 0.0
    cost: Optional[float] = None
    timestamp: str = field(default_factory=current_timestamp)
    
    @classmethod
    def from_db_row(cls, row) -> 'APIUsage':
        """Create instance from database row."""
        return cls(
            id=row['id'],
            engine=row['engine'],
            duration_seconds=row['duration_seconds'],
            cost=row['cost'],
            timestamp=row['timestamp']
        )
    
    def save(self, db_connection):
        """Save usage record in database."""
        query = """
            INSERT INTO api_usage (id, engine, duration_seconds, cost, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (self.id, self.engine, self.duration_seconds, self.cost, self.timestamp)
        db_connection.execute(query, params, commit=True)
        logger.debug(f"Saved API usage record: {self.id}")
    
    @staticmethod
    def get_monthly_usage(db_connection, engine: str, year: int, month: int) -> Dict[str, Any]:
        """Get monthly usage statistics for an engine."""
        query = """
            SELECT
                COUNT(*) as count,
                SUM(duration_seconds) as total_duration,
                SUM(cost) as total_cost
            FROM api_usage
            WHERE engine = ?
            AND strftime('%Y', timestamp) = ?
            AND strftime('%m', timestamp) = ?
        """
        result = db_connection.execute(query, (engine, str(year), f"{month:02d}"))
        
        if result:
            row = result[0]
            return {
                'count': row['count'],
                'total_duration': row['total_duration'] or 0.0,
                'total_cost': row['total_cost'] or 0.0
            }
        
        return {'count': 0, 'total_duration': 0.0, 'total_cost': 0.0}


@dataclass
class ModelUsageStats:
    """Model for Whisper model usage statistics."""
    
    id: str = field(default_factory=generate_uuid)
    model_name: str = ""
    usage_count: int = 0
    last_used: Optional[str] = None
    total_transcription_duration: float = 0.0
    created_at: str = field(default_factory=current_timestamp)
    updated_at: str = field(default_factory=current_timestamp)
    
    @classmethod
    def from_db_row(cls, row) -> 'ModelUsageStats':
        """Create instance from database row."""
        return cls(
            id=row['id'],
            model_name=row['model_name'],
            usage_count=row['usage_count'],
            last_used=row['last_used'],
            total_transcription_duration=row['total_transcription_duration'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def save(self, db_connection):
        """Save or update model usage stats in database."""
        self.updated_at = current_timestamp()
        
        query = """
            INSERT OR REPLACE INTO model_usage_stats (
                id, model_name, usage_count, last_used,
                total_transcription_duration, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            self.id, self.model_name, self.usage_count, self.last_used,
            self.total_transcription_duration, self.created_at, self.updated_at
        )
        db_connection.execute(query, params, commit=True)
        logger.debug(f"Saved model usage stats: {self.model_name}")
    
    @staticmethod
    def get_by_model_name(db_connection, model_name: str) -> Optional['ModelUsageStats']:
        """Get usage stats for a specific model."""
        query = "SELECT * FROM model_usage_stats WHERE model_name = ?"
        result = db_connection.execute(query, (model_name,))
        if result:
            return ModelUsageStats.from_db_row(result[0])
        return None
    
    @staticmethod
    def get_all(db_connection) -> List['ModelUsageStats']:
        """Get all model usage statistics."""
        query = "SELECT * FROM model_usage_stats ORDER BY usage_count DESC"
        result = db_connection.execute(query)
        return [ModelUsageStats.from_db_row(row) for row in result]
    
    @staticmethod
    def increment_usage(
        db_connection,
        model_name: str,
        transcription_duration: float = 0.0
    ):
        """Increment usage count for a model."""
        stats = ModelUsageStats.get_by_model_name(db_connection, model_name)
        
        if stats:
            # Update existing stats
            stats.usage_count += 1
            stats.last_used = current_timestamp()
            stats.total_transcription_duration += transcription_duration
            stats.save(db_connection)
        else:
            # Create new stats
            stats = ModelUsageStats(
                model_name=model_name,
                usage_count=1,
                last_used=current_timestamp(),
                total_transcription_duration=transcription_duration
            )
            stats.save(db_connection)
        
        logger.debug(f"Incremented usage for model: {model_name}")
    
    def delete(self, db_connection):
        """Delete model usage stats from database."""
        query = "DELETE FROM model_usage_stats WHERE id = ?"
        db_connection.execute(query, (self.id,), commit=True)
        logger.debug(f"Deleted model usage stats: {self.model_name}")
