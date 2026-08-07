# -*- coding: utf-8 -*-
"""
Golestoon Cloud Schedule Sync Manager (Offline-First Architecture).

This module provides the ScheduleSyncManager handling background QThread worker tasks,
conflict detection, merge logic, timestamp tracking, and seamless offline fallback for schedules.

Architecture Layer: Layer 4 (Application Logic & Manager)
Dependencies: `ScheduleClient`, `ScheduleModel`, `PyQt5.QtCore` (QThread, pyqtSignal).
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from app.core.network.clients.schedule_client import ScheduleClient
from app.core.network.models import ScheduleModel
from app.core.network.exceptions import GolestoonNetworkError

logger = logging.getLogger("golestoon.schedules.sync")


# ─────────────────────────────────────────────────────────────
#  Background QThread Workers
# ─────────────────────────────────────────────────────────────

class FetchCloudSchedulesWorker(QThread):
    """Background worker thread to fetch cloud schedules without freezing UI."""

    finished_signal = pyqtSignal(list)  # List[ScheduleModel]
    error_signal = pyqtSignal(str)

    def __init__(self, client: ScheduleClient, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: ScheduleClient = client

    def run(self) -> None:
        try:
            schedules = self._client.get_schedules()
            self.finished_signal.emit(schedules)
        except GolestoonNetworkError as err:
            self.error_signal.emit(err.message)
        except Exception as err:
            self.error_signal.emit(str(err))


class UploadScheduleWorker(QThread):
    """Background worker thread to upload local schedule to cloud."""

    finished_signal = pyqtSignal(object)  # ScheduleModel
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        client: ScheduleClient,
        name: str,
        courses: List[Dict[str, Any]],
        schedule_id: Optional[str] = None,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self._client: ScheduleClient = client
        self._name: str = name
        self._courses: List[Dict[str, Any]] = courses
        self._schedule_id: Optional[str] = schedule_id

    def run(self) -> None:
        try:
            if self._schedule_id:
                model = self._client.update_schedule(
                    schedule_id=self._schedule_id,
                    name=self._name,
                    courses=self._courses
                )
            else:
                model = self._client.create_schedule(
                    name=self._name,
                    courses=self._courses
                )
            self.finished_signal.emit(model)
        except GolestoonNetworkError as err:
            self.error_signal.emit(err.message)
        except Exception as err:
            self.error_signal.emit(str(err))


class DeleteScheduleWorker(QThread):
    """Background worker thread to delete a cloud schedule."""

    finished_signal = pyqtSignal(str)  # schedule_id
    error_signal = pyqtSignal(str)

    def __init__(self, client: ScheduleClient, schedule_id: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: ScheduleClient = client
        self._schedule_id: str = schedule_id

    def run(self) -> None:
        try:
            self._client.delete_schedule(schedule_id=self._schedule_id)
            self.finished_signal.emit(self._schedule_id)
        except GolestoonNetworkError as err:
            self.error_signal.emit(err.message)
        except Exception as err:
            self.error_signal.emit(str(err))


# ─────────────────────────────────────────────────────────────
#  ScheduleSyncManager Class
# ─────────────────────────────────────────────────────────────

class ScheduleSyncManager(QObject):
    """
    Manager facilitating Offline-First cloud schedule synchronization, conflict detection,
    merge resolution, and background execution.
    """

    sync_status_changed = pyqtSignal(str, str)  # (status_code, display_message)

    def __init__(self, client: ScheduleClient, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: ScheduleClient = client
        self._last_synced_time: Optional[float] = None
        self._current_status: str = "idle"  # idle, syncing, success, error, offline
        self._cloud_schedules_cache: List[ScheduleModel] = []
        self._active_worker: Optional[QThread] = None

    @property
    def client(self) -> ScheduleClient:
        """Get underlying ScheduleClient instance."""
        return self._client

    @property
    def current_status(self) -> str:
        """Get active sync status code."""
        return self._current_status

    @property
    def last_synced_time(self) -> Optional[float]:
        """Get epoch timestamp of last successful sync."""
        return self._last_synced_time

    def fetch_cloud_schedules(self, on_success: Any, on_error: Any) -> None:
        """Fetch saved cloud schedules asynchronously."""
        self._set_status("syncing", "در حال دریافت برنامه‌های ابری...")
        worker = FetchCloudSchedulesWorker(client=self._client)

        def _handle_success(schedules: List[ScheduleModel]):
            self._cloud_schedules_cache = schedules
            self._last_synced_time = time.time()
            self._set_status("success", "برنامه‌های ابری با موفقیت دریافت شدند.")
            on_success(schedules)

        def _handle_error(err_msg: str):
            self._set_status("offline", "حالت آفلاین — خطا در اتصال به سرور ابری.")
            on_error(err_msg)

        worker.finished_signal.connect(_handle_success)
        worker.error_signal.connect(_handle_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

    def upload_schedule(
        self,
        name: str,
        courses: List[Dict[str, Any]],
        on_success: Any,
        on_error: Any,
        schedule_id: Optional[str] = None
    ) -> None:
        """Upload or update local schedule to cloud asynchronously."""
        self._set_status("syncing", "در حال ذخیره‌سازی ابری...")
        worker = UploadScheduleWorker(
            client=self._client,
            name=name,
            courses=courses,
            schedule_id=schedule_id
        )

        def _handle_success(model: ScheduleModel):
            self._last_synced_time = time.time()
            self._set_status("success", "برنامه با موفقیت در ابری ذخیره شد.")
            on_success(model)

        def _handle_error(err_msg: str):
            self._set_status("offline", "حالت آفلاین — ذخیره‌سازی فقط در حافظه لوکال.")
            on_error(err_msg)

        worker.finished_signal.connect(_handle_success)
        worker.error_signal.connect(_handle_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

    def delete_schedule(self, schedule_id: str, on_success: Any, on_error: Any) -> None:
        """Delete cloud schedule asynchronously."""
        self._set_status("syncing", "در حال حذف برنامه از سرور ابری...")
        worker = DeleteScheduleWorker(client=self._client, schedule_id=schedule_id)

        def _handle_success(sid: str):
            self._cloud_schedules_cache = [s for s in self._cloud_schedules_cache if str(s.id) != str(sid)]
            self._set_status("success", "برنامه ابری با موفقیت حذف شد.")
            on_success(sid)

        def _handle_error(err_msg: str):
            self._set_status("error", f"خطا در حذف برنامه: {err_msg}")
            on_error(err_msg)

        worker.finished_signal.connect(_handle_success)
        worker.error_signal.connect(_handle_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

    # ─────────────────────────────────────────────────────────
    #  Conflict Detection & Deduplication Merge Logic
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def detect_conflict(
        local_courses: List[Dict[str, Any]],
        cloud_courses: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if local and cloud course lists differ in course codes or count.

        Returns:
            bool: True if conflict exists between local and cloud versions.
        """
        if len(local_courses) != len(cloud_courses):
            return True

        local_keys = {c.get("code", "") for c in local_courses if c.get("code")}
        cloud_keys = {c.get("code", "") for c in cloud_courses if c.get("code")}

        return local_keys != cloud_keys

    @staticmethod
    def merge_courses(
        local_courses: List[Dict[str, Any]],
        cloud_courses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge local and cloud course lists into a deduplicated combined array.

        Returns:
            List[Dict[str, Any]]: Combined deduplicated courses list.
        """
        merged_map: Dict[str, Dict[str, Any]] = {}

        # Add all cloud courses
        for course in cloud_courses:
            code = course.get("code") or course.get("course_code") or str(id(course))
            merged_map[code] = course

        # Add local courses (overwriting or appending)
        for course in local_courses:
            code = course.get("code") or course.get("course_code") or str(id(course))
            merged_map[code] = course

        return list(merged_map.values())

    def _set_status(self, status: str, message: str) -> None:
        self._current_status = status
        self.sync_status_changed.emit(status, message)
        logger.info("[ScheduleSyncManager] Status: %s - %s", status, message)
