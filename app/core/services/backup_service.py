import logging
import json
from typing import Dict, Any
from app.core.services.result import Result
from app.core.data_manager import cleanup_old_backups, get_latest_auto_backup, load_auto_backup, get_backup_history

class BackupService:
    """Service responsible for managing schedule backups."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
    def cleanup_old_backups(self) -> Result:
        """Clean up old backup files, keeping only the last 5"""
        try:
            cleanup_old_backups()
            return Result(success=True)
        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")
            return Result(success=False, error=str(e))
            
    def get_latest_backup_data(self) -> Result:
        """Get the data from the latest backup file"""
        try:
            latest_backup = get_latest_auto_backup()
            if latest_backup:
                backup_data = load_auto_backup(latest_backup)
                if backup_data:
                    return Result(success=True, data={'backup_data': backup_data, 'file_path': latest_backup})
                else:
                    return Result(success=False, error="Failed to load backup data")
            return Result(success=False, message="No backups found")
        except Exception as e:
            self.logger.error(f"Error loading latest backup: {e}")
            return Result(success=False, error=str(e))
            
    def load_specific_backup(self, file_path: str) -> Result:
        """Load data from a specific backup file path"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            return Result(success=True, data={'backup_data': backup_data})
        except Exception as e:
            self.logger.error(f"Error loading backup file: {e}")
            return Result(success=False, error=str(e))
            
    def get_all_backups(self) -> Result:
        """Get a list of all backup files"""
        try:
            backups = get_backup_history(limit=50) # Get a reasonable number of backups
            return Result(success=True, data={'backups': backups})
        except Exception as e:
            self.logger.error(f"Error getting backups: {e}")
            return Result(success=False, error=str(e))
