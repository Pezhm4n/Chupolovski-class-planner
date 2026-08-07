# -*- coding: utf-8 -*-
"""
Golestoon Academic Center Manager (ViewModel & Business Logic Layer).

This module provides the AcademicManager handling student academic profiles,
transcript analytics, GPA trend computations, Report 272 degree progress breakdown,
and background QThread workers.

Architecture Layer: Layer 4 (Application Logic & Manager)
Dependencies: `TranscriptClient`, `StudentDatabase`, `PyQt5.QtCore` (QThread, pyqtSignal).
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from app.core.network.clients.transcript_client import TranscriptClient
from app.core.network.models import TranscriptSyncStatusModel
from app.core.network.exceptions import GolestoonNetworkError

logger = logging.getLogger("golestoon.academic.manager")


class SyncTranscriptWorker(QThread):
    """Background worker thread to trigger transcript and Report 272 sync."""

    finished_signal = pyqtSignal(object)  # TranscriptSyncStatusModel
    error_signal = pyqtSignal(str)

    def __init__(self, client: TranscriptClient, student_number: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: TranscriptClient = client
        self._student_number: str = student_number

    def run(self) -> None:
        try:
            status = self._client.sync_transcript(student_number=self._student_number)
            self.finished_signal.emit(status)
        except GolestoonNetworkError as err:
            self.error_signal.emit(err.message)
        except Exception as err:
            self.error_signal.emit(str(err))


class AcademicManager(QObject):
    """
    Manager and ViewModel bridging PyQt5 Academic Center UI with TranscriptClient and local StudentDatabase.
    """

    def __init__(self, client: TranscriptClient, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: TranscriptClient = client
        self._active_worker: Optional[QThread] = None

    @property
    def client(self) -> TranscriptClient:
        """Get underlying TranscriptClient instance."""
        return self._client

    def sync_transcript(self, student_number: str, on_success: Any, on_error: Any) -> None:
        """Trigger async background transcript sync."""
        worker = SyncTranscriptWorker(client=self._client, student_number=student_number)
        worker.finished_signal.connect(on_success)
        worker.error_signal.connect(on_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

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
        Compute Report 272 degree requirement progress breakdown matching Golestan web view.

        Returns:
            Dict[str, Any]: Progress percentages and unit shortages per category.
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
