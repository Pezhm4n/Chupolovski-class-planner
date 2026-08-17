# -*- coding: utf-8 -*-
"""
Golestoon Professor Reviews Manager (ViewModel & Business Logic Layer).

Bridges the PyQt5 professor-review UI with `ProfessorClient` (server-accurate
contracts: `*_avg` aggregates for reading, `*_score` for submitting) through
background QThread workers, caching and web-parity score formulas.

Architecture Layer: Layer 4 (Application Logic & Manager)
Dependencies: `ProfessorClient`, `ProfessorStats`, `ProfessorReview`, PyQt5.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Set

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from app.core.network.clients.professor_client import (
    ProfessorClient,
    ProfessorStats,
    ProfessorReview,
)
from app.core.network.exceptions import GolestoonNetworkError

logger = logging.getLogger("golestoon.professors.manager")

TELEGRAM_WEIGHT: float = 0.4


def clamp_score(val: float) -> float:
    """Clamp score value between 0.0 and 100.0."""
    return max(0.0, min(100.0, float(val)))


def get_score_color_hex(score: float) -> str:
    """Get color hex for score (Green >= 80, Blue >= 60, Amber >= 40, Red < 40) — web thresholds."""
    score = clamp_score(score)
    if score >= 80.0:
        return "#16a34a"
    elif score >= 60.0:
        return "#3b82f6"
    elif score >= 40.0:
        return "#f59e0b"
    return "#ef4444"


def get_inverse_score_color_hex(difficulty_score: float) -> str:
    """Color for difficulty (higher = harder = red)."""
    difficulty_score = clamp_score(difficulty_score)
    if difficulty_score >= 80.0:
        return "#ef4444"
    elif difficulty_score >= 60.0:
        return "#f59e0b"
    elif difficulty_score >= 40.0:
        return "#3b82f6"
    return "#16a34a"


def calc_overall_score(stats: Optional[ProfessorStats]) -> float:
    """
    Web-formula composite: Overall = Teaching*0.30 + Grading*0.40 + (100-ExamDifficulty)*0.30.
    Server-computed `overall_avg` takes precedence when present.
    """
    if not stats:
        return 0.0
    if stats.overall_avg is not None:
        return clamp_score(stats.overall_avg)
    exam_ease = clamp_score(100.0 - stats.exam_difficulty_avg)
    overall = (stats.teaching_avg * 0.30) + (stats.grading_avg * 0.40) + (exam_ease * 0.30)
    return clamp_score(overall)


def calc_display_score(stats: Optional[ProfessorStats]) -> float:
    """Site+Telegram weighted display score (web TELEGRAM_WEIGHT = 0.4)."""
    if not stats:
        return 0.0

    site_reviews = float(stats.total_reviews)
    telegram_voters = float(stats.telegram_effective_voters)
    telegram_score = float(stats.telegram_overall_avg or 0.0)
    site_composite = calc_overall_score(stats)
    telegram_weight = telegram_voters * TELEGRAM_WEIGHT

    if site_reviews > 0 and telegram_voters > 0:
        display = ((site_composite * site_reviews) + (telegram_score * telegram_weight)) / (site_reviews + telegram_weight)
    elif site_reviews > 0:
        display = site_composite
    elif telegram_voters > 0:
        display = telegram_score
    else:
        display = 0.0
    return clamp_score(display)


# ─────────────────────────────────────────────────────────────
#  Background QThread Workers
# ─────────────────────────────────────────────────────────────

def _run_worker(worker: "_Worker", on_success: Any, on_error: Any, manager_ref: "ProfessorManager") -> None:
    """Start a worker while keeping it referenced until it finishes.

    A running QThread whose Python wrapper gets garbage-collected aborts the
    whole process ("QThread: Destroyed while thread is still running"), so
    every active worker is held in a set and released only on completion.
    """
    worker.finished_signal.connect(on_success)
    worker.error_signal.connect(on_error)
    manager_ref._active_workers.add(worker)

    def _release():
        manager_ref._active_workers.discard(worker)
        worker.deleteLater()

    worker.finished.connect(_release)
    worker.start()


class _Worker(QThread):
    """Generic one-call worker wrapping a client callable."""

    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, fn: Callable[[], Any], parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished_signal.emit(self._fn())
        except GolestoonNetworkError as err:
            self.error_signal.emit(err.message)
        except Exception as err:  # noqa: BLE001 — worker boundary
            logger.exception("Professor worker failed")
            self.error_signal.emit(str(err))


# ─────────────────────────────────────────────────────────────
#  ProfessorManager
# ─────────────────────────────────────────────────────────────

class ProfessorManager(QObject):
    """
    Manager bridging PyQt5 UI views with ProfessorClient:
    caching, async thread execution, and score math.
    """

    def __init__(self, client: ProfessorClient, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: ProfessorClient = client
        self._cache_stats: Dict[str, ProfessorStats] = {}
        self._active_workers: Set["_Worker"] = set()

    @property
    def client(self) -> ProfessorClient:
        """Get underlying network client."""
        return self._client

    # ── Stats & search ───────────────────────────────────────
    def fetch_stats(
        self,
        department: str,
        instructor: str,
        on_success: Any,
        on_error: Any,
        force_refresh: bool = False,
    ) -> None:
        """Fetch professor aggregated stats asynchronously (cached)."""
        cache_key = f"{department.strip()}:::{instructor.strip()}"
        if not force_refresh and cache_key in self._cache_stats:
            on_success(self._cache_stats[cache_key])
            return

        def _job() -> Optional[ProfessorStats]:
            return self._client.get_stats(department=department, instructor=instructor)

        def _handle_success(stats: Optional[ProfessorStats]):
            if stats:
                self._cache_stats[cache_key] = stats
            on_success(stats)

        _run_worker(_Worker(_job), _handle_success, on_error, self)

    def search_directory(self, query: str, department: str, on_success: Any, on_error: Any) -> None:
        """
        Search instructors through the approved directory (web InstructorSearch parity):
        fetches the (optionally department-filtered) directory and filters by name locally.
        The full directory (~hundreds of rows) is cached client-side so switching
        departments is instant.
        """
        def _job() -> List[Dict[str, Any]]:
            rows = self._client.get_approved_instructors(department=department)
            q = (query or "").strip()
            if not q:
                return rows[:1000]  # effectively the whole directory
            # Normalize Persian variants (ي→ی, ك→ک) for tolerant matching
            def norm(s: str) -> str:
                return (s or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ").strip()
            qn = norm(q)
            return [r for r in rows if qn in norm(str(r.get("instructor_name", "")))][:1000]

        _run_worker(_Worker(_job), on_success, on_error, self)

    # ── Lists & leaderboards ─────────────────────────────────
    def fetch_departments(self, on_success: Any, on_error: Any) -> None:
        _run_worker(_Worker(lambda: self._client.get_departments()), on_success, on_error, self)

    def fetch_summary(self, on_success: Any, on_error: Any) -> None:
        _run_worker(_Worker(lambda: self._client.get_summary()), on_success, on_error, self)

    def fetch_popular(self, kind: str, department: str, on_success: Any, on_error: Any, limit: int = 6) -> None:
        _run_worker(
            _Worker(lambda: self._client.get_popular(kind=kind, department=department, limit=limit)),
            on_success, on_error, self,
        )

    def compare_professors(self, instructors: List[Dict[str, str]], on_success: Any, on_error: Any) -> None:
        """Fetch stats for multiple instructors side-by-side."""
        _run_worker(
            _Worker(lambda: self._client.compare_professors(instructors)),
            on_success, on_error, self,
        )

    # ── My review lifecycle ──────────────────────────────────
    def fetch_my_review(self, department: str, instructor: str, on_success: Any, on_error: Any) -> None:
        _run_worker(
            _Worker(lambda: self._client.get_my_review(department=department, instructor=instructor)),
            on_success, on_error, self,
        )

    def submit_review(
        self,
        department_name: str,
        instructor_name: str,
        teaching_score: int,
        assignments_score: int,
        grading_score: int,
        exam_difficulty_score: int,
        attendance_sensitivity: str,
        on_success: Any,
        on_error: Any,
    ) -> None:
        _run_worker(
            _Worker(lambda: self._client.submit_review(
                department_name=department_name,
                instructor_name=instructor_name,
                teaching_score=teaching_score,
                assignments_score=assignments_score,
                grading_score=grading_score,
                exam_difficulty_score=exam_difficulty_score,
                attendance_sensitivity=attendance_sensitivity,
            )),
            on_success, on_error, self,
        )

    def delete_my_review(self, department: str, instructor: str, on_success: Any, on_error: Any) -> None:
        _run_worker(
            _Worker(lambda: self._client.delete_my_review(department=department, instructor=instructor)),
            on_success, on_error, self,
        )

    # ── Instructor suggestions ───────────────────────────────
    def check_instructor_exists(self, department_name: str, instructor_name: str, on_success: Any, on_error: Any) -> None:
        _run_worker(
            _Worker(lambda: self._client.instructor_exists(
                department_name=department_name, instructor_name=instructor_name)),
            on_success, on_error, self,
        )

    def suggest_instructor(self, department_name: str, instructor_name: str, on_success: Any, on_error: Any) -> None:
        _run_worker(
            _Worker(lambda: self._client.suggest_instructor(
                department_name=department_name, instructor_name=instructor_name)),
            on_success, on_error, self,
        )

    def track_view(self, department: str, instructor: str) -> None:
        """Fire-and-forget view counter (no worker needed, swallows errors)."""
        try:
            self._client.track_view(department=department, instructor=instructor)
        except Exception:  # noqa: BLE001 — analytics only
            pass
