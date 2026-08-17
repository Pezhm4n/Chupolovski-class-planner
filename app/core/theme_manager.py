# -*- coding: utf-8 -*-
"""
Golestoon Theme Manager.

Provides professional light / dark / system theming for the desktop application,
mirroring modern high-contrast design systems (shadcn/ui & Tailwind Slate).

Implementation Strategy:
    - Single source of truth in `app/ui/styles.qss`.
    - Dark variant derived via carefully balanced semantic Slate tokens.
    - System QPalette synchronization to prevent any unstyled Qt widgets
      from falling back to white backgrounds in dark mode.

Architecture Layer: Layer 4 (Application Logic & Manager)
"""

import logging
import os
from typing import Dict, Optional

from PyQt5.QtCore import QObject, QSettings, pyqtSignal
from PyQt5.QtGui import QGuiApplication, QPalette, QColor

logger = logging.getLogger("golestoon.core.theme")

STYLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
LIGHT_QSS_FILE = os.path.join(STYLES_DIR, "styles.qss")

MODE_LIGHT = "light"
MODE_DARK = "dark"
MODE_SYSTEM = "system"
MODES = (MODE_LIGHT, MODE_DARK, MODE_SYSTEM)

# ─────────────────────────────────────────────────────────────
# Professional Light → Slate Dark Token Map
# ─────────────────────────────────────────────────────────────
DARK_COLOR_MAP: Dict[str, str] = {
    # 1. Primary Colors & Interactive Accents (Vibrant Blue 500 / 400)
    "#2563eb": "#3b82f6",
    "#1d4ed8": "#60a5fa",
    "#1e40af": "#2563eb",
    "#93c5fd": "#1d4ed8",
    "#eff6ff": "#172554",

    # 2. Canvas & Surface Hierarchy (Deep Slate Pro)
    "#f8fafc": "#0b0f19",  # Main Canvas Background
    "#ffffff": "#131b2e",  # Elevated Card / Panel Surface
    "#f1f5f9": "#1e293b",  # Secondary Sub-surface / Item background

    # 3. Structural Borders & Dividers
    "#e2e8f0": "#243048",  # Standard Card Border
    "#cbd5e1": "#334155",  # Control / Input Border

    # 4. Text Hierarchy (Crisp, high-contrast, ultra-legible)
    "#0f172a": "#f8fafc",  # Primary Headings & Body (Slate 50)
    "#1e293b": "#e2e8f0",  # Secondary Text (Slate 200)
    "#334155": "#cbd5e1",  # Neutral Text (Slate 300)
    "#475569": "#94a3b8",  # Label / Caption Text (Slate 400)
    "#64748b": "#64748b",  # Muted Text (Slate 500)
    "#94a3b8": "#475569",  # Disabled Text (Slate 600)

    # 5. Semantic Feedback Colors
    "#10b981": "#10b981",  # Success Emerald
    "#059669": "#059669",
    "#047857": "#047857",
    "#ef4444": "#ef4444",  # Danger Rose
    "#dc2626": "#dc2626",
    "#b91c1c": "#b91c1c",
    "#8b5cf6": "#3b82f6",
    "#7c3aed": "#2563eb",
}

# Semantic palette for inline code styling
PALETTES = {
    MODE_LIGHT: {
        "bg": "#f8fafc",
        "surface": "#ffffff",
        "border": "#e2e8f0",
        "text": "#0f172a",
        "text_mid": "#334155",
        "muted": "#64748b",
        "primary": "#2563eb",
        "primary_hover": "#1d4ed8",
        "primary_text": "#ffffff",
        "tint": "#eff6ff",
        "success": "#10b981",
        "danger": "#ef4444",
    },
    MODE_DARK: {
        "bg": "#0b0f19",
        "surface": "#131b2e",
        "border": "#243048",
        "text": "#f8fafc",
        "text_mid": "#cbd5e1",
        "muted": "#94a3b8",
        "primary": "#3b82f6",
        "primary_hover": "#60a5fa",
        "primary_text": "#ffffff",
        "tint": "#172554",
        "success": "#10b981",
        "danger": "#ef4444",
    },
}


