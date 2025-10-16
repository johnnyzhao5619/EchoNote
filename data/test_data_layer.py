"""
Quick verification script for data layer implementation.

This script tests basic functionality of all data layer components.
"""

import sys
import tempfile
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_database_connection():
    """Test database connection and schema initialization."""
    print("Testing DatabaseConnection...")
    
    from data.database.connection import DatabaseConnection
    
    # Use in-memory database for testing
    db = DatabaseConnection(":memory:")
    
    # Initialize schema
    db.initialize_schema()
    
    # Test version management
    version = db.get_version()
    print(f"  ✓ Schema version: {version}")
    
    # Test query execution
    result = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row['name'] for row in result]
    print(f"  ✓ Created {len(tables)} tables")
    
    db.close()
    print("  ✓ DatabaseConnection test passed\n")


def test_data_models():
    """Test data models."""
    print("Testing Data Models...")
    
    from data.database.connection import DatabaseConnection
    from data.database.models import (
        TranscriptionTask, CalendarEvent, EventAttachment
    )
    
    # Setup database
    db = DatabaseConnection(":memory:")
    db.initialize_schema()
    
    # Test TranscriptionTask
    task = TranscriptionTask(
        file_path="/test/audio.mp3",
        file_name="audio.mp3",
        file_size=1024000,
        status="pending",
        engine="faster-whisper"
    )
    task.save(db)
    
    retrieved_task = TranscriptionTask.get_by_id(db, task.id)
    assert retrieved_task.file_name == "audio.mp3"
    print("  ✓ TranscriptionTask CRUD works")
    
    # Test CalendarEvent
    event = CalendarEvent(
        title="Test Meeting",
        event_type="Event",
        start_time="2025-10-07T10:00:00",
        end_time="2025-10-07T11:00:00",
        attendees=["user1@example.com", "user2@example.com"]
    )
    event.save(db)
    
    retrieved_event = CalendarEvent.get_by_id(db, event.id)
    assert retrieved_event.title == "Test Meeting"
    assert len(retrieved_event.attendees) == 2
    print("  ✓ CalendarEvent CRUD works")
    
    # Test EventAttachment
    attachment = EventAttachment(
        event_id=event.id,
        attachment_type="recording",
        file_path="/recordings/test.wav",
        file_size=5000000
    )
    attachment.save(db)
    
    attachments = EventAttachment.get_by_event_id(db, event.id)
    assert len(attachments) == 1
    print("  ✓ EventAttachment CRUD works")
    
    db.close()
    print("  ✓ Data Models test passed\n")


def test_security_manager():
    """Test security manager."""
    print("Testing SecurityManager...")
    
    from data.security.encryption import SecurityManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        security = SecurityManager(tmpdir)
        
        # Test encryption/decryption
        plaintext = "This is sensitive data!"
        encrypted = security.encrypt(plaintext)
        decrypted = security.decrypt(encrypted)
        
        assert decrypted == plaintext
        print("  ✓ Encryption/decryption works")
        
        # Test dictionary encryption
        data = {
            "api_key": "sk-test123",
            "token": "abc123xyz"
        }
        encrypted_dict = security.encrypt_dict(data)
        decrypted_dict = security.decrypt_dict(encrypted_dict)
        
        assert decrypted_dict == data
        print("  ✓ Dictionary encryption works")
        
        # Test password hashing
        password = "mypassword123"
        hashed = security.hash_password(password)
        
        assert security.verify_password(password, hashed)
        assert not security.verify_password("wrongpassword", hashed)
        print("  ✓ Password hashing works")
    
    print("  ✓ SecurityManager test passed\n")


def test_oauth_manager():
    """Test OAuth manager."""
    print("Testing OAuthManager...")
    
    from data.security.encryption import SecurityManager
    from data.security.oauth_manager import OAuthManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        security = SecurityManager(tmpdir)
        oauth = OAuthManager(security, tmpdir)
        
        # Test token storage
        oauth.store_token(
            provider="google",
            access_token="ya29.test",
            refresh_token="1//test",
            expires_in=3600
        )
        
        assert oauth.has_token("google")
        print("  ✓ Token storage works")
        
        # Test token retrieval
        token = oauth.get_access_token("google")
        assert token == "ya29.test"
        print("  ✓ Token retrieval works")
        
        # Test expiration check
        is_expired = oauth.is_token_expired("google")
        assert not is_expired  # Should not be expired yet
        print("  ✓ Expiration check works")
        
        # Test token refresh (with mock callback)
        oauth.store_token(
            provider="test",
            access_token="old_token",
            refresh_token="refresh_token",
            expires_in=3600
        )
        
        def mock_refresh_callback(refresh_token):
            return {
                'access_token': 'new_token',
                'expires_in': 3600
            }
        
        refreshed = oauth.refresh_token_if_needed("test", mock_refresh_callback)
        assert refreshed['access_token'] == 'old_token'  # Not expired yet
        print("  ✓ Token refresh check works")
        
        # Test token deletion
        oauth.delete_token("google")
        oauth.delete_token("test")
        assert not oauth.has_token("google")
        print("  ✓ Token deletion works")
    
    print("  ✓ OAuthManager test passed\n")


def test_file_manager():
    """Test file manager."""
    print("Testing FileManager...")
    
    from data.storage.file_manager import FileManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_mgr = FileManager(tmpdir)
        
        # Test text file save/read
        content = "This is a test file."
        path = file_mgr.save_text_file(
            content=content,
            filename="test.txt",
            subdirectory="Transcripts"
        )
        
        read_content = file_mgr.read_text_file(path)
        assert read_content == content
        print("  ✓ Text file save/read works")
        
        # Test file exists
        assert file_mgr.file_exists(path)
        print("  ✓ File exists check works")
        
        # Test file size
        size = file_mgr.get_file_size(path)
        assert size > 0
        print("  ✓ File size retrieval works")
        
        # Test file listing
        files = file_mgr.list_files(subdirectory="Transcripts")
        assert len(files) == 1
        print("  ✓ File listing works")
        
        # Test ensure_directory
        file_mgr.ensure_directory("CustomDir")
        custom_dir = Path(tmpdir) / "CustomDir"
        assert custom_dir.exists()
        print("  ✓ Ensure directory works")
        
        # Test set_file_permissions
        file_mgr.set_file_permissions(path, 0o644)
        stat_info = os.stat(path)
        assert stat_info.st_mode & 0o777 == 0o644
        print("  ✓ Set file permissions works")
        
        # Test file deletion
        file_mgr.delete_file(path)
        assert not file_mgr.file_exists(path)
        print("  ✓ File deletion works")
    
    print("  ✓ FileManager test passed\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("EchoNote Data Layer Verification")
    print("=" * 60 + "\n")
    
    try:
        test_database_connection()
        test_data_models()
        test_security_manager()
        test_oauth_manager()
        test_file_manager()
        
        print("=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
