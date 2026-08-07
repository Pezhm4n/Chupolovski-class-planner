# -*- coding: utf-8 -*-
"""
Golestoon Application Settings & Preferences Manager.

This module provides the SettingsManager handling persistent application configuration,
Auto-Sync intervals, export paths, and preference change notifications using QSettings.

Architecture Layer: Layer 4 (Application Logic & Manager)
Dependencies: `PyQt5.QtCore` (QSettings, QObject, pyqtSignal).
"""

import os
import logging
from typing import Any, Dict
from PyQt5.QtCore import QObject, QSettings, pyqtSignal

logger = logging.getLogger("golestoon.core.settings")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "auto_sync_enabled": True,
    "auto_sync_interval_minutes": 30,
    "default_export_path": os.path.expanduser("~/Documents"),
    "theme_mode": "dark",
    "cloud_endpoint_url": "https://golestoon-app.ir",
}


class SettingsManager(QObject):
    """
    Manager facilitating persistent user settings and preference storage via QSettings.
    """

    settings_changed = pyqtSignal()  # Emitted when any setting is updated

    def __init__(self, organization: str = "Golestoon", application: str = "ClassPlanner", parent: QObject = None) -> None:
        super().__init__(parent)
        self._settings = QSettings(organization, application)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get value for a configuration key.

        Args:
            key (str): Setting name key.
            default (Any): Fallback value if key is not set.

        Returns:
            Any: Stored value or fallback default.
        """
        if default is None:
            default = DEFAULT_SETTINGS.get(key)
        return self._settings.value(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """
        Set and persist value for a configuration key.

        Args:
            key (str): Setting name key.
            value (Any): Value to persist.
        """
        self._settings.setValue(key, value)
        self._settings.sync()
        self.settings_changed.emit()
        logger.debug("[SettingsManager] Updated '%s' -> '%s'", key, value)

    @property
    def auto_sync_enabled(self) -> bool:
        """Get auto sync enabled boolean flag."""
        val = self.get_setting("auto_sync_enabled", True)
        return str(val).lower() in ("true", "1")

    @auto_sync_enabled.setter
    def auto_sync_enabled(self, value: bool) -> None:
        self.set_setting("auto_sync_enabled", bool(value))

    @property
    def auto_sync_interval_minutes(self) -> int:
        """Get auto sync interval in minutes."""
        try:
            return int(self.get_setting("auto_sync_interval_minutes", 30))
        except (ValueError, TypeError):
            return 30

    @auto_sync_interval_minutes.setter
    def auto_sync_interval_minutes(self, minutes: int) -> None:
        self.set_setting("auto_sync_interval_minutes", int(minutes))

    @property
    def default_export_path(self) -> str:
        """Get default export directory path."""
        return str(self.get_setting("default_export_path", os.path.expanduser("~/Documents")))

    @default_export_path.setter
    def default_export_path(self, path_str: str) -> None:
        self.set_setting("default_export_path", str(path_str))
