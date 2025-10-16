"""
Data cleanup utilities for EchoNote application.

Provides functions to safely delete all user data.
"""

import logging
import shutil
from pathlib import Path
from typing import List, Optional


logger = logging.getLogger('echonote.cleanup')


class DataCleanup:
    """
    Manages cleanup of all user data.
    
    Provides methods to safely delete database, configuration files,
    recordings, transcripts, and logs.
    """

    def __init__(self, config_dir: Optional[str] = None, data_dir: Optional[str] = None):
        """
        Initialize data cleanup manager.

        Args:
            config_dir: Configuration directory (default: ~/.echonote)
            data_dir: Data directory (default: ~/Documents/EchoNote)
        """
        if config_dir is None:
            self.config_dir = Path.home() / ".echonote"
        else:
            self.config_dir = Path(config_dir).expanduser()
        
        if data_dir is None:
            self.data_dir = Path.home() / "Documents" / "EchoNote"
        else:
            self.data_dir = Path(data_dir).expanduser()
        
        logger.info("Data cleanup manager initialized")
    
    def get_cleanup_summary(self) -> dict:
        """
        Get a summary of what will be deleted.

        Returns:
            Dictionary with file counts and sizes
        """
        summary = {
            'database_exists': False,
            'database_size': 0,
            'config_files': [],
            'config_size': 0,
            'recordings_count': 0,
            'recordings_size': 0,
            'transcripts_count': 0,
            'transcripts_size': 0,
            'logs_count': 0,
            'logs_size': 0,
            'total_size': 0
        }
        
        # Check database
        db_path = self.config_dir / "data.db"
        if db_path.exists():
            summary['database_exists'] = True
            summary['database_size'] = db_path.stat().st_size
            summary['total_size'] += summary['database_size']
        
        # Check config files
        if self.config_dir.exists():
            for file_path in self.config_dir.glob("*"):
                if file_path.is_file():
                    summary['config_files'].append(file_path.name)
                    file_size = file_path.stat().st_size
                    summary['config_size'] += file_size
                    summary['total_size'] += file_size
        
        # Check recordings
        recordings_dir = self.data_dir / "Recordings"
        if recordings_dir.exists():
            for file_path in recordings_dir.rglob("*"):
                if file_path.is_file():
                    summary['recordings_count'] += 1
                    file_size = file_path.stat().st_size
                    summary['recordings_size'] += file_size
                    summary['total_size'] += file_size
        
        # Check transcripts
        transcripts_dir = self.data_dir / "Transcripts"
        if transcripts_dir.exists():
            for file_path in transcripts_dir.rglob("*"):
                if file_path.is_file():
                    summary['transcripts_count'] += 1
                    file_size = file_path.stat().st_size
                    summary['transcripts_size'] += file_size
                    summary['total_size'] += file_size
        
        # Check logs
        logs_dir = self.config_dir / "logs"
        if logs_dir.exists():
            for file_path in logs_dir.rglob("*"):
                if file_path.is_file():
                    summary['logs_count'] += 1
                    file_size = file_path.stat().st_size
                    summary['logs_size'] += file_size
                    summary['total_size'] += file_size
        
        return summary
    
    def cleanup_all_data(self) -> dict:
        """
        Delete all user data.
        
        WARNING: This operation cannot be undone!

        Returns:
            Dictionary with cleanup results
        """
        logger.warning("Starting cleanup of all user data")
        
        results = {
            'success': True,
            'deleted_items': [],
            'failed_items': [],
            'errors': []
        }
        
        # Delete database
        self._delete_database(results)
        
        # Delete config directory
        self._delete_config_directory(results)
        
        # Delete data directory
        self._delete_data_directory(results)
        
        if results['success']:
            logger.info("All user data cleaned up successfully")
        else:
            logger.warning(
                f"Cleanup completed with {len(results['failed_items'])} errors"
            )
        
        return results
    
    def _delete_database(self, results: dict):
        """Delete database file."""
        db_path = self.config_dir / "data.db"
        
        if db_path.exists():
            try:
                db_path.unlink()
                results['deleted_items'].append(str(db_path))
                logger.info(f"Deleted database: {db_path}")
            except Exception as e:
                error_msg = f"Failed to delete database: {e}"
                logger.error(error_msg)
                results['failed_items'].append(str(db_path))
                results['errors'].append(error_msg)
                results['success'] = False
        else:
            logger.debug("Database file does not exist, skipping")
    
    def _delete_config_directory(self, results: dict):
        """Delete configuration directory."""
        if self.config_dir.exists():
            try:
                # Delete all files in config directory
                for item in self.config_dir.iterdir():
                    try:
                        if item.is_file():
                            item.unlink()
                            results['deleted_items'].append(str(item))
                            logger.debug(f"Deleted config file: {item}")
                        elif item.is_dir():
                            shutil.rmtree(item)
                            results['deleted_items'].append(str(item))
                            logger.debug(f"Deleted config directory: {item}")
                    except Exception as e:
                        error_msg = f"Failed to delete {item}: {e}"
                        logger.error(error_msg)
                        results['failed_items'].append(str(item))
                        results['errors'].append(error_msg)
                        results['success'] = False
                
                # Try to delete the config directory itself
                try:
                    self.config_dir.rmdir()
                    results['deleted_items'].append(str(self.config_dir))
                    logger.info(f"Deleted config directory: {self.config_dir}")
                except OSError:
                    # Directory not empty (some files failed to delete)
                    logger.warning(
                        f"Config directory not empty, could not delete: "
                        f"{self.config_dir}"
                    )
                
            except Exception as e:
                error_msg = f"Failed to delete config directory: {e}"
                logger.error(error_msg)
                results['failed_items'].append(str(self.config_dir))
                results['errors'].append(error_msg)
                results['success'] = False
        else:
            logger.debug("Config directory does not exist, skipping")
    
    def _delete_data_directory(self, results: dict):
        """Delete data directory (recordings, transcripts, etc.)."""
        if self.data_dir.exists():
            try:
                shutil.rmtree(self.data_dir)
                results['deleted_items'].append(str(self.data_dir))
                logger.info(f"Deleted data directory: {self.data_dir}")
            except Exception as e:
                error_msg = f"Failed to delete data directory: {e}"
                logger.error(error_msg)
                results['failed_items'].append(str(self.data_dir))
                results['errors'].append(error_msg)
                results['success'] = False
        else:
            logger.debug("Data directory does not exist, skipping")
    
    def cleanup_specific_items(self, items: List[str]) -> dict:
        """
        Delete specific items.

        Args:
            items: List of item types to delete
                   ('database', 'config', 'recordings', 'transcripts', 'logs')

        Returns:
            Dictionary with cleanup results
        """
        logger.info(f"Starting cleanup of specific items: {items}")
        
        results = {
            'success': True,
            'deleted_items': [],
            'failed_items': [],
            'errors': []
        }
        
        if 'database' in items:
            self._delete_database(results)
        
        if 'config' in items:
            # Delete config files but not the directory
            if self.config_dir.exists():
                for file_path in self.config_dir.glob("*.json"):
                    try:
                        file_path.unlink()
                        results['deleted_items'].append(str(file_path))
                        logger.info(f"Deleted config file: {file_path}")
                    except Exception as e:
                        error_msg = f"Failed to delete {file_path}: {e}"
                        logger.error(error_msg)
                        results['failed_items'].append(str(file_path))
                        results['errors'].append(error_msg)
                        results['success'] = False
        
        if 'recordings' in items:
            recordings_dir = self.data_dir / "Recordings"
            if recordings_dir.exists():
                try:
                    shutil.rmtree(recordings_dir)
                    results['deleted_items'].append(str(recordings_dir))
                    logger.info(f"Deleted recordings directory: {recordings_dir}")
                except Exception as e:
                    error_msg = f"Failed to delete recordings: {e}"
                    logger.error(error_msg)
                    results['failed_items'].append(str(recordings_dir))
                    results['errors'].append(error_msg)
                    results['success'] = False
        
        if 'transcripts' in items:
            transcripts_dir = self.data_dir / "Transcripts"
            if transcripts_dir.exists():
                try:
                    shutil.rmtree(transcripts_dir)
                    results['deleted_items'].append(str(transcripts_dir))
                    logger.info(f"Deleted transcripts directory: {transcripts_dir}")
                except Exception as e:
                    error_msg = f"Failed to delete transcripts: {e}"
                    logger.error(error_msg)
                    results['failed_items'].append(str(transcripts_dir))
                    results['errors'].append(error_msg)
                    results['success'] = False
        
        if 'logs' in items:
            logs_dir = self.config_dir / "logs"
            if logs_dir.exists():
                try:
                    shutil.rmtree(logs_dir)
                    results['deleted_items'].append(str(logs_dir))
                    logger.info(f"Deleted logs directory: {logs_dir}")
                except Exception as e:
                    error_msg = f"Failed to delete logs: {e}"
                    logger.error(error_msg)
                    results['failed_items'].append(str(logs_dir))
                    results['errors'].append(error_msg)
                    results['success'] = False
        
        return results
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string (e.g., "1.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"


def cleanup_all_data(config_dir: Optional[str] = None, data_dir: Optional[str] = None) -> dict:
    """
    Convenience function to cleanup all user data.

    Args:
        config_dir: Configuration directory (default: ~/.echonote)
        data_dir: Data directory (default: ~/Documents/EchoNote)

    Returns:
        Dictionary with cleanup results
    """
    cleanup = DataCleanup(config_dir, data_dir)
    return cleanup.cleanup_all_data()


def get_cleanup_summary(config_dir: Optional[str] = None, data_dir: Optional[str] = None) -> dict:
    """
    Convenience function to get cleanup summary.

    Args:
        config_dir: Configuration directory (default: ~/.echonote)
        data_dir: Data directory (default: ~/Documents/EchoNote)

    Returns:
        Dictionary with file counts and sizes
    """
    cleanup = DataCleanup(config_dir, data_dir)
    return cleanup.get_cleanup_summary()
