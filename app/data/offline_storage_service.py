# -*- coding: utf-8 -*-
"""
Golestoon Offline Data Storage & SQLite Backup Service.

This module provides the OfflineStorageService for local SQLite database maintenance,
metadata storage, database integrity checks, and backup/restoration operations.

Architecture Layer: Layer 2 (Data Storage & Persistence)
Dependencies: Python Standard Library (`sqlite3`, `shutil`, `os`, `time`, `logging`).
"""

import os
import shutil
import sqlite3
import logging
from typing import Tuple, Optional
from pathlib import Path

logger = logging.getLogger("golestoon.data.offline")


class OfflineStorageService:
    """
    Service managing local SQLite database persistence, integrity checks, and backups.
    Enforces zero-credential storage policy in SQLite database.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            data_dir = Path(__file__).resolve().parent
            db_path = os.path.join(data_dir, "offline_app_data.db")
        self._db_path: str = str(db_path)
        self._init_database()

    @property
    def db_path(self) -> str:
        """Get absolute path to SQLite database file."""
        return self._db_path

    def _init_database(self) -> None:
        """Initialize database tables for app metadata."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def check_integrity(self) -> Tuple[bool, str]:
        """
        Run SQLite integrity check (PRAGMA quick_check).

        Returns:
            Tuple[bool, str]: (is_ok, status_message)
        """
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check")
            res = cursor.fetchone()
            msg = res[0] if res else "ok"
            is_ok = msg.lower() == "ok"
            return is_ok, msg
        except Exception as err:
            return False, str(err)
        finally:
            conn.close()

    def create_backup(self, target_backup_path: str) -> bool:
        """
        Create a file backup copy of the current SQLite database.

        Args:
            target_backup_path (str): Filepath to save backup copy.

        Returns:
            bool: True if backup succeeded.
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(target_backup_path)), exist_ok=True)
            shutil.copy2(self._db_path, target_backup_path)
            logger.info("[OfflineStorageService] Backup saved to %s", target_backup_path)
            return True
        except Exception as err:
            logger.error("[OfflineStorageService] Backup failed: %s", err)
            return False

    def restore_backup(self, source_backup_path: str) -> bool:
        """
        Restore current SQLite database from a backup file.

        Args:
            source_backup_path (str): Filepath to backup file.

        Returns:
            bool: True if restore succeeded.
        """
        if not os.path.exists(source_backup_path):
            logger.warning("[OfflineStorageService] Backup file does not exist: %s", source_backup_path)
            return False

        try:
            shutil.copy2(source_backup_path, self._db_path)
            logger.info("[OfflineStorageService] Database restored from %s", source_backup_path)
            return True
        except Exception as err:
            logger.error("[OfflineStorageService] Restore failed: %s", err)
            return False
