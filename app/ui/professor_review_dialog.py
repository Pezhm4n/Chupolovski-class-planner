# -*- coding: utf-8 -*-
"""
Golestoon Professor Reviews PyQt5 Dialog.

This module provides the primary UI dialog for Professor Reviews, Rating Cards,
3-Way Side-by-Side Comparison Matrix, and Popular Instructors list.

Architecture Layer: Layer 5 (Presentation & UI)
Dependencies: `PyQt5`, `ProfessorManager`, `DESIGN.md` Tokens.
"""

import logging
from typing import Optional, List, Dict, Any
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot

from app.core.professor_manager import (
    ProfessorManager,
    ProfessorStatsModel,
    calc_overall_score,
    calc_display_score,
    get_score_color_hex,
    get_inverse_score_color_hex,
)

logger = logging.getLogger("golestoon.ui.professor_dialog")


class StatScoreCard(QtWidgets.QFrame):
    """Custom widget rendering a single score criteria card with colored progress bar."""

    def __init__(
        self,
        title: str,
        score: float,
        is_inverse: bool = False,
        sublabel: str = "",
        parent: Optional[QtWidgets.QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
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

        # Header Row
        header_layout = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet("color: #94a3b8; font-size: 9.5pt; font-weight: bold;")
        header_layout.addWidget(title_label)

        color_hex = get_inverse_score_color_hex(score) if is_inverse else get_score_color_hex(score)
        val_label = QtWidgets.QLabel(f"{score:.1f}")
        val_label.setStyleSheet(f"color: {color_hex}; font-size: 14pt; font-weight: bold;")
        header_layout.addStretch()
        header_layout.addWidget(val_label)
        layout.addLayout(header_layout)

        # Progress Bar
        pbar = QtWidgets.QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(int(score))
        pbar.setTextVisible(False)
        pbar.setFixedHeight(8)
        pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color_hex};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(pbar)

        if sublabel:
            sub_lbl = QtWidgets.QLabel(sublabel)
            sub_lbl.setStyleSheet("color: #64748b; font-size: 8pt;")
            layout.addWidget(sub_lbl)


class ProfessorReviewDialog(QtWidgets.QDialog):
    """
    PyQt5 Professor Review & Compare Dialog.
    """

    def __init__(self, manager: ProfessorManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._manager: ProfessorManager = manager
        self.setWindowTitle("نظرسنجی و مقایسه اساتید")
        self.resize(920, 680)
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Title Bar
        header_box = QtWidgets.QHBoxLayout()
        title_lbl = QtWidgets.QLabel("👨‍🏫 نظرسنجی و مقایسه اساتید")
        title_lbl.setStyleSheet("font-size: 14pt; font-weight: bold; color: #f8fafc;")
        header_box.addWidget(title_lbl)
        header_box.addStretch()

        badge = QtWidgets.QLabel("✨ نظرسنجی زنده دانشجوها")
        badge.setStyleSheet("background-color: #1e293b; color: #3b82f6; border: 1px solid #3b82f6; border-radius: 12px; padding: 4px 10px; font-size: 8.5pt;")
        header_box.addWidget(badge)
        main_layout.addLayout(header_box)

        # Main Tab Widget
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setLayoutDirection(Qt.RightToLeft)

        # Tab 1: Submit Review
        self.tab_submit = QtWidgets.QWidget()
        self._setup_submit_tab()
        self.tab_widget.addTab(self.tab_submit, "✍️ ثبت نظر")

        # Tab 2: Stats & Ratings
        self.tab_stats = QtWidgets.QWidget()
        self._setup_stats_tab()
        self.tab_widget.addTab(self.tab_stats, "📊 آمار و امتیازات استاد")

        # Tab 3: Compare
        self.tab_compare = QtWidgets.QWidget()
        self._setup_compare_tab()
        self.tab_widget.addTab(self.tab_compare, "⚔️ مقایسه اساتید")

        # Tab 4: Popular
        self.tab_popular = QtWidgets.QWidget()
        self._setup_popular_tab()
        self.tab_widget.addTab(self.tab_popular, "🔥 اساتید محبوب")

        main_layout.addWidget(self.tab_widget)

    # ─────────────────────────────────────────────────────────
    # Tab 1: Submit Review Layout
    # ─────────────────────────────────────────────────────────
    def _setup_submit_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_submit)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form_card = QtWidgets.QFrame()
        form_card.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px;")
        card_layout = QtWidgets.QVBoxLayout(form_card)

        # Inputs Row
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QtWidgets.QLabel("نام دانشکده / گروه:"), 0, 0)
        self.txt_submit_dept = QtWidgets.QLineEdit()
        self.txt_submit_dept.setPlaceholderText("مثال: مهندسی کامپیوتر")
        grid.addWidget(self.txt_submit_dept, 0, 1)

        grid.addWidget(QtWidgets.QLabel("نام استاد:"), 1, 0)
        self.txt_submit_inst = QtWidgets.QLineEdit()
        self.txt_submit_inst.setPlaceholderText("مثال: دکتر علی رضایی")
        grid.addWidget(self.txt_submit_inst, 1, 1)

        card_layout.addLayout(grid)
        card_layout.addSpacing(10)

        # Slider Criteria
        self.slider_teaching = self._add_slider_row(card_layout, "کیفیت تدریس (۰ تا ۱۰۰):", 75)
        self.slider_grading = self._add_slider_row(card_layout, "نمره‌دهی و ارفاق (۰ تا ۱۰۰):", 70)
        self.slider_exam = self._add_slider_row(card_layout, "سختی امتحان (۰ = خیلی آسان, ۱۰۰ = خیلی سخت):", 50)
        self.slider_assign = self._add_slider_row(card_layout, "حجم تکالیف و پروژه (۰ تا ۱۰۰):", 60)

        # Radio Attendance
        radio_box = QtWidgets.QHBoxLayout()
        radio_box.addWidget(QtWidgets.QLabel("حضور و غیاب:"))
        self.radio_att_strict = QtWidgets.QRadioButton("خیلی حساس")
        self.radio_att_normal = QtWidgets.QRadioButton("معمولی")
        self.radio_att_normal.setChecked(True)
        self.radio_att_easy = QtWidgets.QRadioButton("بی‌خیال")
        radio_box.addWidget(self.radio_att_strict)
        radio_box.addWidget(self.radio_att_normal)
        radio_box.addWidget(self.radio_att_easy)
        radio_box.addStretch()
        card_layout.addLayout(radio_box)
        card_layout.addSpacing(12)

        # Submit Button
        btn_submit = QtWidgets.QPushButton("🚀 ثبت و ارسال نظر")
        btn_submit.setObjectName("primaryButton")
        btn_submit.setCursor(Qt.PointingHandCursor)
        btn_submit.clicked.connect(self._on_submit_review_clicked)
        card_layout.addWidget(btn_submit)

        layout.addWidget(form_card)
        layout.addStretch()

    def _add_slider_row(self, layout: QtWidgets.QVBoxLayout, title: str, default_val: int) -> QtWidgets.QSlider:
        box = QtWidgets.QHBoxLayout()
        lbl_title = QtWidgets.QLabel(title)
        lbl_title.setFixedWidth(240)
        box.addWidget(lbl_title)

        slider = QtWidgets.QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(default_val)
        box.addWidget(slider)

        val_lbl = QtWidgets.QLabel(str(default_val))
        val_lbl.setFixedWidth(35)
        val_lbl.setAlignment(Qt.AlignCenter)
        slider.valueChanged.connect(lambda v: val_lbl.setText(str(v)))
        box.addWidget(val_lbl)

        layout.addLayout(box)
        return slider

    # ─────────────────────────────────────────────────────────
    # Tab 2: Stats & Ratings Layout
    # ─────────────────────────────────────────────────────────
    def _setup_stats_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_stats)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Search Bar
        search_box = QtWidgets.QHBoxLayout()
        self.txt_stats_dept = QtWidgets.QLineEdit()
        self.txt_stats_dept.setPlaceholderText("دانشکده...")
        self.txt_stats_inst = QtWidgets.QLineEdit()
        self.txt_stats_inst.setPlaceholderText("نام استاد...")

        btn_search = QtWidgets.QPushButton("🔍 دریافت آمار")
        btn_search.setObjectName("primaryButton")
        btn_search.clicked.connect(self._on_fetch_stats_clicked)

        search_box.addWidget(self.txt_stats_dept)
        search_box.addWidget(self.txt_stats_inst)
        search_box.addWidget(btn_search)
        layout.addLayout(search_box)

        # Cards Container Grid
        self.stats_cards_widget = QtWidgets.QWidget()
        self.cards_layout = QtWidgets.QGridLayout(self.stats_cards_widget)
        self.cards_layout.setSpacing(12)

        # Placeholder Banner
        self.lbl_stats_placeholder = QtWidgets.QLabel("لطفاً نام دانشکده و استاد را وارد کنید تا آمار نمایش داده شود.")
        self.lbl_stats_placeholder.setAlignment(Qt.AlignCenter)
        self.lbl_stats_placeholder.setStyleSheet("color: #94a3b8; font-size: 11pt; padding: 40px;")

        layout.addWidget(self.lbl_stats_placeholder)
        layout.addWidget(self.stats_cards_widget)
        self.stats_cards_widget.hide()
        layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # Tab 3: Compare Layout
    # ─────────────────────────────────────────────────────────
    def _setup_compare_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_compare)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 3 Instructor Inputs
        inputs_box = QtWidgets.QHBoxLayout()
        self.txt_cmp1 = QtWidgets.QLineEdit()
        self.txt_cmp1.setPlaceholderText("استاد ۱ (مثال: رضایی)")
        self.txt_cmp2 = QtWidgets.QLineEdit()
        self.txt_cmp2.setPlaceholderText("استاد ۲ (مثال: احمدی)")
        self.txt_cmp3 = QtWidgets.QLineEdit()
        self.txt_cmp3.setPlaceholderText("استاد ۳ (اختیاری)")

        btn_cmp = QtWidgets.QPushButton("⚔️ مقایسه همزمان")
        btn_cmp.setObjectName("primaryButton")
        btn_cmp.clicked.connect(self._on_compare_clicked)

        inputs_box.addWidget(self.txt_cmp1)
        inputs_box.addWidget(self.txt_cmp2)
        inputs_box.addWidget(self.txt_cmp3)
        inputs_box.addWidget(btn_cmp)
        layout.addLayout(inputs_box)

        # Comparison Table
        self.cmp_table = QtWidgets.QTableWidget()
        self.cmp_table.setColumnCount(4)
        self.cmp_table.setHorizontalHeaderLabels(["معیار مقایسه", "استاد ۱", "استاد ۲", "استاد ۳"])
        self.cmp_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.cmp_table)

    # ─────────────────────────────────────────────────────────
    # Tab 4: Popular Layout
    # ─────────────────────────────────────────────────────────
    def _setup_popular_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_popular)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        btn_load_popular = QtWidgets.QPushButton("🔄 بارگذاری اساتید محبوب و برتر")
        btn_load_popular.setObjectName("secondaryButton")
        btn_load_popular.clicked.connect(self._on_load_popular_clicked)
        layout.addWidget(btn_load_popular)

        self.popular_table = QtWidgets.QTableWidget()
        self.popular_table.setColumnCount(4)
        self.popular_table.setHorizontalHeaderLabels(["استاد", "دانشکده", "امتیاز کل", "تعداد نظرات"])
        self.popular_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.popular_table)

    # ─────────────────────────────────────────────────────────
    # Slot Callbacks & Business Logic
    # ─────────────────────────────────────────────────────────
    def _on_submit_review_clicked(self) -> None:
        dept = self.txt_submit_dept.text().strip()
        inst = self.txt_submit_inst.text().strip()
        if not dept or not inst:
            QtWidgets.QMessageBox.warning(self, "خطا", "لطفاً نام دانشکده و استاد را وارد کنید.")
            return

        att = "normal"
        if self.radio_att_strict.isChecked():
            att = "strict"
        elif self.radio_att_easy.isChecked():
            att = "easy"

        payload = {
            "department_name": dept,
            "instructor_name": inst,
            "teaching_score": float(self.slider_teaching.value()),
            "grading_score": float(self.slider_grading.value()),
            "exam_difficulty_score": float(self.slider_exam.value()),
            "assignments_score": float(self.slider_assign.value()),
            "attendance_sensitivity": att,
        }

        def _on_success(res: dict):
            QtWidgets.QMessageBox.information(self, "موفقیت", "نظر شما با موفقیت به صورت ناشناس ثبت شد.")

        def _on_error(err_msg: str):
            QtWidgets.QMessageBox.critical(self, "خطا در ثبت نظر", f"ثبت نظر با خطا مواجه شد:\n{err_msg}")

        self._manager.submit_review(review_data=payload, on_success=_on_success, on_error=_on_error)

    def _on_fetch_stats_clicked(self) -> None:
        dept = self.txt_stats_dept.text().strip()
        inst = self.txt_stats_inst.text().strip()
        if not inst:
            QtWidgets.QMessageBox.warning(self, "خطا", "لطفاً نام استاد را وارد کنید.")
            return

        def _on_success(stats: Optional[ProfessorStatsModel]):
            if not stats:
                self.lbl_stats_placeholder.setText(f"هیچ آماری برای استاد '{inst}' یافت نشد.")
                self.lbl_stats_placeholder.show()
                self.stats_cards_widget.hide()
                return

            self._render_stats_cards(stats)
            self.lbl_stats_placeholder.hide()
            self.stats_cards_widget.show()

        def _on_error(err_msg: str):
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در دریافت آمار:\n{err_msg}")

        self._manager.fetch_stats(department=dept, instructor=inst, on_success=_on_success, on_error=_on_error)

    def _render_stats_cards(self, stats: ProfessorStatsModel) -> None:
        # Clear existing cards
        for i in reversed(range(self.cards_layout.count())):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        disp_score = calc_display_score(stats)
        card_overall = StatScoreCard("امتیاز کل ترکیبی", disp_score, sublabel=f"بر اساس {stats.total_reviews} نظر سایت + تلگرام")
        card_teaching = StatScoreCard("کیفیت تدریس", stats.teaching_score)
        card_grading = StatScoreCard("نمره‌دهی و ارفاق", stats.grading_score)
        card_exam = StatScoreCard("سختی امتحان", stats.exam_difficulty_score, is_inverse=True, sublabel="عدد کمتر = امتحان آسان‌تر")

        self.cards_layout.addWidget(card_overall, 0, 0)
        self.cards_layout.addWidget(card_teaching, 0, 1)
        self.cards_layout.addWidget(card_grading, 1, 0)
        self.cards_layout.addWidget(card_exam, 1, 1)

    def _on_compare_clicked(self) -> None:
        inst1 = self.txt_cmp1.text().strip()
        inst2 = self.txt_cmp2.text().strip()
        inst3 = self.txt_cmp3.text().strip()

        targets = [inst for inst in [inst1, inst2, inst3] if inst]
        if len(targets) < 2:
            QtWidgets.QMessageBox.warning(self, "خطا", "لطفاً حداقل نام ۲ استاد را برای مقایسه وارد کنید.")
            return

        def _on_success(results: List[ProfessorStatsModel]):
            self._render_compare_table(results)

        def _on_error(err_msg: str):
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در مقایسه اساتید:\n{err_msg}")

        cmp_list = [{"department_name": "", "instructor_name": inst} for inst in targets]
        # Execute comparison asynchronously
        def _run_compare():
            try:
                res = self._manager.client.compare_professors(cmp_list)
                _on_success(res)
            except Exception as e:
                _on_error(str(e))

        QtCore.QTimer.singleShot(0, _run_compare)

    def _render_compare_table(self, results: List[ProfessorStatsModel]) -> None:
        self.cmp_table.setRowCount(5)
        headers = ["معیار"] + [s.instructor_name for s in results]
        self.cmp_table.setColumnCount(len(headers))
        self.cmp_table.setHorizontalHeaderLabels(headers)

        att_map = {"strict": "خیلی حساس", "normal": "معمولی", "easy": "بی‌خیال"}
        att_labels = [att_map.get(s.attendance_sensitivity.lower(), s.attendance_sensitivity) for s in results]

        rows = [
            ("امتیاز کل ترکیبی", [f"{calc_display_score(s):.1f}" for s in results]),
            ("کیفیت تدریس", [f"{s.teaching_score:.1f}" for s in results]),
            ("نمره‌دهی و ارفاق", [f"{s.grading_score:.1f}" for s in results]),
            ("سختی امتحان", [f"{s.exam_difficulty_score:.1f}" for s in results]),
            ("حضور و غیاب", att_labels),
        ]

        for r_idx, (criteria, vals) in enumerate(rows):
            self.cmp_table.setItem(r_idx, 0, QtWidgets.QTableWidgetItem(criteria))
            for c_idx, val in enumerate(vals):
                self.cmp_table.setItem(r_idx, c_idx + 1, QtWidgets.QTableWidgetItem(val))

    def _on_load_popular_clicked(self) -> None:
        def _run():
            try:
                popular = self._manager.client.get_popular_professors()
                self.popular_table.setRowCount(len(popular))
                for idx, p in enumerate(popular):
                    self.popular_table.setItem(idx, 0, QtWidgets.QTableWidgetItem(p.instructor_name))
                    self.popular_table.setItem(idx, 1, QtWidgets.QTableWidgetItem(p.department_name))
                    self.popular_table.setItem(idx, 2, QtWidgets.QTableWidgetItem(f"{calc_display_score(p):.1f}"))
                    self.popular_table.setItem(idx, 3, QtWidgets.QTableWidgetItem(str(p.total_reviews)))
            except Exception as e:
                user_msg = humanize_error(e, "دریافت اطلاعات اساتید محبوب با خطا مواجه شد.")
                QtWidgets.QMessageBox.critical(self, "خطا", user_msg)

        QtCore.QTimer.singleShot(0, _run)

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
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
            QPushButton#primaryButton {
                background-color: #3b82f6;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton#primaryButton:hover {
                background-color: #2563eb;
            }
            QPushButton#secondaryButton {
                background-color: #334155;
                color: #f8fafc;
                border-radius: 6px;
                padding: 8px 16px;
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
