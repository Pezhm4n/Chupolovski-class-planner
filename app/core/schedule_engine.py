# -*- coding: utf-8 -*-
"""
Golestoon Master Scheduling & Exam Conflict Engine.

This module provides the ScheduleEngine, ConflictEngine, ExamConflictEngine,
and CombinationGenerator matching Golestoon Web algorithms.

Architecture Layer: Layer 4 (Application Logic & Engine)
Dependencies: Python Standard Library (`itertools`, `typing`, `logging`), `PyQt5.QtCore` (QThread, pyqtSignal).
"""

import logging
import itertools
from typing import List, Dict, Any, Optional, Tuple
from PyQt5.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger("golestoon.schedule.engine")


def time_to_minutes(time_val: Any) -> Optional[int]:
    """
    Convert a time string ("HH:MM" or "HH") or number to minutes since midnight.

    Args:
        time_val: Hour integer/float or "HH:MM" string.

    Returns:
        Optional[int]: Minutes since midnight, or None if invalid.
    """
    if time_val is None:
        return None

    if isinstance(time_val, (int, float)):
        if time_val <= 24:
            return int(time_val * 60)
        return int(time_val)

    raw = str(time_val).strip()
    if not raw:
        return None

    parts = raw.split(":")
    if len(parts) == 2:
        try:
            h, m = int(parts[0]), int(parts[1])
            return h * 60 + m
        except ValueError:
            return None

    try:
        h = float(raw)
        return int(h * 60)
    except ValueError:
        return None


def check_time_overlap(start1: int, end1: int, start2: int, end2: int) -> bool:
    """
    Check if two time intervals [start1, end1) and [start2, end2) overlap.

    Returns:
        bool: True if intervals overlap.
    """
    return not (end1 <= start2 or end2 <= start1)


def week_types_conflict(type1: str, type2: str) -> bool:
    """
    Check if week parity types conflict ('both', 'odd', 'even').

    Returns:
        bool: True if conflicting.
    """
    if type1 == "both" or type2 == "both":
        return True
    return type1 == type2


# ─────────────────────────────────────────────────────────────
#  Conflict Detection Engines
# ─────────────────────────────────────────────────────────────

