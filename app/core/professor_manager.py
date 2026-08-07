# -*- coding: utf-8 -*-
"""
Golestoon Professor Reviews Manager (ViewModel & Business Logic Layer).

This module provides the ProfessorManager handling business logic, background QThread worker tasks,
caching, score formulas, and state management for professor ratings and comparisons.

Architecture Layer: Layer 4 (Application Logic & Manager)
Dependencies: `ProfessorClient`, `ProfessorStatsModel`, `ProfessorReviewModel`, `PyQt5.QtCore` (QThread, pyqtSignal).
"""

import logging
from typing import List, Dict, Any, Optional
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from app.core.network.clients.professor_client import ProfessorClient
from app.core.network.models import ProfessorStatsModel, ProfessorReviewModel
from app.core.network.exceptions import GolestoonNetworkError

logger = logging.getLogger("golestoon.professors.manager")

TELEGRAM_WEIGHT: float = 0.4


def clamp_score(val: float) -> float:
    """Clamp score value between 0.0 and 100.0."""
    return max(0.0, min(100.0, float(val)))


def get_score_color_hex(score: float) -> str:
    """Get color hex code for score value (Green >= 80, Blue >= 60, Orange >= 40, Red < 40)."""
    score = clamp_score(score)
    if score >= 80.0:
        return "#16a34a"  # Green
    elif score >= 60.0:
        return "#3b82f6"  # Blue
    elif score >= 40.0:
        return "#f59e0b"  # Amber / Orange
    else:
        return "#ef4444"  # Red


def get_inverse_score_color_hex(difficulty_score: float) -> str:
    """Get color hex code for difficulty (Higher difficulty = Red, Lower difficulty = Green)."""
    difficulty_score = clamp_score(difficulty_score)
    if difficulty_score >= 80.0:
        return "#ef4444"  # Red (Very Hard)
    elif difficulty_score >= 60.0:
        return "#f59e0b"  # Orange (Hard)
    elif difficulty_score >= 40.0:
        return "#3b82f6"  # Blue (Normal)
    else:
        return "#16a34a"  # Green (Easy)


def calc_overall_score(stats: Optional[ProfessorStatsModel]) -> float:
    """
    Compute site composite overall score matching web formula:
    Overall = (Teaching * 0.30) + (Grading * 0.40) + ((100 - ExamDifficulty) * 0.30)
    """
    if not stats:
        return 0.0
    exam_ease = clamp_score(100.0 - stats.exam_difficulty_score)
    overall = (
        (stats.teaching_score * 0.30) +
        (stats.grading_score * 0.40) +
        (exam_ease * 0.30)
    )
    return clamp_score(overall)


def calc_display_score(stats: Optional[ProfessorStatsModel]) -> float:
    """
    Compute weighted display score combining site reviews and Telegram voters matching web formula.
    """
    if not stats:
        return 0.0

    site_reviews = float(stats.total_reviews)
    telegram_voters = float(stats.telegram_effective_voters)
    telegram_score = float(stats.telegram_overall_avg or 0.0)
    site_composite = calc_overall_score(stats)
    telegram_weight = telegram_voters * TELEGRAM_WEIGHT

    if site_reviews > 0 and telegram_voters > 0:
        display_score = ((site_composite * site_reviews) + (telegram_score * telegram_weight)) / (site_reviews + telegram_weight)
    elif site_reviews > 0:
        display_score = site_composite
    elif telegram_voters > 0:
        display_score = telegram_score
    else:
        display_score = 0.0

    return clamp_score(display_score)


# ─────────────────────────────────────────────────────────────
#  Background QThread Workers
# ─────────────────────────────────────────────────────────────

class FetchStatsWorker(QThread):
    """Background worker thread to fetch professor stats without freezing UI."""

    finished_signal = pyqtSignal(object)  # ProfessorStatsModel or None
    error_signal = pyqtSignal(str)

    def __init__(self, client: ProfessorClient, department: str, instructor: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: ProfessorClient = client
        self._department: str = department
        self._instructor: str = instructor

    def run(self) -> None:
        try:
            stats = self._client.get_stats(department=self._department, instructor=self._instructor)
            self.finished_signal.emit(stats)
        except GolestoonNetworkError as err:
            self.error_signal.emit(err.message)
        except Exception as err:
            self.error_signal.emit(str(err))


class SearchProfessorsWorker(QThread):
    """Background worker thread to search professors."""

    finished_signal = pyqtSignal(list)  # List[ProfessorStatsModel]
    error_signal = pyqtSignal(str)

    def __init__(self, client: ProfessorClient, query: str, department: str = "", parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: ProfessorClient = client
        self._query: str = query
        self._department: str = department

    def run(self) -> None:
        try:
            results = self._client.search_professor(query=self._query, department=self._department)
            self.finished_signal.emit(results)
        except GolestoonNetworkError as err:
            self.error_signal.emit(err.message)
        except Exception as err:
            self.error_signal.emit(str(err))


class SubmitReviewWorker(QThread):
    """Background worker thread to submit professor review."""

    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, client: ProfessorClient, review_data: dict, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: ProfessorClient = client
        self._review_data: dict = review_data

    def run(self) -> None:
        try:
            res = self._client.submit_review(review_data=self._review_data)
            self.finished_signal.emit(res)
        except GolestoonNetworkError as err:
            self.error_signal.emit(err.message)
        except Exception as err:
            self.error_signal.emit(str(err))


# ─────────────────────────────────────────────────────────────
#  ProfessorManager Manager Class
# ─────────────────────────────────────────────────────────────

class ProfessorManager(QObject):
    """
    Manager and ViewModel bridging PyQt5 UI views with ProfessorClient network client.
    Handles caching, asynchronous thread execution, and math formulas.
    """

    def __init__(self, client: ProfessorClient, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._client: ProfessorClient = client
        self._cache_stats: Dict[str, ProfessorStatsModel] = {}
        self._active_worker: Optional[QThread] = None

    @property
    def client(self) -> ProfessorClient:
        """Get underlying network client."""
        return self._client

    def fetch_stats(
        self,
        department: str,
        instructor: str,
        on_success: Any,
        on_error: Any,
        force_refresh: bool = False
    ) -> None:
        """Fetch professor stats asynchronously."""
        cache_key = f"{department.strip()}:::{instructor.strip()}"
        if not force_refresh and cache_key in self._cache_stats:
            on_success(self._cache_stats[cache_key])
            return

        worker = FetchStatsWorker(client=self._client, department=department, instructor=instructor)

        def _handle_success(stats: Optional[ProfessorStatsModel]):
            if stats:
                self._cache_stats[cache_key] = stats
            on_success(stats)

        worker.finished_signal.connect(_handle_success)
        worker.error_signal.connect(on_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

    def search(self, query: str, department: str, on_success: Any, on_error: Any) -> None:
        """Search professors asynchronously."""
        worker = SearchProfessorsWorker(client=self._client, query=query, department=department)
        worker.finished_signal.connect(on_success)
        worker.error_signal.connect(on_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

    def submit_review(self, review_data: dict, on_success: Any, on_error: Any) -> None:
        """Submit review asynchronously."""
        worker = SubmitReviewWorker(client=self._client, review_data=review_data)
        worker.finished_signal.connect(on_success)
        worker.error_signal.connect(on_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker
