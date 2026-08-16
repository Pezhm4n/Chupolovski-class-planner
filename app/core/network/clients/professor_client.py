# -*- coding: utf-8 -*-
"""
Golestoon Professor Reviews Network Client.

Implements the exact professor-review contracts of `golestan-web/server/index.ts`:

  READ  GET  /api/professor-reviews/stats?department=X&instructor=Y
        → {stats: row|null} where row aggregates use **`*_avg`** fields
          (teaching_avg, assignments_avg, grading_avg, exam_difficulty_avg,
           overall_avg, ethics_avg, …) + total_reviews/total_voters/telegram_*/view_count.
  WRITE POST /api/professor-reviews  (auth)
        body {department_name, instructor_name, teaching_score, assignments_score,
              grading_score, exam_difficulty_score, attendance_sensitivity}
        — submission uses **`*_score`** fields (individual 0-100 scores), NOT *_avg.
  MY    GET/DELETE /api/professor-reviews/my-review?department&instructor (auth)
  LIST  GET  /api/professor-reviews/departments        → {departments: [..]}
        GET  /api/professor-reviews/summary  (auth)    → {departmentCount, instructorCount,
                                                          userReviewCount, hasContributed}
        GET  /api/professor-reviews/popular-by-{views|score|voters} → {instructors: [..]}
  DIR   GET  /api/instructors/approved?department      → {instructors: [..]}
        GET  /api/instructors/exists?department_name&instructor_name → {exists, source}
        POST /api/instructors/suggest (auth)           → {success, suggestion}

Architecture Layer: Layer 2 (Modular Network Sub-Clients)
Dependencies: `BaseClient`.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.network.clients.base_client import BaseClient

logger = logging.getLogger("golestoon.network.professor_client")

ATTENDANCE_MODES = ("very", "normal", "not_important")


@dataclass
class ProfessorStats:
    """Aggregated stats for one instructor (server `professor_stats` row, `*_avg` fields)."""

    department_name: str = ""
    instructor_name: str = ""
    teaching_avg: float = 0.0
    assignments_avg: float = 0.0
    grading_avg: float = 0.0
    exam_difficulty_avg: float = 0.0
    overall_avg: Optional[float] = None
    total_reviews: int = 0
    total_voters: int = 0
    view_count: int = 0
    telegram_has_data: bool = False
    telegram_overall_avg: Optional[float] = None
    telegram_effective_voters: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def computed_overall(self) -> float:
        """Mirror the web formula: 0.30*teaching + 0.40*grading + 0.30*(100-exam)."""
        if self.overall_avg is not None:
            return float(self.overall_avg)
        return round(
            0.30 * self.teaching_avg
            + 0.40 * self.grading_avg
            + 0.30 * (100.0 - self.exam_difficulty_avg),
            2,
        )


@dataclass
class ProfessorReview:
    """The current user's own review for an instructor (raw `*_score` fields)."""

    department_name: str = ""
    instructor_name: str = ""
    teaching_score: int = 50
    assignments_score: int = 50
    grading_score: int = 50
    exam_difficulty_score: int = 50
    attendance_sensitivity: str = "normal"
    updated_at: str = ""


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class ProfessorClient(BaseClient):
    """
    Sub-client managing professor ratings, stats, reviews, comparisons,
    leaderboards and the instructor directory.
    """

    # ── Aggregated stats ─────────────────────────────────────
    def get_stats(self, department: str, instructor: str) -> Optional[ProfessorStats]:
        """
        Fetch aggregated review statistics for a specific instructor.

        Query params are `department` and `instructor` (NOT *_name — that is
        only the POST body / instructors/exists convention).
        """
        params = {"department": department, "instructor": instructor}
        res = self._get(self.routes.PROFESSORS.STATS, params=params)
        stats_raw = res.get("stats") if isinstance(res, dict) else None
        if not stats_raw:
            return None
        return ProfessorStats(
            department_name=str(stats_raw.get("department_name", "")),
            instructor_name=str(stats_raw.get("instructor_name", "")),
            teaching_avg=_to_float(stats_raw.get("teaching_avg")),
            assignments_avg=_to_float(stats_raw.get("assignments_avg")),
            grading_avg=_to_float(stats_raw.get("grading_avg")),
            exam_difficulty_avg=_to_float(stats_raw.get("exam_difficulty_avg")),
            overall_avg=(
                _to_float(stats_raw.get("overall_avg"))
                if stats_raw.get("overall_avg") is not None else None
            ),
            total_reviews=_to_int(stats_raw.get("total_reviews")),
            total_voters=_to_int(stats_raw.get("total_voters")),
            view_count=_to_int(stats_raw.get("view_count")),
            telegram_has_data=bool(stats_raw.get("telegram_has_data", False)),
            telegram_overall_avg=(
                _to_float(stats_raw.get("telegram_overall_avg"))
                if stats_raw.get("telegram_overall_avg") is not None else None
            ),
            telegram_effective_voters=_to_int(stats_raw.get("telegram_effective_voters")),
            raw=stats_raw,
        )

    def compare_professors(self, instructors: List[Dict[str, str]]) -> List[ProfessorStats]:
        """Fetch side-by-side stats for up to 3 instructors."""
        results: List[ProfessorStats] = []
        for item in instructors[:3]:
            dept = item.get("department", item.get("department_name", ""))
            inst = item.get("instructor", item.get("instructor_name", ""))
            if inst:
                stat = self.get_stats(department=dept, instructor=inst)
                if stat:
                    results.append(stat)
        return results

    # ── My review (write-path) ───────────────────────────────
    def get_my_review(self, department: str, instructor: str) -> Optional[ProfessorReview]:
        """Fetch the current user's own review (auth required)."""
        params = {"department": department, "instructor": instructor}
        res = self._get(self.routes.PROFESSORS.MY_REVIEW, params=params)
        review_raw = res.get("review") if isinstance(res, dict) else None
        if not review_raw:
            return None
        return ProfessorReview(
            department_name=str(review_raw.get("department_name", "")),
            instructor_name=str(review_raw.get("instructor_name", "")),
            teaching_score=_to_int(review_raw.get("teaching_score"), 50),
            assignments_score=_to_int(review_raw.get("assignments_score"), 50),
            grading_score=_to_int(review_raw.get("grading_score"), 50),
            exam_difficulty_score=_to_int(review_raw.get("exam_difficulty_score"), 50),
            attendance_sensitivity=str(review_raw.get("attendance_sensitivity", "normal")),
            updated_at=str(review_raw.get("updated_at", "")),
        )

    def submit_review(
        self,
        department_name: str,
        instructor_name: str,
        teaching_score: int,
        assignments_score: int,
        grading_score: int,
        exam_difficulty_score: int,
        attendance_sensitivity: str = "normal",
    ) -> Dict[str, Any]:
        """
        Submit or update the user's pseudonymous review (auth required).

        Body uses `*_score` fields (individual 0-100), unlike stats reading.
        Returns {hasContributed, reviewCount, …}.
        """
        if attendance_sensitivity not in ATTENDANCE_MODES:
            attendance_sensitivity = "normal"
        payload = {
            "department_name": department_name,
            "instructor_name": instructor_name,
            "teaching_score": int(teaching_score),
            "assignments_score": int(assignments_score),
            "grading_score": int(grading_score),
            "exam_difficulty_score": int(exam_difficulty_score),
            "attendance_sensitivity": attendance_sensitivity,
        }
        return self._post(self.routes.PROFESSORS.SUBMIT_REVIEW, data=payload)

    def delete_my_review(self, department: str, instructor: str) -> Dict[str, Any]:
        """Delete the user's own review and recompute stats (auth required)."""
        params = {"department": department, "instructor": instructor}
        return self._delete(self.routes.PROFESSORS.MY_REVIEW, params=params)

    # ── Lists & leaderboards ─────────────────────────────────
    def get_departments(self) -> List[str]:
        """Distinct department list (canonicalized server-side)."""
        res = self._get(self.routes.PROFESSORS.DEPARTMENTS)
        departments = res.get("departments", []) if isinstance(res, dict) else []
        return [str(d) for d in departments if d]

    def get_summary(self) -> Dict[str, Any]:
        """Auth'd summary: departmentCount / instructorCount / userReviewCount / hasContributed."""
        return self._get(self.routes.PROFESSORS.SUMMARY)

    def get_popular(self, kind: str = "score", department: str = "", limit: int = 6) -> List[ProfessorStats]:
        """
        Leaderboard rows: kind ∈ {'views', 'score', 'voters'}.
        Response rows already carry a merged `display_score` where applicable.
        """
        kind = kind if kind in ("views", "score", "voters") else "score"
        endpoint = {
            "views": self.routes.PROFESSORS.POPULAR_BY_VIEWS,
            "score": self.routes.PROFESSORS.POPULAR_BY_SCORE,
            "voters": self.routes.PROFESSORS.POPULAR_BY_VOTERS,
        }[kind]
        params: Dict[str, Any] = {"limit": int(limit)}
        if department:
            params["department"] = department
        res = self._get(endpoint, params=params)
        rows = res.get("instructors", []) if isinstance(res, dict) else []
        results: List[ProfessorStats] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            results.append(ProfessorStats(
                department_name=str(row.get("department_name", "")),
                instructor_name=str(row.get("instructor_name", "")),
                teaching_avg=_to_float(row.get("teaching_avg")),
                assignments_avg=_to_float(row.get("assignments_avg")),
                grading_avg=_to_float(row.get("grading_avg")),
                exam_difficulty_avg=_to_float(row.get("exam_difficulty_avg")),
                overall_avg=(
                    _to_float(row.get("display_score", row.get("overall_avg")))
                    if row.get("display_score", row.get("overall_avg")) is not None else None
                ),
                total_reviews=_to_int(row.get("total_reviews")),
                total_voters=_to_int(row.get("total_voters")),
                view_count=_to_int(row.get("view_count")),
                telegram_has_data=bool(row.get("telegram_has_data", False)),
                telegram_overall_avg=(
                    _to_float(row.get("telegram_overall_avg"))
                    if row.get("telegram_overall_avg") is not None else None
                ),
                telegram_effective_voters=_to_int(row.get("telegram_effective_voters")),
                raw=row,
            ))
        return results

    def track_view(self, department: str, instructor: str) -> None:
        """Fire-and-forget view counter increment (errors swallowed)."""
        try:
            self._post(self.routes.PROFESSORS.TRACK_VIEW,
                       data={"department_name": department, "instructor_name": instructor})
        except Exception as err:  # noqa: BLE001 — analytics must never break UI
            logger.debug("track_view failed silently: %s", err)

    # ── Instructor directory ─────────────────────────────────
    def get_approved_instructors(self, department: str = "") -> List[Dict[str, Any]]:
        """Approved instructor directory rows (optionally per department)."""
        params = {"department": department} if department else None
        res = self._get(self.routes.PROFESSORS.APPROVED_INSTRUCTORS, params=params)
        rows = res.get("instructors", []) if isinstance(res, dict) else []
        return [r for r in rows if isinstance(r, dict)]

    def instructor_exists(self, department_name: str, instructor_name: str) -> Dict[str, Any]:
        """Duplicate check → {exists: bool, source: 'approved'|'pending'|'stats'|None, message}."""
        params = {"department_name": department_name, "instructor_name": instructor_name}
        return self._get(self.routes.PROFESSORS.INSTRUCTOR_EXISTS, params=params)

    def suggest_instructor(self, department_name: str, instructor_name: str) -> Dict[str, Any]:
        """Suggest a new instructor for admin approval (auth required)."""
        payload = {"department_name": department_name, "instructor_name": instructor_name}
        return self._post(self.routes.PROFESSORS.SUGGEST_INSTRUCTOR, data=payload)
