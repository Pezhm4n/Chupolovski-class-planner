# -*- coding: utf-8 -*-
"""
Golestoon Theme Manager.

Provides light / dark / system theming for the whole desktop application,
mirroring golestan-web's SettingsContext behaviour (`light | dark | system`,
persisted, applied globally, live-switchable).

Implementation strategy — single source of truth:
    `app/ui/styles.qss` holds the LIGHT theme using the Tailwind/slate palette.
    The DARK theme is derived deterministically at runtime by hex-token
    substitution (LIGHT→DARK map below), so both themes can never drift apart
    and new widgets styled in styles.qss automatically support dark mode.

Dark palette follows the web design tokens:
    background hsl(0 0% 9%) ≈ #171717 → tinted #131316,
    surfaces #212126, borders #2e2e36, primary hsl(234 89% 73%) ≈ #7c86f5.

Architecture Layer: Layer 4 (Application Logic & Manager)
Dependencies: `PyQt5.QtCore`, QSettings persistence, `styles.qss`.
"""

import logging
import os
from typing import Dict, Optional

from PyQt5.QtCore import QObject, QSettings, pyqtSignal
from PyQt5.QtGui import QGuiApplication, QPalette

logger = logging.getLogger("golestoon.core.theme")

STYLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
LIGHT_QSS_FILE = os.path.join(STYLES_DIR, "styles.qss")

MODE_LIGHT = "light"
MODE_DARK = "dark"
MODE_SYSTEM = "system"
MODES = (MODE_LIGHT, MODE_DARK, MODE_SYSTEM)

# ─────────────────────────────────────────────────────────────
# Deterministic light→dark token map (Tailwind slate → web dark)
# ─────────────────────────────────────────────────────────────
DARK_COLOR_MAP: Dict[str, str] = {
    # Primary (blue-600 → indigo-400 web-dark primary)
    "#2563eb": "#7c86f5",
    "#1d4ed8": "#939cf7",
    "#1e40af": "#a5adfa",
    "#93c5fd": "#4b5064",
    # Surfaces & backgrounds
    "#ffffff": "#212126",
    "#f8fafc": "#131316",
    "#f1f5f9": "#1b1b20",
    "#eff6ff": "#20233a",
    # Borders
    "#e2e8f0": "#2e2e36",
    "#cbd5e1": "#3a3a44",
    # Text
    "#0f172a": "#f4f4f5",
    "#1e293b": "#e4e4e7",
    "#334155": "#d4d4d8",
    "#475569": "#b9bcc4",
    "#64748b": "#9ca0ab",
    "#94a3b8": "#6f7480",
    # Semantic accents
    "#dc2626": "#f87171",
    "#b91c1c": "#ef4444",
    "#ef4444": "#f87171",
    "#059669": "#34d399",
    "#047857": "#6ee7b7",
    "#10b981": "#34d399",
    "#7c3aed": "#a78bfa",
    "#8b5cf6": "#b39dfb",
}

# Semantic palette for code-built (inline) styles, per effective theme.
PALETTES = {
    MODE_LIGHT: {
        "bg": "#f8fafc", "surface": "#ffffff", "border": "#e2e8f0",
        "text": "#0f172a", "text_mid": "#334155", "muted": "#64748b",
        "primary": "#2563eb", "primary_hover": "#1d4ed8", "primary_text": "#ffffff",
        "tint": "#eff6ff",
        "success": "#059669", "danger": "#dc2626",
    },
    MODE_DARK: {
        "bg": "#131316", "surface": "#212126", "border": "#2e2e36",
        "text": "#f4f4f5", "text_mid": "#d4d4d8", "muted": "#9ca0ab",
        "primary": "#7c86f5", "primary_hover": "#939cf7", "primary_text": "#14142a",
        "tint": "#20233a",
        "success": "#34d399", "danger": "#f87171",
    },
}


class ThemeManager(QObject):
    """
    Singleton theme controller: persists the user's mode preference,
    resolves the effective theme (system mode follows the OS palette),
    builds themed QSS, and broadcasts changes.
    """

    theme_changed = pyqtSignal(str)  # effective theme: 'light' | 'dark'

    _instance: Optional["ThemeManager"] = None

    def __init__(self, organization: str = "Golestoon", application: str = "ClassPlanner") -> None:
        super().__init__()
        self._settings = QSettings(organization, application)
        self._mode = str(self._settings.value("theme_mode", MODE_SYSTEM))
        if self._mode not in MODES:
            self._mode = MODE_SYSTEM

    # ── Singleton access ─────────────────────────────────────
    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    # ── Mode persistence ─────────────────────────────────────
    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            logger.warning("Unknown theme mode '%s' ignored", mode)
            return
        self._mode = mode
        self._settings.setValue("theme_mode", mode)
        self._settings.sync()
        logger.info("Theme mode set to '%s'", mode)

    # ── Effective theme resolution ───────────────────────────
    def effective_theme(self) -> str:
        if self._mode == MODE_SYSTEM:
            try:
                color = QGuiApplication.palette().color(QPalette.Window)
                return MODE_DARK if color.lightness() < 128 else MODE_LIGHT
            except Exception:  # noqa: BLE001 — headless fallback
                return MODE_LIGHT
        return self._mode

    # ── QSS building ─────────────────────────────────────────
    def build_qss(self) -> str:
        """Load the base light QSS and derive the dark variant when needed."""
        try:
            with open(LIGHT_QSS_FILE, "r", encoding="utf-8") as fh:
                qss = fh.read()
        except OSError as err:
            logger.error("Failed to read styles.qss: %s", err)
            return ""

        if self.effective_theme() == MODE_DARK:
            for light_hex, dark_hex in DARK_COLOR_MAP.items():
                qss = qss.replace(light_hex, dark_hex)
                # Also cover uppercase occurrences for safety.
                qss = qss.replace(light_hex.upper(), dark_hex)
        return qss

    # ── Application helpers ──────────────────────────────────
    def apply(self, app) -> None:
        """Apply the themed stylesheet application-wide and notify listeners."""
        qss = self.build_qss()
        if qss:
            app.setStyleSheet(qss)
        self.theme_changed.emit(self.effective_theme())
        logger.info("Applied '%s' theme stylesheet", self.effective_theme())

    def palette(self) -> Dict[str, str]:
        """Semantic color palette for the current effective theme."""
        return PALETTES[self.effective_theme()]

    def toggle(self) -> None:
        """Switch between light and dark (system mode snaps to the opposite)."""
        self.set_mode(MODE_LIGHT if self.effective_theme() == MODE_DARK else MODE_DARK)


# Module-level singleton for convenient imports
theme_manager = ThemeManager.instance()
