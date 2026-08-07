# -*- coding: utf-8 -*-
"""
Golestoon Professor Reviews Network Client.

This module provides the ProfessorClient for fetching professor stats, submitting pseudonymous ratings,
and executing side-by-side professor comparisons (`/api/professor-reviews/*`).

Architecture Layer: Layer 2 (Modular Network Sub-Clients)
Dependencies: `BaseClient`, `ProfessorStatsModel`, `ProfessorReviewModel`.
"""

from typing import List, Dict, Any, Optional
from app.core.network.clients.base_client import BaseClient
from app.core.network.models import ProfessorStatsModel, ProfessorReviewModel


class ProfessorClient(BaseClient):
    """
    Sub-client managing professor ratings, stats, reviews, and comparison matrix.
    """

    def get_stats(self, department: str, instructor: str) -> Optional[ProfessorStatsModel]:
        """
        Fetch aggregated review statistics for a specific professor.

        Args:
            department (str): Department name.
            instructor (str): Instructor full name.

        Returns:
            Optional[ProfessorStatsModel]: Stats model if found, None otherwise.
        """
        params = {"department_name": department, "instructor_name": instructor}
        res = self._get(self.routes.PROFESSORS.STATS, params=params)
        if not res or "stats" not in res and not res.get("instructor_name"):
            return None
        stats_data = res.get("stats", res)
        return self._parse_stats_model(stats_data)

    def search_professor(self, query: str, department: str = "") -> List[ProfessorStatsModel]:
        """
        Search for professors by name or department.

        Args:
            query (str): Search string.
            department (str): Optional department filter.

        Returns:
            List[ProfessorStatsModel]: Matching professor stats models list.
        """
        params = {"q": query, "department": department}
        res = self._get(self.routes.PROFESSORS.STATS, params=params)
        results = res.get("results", res if isinstance(res, list) else [])
        return [self._parse_stats_model(item) for item in results]

    def get_reviews(self, instructor_name: str, department_name: str) -> List[ProfessorReviewModel]:
        """
        Fetch pseudonymous reviews list for an instructor.

        Args:
            instructor_name (str): Instructor name.
            department_name (str): Department name.

        Returns:
            List[ProfessorReviewModel]: List of review models.
        """
        params = {"instructor_name": instructor_name, "department_name": department_name}
        res = self._get(self.routes.PROFESSORS.MY_REVIEW, params=params)
        reviews_list = res.get("reviews", [res] if "reviewer_hash" in res else [])
        return [self._parse_review_model(r) for r in reviews_list if r]

    def compare_professors(self, instructors: List[Dict[str, str]]) -> List[ProfessorStatsModel]:
        """
        Fetch side-by-side stats comparison for up to 3 professors.

        Args:
            instructors (List[Dict[str, str]]): List of dicts with 'department_name' and 'instructor_name'.

        Returns:
            List[ProfessorStatsModel]: Stats models list matching requested instructors.
        """
        results: List[ProfessorStatsModel] = []
        for item in instructors[:3]:
            dept = item.get("department_name", "")
            inst = item.get("instructor_name", "")
            if inst:
                stat = self.get_stats(department=dept, instructor=inst)
                if stat:
                    results.append(stat)
        return results

    def get_popular_professors(self) -> List[ProfessorStatsModel]:
        """
        Fetch top-rated and most reviewed popular professors list.

        Returns:
            List[ProfessorStatsModel]: Popular professor stats models.
        """
        res = self._get(self.routes.PROFESSORS.STATS, params={"popular": "true"})
        results = res.get("results", res if isinstance(res, list) else [])
        return [self._parse_stats_model(item) for item in results]

    def submit_review(self, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit or update pseudonymous review rating for an instructor.

        Args:
            review_data (Dict[str, Any]): Rating scores dict.

        Returns:
            Dict[str, Any]: API confirmation response.
        """
        return self._post(self.routes.PROFESSORS.SUBMIT_REVIEW, data=review_data)

    def _parse_stats_model(self, data: Dict[str, Any]) -> ProfessorStatsModel:
        """Helper to parse API dict into ProfessorStatsModel."""
        return ProfessorStatsModel(
            department_name=str(data.get("department_name", "")),
            instructor_name=str(data.get("instructor_name", "")),
            teaching_score=float(data.get("teaching_score", 0.0)),
            ethics_score=float(data.get("ethics_score", 0.0)),
            assignments_score=float(data.get("assignments_score", 0.0)),
            grading_score=float(data.get("grading_score", 0.0)),
            overall_score=float(data.get("overall_score", 0.0)),
            exam_difficulty_score=float(data.get("exam_difficulty_score", 0.0)),
            exam_source_score=float(data.get("exam_source_score", 0.0)),
            interaction_score=float(data.get("interaction_score", 0.0)),
            attendance_sensitivity=str(data.get("attendance_sensitivity", "normal")),
            time_sensitivity=str(data.get("time_sensitivity", "normal")),
            total_reviews=int(data.get("total_reviews", 0)),
            total_voters=int(data.get("total_voters", 0)),
            telegram_has_data=bool(data.get("telegram_has_data", False)),
            telegram_overall_avg=data.get("telegram_overall_avg"),
            telegram_effective_voters=int(data.get("telegram_effective_voters", 0)),
        )

    def _parse_review_model(self, data: Dict[str, Any]) -> ProfessorReviewModel:
        """Helper to parse API dict into ProfessorReviewModel."""
        return ProfessorReviewModel(
            reviewer_hash=str(data.get("reviewer_hash", "")),
            department_name=str(data.get("department_name", "")),
            instructor_name=str(data.get("instructor_name", "")),
            teaching_score=float(data.get("teaching_score", 0.0)),
            assignments_score=float(data.get("assignments_score", 0.0)),
            grading_score=float(data.get("grading_score", 0.0)),
            exam_difficulty_score=float(data.get("exam_difficulty_score", 0.0)),
            attendance_sensitivity=str(data.get("attendance_sensitivity", "normal")),
            updated_at=str(data.get("updated_at", "")),
        )
