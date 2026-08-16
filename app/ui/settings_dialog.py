# -*- coding: utf-8 -*-
"""
Golestoon Application Settings PyQt5 Dialog.

This module provides the SettingsDialog with a 2-tiered user layout:
- Tier 1 (Standard Users): Auto-sync, Sync interval, Export folder path, Update check.
- Tier 2 (Advanced Users - Collapsible): Data backup, restore, and health diagnostics.

Architecture Layer: Layer 5 (Presentation & UI)
"""

import logging
from typing import Optional
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt

from app.core.settings_manager import SettingsManager
from app.data.offline_storage_service import OfflineStorageService
from app.core.error_humanizer import humanize_error
from app.core.theme_manager import theme_manager
from app.core.translator import translator

logger = logging.getLogger("golestoon.ui.settings_dialog")


class SettingsDialog(QtWidgets.QDialog):
    """
    Two-Tiered PyQt5 Dialog for Golestoon Settings & Preference Configuration.
    """

    def __init__(
        self,
        settings_manager: SettingsManager,
        storage_service: OfflineStorageService,
        parent: Optional[QtWidgets.QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._settings_mgr: SettingsManager = settings_manager
        self._storage_service: OfflineStorageService = storage_service

        self.setWindowTitle(translator.t("ui.settings.title"))
        self.resize(500, 480)
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()
        self._apply_styles()
        self._load_current_settings()

    def _setup_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header Title
        title_lbl = QtWidgets.QLabel(translator.t("ui.settings.title_label"))
        title_lbl.setObjectName("settingsTitle")
        main_layout.addWidget(title_lbl)

        # ── TIER 1: Standard Everyday Settings ────────────────────
        self.card_standard = QtWidgets.QFrame()
        self.card_standard.setObjectName("settingsCard")
        std_layout = QtWidgets.QVBoxLayout(self.card_standard)
        std_layout.setSpacing(12)

        # Auto Sync Checkbox
        self.chk_auto_sync = QtWidgets.QCheckBox(translator.t("ui.settings.auto_sync"))
        std_layout.addWidget(self.chk_auto_sync)

        # Interval SpinBox
        spin_box = QtWidgets.QHBoxLayout()
        spin_box.addWidget(QtWidgets.QLabel(translator.t("ui.settings.interval")))
        self.spn_interval = QtWidgets.QSpinBox()
        self.spn_interval.setRange(5, 120)
        self.spn_interval.setSingleStep(5)
        spin_box.addWidget(self.spn_interval)
        spin_box.addStretch()
        std_layout.addLayout(spin_box)

        # Theme selection (applies live, persisted immediately)
        theme_row = QtWidgets.QHBoxLayout()
        theme_row.addWidget(QtWidgets.QLabel(translator.t("ui.settings.theme")))
        self.theme_group = QtWidgets.QButtonGroup(self)
        self.radio_theme_light = QtWidgets.QRadioButton(translator.t("ui.settings.theme_light"))
        self.radio_theme_dark = QtWidgets.QRadioButton(translator.t("ui.settings.theme_dark"))
        self.radio_theme_system = QtWidgets.QRadioButton(translator.t("ui.settings.theme_system"))
        for radio in (self.radio_theme_light, self.radio_theme_dark, self.radio_theme_system):
            self.theme_group.addButton(radio)
            theme_row.addWidget(radio)
        self.theme_group.buttonClicked.connect(self._on_theme_radio_clicked)
        theme_row.addStretch()
        std_layout.addLayout(theme_row)

        # Default Export Path
        std_layout.addSpacing(6)
        std_layout.addWidget(QtWidgets.QLabel(translator.t("ui.settings.export_path")))

        path_box = QtWidgets.QHBoxLayout()
        self.txt_export_path = QtWidgets.QLineEdit()
        btn_browse = QtWidgets.QPushButton(translator.t("ui.settings.browse"))
        btn_browse.setObjectName("secondaryButton")
        btn_browse.clicked.connect(self._browse_export_directory)

        path_box.addWidget(self.txt_export_path)
        path_box.addWidget(btn_browse)
        std_layout.addLayout(path_box)

        main_layout.addWidget(self.card_standard)

        # ── TIER 2: Advanced Collapsible Section ──────────────────
        self.btn_toggle_advanced = QtWidgets.QPushButton(translator.t("ui.settings.advanced") + " ▼")
        self.btn_toggle_advanced.setObjectName("secondaryButton")
        self.btn_toggle_advanced.setCheckable(True)
        self.btn_toggle_advanced.clicked.connect(self._toggle_advanced_section)
        main_layout.addWidget(self.btn_toggle_advanced)

        self.adv_container = QtWidgets.QWidget()
        adv_layout = QtWidgets.QVBoxLayout(self.adv_container)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(10)

        # Status Label
        self.lbl_health_status = QtWidgets.QLabel(translator.t("ui.settings.health_ready"))
        self.lbl_health_status.setObjectName("mutedLabel")
        adv_layout.addWidget(self.lbl_health_status)

        # Backup & Restore Action Buttons
        btn_backup = QtWidgets.QPushButton(translator.t("ui.settings.backup"))
        btn_backup.setObjectName("secondaryButton")
        btn_backup.clicked.connect(self._create_backup)
        adv_layout.addWidget(btn_backup)

        btn_restore = QtWidgets.QPushButton(translator.t("ui.settings.restore"))
        btn_restore.setObjectName("secondaryButton")
        btn_restore.clicked.connect(self._restore_backup)
        adv_layout.addWidget(btn_restore)

        btn_check = QtWidgets.QPushButton(translator.t("ui.settings.check"))
        btn_check.setObjectName("secondaryButton")
        btn_check.clicked.connect(self._run_health_check)
        adv_layout.addWidget(btn_check)

        main_layout.addWidget(self.adv_container)
        self.adv_container.setVisible(False)  # Collapsed by default for 95% of users

        main_layout.addStretch()

        # Bottom Actions Bar
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.addStretch()

        btn_save = QtWidgets.QPushButton(translator.t("ui.settings.save"))
        btn_save.setObjectName("primaryButton")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._save_settings)
        btn_box.addWidget(btn_save)

        btn_cancel = QtWidgets.QPushButton(translator.t("ui.settings.cancel"))
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        main_layout.addLayout(btn_box)

    def _toggle_advanced_section(self, checked: bool) -> None:
        self.adv_container.setVisible(checked)
        adv = translator.t("ui.settings.advanced")
        self.btn_toggle_advanced.setText(f"{adv} ▲" if checked else f"{adv} ▼")

    def _load_current_settings(self) -> None:
        self.chk_auto_sync.setChecked(self._settings_mgr.auto_sync_enabled)
        self.spn_interval.setValue(self._settings_mgr.auto_sync_interval_minutes)
        self.txt_export_path.setText(self._settings_mgr.default_export_path)

        # Reflect the persisted theme mode
        mode = theme_manager.mode
        self.radio_theme_light.setChecked(mode == "light")
        self.radio_theme_dark.setChecked(mode == "dark")
        self.radio_theme_system.setChecked(mode == "system")

    def _on_theme_radio_clicked(self, button: QtWidgets.QAbstractButton) -> None:
        """Apply the selected theme mode live (persisted immediately)."""
        mode = {
            self.radio_theme_light: "light",
            self.radio_theme_dark: "dark",
            self.radio_theme_system: "system",
        }.get(button, "system")
        try:
            app = QtWidgets.QApplication.instance()
            theme_manager.set_mode(mode)
            if app is not None:
                theme_manager.apply(app)
            self._apply_styles()
        except Exception as err:  # noqa: BLE001 — UI boundary
            logger.error("Failed to apply theme '%s': %s", mode, err)

    def _save_settings(self) -> None:
        self._settings_mgr.auto_sync_enabled = self.chk_auto_sync.isChecked()
        self._settings_mgr.auto_sync_interval_minutes = self.spn_interval.value()
        self._settings_mgr.default_export_path = self.txt_export_path.text().strip()

        QtWidgets.QMessageBox.information(self, translator.t("ui.settings.success"), translator.t("ui.settings.saved_msg"))
        self.accept()

    def _browse_export_directory(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "انتخاب پوشه ذخیره فایل‌ها", self.txt_export_path.text())
        if folder:
            self.txt_export_path.setText(folder)

    def _create_backup(self) -> None:
        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "ذخیره نسخه پشتیبان", "Golestoon_Backup.bak", "نسخه پشتیبان (*.bak)")
        if save_path:
            if self._storage_service.create_backup(save_path):
                QtWidgets.QMessageBox.information(self, translator.t("ui.settings.success"), translator.t("ui.settings.backup_done"))
            else:
                QtWidgets.QMessageBox.critical(self, translator.t("ui.settings.success"), translator.t("ui.settings.backup_fail"))

    def _restore_backup(self) -> None:
        open_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "انتخاب نسخه پشتیبان", "", "نسخه پشتیبان (*.bak)")
        if open_path:
            reply = QtWidgets.QMessageBox.question(self, "تایید بازیابی", "آیا از بازیابی این نسخه پشتیبان اطمینان دارید؟ اطلاعات فعلی جایگزین خواهند شد.", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                if self._storage_service.restore_backup(open_path):
                    QtWidgets.QMessageBox.information(self, translator.t("ui.settings.success"), translator.t("ui.settings.restore_done"))
                else:
                    QtWidgets.QMessageBox.critical(self, translator.t("ui.settings.success"), translator.t("ui.settings.restore_fail"))

    def _run_health_check(self) -> None:
        is_ok, msg = self._storage_service.check_integrity()
        if is_ok:
            self.lbl_health_status.setText("🟢 اطلاعات برنامه کاملاً سالم و بدون مشکل می‌باشد.")
            QtWidgets.QMessageBox.information(self, translator.t("ui.settings.health_title"), translator.t("ui.settings.health_ok"))
        else:
            user_msg = humanize_error(msg, "در بررسی اطلاعات برنامه مشکلی یافت شد.")
            self.lbl_health_status.setText(f"🔴 مشکل در اطلاعات برنامه")
            QtWidgets.QMessageBox.critical(self, "بررسی سلامت اطلاعات", user_msg)

    def _apply_styles(self) -> None:
        p = theme_manager.palette()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p['bg']};
                color: {p['text']};
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
            }}
            QLabel#settingsTitle {{
                font-size: 14pt;
                font-weight: bold;
                color: {p['text']};
            }}
            QLabel#mutedLabel {{
                color: {p['muted']};
                font-size: 9.5pt;
            }}
            QFrame#settingsCard {{
                background-color: {p['surface']};
                border: 1px solid {p['border']};
                border-radius: 8px;
            }}
            QLineEdit, QSpinBox {{
                background-color: {p['surface']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 9.5pt;
            }}
            QCheckBox, QRadioButton {{
                font-size: 10pt;
                color: {p['text']};
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
            }}
            QPushButton#primaryButton {{
                background-color: {p['primary']};
                color: {p['primary_text']};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton#primaryButton:hover {{
                background-color: {p['primary_hover']};
            }}
            QPushButton#secondaryButton {{
                background-color: {p['surface']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 6px;
                padding: 6px 14px;
            }}
            QPushButton#secondaryButton:hover {{
                border-color: {p['primary']};
                color: {p['primary']};
            }}
        """)