class ThemeManager(QObject):
    """
    Singleton theme controller managing application-wide light/dark/system themes,
    QSettings persistence, and real-time palette synchronization.
    """

    theme_changed = pyqtSignal(str)  # 'light' | 'dark'

    _instance: Optional["ThemeManager"] = None

    def __init__(self, organization: str = "Golestoon", application: str = "ClassPlanner") -> None:
        super().__init__()
        self._settings = QSettings(organization, application)
        self._mode = str(self._settings.value("theme_mode", MODE_SYSTEM))
        if self._mode not in MODES:
            self._mode = MODE_SYSTEM

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

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

    def effective_theme(self) -> str:
        if self._mode == MODE_SYSTEM:
            try:
                color = QGuiApplication.palette().color(QPalette.Window)
                return MODE_DARK if color.lightness() < 128 else MODE_LIGHT
            except Exception:
                return MODE_LIGHT
        return self._mode

    def build_qss(self) -> str:
        """Load the base stylesheet and apply deterministic dark tokens if in dark mode."""
        try:
            with open(LIGHT_QSS_FILE, "r", encoding="utf-8") as fh:
                qss = fh.read()
        except OSError as err:
            logger.error("Failed to read styles.qss: %s", err)
            return ""

        if self.effective_theme() == MODE_DARK:
            import re
            lower_map = {k.lower(): v for k, v in DARK_COLOR_MAP.items()}
            qss = re.sub(
                r"#[0-9a-fA-F]{6}",
                lambda m: lower_map.get(m.group(0).lower(), m.group(0)),
                qss
            )
        return qss

    def apply_palette(self, app) -> None:
        """Synchronize Qt application palette to prevent native white fallbacks."""
        if not app:
            return

        is_dark = self.effective_theme() == MODE_DARK
        palette = QPalette()

        if is_dark:
            palette.setColor(QPalette.Window, QColor("#0b0f19"))
            palette.setColor(QPalette.WindowText, QColor("#f8fafc"))
            palette.setColor(QPalette.Base, QColor("#131b2e"))
            palette.setColor(QPalette.AlternateBase, QColor("#1e293b"))
            palette.setColor(QPalette.ToolTipBase, QColor("#1e293b"))
            palette.setColor(QPalette.ToolTipText, QColor("#f8fafc"))
            palette.setColor(QPalette.Text, QColor("#f8fafc"))
            palette.setColor(QPalette.Button, QColor("#131b2e"))
            palette.setColor(QPalette.ButtonText, QColor("#f8fafc"))
            palette.setColor(QPalette.BrightText, QColor("#ffffff"))
            palette.setColor(QPalette.Highlight, QColor("#3b82f6"))
            palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
            palette.setColor(QPalette.Link, QColor("#60a5fa"))
            palette.setColor(QPalette.LinkVisited, QColor("#93c5fd"))
        else:
            palette.setColor(QPalette.Window, QColor("#f8fafc"))
            palette.setColor(QPalette.WindowText, QColor("#0f172a"))
            palette.setColor(QPalette.Base, QColor("#ffffff"))
            palette.setColor(QPalette.AlternateBase, QColor("#f1f5f9"))
            palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
            palette.setColor(QPalette.ToolTipText, QColor("#0f172a"))
            palette.setColor(QPalette.Text, QColor("#0f172a"))
            palette.setColor(QPalette.Button, QColor("#ffffff"))
            palette.setColor(QPalette.ButtonText, QColor("#0f172a"))
            palette.setColor(QPalette.BrightText, QColor("#ffffff"))
            palette.setColor(QPalette.Highlight, QColor("#2563eb"))
            palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
            palette.setColor(QPalette.Link, QColor("#2563eb"))
            palette.setColor(QPalette.LinkVisited, QColor("#1d4ed8"))

        app.setPalette(palette)

    def apply(self, app) -> None:
        """Apply both the themed stylesheet and the synced palette application-wide."""
        self.apply_palette(app)
        qss = self.build_qss()
        if qss and app:
            app.setStyleSheet(qss)
        self.theme_changed.emit(self.effective_theme())
        logger.info("Applied '%s' theme stylesheet & palette", self.effective_theme())

    def palette(self) -> Dict[str, str]:
        """Semantic color palette for the current effective theme."""
        return PALETTES[self.effective_theme()]

    def toggle(self) -> None:
        """Switch between light and dark modes."""
        self.set_mode(MODE_LIGHT if self.effective_theme() == MODE_DARK else MODE_DARK)


# Module-level singleton
theme_manager = ThemeManager.instance()
