# -*- coding: utf-8 -*-
"""
Golestoon Cloud Schedule Synchronization Dialog & Conflict Resolver.

This module provides the PyQt5 UI Dialogs for managing cloud saved schedules,
displaying sync status, handling offline modes, and resolving version conflicts.

Architecture Layer: Layer 5 (Presentation & UI)
Dependencies: `PyQt5`, `ScheduleSyncManager`, `DESIGN.md` Tokens.
"""

import time
import logging
from typing import Optional, List, Dict, Any
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, pyqtSignal

from app.core.cloud_sync_manager import ScheduleSyncManager
from app.core.network import ScheduleModel
from app.core.error_humanizer import humanize_error

logger = logging.getLogger("golestoon.ui.sync_dialog")
class SyncConflictDialog(QtWidgets.QDialog):
    """
    PyQt5 Dialog for resolving conflicts between local table and cloud schedule.
    """

    resolution_chosen = pyqtSignal(str)  # "local", "cloud", "merge"

    def __init__(
        self,
        local_courses_count: int,
        cloud_courses_count: int,
        schedule_name: str,
        parent: Optional[QtWidgets.QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("مغایرت در اطلاعات برنامه کلاسی")
        self.resize(520, 320)
        self.setLayoutDirection(Qt.RightToLeft)

        self._local_count: int = local_courses_count
        self._cloud_count: int = cloud_courses_count
        self._name: str = schedule_name
        self.chosen_resolution: Optional[str] = None

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Warning Icon & Title
        header_box = QtWidgets.QHBoxLayout()
        icon_lbl = QtWidgets.QLabel("⚠️")
        icon_lbl.setStyleSheet("font-size: 24pt;")
        header_box.addWidget(icon_lbl)

        title_box = QtWidgets.QVBoxLayout()
        lbl_title = QtWidgets.QLabel("تفاوت بین برنامه موجود و نسخه ابری")
        lbl_title.setStyleSheet("font-size: 13pt; font-weight: bold; color: #f59e0b;")
        lbl_desc = QtWidgets.QLabel(f"برنامه '{self._name}' در این دستگاه با نسخه ذخیره‌شده در حساب ابری متفاوت است.")
        lbl_desc.setStyleSheet("font-size: 9.5pt; color: #94a3b8;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_desc)
        header_box.addLayout(title_box)
        header_box.addStretch()
        layout.addLayout(header_box)

        # Side-by-Side Comparison Box
        compare_frame = QtWidgets.QFrame()
        compare_frame.setStyleSheet("background- border: 1px solid #334155; border-radius: 8px; padding: 12px;")
        cmp_layout = QtWidgets.QHBoxLayout(compare_frame)

        # Local Box
        box_local = QtWidgets.QVBoxLayout()
        lbl_loc_t = QtWidgets.QLabel("🖥️ نسخه روی این دستگاه")
        lbl_loc_t.setStyleSheet("font-weight: bold; color: #f8fafc;")
        lbl_loc_c = QtWidgets.QLabel(f"{self._local_count} درس در جدول")
        lbl_loc_c.setStyleSheet("color: #3b82f6; font-size: 11pt; font-weight: bold;")
        box_local.addWidget(lbl_loc_t)
        box_local.addWidget(lbl_loc_c)

        # Cloud Box
        box_cloud = QtWidgets.QVBoxLayout()
        lbl_cld_t = QtWidgets.QLabel("☁️ نسخه حساب ابری")
        lbl_cld_t.setStyleSheet("font-weight: bold; color: #f8fafc;")
        lbl_cld_c = QtWidgets.QLabel(f"{self._cloud_count} درس در حساب ابری")
        lbl_cld_c.setStyleSheet("color: #10b981; font-size: 11pt; font-weight: bold;")
        box_cloud.addWidget(lbl_cld_t)
        box_cloud.addWidget(lbl_cld_c)

        cmp_layout.addLayout(box_local)
        cmp_layout.addWidget(QtWidgets.QLabel("در برابر"))
        cmp_layout.addLayout(box_cloud)
        layout.addWidget(compare_frame)

        # Resolution Options Label
        layout.addWidget(QtWidgets.QLabel("لطفاً نحوه‌ جایگزینی را انتخاب کنید:"))

        # Resolution Buttons
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.setSpacing(10)

        btn_keep_local = QtWidgets.QPushButton("🖥️ حفظ برنامه این دستگاه")
        btn_keep_local.setObjectName("secondaryButton")
        btn_keep_local.clicked.connect(lambda: self._select("local"))

        btn_keep_cloud = QtWidgets.QPushButton("☁️ حفظ برنامه حساب ابری")
        btn_keep_cloud.setObjectName("secondaryButton")
        btn_keep_cloud.clicked.connect(lambda: self._select("cloud"))

        btn_merge = QtWidgets.QPushButton("🔀 ترکیب هر دو نسخه")
        btn_merge.setObjectName("primaryButton")
        btn_merge.clicked.connect(lambda: self._select("merge"))

        btn_box.addWidget(btn_keep_local)
        btn_box.addWidget(btn_keep_cloud)
        btn_box.addWidget(btn_merge)
        layout.addLayout(btn_box)

    def _select(self, option: str) -> None:
        self.chosen_resolution = option
        self.resolution_chosen.emit(option)
        self.accept()

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-
                color: #f8fafc;
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
            }
            QPushButton#primaryButton {
                background-color: #3b82f6;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton#secondaryButton {
                background-
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 14px;
            }
        """)
class CloudScheduleDialog(QtWidgets.QDialog):
    """
    Main PyQt5 Dialog for Cloud Schedule Sync, Management, and Local Integration.
    """

    load_schedule_requested = pyqtSignal(list)  # Emits course dictionaries list

    def __init__(
        self,
        sync_manager: ScheduleSyncManager,
        current_local_courses: Optional[List[Dict[str, Any]]] = None,
        parent: Optional[QtWidgets.QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._sync_manager: ScheduleSyncManager = sync_manager
        self._local_courses: List[Dict[str, Any]] = current_local_courses if current_local_courses else []
        self.setWindowTitle("همگام‌سازی و پشتیبان‌گیری ابری برنامه‌ها")
        self.resize(720, 520)
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()
        self._apply_styles()
        self._sync_manager.sync_status_changed.connect(self._on_status_changed)

        # Initial fetch
        self._refresh_cloud_schedules()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title & Status Bar
        header_box = QtWidgets.QHBoxLayout()
        title_lbl = QtWidgets.QLabel("☁️ همگام‌سازی ابری برنامه‌های کلاسی")
        title_lbl.setStyleSheet("font-size: 13pt; font-weight: bold; color: #f8fafc;")
        header_box.addWidget(title_lbl)
        header_box.addStretch()

        btn_refresh = QtWidgets.QPushButton("🔄 دریافت مجدد")
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.clicked.connect(self._refresh_cloud_schedules)
        header_box.addWidget(btn_refresh)
        layout.addLayout(header_box)

        # Status Bar Banner
        self.status_banner = QtWidgets.QFrame()
        self.status_banner.setStyleSheet("background- border: 1px solid #334155; border-radius: 6px; padding: 8px;")
        banner_layout = QtWidgets.QHBoxLayout(self.status_banner)
        banner_layout.setContentsMargins(10, 4, 10, 4)

        self.lbl_status_icon = QtWidgets.QLabel("🟢")
        self.lbl_status_text = QtWidgets.QLabel("وضعیت: آماده به کار")
        self.lbl_status_text.setStyleSheet("color: #f8fafc; font-size: 9.5pt;")
        self.lbl_last_sync = QtWidgets.QLabel("آخرین همگام‌سازی: ثبت نشده")
        self.lbl_last_sync.setStyleSheet(" font-size: 8.5pt;")

        banner_layout.addWidget(self.lbl_status_icon)
        banner_layout.addWidget(self.lbl_status_text)
        banner_layout.addStretch()
        banner_layout.addWidget(self.lbl_last_sync)
        layout.addWidget(self.status_banner)

        # Table of Cloud Schedules
        self.schedules_table = QtWidgets.QTableWidget()
        self.schedules_table.setColumnCount(4)
        self.schedules_table.setHorizontalHeaderLabels(["ردیف", "عنوان برنامه", "تعداد دروس", "تاریخ ثبت"])
        self.schedules_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.schedules_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.schedules_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        layout.addWidget(self.schedules_table)

        # Actions Buttons Bar
        actions_box = QtWidgets.QHBoxLayout()

        btn_upload_current = QtWidgets.QPushButton("☁️ ذخیره برنامه فعلی در حساب ابری")
        btn_upload_current.setObjectName("primaryButton")
        btn_upload_current.clicked.connect(self._on_upload_current_clicked)

        btn_load_selected = QtWidgets.QPushButton("📥 اعمال برنامه انتخابی در برنامه اصلی")
        btn_load_selected.setObjectName("secondaryButton")
        btn_load_selected.clicked.connect(self._on_load_selected_clicked)

        btn_delete_selected = QtWidgets.QPushButton("🗑️ حذف از حساب ابری")
        btn_delete_selected.setStyleSheet("background-color: #ef4444; color: #ffffff; border-radius: 6px; padding: 8px 14px; font-weight: bold;")
        btn_delete_selected.clicked.connect(self._on_delete_selected_clicked)

        actions_box.addWidget(btn_upload_current)
        actions_box.addWidget(btn_load_selected)
        actions_box.addWidget(btn_delete_selected)
        layout.addLayout(actions_box)

    def _refresh_cloud_schedules(self) -> None:
        def _on_success(schedules: List[ScheduleModel]):
            self._render_schedules_table(schedules)

        def _on_error(err_msg: str):
            logger.warning("Cloud schedule fetch failed (Offline Mode): %s", err_msg)

        self._sync_manager.fetch_cloud_schedules(on_success=_on_success, on_error=_on_error)

    def _render_schedules_table(self, schedules: List[ScheduleModel]) -> None:
        self.schedules_table.setRowCount(len(schedules))
        for r_idx, s in enumerate(schedules):
            self.schedules_table.setItem(r_idx, 0, QtWidgets.QTableWidgetItem(str(r_idx + 1)))
            self.schedules_table.setItem(r_idx, 1, QtWidgets.QTableWidgetItem(str(s.name)))
            self.schedules_table.setItem(r_idx, 2, QtWidgets.QTableWidgetItem(str(len(s.courses))))

            # Formatted Created Time
            created_str = time.strftime('%Y/%m/%d %H:%M', time.localtime(s.created_at / 1000)) if s.created_at > 1000000000 else "-"
            self.schedules_table.setItem(r_idx, 3, QtWidgets.QTableWidgetItem(created_str))

    def _on_upload_current_clicked(self) -> None:
        if not self._local_courses:
            QtWidgets.QMessageBox.warning(self, "اطلاعات خالی", "برنامه کلاسی این دستگاه خالی است. هیچ درسی برای ذخیره‌سازی ابری وجود ندارد.")
            return

        text, ok = QtWidgets.QInputDialog.getText(self, "نام برنامه ابری", "لطفاً عنوانی برای ذخیره برنامه در حساب ابری وارد کنید:", text="برنامه من")
        if not ok or not text.strip():
            return

        name = text.strip()

        def _on_success(model: ScheduleModel):
            QtWidgets.QMessageBox.information(self, "موفقیت", f"برنامه '{model.name}' با موفقیت در حساب ابری ذخیره شد.")
            self._refresh_cloud_schedules()

        def _on_error(err_msg: str):
            user_msg = humanize_error(err_msg, "ذخیره‌سازی برنامه در حساب ابری با خطا مواجه شد. لطفاً اتصال اینترنت خود را بررسی کنید.")
            QtWidgets.QMessageBox.critical(self, "خطا", user_msg)

        self._sync_manager.upload_schedule(name=name, courses=self._local_courses, on_success=_on_success, on_error=_on_error)

    def _on_load_selected_clicked(self) -> None:
        selected = self.schedules_table.currentRow()
        if selected < 0:
            QtWidgets.QMessageBox.warning(self, "انتخاب برنامه", "لطفاً ابتدا یک برنامه را از جدول انتخاب کنید.")
            return

        schedule_name = self.schedules_table.item(selected, 1).text()

        # Find in cache
        target: Optional[ScheduleModel] = None
        if selected < len(self._sync_manager._cloud_schedules_cache):
            target = self._sync_manager._cloud_schedules_cache[selected]

        if not target:
            return

        # Check for conflicts if local table has courses
        if self._local_courses and ScheduleSyncManager.detect_conflict(self._local_courses, target.courses):
            dlg = SyncConflictDialog(
                local_courses_count=len(self._local_courses),
                cloud_courses_count=len(target.courses),
                schedule_name=schedule_name,
                parent=self
            )
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                mode = dlg.chosen_resolution
                if mode == "local":
                    # Keep local: push local courses to update this cloud schedule
                    self._sync_manager.upload_schedule(name=target.name, courses=self._local_courses, on_success=lambda m: None, on_error=lambda e: None, schedule_id=target.id)
                    return
                elif mode == "cloud":
                    # Keep cloud: overwrite local table
                    self.load_schedule_requested.emit(target.courses)
                    self.accept()
                    return
                elif mode == "merge":
                    # Merge both
                    merged = ScheduleSyncManager.merge_courses(self._local_courses, target.courses)
                    self.load_schedule_requested.emit(merged)
                    self.accept()
                    return
            return

        # No conflict: apply directly
        self.load_schedule_requested.emit(target.courses)
        self.accept()

    def _on_delete_selected_clicked(self) -> None:
        selected = self.schedules_table.currentRow()
        if selected < 0:
            QtWidgets.QMessageBox.warning(self, "انتخاب برنامه", "لطفاً ابتدا یک برنامه را از جدول انتخاب کنید.")
            return

        target: Optional[ScheduleModel] = None
        if selected < len(self._sync_manager._cloud_schedules_cache):
            target = self._sync_manager._cloud_schedules_cache[selected]

        if not target:
            return

        schedule_id = str(target.id)
        schedule_name = target.name

        reply = QtWidgets.QMessageBox.question(self, "تایید حذف", f"آیا از حذف برنامه '{schedule_name}' از حساب ابری اطمینان دارید؟", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            def _on_success(sid: str):
                self._refresh_cloud_schedules()

            def _on_error(err_msg: str):
                user_msg = humanize_error(err_msg, "حذف برنامه انجام نشد. لطفاً اتصال اینترنت خود را بررسی کنید.")
                QtWidgets.QMessageBox.critical(self, "خطا", user_msg)

            self._sync_manager.delete_schedule(schedule_id=schedule_id, on_success=_on_success, on_error=_on_error)

    def _on_status_changed(self, status: str, message: str) -> None:
        if status == "syncing":
            self.lbl_status_icon.setText("🟡")
        elif status == "success":
            self.lbl_status_icon.setText("🟢")
        elif status == "offline":
            self.lbl_status_icon.setText("🟠")
        else:
            self.lbl_status_icon.setText("🔴")

        self.lbl_status_text.setText(f"وضعیت: {message}")
        if self._sync_manager.last_synced_time:
            t_str = time.strftime("%H:%M:%S", time.localtime(self._sync_manager.last_synced_time))
            self.lbl_last_sync.setText(f"آخرین Sync: {t_str}")

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-
                color: #f8fafc;
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
            }
            QPushButton#primaryButton {
                background-color: #3b82f6;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton#primaryButton:hover {
                background-color: #2563eb;
            }
            QPushButton#secondaryButton {
                background-color: #334155;
                color: #f8fafc;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QTableWidget {
                background-
                color: #f8fafc;
                gridline-color: #334155;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-
                color: #f8fafc;
                padding: 8px;
                font-weight: bold;
                border: 1px solid #334155;
            }
        """)
