# -*- coding: utf-8 -*-
"""
Course Details Dialog.

Beautiful, complete, theme-aware course information card shown when the user
clicks a placed course in the weekly schedule grid — the desktop counterpart
of the web's course popover with schedule, capacity and exam details.

Architecture Layer: Layer 5 (Presentation & UI)
"""

from typing import Any, Dict, Optional

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt

from app.core.config import COURSES, get_days
from app.core.theme_manager import theme_manager


class CourseDetailsDialog(QtWidgets.QDialog):
    """Rich read-only details card for a single course."""

    def __init__(
        self,
        course_key: str,
        parent: Optional[QtWidgets.QWidget] = None,
        on_remove: Any = None,
    ) -> None:
        super().__init__(parent)
        self._course_key = course_key
        self._on_remove = on_remove
        self.course: Dict[str, Any] = COURSES.get(course_key, {})

        name = self.course.get("name", "نامشخص")
        self.setWindowTitle(f"جزئیات درس — {name}")
        self.setMinimumWidth(480)
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()
        self._apply_styles()

    # ─────────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        course = self.course
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # ── Header: name + code chip ──
        head = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(f"📘 {course.get('name', 'نامشخص')}")
        title.setObjectName("cdTitle")
        title.setWordWrap(True)
        head.addWidget(title, stretch=1)
        code_chip = QtWidgets.QLabel(str(course.get("code", "—")))
        code_chip.setObjectName("cdChip")
        head.addWidget(code_chip, alignment=Qt.AlignTop)
        root.addLayout(head)

        # ── Key facts grid ──
        facts = QtWidgets.QGridLayout()
        facts.setHorizontalSpacing(14)
        facts.setVerticalSpacing(8)
        capacity = course.get("capacity")
        enrolled = course.get("enrolled")
        if capacity:
            cap_text = f"{enrolled if enrolled is not None else '؟'} / {capacity}"
        else:
            cap_text = "—"
        rows = [
            ("👨‍🏫 استاد:", course.get("instructor") or "نامشخص"),
            ("🎯 تعداد واحد:", str(course.get("credits", "—"))),
            ("👥 ظرفیت / ثبت‌نام:", cap_text),
            ("📍 محل برگزاری:", course.get("location") or "اعلام نشده"),
        ]
        gender = course.get("gender_restriction") or course.get("gender")
        if gender:
            rows.append(("⚥ ویژه:", str(gender)))
        for r, (label, value) in enumerate(rows):
            lbl = QtWidgets.QLabel(label)
            lbl.setObjectName("cdLabel")
            val = QtWidgets.QLabel(str(value))
            val.setObjectName("cdValue")
            val.setWordWrap(True)
            facts.addWidget(lbl, r, 0)
            facts.addWidget(val, r, 1)
        root.addLayout(facts)

        # ── Sessions ──
        sessions_group = QtWidgets.QGroupBox("🗓️ زمان‌های برگزاری")
        sessions_lay = QtWidgets.QVBoxLayout(sessions_group)
        sessions = course.get("schedule", []) or []
        if sessions:
            for sess in sessions:
                day = sess.get("day", "")
                start = sess.get("start", "")
                end = sess.get("end", "")
                parity = sess.get("parity", "")
                location = sess.get("location", "")
                parity_text = ""
                if parity == "ز":
                    parity_text = " · زوج"
                elif parity == "ف":
                    parity_text = " · فرد"
                loc_text = f" · {location}" if location else ""
                line = QtWidgets.QLabel(f"▫️ {day}، {start} تا {end}{parity_text}{loc_text}")
                line.setObjectName("cdSession")
                sessions_lay.addWidget(line)
        else:
            empty = QtWidgets.QLabel("زمان‌بندی برای این درس ثبت نشده است.")
            empty.setObjectName("cdMuted")
            sessions_lay.addWidget(empty)
        root.addWidget(sessions_group)

        # ── Exam card ──
        exam_time = course.get("exam_time", "")
        exam_card = QtWidgets.QFrame()
        exam_card.setObjectName("cdExamCard" if exam_time else "cdExamCardEmpty")
        exam_lay = QtWidgets.QHBoxLayout(exam_card)
        exam_title = QtWidgets.QLabel("📝 امتحان")
        exam_title.setObjectName("cdExamTitle")
        exam_lay.addWidget(exam_title)
        exam_lay.addStretch()
        exam_val = QtWidgets.QLabel(str(exam_time) if exam_time else "اعلام نشده")
        exam_val.setObjectName("cdExamValue")
        exam_val.setWordWrap(True)
        exam_lay.addWidget(exam_val)
        root.addWidget(exam_card)

        # ── Enrollment conditions ──
        conditions = course.get("enrollment_conditions") or course.get("prerequisites")
        if conditions:
            cond_group = QtWidgets.QGroupBox("📋 شرایط / پیش‌نیاز ثبت‌نام")
            cond_lay = QtWidgets.QVBoxLayout(cond_group)
            cond_lbl = QtWidgets.QLabel(str(conditions))
            cond_lbl.setObjectName("cdSession")
            cond_lbl.setWordWrap(True)
            cond_lay.addWidget(cond_lbl)
            root.addWidget(cond_group)

        root.addStretch()

        # ── Actions ──
        actions = QtWidgets.QHBoxLayout()
        actions.addStretch()
        if self._on_remove is not None:
            btn_remove = QtWidgets.QPushButton("🗑️ حذف از برنامه")
            btn_remove.setObjectName("cdDangerButton")
            btn_remove.setMinimumWidth(140)
            btn_remove.clicked.connect(self._handle_remove)
            actions.addWidget(btn_remove)
        btn_close = QtWidgets.QPushButton("بستن")
        btn_close.setObjectName("primaryButton")
        btn_close.setMinimumWidth(110)
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)
        root.addLayout(actions)

    def _handle_remove(self) -> None:
        if self._on_remove is not None:
            try:
                self._on_remove(self._course_key)
            finally:
                self.accept()

    # ─────────────────────────────────────────────────────────
    def _apply_styles(self) -> None:
        p = theme_manager.palette()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p['bg']};
                color: {p['text']};
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
                font-size: 10.5pt;
            }}
            QLabel#cdTitle {{ font-size: 15pt; font-weight: bold; color: {p['text']}; }}
            QLabel#cdChip {{
                background-color: {p['tint']};
                color: {p['primary']};
                border-radius: 10px;
                padding: 4px 12px;
                font-weight: bold;
            }}
            QLabel#cdLabel {{ color: {p['muted']}; }}
            QLabel#cdValue {{ color: {p['text']}; font-weight: bold; }}
            QLabel#cdSession {{ color: {p['text_mid']}; font-size: 10pt; }}
            QLabel#cdMuted {{ color: {p['muted']}; }}
            QGroupBox {{
                font-weight: bold;
                color: {p['primary']};
                border: 1px solid {p['border']};
                border-radius: 10px;
                margin-top: 12px;
                padding: 12px 10px 8px 10px;
                background: transparent;
            }}
            QFrame#cdExamCard {{
                background-color: {p['tint']};
                border: 1px solid {p['primary']};
                border-radius: 10px;
                padding: 10px;
            }}
            QFrame#cdExamCardEmpty {{
                background-color: {p['surface']};
                border: 1px dashed {p['border']};
                border-radius: 10px;
                padding: 10px;
            }}
            QLabel#cdExamTitle {{ font-weight: bold; color: {p['primary']}; border: none; }}
            QLabel#cdExamValue {{ font-weight: bold; border: none; }}
            QPushButton#primaryButton {{
                background-color: {p['primary']};
                color: {p['primary_text']};
                border: none;
                border-radius: 8px;
                padding: 9px 18px;
                font-weight: bold;
            }}
            QPushButton#cdDangerButton {{
                background-color: {p['surface']};
                color: {p['danger']};
                border: 1px solid {p['danger']};
                border-radius: 8px;
                padding: 9px 16px;
                font-weight: bold;
            }}
            QPushButton#cdDangerButton:hover {{
                background-color: {p['danger']};
                color: #ffffff;
            }}
        """)
