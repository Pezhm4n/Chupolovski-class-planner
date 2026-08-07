# -*- coding: utf-8 -*-
"""
Golestoon Version Manager & Compatibility Layer.

This module provides the VersionManager enforcing API version compatibility checks,
local database schema migrations, and version compatibility metadata.

Architecture Layer: Layer 4 (Application Logic & Manager)
Dependencies: `BaseClient`, `PyQt5.QtCore` (QThread, pyqtSignal).
"""

import logging
from typing import Optional, Dict, Any
from PyQt5.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger("golestoon.core.version")

CURRENT_DESKTOP_VERSION: str = "1.0.0"
MIN_COMPATIBLE_API_VERSION: str = "1.0.0"
CURRENT_DB_SCHEMA_VERSION: int = 1


class VersionCheckWorker(QThread):
    """Background worker thread to check API version compatibility."""

    finished_signal = pyqtSignal(dict)  # Version info dict
    error_signal = pyqtSignal(str)

    def __init__(self, base_client: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client = base_client

    def run(self) -> None:
        try:
            # Check backend health/version endpoint
            if hasattr(self._client, "get"):
                res = self._client.get("/api/health")
            elif hasattr(self._client, "request"):
                res = self._client.request("GET", "/api/health")
            else:
                res = {"status": "ok", "version": "1.0.0"}
            self.finished_signal.emit(res if isinstance(res, dict) else {})
        except Exception as err:
            self.error_signal.emit(str(err))


class VersionManager(QObject):
    """
    Manager facilitating desktop application version checks, API compatibility validation,
    and database schema migration logic.
    """

    def __init__(self, base_client: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client = base_client
        self._active_worker: Optional[QThread] = None

    @property
    def desktop_version(self) -> str:
        """Get current desktop application version string."""
        return CURRENT_DESKTOP_VERSION

    @property
    def schema_version(self) -> int:
        """Get current database schema version integer."""
        return CURRENT_DB_SCHEMA_VERSION

    def check_api_compatibility(self, on_result: Any) -> None:
        """Check API backend compatibility asynchronously."""
        worker = VersionCheckWorker(base_client=self._client)

        def _handle_success(data: dict):
            api_ver = data.get("version", "1.0.0")
            is_compatible = self.is_version_compatible(api_ver)
            on_result(is_compatible, api_ver, "")

        def _handle_error(err_msg: str):
            logger.warning("[VersionManager] Health check failed (Offline mode): %s", err_msg)
            on_result(True, "1.0.0", err_msg)

        worker.finished_signal.connect(_handle_success)
        worker.error_signal.connect(_handle_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

    @staticmethod
    def is_version_compatible(api_version: str) -> bool:
        """
        Validate if API version meets minimum desktop compatibility requirement.

        Args:
            api_version (str): Server API version string (e.g. "1.2.0").

        Returns:
            bool: True if compatible.
        """
        try:
            api_parts = [int(x) for x in api_version.split(".")[:3]]
            min_parts = [int(x) for x in MIN_COMPATIBLE_API_VERSION.split(".")[:3]]
            return api_parts >= min_parts
        except Exception:
            return True

    @staticmethod
    def run_database_migrations(db_connection: Any) -> int:
        """
        Perform automatic local SQLite database schema migrations if needed.

        Args:
            db_connection: Active sqlite3 Connection object.

        Returns:
            int: Applied schema version.
        """
        cursor = db_connection.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()

        current_ver = row[0] if row else 0

        if current_ver < 1:
            logger.info("[VersionManager] Migrating database schema to version 1...")
            cursor.execute("DELETE FROM schema_version")
            cursor.execute("INSERT INTO schema_version (version) VALUES (1)")
            db_connection.commit()
            current_ver = 1

        return current_ver
