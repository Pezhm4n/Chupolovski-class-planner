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

        self.setWindowTitle("تنظیمات برنامه")
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
        title_lbl = QtWidgets.QLabel("⚙️ تنظیمات برنامه")
        title_lbl.setStyleSheet("font-size: 14pt; font-weight: bold; color: #f8fafc;")
        main_layout.addWidget(title_lbl)

        # ── TIER 1: Standard Everyday Settings ────────────────────
        self.card_standard = QtWidgets.QFrame()
        self.card_standard.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px;")
        std_layout = QtWidgets.QVBoxLayout(self.card_standard)
        std_layout.setSpacing(12)

        # Auto Sync Checkbox
        self.chk_auto_sync = QtWidgets.QCheckBox("همگام‌سازی خودکار برنامه‌ها")
        self.chk_auto_sync.setStyleSheet("font-weight: bold; color: #f8fafc;")
        std_layout.addWidget(self.chk_auto_sync)

        # Interval SpinBox
        spin_box = QtWidgets.QHBoxLayout()
        spin_box.addWidget(QtWidgets.QLabel("فاصله زمان همگام‌سازی (دقیقه):"))
        self.spn_interval = QtWidgets.QSpinBox()
        self.spn_interval.setRange(5, 120)
        self.spn_interval.setSingleStep(5)
        spin_box.addWidget(self.spn_interval)
        spin_box.addStretch()
        std_layout.addLayout(spin_box)

        # Default Export Path
        std_layout.addSpacing(6)
        std_layout.addWidget(QtWidgets.QLabel("پوشه پیش‌فرض ذخیره فایل‌ها (PDF / Excel / CSV):"))

        path_box = QtWidgets.QHBoxLayout()
        self.txt_export_path = QtWidgets.QLineEdit()
        btn_browse = QtWidgets.QPushButton("📁 تغییر پوشه...")
        btn_browse.setObjectName("secondaryButton")
        btn_browse.clicked.connect(self._browse_export_directory)

        path_box.addWidget(self.txt_export_path)
        path_box.addWidget(btn_browse)
        std_layout.addLayout(path_box)

        main_layout.addWidget(self.card_standard)

        # ── TIER 2: Advanced Collapsible Section ──────────────────
        self.btn_toggle_advanced = QtWidgets.QPushButton("تنظیمات پیشرفته ▼")
        self.btn_toggle_advanced.setObjectName("secondaryButton")
        self.btn_toggle_advanced.setCheckable(True)
        self.btn_toggle_advanced.clicked.connect(self._toggle_advanced_section)
        main_layout.addWidget(self.btn_toggle_advanced)

        self.adv_container = QtWidgets.QWidget()
        adv_layout = QtWidgets.QVBoxLayout(self.adv_container)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(10)

        # Status Label
        self.lbl_health_status = QtWidgets.QLabel("وضعیت فایل‌های برنامه: آماده به کار")
        self.lbl_health_status.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        adv_layout.addWidget(self.lbl_health_status)

        # Backup & Restore Action Buttons
        btn_backup = QtWidgets.QPushButton("📂 پشتیبان‌گیری از اطلاعات برنامه")
        btn_backup.setObjectName("secondaryButton")
        btn_backup.clicked.connect(self._create_backup)
        adv_layout.addWidget(btn_backup)

        btn_restore = QtWidgets.QPushButton("📥 بازیابی اطلاعات از نسخه پشتیبان")
        btn_restore.setObjectName("secondaryButton")
        btn_restore.clicked.connect(self._restore_backup)
        adv_layout.addWidget(btn_restore)

        btn_check = QtWidgets.QPushButton("🔍 بررسی سلامت اطلاعات برنامه")
        btn_check.setObjectName("secondaryButton")
        btn_check.clicked.connect(self._run_health_check)
        adv_layout.addWidget(btn_check)

        main_layout.addWidget(self.adv_container)
        self.adv_container.setVisible(False)  # Collapsed by default for 95% of users

        main_layout.addStretch()

        # Bottom Actions Bar
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.addStretch()

        btn_save = QtWidgets.QPushButton("ذخیره تغییرات")
        btn_save.setObjectName("primaryButton")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._save_settings)
        btn_box.addWidget(btn_save)

        btn_cancel = QtWidgets.QPushButton("انصراف")
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        main_layout.addLayout(btn_box)

    def _toggle_advanced_section(self, checked: bool) -> None:
        self.adv_container.setVisible(checked)
        self.btn_toggle_advanced.setText("تنظیمات پیشرفته ▲" if checked else "تنظیمات پیشرفته ▼")

    def _load_current_settings(self) -> None:
        self.chk_auto_sync.setChecked(self._settings_mgr.auto_sync_enabled)
        self.spn_interval.setValue(self._settings_mgr.auto_sync_interval_minutes)
        self.txt_export_path.setText(self._settings_mgr.default_export_path)

    def _save_settings(self) -> None:
        self._settings_mgr.auto_sync_enabled = self.chk_auto_sync.isChecked()
        self._settings_mgr.auto_sync_interval_minutes = self.spn_interval.value()
        self._settings_mgr.default_export_path = self.txt_export_path.text().strip()

        QtWidgets.QMessageBox.information(self, "موفقیت", "تنظیمات برنامه با موفقیت ذخیره شد.")
        self.accept()

    def _browse_export_directory(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "انتخاب پوشه ذخیره فایل‌ها", self.txt_export_path.text())
        if folder:
            self.txt_export_path.setText(folder)

    def _create_backup(self) -> None:
        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "ذخیره نسخه پشتیبان", "Golestoon_Backup.bak", "نسخه پشتیبان (*.bak)")
        if save_path:
            if self._storage_service.create_backup(save_path):
                QtWidgets.QMessageBox.information(self, "موفقیت", "نسخه پشتیبان با موفقیت ایجاد شد.")
            else:
                QtWidgets.QMessageBox.critical(self, "خطا", "ایجاد نسخه پشتیبان انجام نشد.")

    def _restore_backup(self) -> None:
        open_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "انتخاب نسخه پشتیبان", "", "نسخه پشتیبان (*.bak)")
        if open_path:
            reply = QtWidgets.QMessageBox.question(self, "تایید بازیابی", "آیا از بازیابی این نسخه پشتیبان اطمینان دارید؟ اطلاعات فعلی جایگزین خواهند شد.", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                if self._storage_service.restore_backup(open_path):
                    QtWidgets.QMessageBox.information(self, "موفقیت", "اطلاعات برنامه با موفقیت بازیابی شد.")
                else:
                    QtWidgets.QMessageBox.critical(self, "خطا", "بازیابی نسخه پشتیبان انجام نشد.")

    def _run_health_check(self) -> None:
        is_ok, msg = self._storage_service.check_integrity()
        if is_ok:
            self.lbl_health_status.setText("🟢 اطلاعات برنامه کاملاً سالم و بدون مشکل می‌باشد.")
            QtWidgets.QMessageBox.information(self, "بررسی سلامت اطلاعات", "بررسی سلامت اطلاعات برنامه انجام شد و هیچ مشکلی یافت نشد.")
        else:
            user_msg = humanize_error(msg, "در بررسی اطلاعات برنامه مشکلی یافت شد.")
            self.lbl_health_status.setText(f"🔴 مشکل در اطلاعات برنامه")
            QtWidgets.QMessageBox.critical(self, "بررسی سلامت اطلاعات", user_msg)

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
            }
            QLineEdit, QSpinBox {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 9.5pt;
            }
            QPushButton#primaryButton {
                background-color: #3b82f6;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton#primaryButton:hover {
                background-color: #2563eb;
            }
            QPushButton#secondaryButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton#secondaryButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
            QCheckBox {
                font-size: 10pt;
                color: #f8fafc;
            }
        """)
