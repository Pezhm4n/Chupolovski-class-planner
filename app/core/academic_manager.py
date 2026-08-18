# -*- coding: utf-8 -*-
"""
Golestoon Academic Center Manager (ViewModel & Business Logic Layer).

This module provides the AcademicManager orchestrating real transcript syncs:
it reads locally-stored Golestan credentials, triggers the backend sync job
(`POST /api/transcript/sync` with wait=True), converts the returned JSON into
the desktop `Student` model, caches it into the per-student SQLite database,
and reports progress through QThread signals.

Architecture Layer: Layer 4 (Application Logic & Manager)
Dependencies: `TranscriptClient`, `StudentDatabase`, `converters`,
`PyQt5.QtCore` (QThread, pyqtSignal).
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from app.core.network.clients.transcript_client import TranscriptClient
from app.core.network.models import TranscriptSyncStatusModel
from app.core.network.converters import student_from_api
from app.core.network.exceptions import (
    GolestoonNetworkError,
    AuthenticationError,
    ValidationApiError,
)
from app.scrapers.requests_scraper.models import Student

logger = logging.getLogger("golestoon.academic.manager")


class SyncTranscriptWorker(QThread):
    """Background worker executing a blocking transcript sync and local caching."""

    finished_signal = pyqtSignal(object)     # Student model on success
    status_signal = pyqtSignal(str, str)     # (status, human message)
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        client: TranscriptClient,
        golestan_username: str,
        golestan_password: str,
        mode: str = "full",
        force: bool = True,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._client: TranscriptClient = client
        self._username: str = golestan_username
        self._password: str = golestan_password
        self._mode: str = mode
        self._force: bool = force

    def run(self) -> None:
        from app.core.network.config import is_api_configured
        if is_api_configured():
            try:
                result: TranscriptSyncStatusModel = self._client.trigger_sync(
                    golestan_username=self._username,
                    golestan_password=self._password,
                    mode=self._mode,
                    wait=True,
                    force=self._force,
                )
                self._handle_status(result)
                return
            except (GolestoonNetworkError, ValidationApiError) as err:
                logger.warning("API transcript sync failed (%s), falling back to local scraper.", err)

        # ── Standalone / Offline Scraper Mode ──
        try:
            self.status_signal.emit("syncing", "در حال دریافت مستقیم کارنامه از سامانه گلستان (حالت آفلاین/محلی)...")
            from app.scrapers.requests_scraper.fetch_data import get_student_record
            from app.data.student_db import StudentDatabase

            db = StudentDatabase(self._username)
            student = get_student_record(
                username=self._username,
                password=self._password,
                db=db
            )
            if student:
                self.finished_signal.emit(student)
            else:
                self.error_signal.emit("خطا در دریافت کارنامه از گلستان. لطفاً اطلاعات ورود را بررسی فرمایید.")
        except Exception as err:
            logger.exception("Local scraper transcript sync failed")
            err_msg = str(err)
            if "Authentication failed" in err_msg:
                err_msg = "نام کاربری یا رمز عبور گلستان نادرست است."
            self.error_signal.emit(f"خطا در دریافت کارنامه: {err_msg}")

    def _handle_status(self, result: TranscriptSyncStatusModel) -> None:
        status = result.status

        if status == "done" and result.student:
            try:
                student: Student = student_from_api(result.student)
            except Exception as err:  # noqa: BLE001 — conversion boundary
                logger.exception("Failed to convert student payload")
                self.error_signal.emit(f"CONVERSION_ERROR:{err}")
                return

            try:
                from app.data.student_db import StudentDatabase
                StudentDatabase(student.student_id).save_student(student)
            except Exception as err:  # noqa: BLE001 — cache write boundary
                logger.warning("Failed to cache student record locally: %s", err)

            self.finished_signal.emit(student)
            return

        if status == "too_recent":
            minutes = result.minutes_left
            msg = result.message or (
                "در ۱۰ دقیقه گذشته بروزرسانی انجام شده؛ لطفاً کمی بعد دوباره تلاش کنید."
                if minutes is None else
                f"محدودیت تعداد درخواست؛ {minutes} دقیقه دیگر تلاش کنید."
            )
            self.status_signal.emit(status, msg)
            return

        if status == "needs_login":
            self.status_signal.emit(status, "اعتبارنامه گلستان برای همگام‌سازی لازم است.")
            return

        if status in ("queued", "syncing"):
            self.status_signal.emit(status, "همگام‌سازی در حال اجراست؛ لطفاً منتظر بمانید.")
            return

        self.error_signal.emit(result.message or f"UNKNOWN_STATUS:{status}")


class AcademicManager(QObject):
    """
    Manager and ViewModel bridging PyQt5 dashboard UI with TranscriptClient
    and the local StudentDatabase cache.
    """

    def __init__(self, client: TranscriptClient, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: TranscriptClient = client
        # Hold every running worker so its Python wrapper is never GC'd
        # mid-run (a destroyed running QThread aborts the whole process).
        self._active_workers: set = set()

    @property
    def client(self) -> TranscriptClient:
        """Get underlying TranscriptClient instance."""
        return self._client

    def sync_transcript(
        self,
        golestan_username: str,
        golestan_password: str,
        on_success: Callable[[Student], Any],
        on_error: Callable[[str], Any],
        on_status: Optional[Callable[[str, str], Any]] = None,
        mode: str = "full",
        force: bool = True,
    ) -> None:
        """
        Trigger an async background transcript sync in a QThread.

        Args:
            golestan_username (str): University student ID.
            golestan_password (str): University Golestan password.
            on_success: Callback receiving the cached `Student` model.
            on_error: Callback receiving a human-readable error string
                (prefixed `AUTH_REQUIRED:` when the cloud JWT is missing/expired).
            on_status: Optional callback for non-terminal statuses
                (too_recent / needs_login / queued / syncing).
            mode (str): 'full' or 'recent'.
            force (bool): Skip the 10-minute freshness window.
        """
        worker = SyncTranscriptWorker(
            client=self._client,
            golestan_username=golestan_username,
            golestan_password=golestan_password,
            mode=mode,
            force=force,
        )
        worker.finished_signal.connect(on_success)
        worker.error_signal.connect(on_error)
        if on_status is not None:
            worker.status_signal.connect(on_status)
        self._active_workers.add(worker)

        def _release():
            self._active_workers.discard(worker)
            worker.deleteLater()

        worker.finished.connect(_release)
        worker.start()

    # ─────────────────────────────────────────────────────────
    #  GPA & Academic Analytics Calculations
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def calculate_gpa_analytics(semesters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute GPA trend, best/worst term, total passed vs failed units.

        Args:
            semesters (List[Dict[str, Any]]): List of semester dict records.

        Returns:
            Dict[str, Any]: Analytics summary containing gpa_trend, overall_gpa, etc.
        """
        if not semesters:
            return {
                "overall_gpa": 0.0,
                "best_term": None,
                "worst_term": None,
                "total_passed_units": 0,
                "total_failed_units": 0,
                "avg_units_per_term": 0.0,
                "gpa_trend": [],
            }

        gpa_trend: List[Tuple[str, float]] = []
        best_term: Optional[Tuple[str, float]] = None
        worst_term: Optional[Tuple[str, float]] = None
        total_passed = 0
        total_failed = 0
        valid_gpas: List[float] = []

        for sem in semesters:
            sem_title = sem.get("semester_description") or f"ترم {sem.get('semester_id', '')}"
            try:
                gpa_val = float(sem.get("semester_gpa", 0.0))
            except (ValueError, TypeError):
                gpa_val = 0.0

            try:
                passed_units = int(sem.get("units_passed", 0))
            except (ValueError, TypeError):
                passed_units = 0

            try:
                failed_units = int(sem.get("units_failed", 0))
            except (ValueError, TypeError):
                failed_units = 0

            total_passed += passed_units
            total_failed += failed_units

            if gpa_val > 0.0:
                valid_gpas.append(gpa_val)
                gpa_trend.append((sem_title, gpa_val))
                if best_term is None or gpa_val > best_term[1]:
                    best_term = (sem_title, gpa_val)
                if worst_term is None or gpa_val < worst_term[1]:
                    worst_term = (sem_title, gpa_val)

        overall_gpa = (sum(valid_gpas) / len(valid_gpas)) if valid_gpas else 0.0
        avg_units = (total_passed / len(semesters)) if semesters else 0.0

        return {
            "overall_gpa": round(overall_gpa, 2),
            "best_term": best_term,
            "worst_term": worst_term,
            "total_passed_units": total_passed,
            "total_failed_units": total_failed,
            "avg_units_per_term": round(avg_units, 1),
            "gpa_trend": gpa_trend,
        }

    @staticmethod
    def calculate_degree_progress_272(
        general_passed: int = 0, general_req: int = 22,
        basic_passed: int = 0, basic_req: int = 26,
        specialized_passed: int = 0, specialized_req: int = 80,
        elective_passed: int = 0, elective_req: int = 12
    ) -> Dict[str, Any]:
        """
        Compute a *synthetic* Report 272 breakdown (legacy helper).

        The dashboard now renders real server-side Report 272 data via
        `Student.degree_status`; this fallback remains for the legacy
        academic center dialog.
        """
        total_passed = general_passed + basic_passed + specialized_passed + elective_passed
        total_required = general_req + basic_req + specialized_req + elective_req
        total_pct = (total_passed / total_required * 100.0) if total_required > 0 else 0.0

        return {
            "general": {
                "title": "دروس عمومی",
                "passed": general_passed,
                "required": general_req,
                "remaining": max(0, general_req - general_passed),
                "pct": min(100.0, (general_passed / general_req * 100.0) if general_req > 0 else 0.0)
            },
            "basic": {
                "title": "دروس پایه",
                "passed": basic_passed,
                "required": basic_req,
                "remaining": max(0, basic_req - basic_passed),
                "pct": min(100.0, (basic_passed / basic_req * 100.0) if basic_req > 0 else 0.0)
            },
            "specialized": {
                "title": "دروس تخصصی",
                "passed": specialized_passed,
                "required": specialized_req,
                "remaining": max(0, specialized_req - specialized_passed),
                "pct": min(100.0, (specialized_passed / specialized_req * 100.0) if specialized_req > 0 else 0.0)
            },
            "elective": {
                "title": "دروس اختیاری",
                "passed": elective_passed,
                "required": elective_req,
                "remaining": max(0, elective_req - elective_passed),
                "pct": min(100.0, (elective_passed / elective_req * 100.0) if elective_req > 0 else 0.0)
            },
            "total_passed": total_passed,
            "total_required": total_required,
            "total_remaining": max(0, total_required - total_passed),
            "total_pct": round(min(100.0, total_pct), 1)
        }