class ConflictEngine:
    """Class session time and week parity conflict detection engine."""

    @staticmethod
    def has_time_conflict(current_schedule: List[Dict[str, Any]], candidate_course: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check if candidate course conflicts in class time with any course in current schedule.

        Returns:
            Tuple[bool, Optional[str]]: (has_conflict, conflicting_course_name)
        """
        cand_sessions = candidate_course.get("sessions") or candidate_course.get("time_slots") or []
        for existing in current_schedule:
            exist_sessions = existing.get("sessions") or existing.get("time_slots") or []

            for ns in cand_sessions:
                n_day = ns.get("day") or ns.get("day_index")
                for es in exist_sessions:
                    e_day = es.get("day") or es.get("day_index")
                    if n_day != e_day:
                        continue

                    s1 = time_to_minutes(ns.get("start") or ns.get("startTime"))
                    e1 = time_to_minutes(ns.get("end") or ns.get("endTime"))
                    s2 = time_to_minutes(es.get("start") or es.get("startTime"))
                    e2 = time_to_minutes(es.get("end") or es.get("endTime"))

                    if s1 is None or e1 is None or s2 is None or e2 is None:
                        continue

                    if check_time_overlap(s1, e1, s2, e2):
                        w1 = ns.get("weekType") or ns.get("week_type") or "both"
                        w2 = es.get("weekType") or es.get("week_type") or "both"
                        if week_types_conflict(w1, w2):
                            cand_name = existing.get("name") or existing.get("title") or "درس دیگر"
                            return True, cand_name

        return False, None


class ExamConflictEngine:
    """Exam schedule conflict and distance analysis engine."""

    @staticmethod
    def has_exam_conflict(current_schedule: List[Dict[str, Any]], candidate_course: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check if candidate course conflicts in exam date & time with any course in current schedule.

        Returns:
            Tuple[bool, Optional[str]]: (has_conflict, conflicting_course_name)
        """
        c_date = candidate_course.get("examDate") or candidate_course.get("exam_date")
        c_time = candidate_course.get("examTime") or candidate_course.get("exam_time")

        if not c_date or not c_time or c_time == "اعلام نشده":
            return False, None

        for existing in current_schedule:
            e_date = existing.get("examDate") or existing.get("exam_date")
            e_time = existing.get("examTime") or existing.get("exam_time")

            if not e_date or not e_time or e_time == "اعلام نشده":
                continue

            if c_date == e_date and c_time == e_time:
                exist_name = existing.get("name") or existing.get("title") or "درس دیگر"
                return True, exist_name

        return False, None

    @staticmethod
    def analyze_exam_distances(courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze time distances between exams and categorize conflict severity (Critical, Warning, Safe).

        Returns:
            List[Dict[str, Any]]: List of exam pairs with distance and severity level.
        """
        results: List[Dict[str, Any]] = []
        exam_courses = [c for c in courses if (c.get("examDate") or c.get("exam_date"))]

        for c1, c2 in itertools.combinations(exam_courses, 2):
            d1 = c1.get("examDate") or c1.get("exam_date")
            d2 = c2.get("examDate") or c2.get("exam_date")
            t1 = c1.get("examTime") or c1.get("exam_time")
            t2 = c2.get("examTime") or c2.get("exam_time")

            if d1 == d2:
                if t1 == t2:
                    severity = "Critical"  # Same day, same time
                    desc = "تداخل کامل زمان امتحان در یک روز و یک ساعت!"
                else:
                    severity = "Warning"   # Same day, different time
                    desc = "دو امتحان در یک روز با فاصله چند ساعت"
            else:
                severity = "Safe"
                desc = "زمان امتحانات مجزا در روزهای متفاوت"

            results.append({
                "course1": c1.get("name") or c1.get("title") or "درس ۱",
                "course2": c2.get("name") or c2.get("title") or "درس ۲",
                "date1": d1,
                "date2": d2,
                "severity": severity,
                "description": desc,
            })

        return results


# ─────────────────────────────────────────────────────────────
#  Combinatorial Schedule Generator Engine
# ─────────────────────────────────────────────────────────────

class CombinationGenerator:
    """Generate all valid, non-conflicting schedule combinations from course groups."""

    @staticmethod
    def generate_combinations(grouped_courses: List[List[Dict[str, Any]]], max_results: int = 50) -> List[List[Dict[str, Any]]]:
        """
        Generate list of non-conflicting schedule choices across course groups.

        Args:
            grouped_courses: List of course groups (e.g. [[Math Group 1, Math Group 2], [Physics Group 1]]).
            max_results: Cap on max combinations to generate.

        Returns:
            List[List[Dict[str, Any]]]: List of valid schedule combinations.
        """
        valid_schedules: List[List[Dict[str, Any]]] = []
        if not grouped_courses:
            return valid_schedules

        for product in itertools.product(*grouped_courses):
            current_schedule: List[Dict[str, Any]] = []
            is_valid = True

            for candidate in product:
                has_t_conflict, _ = ConflictEngine.has_time_conflict(current_schedule, candidate)
                has_e_conflict, _ = ExamConflictEngine.has_exam_conflict(current_schedule, candidate)

                if has_t_conflict or has_e_conflict:
                    is_valid = False
                    break

                current_schedule.append(candidate)

            if is_valid:
                valid_schedules.append(current_schedule)
                if len(valid_schedules) >= max_results:
                    break

        return valid_schedules


# ─────────────────────────────────────────────────────────────
#  Background QThread Worker
# ─────────────────────────────────────────────────────────────

class GenerateCombinationsWorker(QThread):
    """Background worker thread to run combinatorial schedule generation without UI freeze."""

    finished_signal = pyqtSignal(list)  # List[List[Dict[str, Any]]]
    error_signal = pyqtSignal(str)

    def __init__(self, grouped_courses: List[List[Dict[str, Any]]], max_results: int = 50, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._grouped_courses: List[List[Dict[str, Any]]] = grouped_courses
        self._max_results: int = max_results

    def run(self) -> None:
        try:
            results = CombinationGenerator.generate_combinations(self._grouped_courses, max_results=self._max_results)
            self.finished_signal.emit(results)
        except Exception as err:
            self.error_signal.emit(str(err))
