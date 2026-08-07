# -*- coding: utf-8 -*-
"""
Golestoon Application Settings PyQt5 Dialog.

This module provides the SettingsDialog for configuring application preferences,
Auto-Sync intervals, export directories, and offline database backup/restore operations.

Architecture Layer: Layer 5 (Presentation & UI)
Dependencies: `PyQt5`, `SettingsManager`, `OfflineStorageService`, `DESIGN.md` Tokens.
"""

import logging
from typing import Optional
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt

from app.core.settings_manager import SettingsManager
from app.data.offline_storage_service import OfflineStorageService

logger = logging.getLogger("golestoon.ui.settings_dialog")


class SettingsDialog(QtWidgets.QDialog):
    """
    Main PyQt5 Dialog for Golestoon Settings & Preference Configuration.
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

        self.setWindowTitle("تنظیمات و پیکربندی برنامه (Golestoon Settings)")
        self.resize(520, 440)
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()
        self._apply_styles()
        self._load_current_settings()

    def _setup_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Title
        title_lbl = QtWidgets.QLabel("⚙️ تنظیمات و پیکربندی برنامه")
        title_lbl.setStyleSheet("font-size: 13pt; font-weight: bold; color: #f8fafc;")
        main_layout.addWidget(title_lbl)

        # Main Tab Widget
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setLayoutDirection(Qt.RightToLeft)

        # Tab 1: General & Sync Settings
        self.tab_general = QtWidgets.QWidget()
        self._setup_general_tab()
        self.tab_widget.addTab(self.tab_general, "⚙️ عمومی و همگام‌سازی")

        # Tab 2: Database & Backup
        self.tab_db = QtWidgets.QWidget()
        self._setup_db_tab()
        self.tab_widget.addTab(self.tab_db, "💾 پایگاه داده و بکاپ")

        main_layout.addWidget(self.tab_widget)

        # Bottom Actions Bar
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.addStretch()

        btn_save = QtWidgets.QPushButton("💾 ذخیره تغییرات")
        btn_save.setObjectName("primaryButton")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self._save_settings)
        btn_box.addWidget(btn_save)

        btn_cancel = QtWidgets.QPushButton("انصراف")
        btn_cancel.setObjectName("secondaryButton")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        main_layout.addLayout(btn_box)

    # ─────────────────────────────────────────────────────────
    # Tab 1: General & Sync
    # ─────────────────────────────────────────────────────────
    def _setup_general_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_general)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Auto Sync Checkbox
        self.chk_auto_sync = QtWidgets.QCheckBox("فعال‌سازی همگام‌سازی خودکار ابری (Auto-Sync)")
        self.chk_auto_sync.setStyleSheet("font-weight: bold; color: #f8fafc;")
        layout.addWidget(self.chk_auto_sync)

        # Interval SpinBox
        spin_box = QtWidgets.QHBoxLayout()
        spin_box.addWidget(QtWidgets.QLabel("بازه همگام‌سازی خودکار (دقیقه):"))
        self.spn_interval = QtWidgets.QSpinBox()
        self.spn_interval.setRange(5, 120)
        self.spn_interval.setSingleStep(5)
        spin_box.addWidget(self.spn_interval)
        spin_box.addStretch()
        layout.addLayout(spin_box)

        # Default Export Path
        layout.addSpacing(10)
        layout.addWidget(QtWidgets.QLabel("مسیر پیش‌فرض ذخیره خروجی‌ها (PDF / HTML / Excel):"))

        path_box = QtWidgets.QHBoxLayout()
        self.txt_export_path = QtWidgets.QLineEdit()
        btn_browse = QtWidgets.QPushButton("📁 انتخاب...")
        btn_browse.setObjectName("secondaryButton")
        btn_browse.clicked.connect(self._browse_export_directory)

        path_box.addWidget(self.txt_export_path)
        path_box.addWidget(btn_browse)
        layout.addLayout(path_box)

        layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # Tab 2: Database & Backup
    # ─────────────────────────────────────────────────────────
    def _setup_db_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_db)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Integrity Status Card
        self.card_db = QtWidgets.QFrame()
        self.card_db.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px;")
        card_layout = QtWidgets.QVBoxLayout(self.card_db)

        self.lbl_integrity_status = QtWidgets.QLabel("وضعیت پایگاه داده: آماده به کار")
        self.lbl_integrity_status.setStyleSheet("color: #f8fafc; font-weight: bold;")
        card_layout.addWidget(self.lbl_integrity_status)

        layout.addWidget(self.card_db)

        # Action Buttons
        btn_backup = QtWidgets.QPushButton("📂 ایجاد نسخه پشتیبان از پایگاه داده (Backup)")
        btn_backup.setObjectName("secondaryButton")
        btn_backup.clicked.connect(self._create_backup)
        layout.addWidget(btn_backup)

        btn_restore = QtWidgets.QPushButton("📥 بازیابی پایگاه داده از نسخه پشتیبان (Restore)")
        btn_restore.setObjectName("secondaryButton")
        btn_restore.clicked.connect(self._restore_backup)
        layout.addWidget(btn_restore)

        btn_check = QtWidgets.QPushButton("🔍 تست سلامت پایگاه داده (Integrity Check)")
        btn_check.setObjectName("secondaryButton")
        btn_check.clicked.connect(self._run_integrity_check)
        layout.addWidget(btn_check)

        layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # Slots & Helpers
    # ─────────────────────────────────────────────────────────
    def _load_current_settings(self) -> None:
        self.chk_auto_sync.setChecked(self._settings_mgr.auto_sync_enabled)
        self.spn_interval.setValue(self._settings_mgr.auto_sync_interval_minutes)
        self.txt_export_path.setText(self._settings_mgr.default_export_path)

    def _save_settings(self) -> None:
        self._settings_mgr.auto_sync_enabled = self.chk_auto_sync.isChecked()
        self._settings_mgr.auto_sync_interval_minutes = self.spn_interval.value()
        self._settings_mgr.default_export_path = self.txt_export_path.text().strip()

        QtWidgets.QMessageBox.information(self, "موفقیت", "تنظیمات برنامه با موفقیت ذخیره گردید.")
        self.accept()

    def _browse_export_directory(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "انتخاب پوشه پیش‌فرض خروجی‌ها", self.txt_export_path.text())
        if folder:
            self.txt_export_path.setText(folder)

    def _create_backup(self) -> None:
        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "ذخیره نسخه پشتیبان", "Golestoon_Backup.db", "SQLite Database (*.db)")
        if save_path:
            if self._storage_service.create_backup(save_path):
                QtWidgets.QMessageBox.information(self, "موفقیت", "نسخه پشتیبان با موفقیت ایجاد شد.")
            else:
                QtWidgets.QMessageBox.critical(self, "خطا", "ایجاد نسخه پشتیبان با خطا مواجه شد.")

    def _restore_backup(self) -> None:
        open_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "انتخاب نسخه پشتیبان", "", "SQLite Database (*.db)")
        if open_path:
            reply = QtWidgets.QMessageBox.question(self, "تایید بازیابی", "آیا از بازیابی این نسخه پشتیبان اطمینان دارید؟ داده‌های فعلی جایگزین خواهند شد.", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                if self._storage_service.restore_backup(open_path):
                    QtWidgets.QMessageBox.information(self, "موفقیت", "پایگاه داده با موفقیت بازیابی گردید.")
                else:
                    QtWidgets.QMessageBox.critical(self, "خطا", "بازیابی نسخه پشتیبان با خطا مواجه شد.")

    def _run_integrity_check(self) -> None:
        is_ok, msg = self._storage_service.check_integrity()
        if is_ok:
            self.lbl_integrity_status.setText("🟢 سلامت پایگاه داده لوکال کاملاً تایید شد (Integrity OK).")
            QtWidgets.QMessageBox.information(self, "سلامت پایگاه داده", "تست سلامت پایگاه داده با موفقیت انجام شد و هیچ خطایی یافت نشد.")
        else:
            self.lbl_integrity_status.setText(f"🔴 خطای سلامت دیتابیس: {msg}")
            QtWidgets.QMessageBox.critical(self, "خطای پایگاه داده", f"تست سلامت پایگاه داده خطای زیر را گزارش کرد:\n{msg}")

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #0f172a;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #94a3b8;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 9.5pt;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #3b82f6;
                color: #ffffff;
            }
            QLineEdit, QSpinBox {
                background-color: #1e293b;
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
            QPushButton#secondaryButton {
                background-color: #334155;
                color: #f8fafc;
                border-radius: 6px;
                padding: 8px 14px;
            }
        """)
