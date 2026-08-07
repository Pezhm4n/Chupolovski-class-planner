# -*- coding: utf-8 -*-
"""
Golestoon Academic Center PyQt5 Dialog & Visual Widgets.

This module provides the AcademicCenterDialog displaying student profile info,
Report 272 degree requirement progress bars, transcript semester tables, GPA trend chart,
and desktop-exclusive Persian HTML/PDF transcript exporting.

Architecture Layer: Layer 5 (Presentation & UI)
Dependencies: `PyQt5`, `AcademicManager`, `DESIGN.md` Tokens.
"""

import logging
import base64
from typing import Optional, List, Dict, Any
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from app.core.academic_manager import AcademicManager

logger = logging.getLogger("golestoon.ui.academic_dialog")


class VisualGpaTrendWidget(QtWidgets.QFrame):
    """Custom PyQt5 visual bar chart rendering semester GPA trends without heavy dependencies."""

    def __init__(self, gpa_trend: List[tuple], parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._trend: List[tuple] = gpa_trend
        self.setMinimumHeight(180)
        self.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px;")

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        if not self._trend:
            painter = QtGui.QPainter(self)
            painter.setPen(QtGui.QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignCenter, "هیچ داده‌ای برای رسم نمودار معدل موجود نیست.")
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        padding = 30
        chart_w = w - (padding * 2)
        chart_h = h - (padding * 2)

        num_items = len(self._trend)
        bar_width = min(40, max(15, int(chart_w / (num_items * 1.5))))

        for i, (term_title, gpa_val) in enumerate(self._trend):
            x = padding + int(i * (chart_w / num_items)) + 10
            bar_h = int((gpa_val / 20.0) * chart_h)
            y = h - padding - bar_h

            # Color gradient based on GPA
            color = QtGui.QColor("#16a34a") if gpa_val >= 17.0 else (QtGui.QColor("#3b82f6") if gpa_val >= 14.0 else QtGui.QColor("#f59e0b"))
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(x, y, bar_width, bar_h, 4, 4)

            # GPA Text above bar
            painter.setPen(QtGui.QColor("#f8fafc"))
            painter.setFont(QtGui.QFont("Vazirmatn", 8, QtGui.QFont.Bold))
            painter.drawText(x - 5, y - 5, bar_width + 10, 15, Qt.AlignCenter, f"{gpa_val:.2f}")


class CategoryProgressBarCard(QtWidgets.QFrame):
    """Card widget displaying Report 272 course requirement category progress."""

    def __init__(self, title: str, passed: int, required: int, pct: float, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header
        hdr = QtWidgets.QHBoxLayout()
        lbl_t = QtWidgets.QLabel(title)
        lbl_t.setStyleSheet("font-weight: bold; color: #f8fafc; font-size: 10pt;")
        hdr.addWidget(lbl_t)
        hdr.addStretch()

        color = "#16a34a" if pct >= 100.0 else ("#3b82f6" if pct >= 60.0 else "#f59e0b")
        lbl_info = QtWidgets.QLabel(f"{passed} از {required} واحد ({pct:.1f}%)")
        lbl_info.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 9.5pt;")
        hdr.addWidget(lbl_info)
        layout.addLayout(hdr)

        # Progress Bar
        pbar = QtWidgets.QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(int(pct))
        pbar.setTextVisible(False)
        pbar.setFixedHeight(8)
        pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(pbar)


class AcademicCenterDialog(QtWidgets.QDialog):
    """
    Main PyQt5 Dialog for Golestoon Academic Center & Transcript Analytics.
    """

    def __init__(
        self,
        manager: AcademicManager,
        student_data: Dict[str, Any],
        semesters_data: List[Dict[str, Any]],
        parent: Optional[QtWidgets.QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._manager: AcademicManager = manager
        self._student: Dict[str, Any] = student_data
        self._semesters: List[Dict[str, Any]] = semesters_data

        self.setWindowTitle("مرکز خدمات تحصیلی و کارنامه دانشجو (Golestoon Academic Center)")
        self.resize(920, 700)
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Title Bar & Desktop Export Button
        header_box = QtWidgets.QHBoxLayout()
        title_lbl = QtWidgets.QLabel("🎓 مرکز وضعیت تحصیلی و کارنامه جامع")
        title_lbl.setStyleSheet("font-size: 14pt; font-weight: bold; color: #f8fafc;")
        header_box.addWidget(title_lbl)
        header_box.addStretch()

        # Desktop Enhancement: Export HTML Transcript
        btn_export = QtWidgets.QPushButton("🚀 خروجی رسمی HTML / PDF کارنامه")
        btn_export.setObjectName("primaryButton")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self._export_transcript_html)
        header_box.addWidget(btn_export)

        main_layout.addLayout(header_box)

        # Main Tab Widget
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setLayoutDirection(Qt.RightToLeft)

        # Tab 1: Profile
        self.tab_profile = QtWidgets.QWidget()
        self._setup_profile_tab()
        self.tab_widget.addTab(self.tab_profile, "👤 شناسنامه دانشجو")

        # Tab 2: Report 272 Progress
        self.tab_progress = QtWidgets.QWidget()
        self._setup_progress_tab()
        self.tab_widget.addTab(self.tab_progress, "🎓 پیشرفت تحصیلی (گزارش ۲۷۲)")

        # Tab 3: Transcript & Semesters
        self.tab_transcript = QtWidgets.QWidget()
        self._setup_transcript_tab()
        self.tab_widget.addTab(self.tab_transcript, "📄 سوابق و کارنامه")

        # Tab 4: GPA Analytics
        self.tab_analytics = QtWidgets.QWidget()
        self._setup_analytics_tab()
        self.tab_widget.addTab(self.tab_analytics, "📈 تحلیل معدل و آمار")

        main_layout.addWidget(self.tab_widget)

    # ─────────────────────────────────────────────────────────
    # Tab 1: Student Profile Layout
    # ─────────────────────────────────────────────────────────
    def _setup_profile_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_profile)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        card = QtWidgets.QFrame()
        card.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px;")
        card_layout = QtWidgets.QHBoxLayout(card)

        # Avatar Image
        lbl_avatar = QtWidgets.QLabel()
        lbl_avatar.setFixedSize(90, 90)
        lbl_avatar.setStyleSheet("border: 2px solid #3b82f6; border-radius: 45px; background-color: #0f172a;")
        lbl_avatar.setAlignment(Qt.AlignCenter)
        lbl_avatar.setText("👤")

        img_b64 = self._student.get("image_b64")
        if img_b64:
            try:
                pix = QtGui.QPixmap()
                pix.loadFromData(base64.b64decode(img_b64))
                lbl_avatar.setPixmap(pix.scaled(90, 90, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
            except Exception:
                pass
        card_layout.addWidget(lbl_avatar)
        card_layout.addSpacing(16)

        # Info Grid
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(8)

        name_str = self._student.get("name") or self._student.get("fullName") or "دانشجوی مهمان"
        grid.addWidget(self._make_lbl("نام و نام خانوادگی:", True), 0, 0)
        grid.addWidget(self._make_lbl(name_str), 0, 1)

        grid.addWidget(self._make_lbl("شماره دانشجویی:", True), 0, 2)
        grid.addWidget(self._make_lbl(str(self._student.get("student_id", "—"))), 0, 3)

        grid.addWidget(self._make_lbl("دانشکده:", True), 1, 0)
        grid.addWidget(self._make_lbl(str(self._student.get("faculty", "—"))), 1, 1)

        grid.addWidget(self._make_lbl("رشته تحصیلی:", True), 1, 2)
        grid.addWidget(self._make_lbl(str(self._student.get("major", "—"))), 1, 3)

        grid.addWidget(self._make_lbl("مقطع تحصیلی:", True), 2, 0)
        grid.addWidget(self._make_lbl(str(self._student.get("degree_level", "کارشناسی"))), 2, 1)

        grid.addWidget(self._make_lbl("وضعیت ثبت‌نام:", True), 2, 2)
        grid.addWidget(self._make_lbl(str(self._student.get("enrollment_status", "مجاز به ثبت‌نام"))), 2, 3)

        card_layout.addLayout(grid)
        layout.addWidget(card)
        layout.addStretch()

    def _make_lbl(self, text: str, is_title: bool = False) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel(text)
        if is_title:
            lbl.setStyleSheet("font-weight: bold; color: #94a3b8; font-size: 9.5pt;")
        else:
            lbl.setStyleSheet("color: #f8fafc; font-size: 9.5pt;")
        return lbl

    # ─────────────────────────────────────────────────────────
    # Tab 2: Report 272 Degree Progress Layout
    # ─────────────────────────────────────────────────────────
    def _setup_progress_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_progress)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Compute Report 272 progress
        data = AcademicManager.calculate_degree_progress_272()

        card_gen = CategoryProgressBarCard(data["general"]["title"], data["general"]["passed"], data["general"]["required"], data["general"]["pct"])
        card_basic = CategoryProgressBarCard(data["basic"]["title"], data["basic"]["passed"], data["basic"]["required"], data["basic"]["pct"])
        card_spec = CategoryProgressBarCard(data["specialized"]["title"], data["specialized"]["passed"], data["specialized"]["required"], data["specialized"]["pct"])
        card_elec = CategoryProgressBarCard(data["elective"]["title"], data["elective"]["passed"], data["elective"]["required"], data["elective"]["pct"])

        layout.addWidget(card_gen)
        layout.addWidget(card_basic)
        layout.addWidget(card_spec)
        layout.addWidget(card_elec)
        layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # Tab 3: Transcript & Semesters Layout
    # ─────────────────────────────────────────────────────────
    def _setup_transcript_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_transcript)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Real-time search input
        self.txt_search_course = QtWidgets.QLineEdit()
        self.txt_search_course.setPlaceholderText("🔍 جستجوی سریع نام یا کد درس در کارنامه...")
        self.txt_search_course.textChanged.connect(self._filter_transcript_courses)
        layout.addWidget(self.txt_search_course)

        # Transcript Table
        self.transcript_table = QtWidgets.QTableWidget()
        self.transcript_table.setColumnCount(5)
        self.transcript_table.setHorizontalHeaderLabels(["ترم", "کد درس", "نام درس", "واحد", "نمره / وضعیت"])
        self.transcript_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.transcript_table)

        self._render_transcript_rows(self._semesters)

    def _render_transcript_rows(self, semesters: List[Dict[str, Any]], filter_query: str = "") -> None:
        all_rows: List[tuple] = []
        for sem in semesters:
            sem_title = sem.get("semester_description") or f"ترم {sem.get('semester_id', '')}"
            courses = sem.get("courses", [])
            for c in courses:
                c_code = str(c.get("course_code", ""))
                c_name = str(c.get("course_name", ""))
                c_units = str(c.get("course_units", ""))
                grade = str(c.get("grade", c.get("grade_state", "—")))

                if filter_query:
                    q = filter_query.lower()
                    if q not in c_code.lower() and q not in c_name.lower():
                        continue

                all_rows.append((sem_title, c_code, c_name, c_units, grade))

        self.transcript_table.setRowCount(len(all_rows))
        for r_idx, (st, cc, cn, cu, gr) in enumerate(all_rows):
            self.transcript_table.setItem(r_idx, 0, QtWidgets.QTableWidgetItem(st))
            self.transcript_table.setItem(r_idx, 1, QtWidgets.QTableWidgetItem(cc))
            self.transcript_table.setItem(r_idx, 2, QtWidgets.QTableWidgetItem(cn))
            self.transcript_table.setItem(r_idx, 3, QtWidgets.QTableWidgetItem(cu))
            self.transcript_table.setItem(r_idx, 4, QtWidgets.QTableWidgetItem(gr))

    def _filter_transcript_courses(self, text: str) -> None:
        self._render_transcript_rows(self._semesters, filter_query=text.strip())

    # ─────────────────────────────────────────────────────────
    # Tab 4: GPA Analytics & Visual Chart Layout
    # ─────────────────────────────────────────────────────────
    def _setup_analytics_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_analytics)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        analytics = AcademicManager.calculate_gpa_analytics(self._semesters)

        # Overview Stats Row
        stats_box = QtWidgets.QHBoxLayout()
        lbl_gpa = QtWidgets.QLabel(f"معدل کل: {analytics['overall_gpa']}")
        lbl_gpa.setStyleSheet("background-color: #1e293b; color: #10b981; border: 1px solid #10b981; border-radius: 6px; padding: 10px; font-weight: bold; font-size: 11pt;")

        lbl_passed = QtWidgets.QLabel(f"کل واحدهای گذرانده: {analytics['total_passed_units']}")
        lbl_passed.setStyleSheet("background-color: #1e293b; color: #3b82f6; border: 1px solid #3b82f6; border-radius: 6px; padding: 10px; font-weight: bold; font-size: 11pt;")

        stats_box.addWidget(lbl_gpa)
        stats_box.addWidget(lbl_passed)
        layout.addLayout(stats_box)

        # Visual Chart Widget
        layout.addWidget(QtWidgets.QLabel("📈 روند تغییرات معدل ترم‌ها:"))
        chart_widget = VisualGpaTrendWidget(gpa_trend=analytics["gpa_trend"])
        layout.addWidget(chart_widget)

        layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # Desktop Enhancement: Export HTML Transcript Report
    # ─────────────────────────────────────────────────────────
    def _export_transcript_html(self) -> None:
        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "ذخیره کارنامه تحصیلی", "Golestoon_Transcript.html", "HTML Files (*.html)")
        if not save_path:
            return

        name = self._student.get("name") or "دانشجو"
        sid = self._student.get("student_id") or "—"
        major = self._student.get("major") or "—"

        html_content = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>کارنامه تحصیلی گلستون - {name}</title>
    <style>
        body {{ font-family: 'Tahoma', sans-serif; background: #f8fafc; color: #0f172a; padding: 20px; }}
        .header {{ background: #1e293b; color: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; }}
        th, td {{ border: 1px solid #cbd5e1; padding: 10px; text-align: right; }}
        th {{ background: #3b82f6; color: #fff; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>🌸 کارنامه تحصیلی و سوابق آموزشی گلستون</h2>
        <p>نام دانشجو: <strong>{name}</strong> | شماره دانشجویی: <strong>{sid}</strong> | رشته: <strong>{major}</strong></p>
    </div>
    <h3>فهرست سوابق ترم‌ها</h3>
    <table>
        <thead>
            <tr><th>ترم</th><th>کد درس</th><th>نام درس</th><th>واحد</th><th>نمره</th></tr>
        </thead>
        <tbody>
"""
        for sem in self._semesters:
            sem_title = sem.get("semester_description") or f"ترم {sem.get('semester_id', '')}"
            for c in sem.get("courses", []):
                html_content += f"<tr><td>{sem_title}</td><td>{c.get('course_code','')}</td><td>{c.get('course_name','')}</td><td>{c.get('course_units','')}</td><td>{c.get('grade','—')}</td></tr>\n"

        html_content += "</tbody></table></body></html>"

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            QtWidgets.QMessageBox.information(self, "موفقیت", f"کارنامه تحصیلی با موفقیت در مسیر زیر ذخیره شد:\n{save_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در ذخیره کارنامه:\n{str(e)}")

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #0f172a;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #94a3b8;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 10pt;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #3b82f6;
                color: #ffffff;
            }
            QLineEdit {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 9.5pt;
            }
            QPushButton#primaryButton {
                background-color: #3b82f6;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QTableWidget {
                background-color: #0f172a;
                color: #f8fafc;
                gridline-color: #334155;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #f8fafc;
                padding: 8px;
                font-weight: bold;
                border: 1px solid #334155;
            }
        """)
