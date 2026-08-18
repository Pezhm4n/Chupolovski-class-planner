# -*- coding: utf-8 -*-
"""
Golestoon Professor Reviews PyQt5 Dialog — redesigned, web-parity UI.

UX principles applied (matching golestan-web ProfessorReview page):
- Selection-first: department & instructor are NON-EDITABLE combos fed by the
  server (no free typing that leads to invalid queries); an optional, clearly
  labeled filter box narrows the instructor list.
- Interactive: selecting an instructor instantly loads its stats (async) and
  registers a view; double-clicking a popular row jumps to its stats.
- Live feedback: slider values show numeric + descriptive preset labels with
  web color thresholds; every async action shows a status line.
- Give-to-Get gate, my-review edit/delete, 3-way compare, leaderboards and
  instructor suggestion — all wired to the real backend contracts.

Architecture Layer: Layer 5 (Presentation & UI)
Dependencies: `ProfessorManager`, `theme_manager`, `AccountAuthDialog`.
"""

import logging
from typing import Any, Dict, List, Optional

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt

from app.core.professor_manager import (
    ProfessorManager,
    ProfessorStats,
    calc_display_score,
    get_score_color_hex,
    get_inverse_score_color_hex,
)
from app.core.theme_manager import theme_manager
from app.core.language_manager import language_manager

logger = logging.getLogger("golestoon.ui.professor_dialog")

def get_attendance_labels() -> Dict[str, str]:
    if language_manager.get_current_language() == "en":
        return {
            "very": "Strict",
            "normal": "Regular",
            "not_important": "Lenient / Optional",
        }
    return {
        "very": "خیلی حساس",
        "normal": "معمولی",
        "not_important": "مهم نیست",
    }

ATTENDANCE_VALUES = ("very", "normal", "not_important")

# Web-parity preset labels for each slider (value → (label, is_inverse))
def _preset_for(kind: str, value: int) -> str:
    is_en = (language_manager.get_current_language() == "en")
    if kind == "teaching":
        if value >= 80: return "Excellent" if is_en else "عالی"
        if value >= 60: return "Good" if is_en else "خوب"
        if value >= 40: return "Average" if is_en else "متوسط"
        return "Weak" if is_en else "ضعیف"
    if kind == "assignments":
        if value >= 80: return "Very Heavy" if is_en else "خیلی سنگین"
        if value >= 60: return "Heavy" if is_en else "سنگین"
        if value >= 40: return "Moderate" if is_en else "متوسط"
        return "Light" if is_en else "سبک"
    if kind == "grading":
        if value >= 80: return "Very Lenient" if is_en else "خیلی آسان‌گیر"
        if value >= 60: return "Fair" if is_en else "منصف"
        if value >= 40: return "Strict" if is_en else "کمی سخت‌گیر"
        return "Very Strict" if is_en else "سخت‌گیر"
    if kind == "exam":
        if value >= 80: return "Very Hard" if is_en else "خیلی سخت"
        if value >= 60: return "Hard" if is_en else "سخت"
        if value >= 40: return "Moderate" if is_en else "متوسط"
        return "Easy" if is_en else "آسان"
    return ""


class ScoreBar(QtWidgets.QFrame):
    """A titled horizontal score bar with value + preset label (web style)."""

    def __init__(self, title: str, value: float, inverse: bool = False,
                 parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        p = theme_manager.palette()
        v = max(0.0, min(100.0, float(value)))
        color = get_inverse_score_color_hex(v) if inverse else get_score_color_hex(v)
        preset = _preset_for(
            "exam" if inverse else "grading", int(v)) if inverse else _preset_for("teaching", int(v))
        self.setStyleSheet(f"""
            ScoreBar {{ background: transparent; border: none; }}
            QProgressBar {{
                background-color: {p['bg']};
                border: 1px solid {p['border']};
                border-radius: 7px;
                min-height: 14px;
                max-height: 14px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 6)
        lay.setSpacing(3)
        head = QtWidgets.QHBoxLayout()
        t = QtWidgets.QLabel(title)
        t.setStyleSheet(f"color: {p['text_mid']}; font-size: 10pt; font-weight: bold; border: none;")
        head.addWidget(t)
        head.addStretch()
        val_lbl = QtWidgets.QLabel(f"{v:.0f}  ·  {preset}")
        val_lbl.setStyleSheet(f"color: {color}; font-size: 10pt; font-weight: bold; border: none;")
        head.addWidget(val_lbl)
        lay.addLayout(head)
        bar = QtWidgets.QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(v))
        bar.setTextVisible(False)
        lay.addWidget(bar)


class ProfessorReviewDialog(QtWidgets.QWidget):
    """Professor Review, Stats, Compare & Popular widget (embedded in main window, web parity, v2 UX)."""

    back_requested = QtCore.pyqtSignal()

    def __init__(
        self,
        manager: ProfessorManager,
        parent: Optional[QtWidgets.QWidget] = None,
        token_manager: Optional[Any] = None,
        auth_client: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._token_manager = token_manager
        self._auth_client = auth_client

        # Track gate status locally (updated on summary)
        self._user_review_count: int = 0

        # Caches
        self._departments: List[str] = []
        self._directory: List[Dict[str, Any]] = []  # full approved directory
        self._last_stats: Optional[ProfessorStats] = None
        self._is_fa = (language_manager.get_current_language() == "fa")

        self.setWindowTitle("👨‍🏫 نظرسنجی و مقایسه اساتید" if self._is_fa else "👨‍🏫 Professor Reviews & Comparison")
        self.resize(1100, 750)
        self.setMinimumSize(940, 620)
        self.setLayoutDirection(Qt.RightToLeft if self._is_fa else Qt.LeftToRight)

        self._setup_ui()
        self._apply_styles()
        try:
            theme_manager.theme_changed.connect(self._on_theme_changed)
            language_manager.language_changed.connect(self._on_language_changed)
        except Exception as err:
            logger.warning("Could not subscribe to theme or language changes: %s", err)
        self._bootstrap_data()

    # ═════════════════════════════════════════════════════════
    # UI skeleton
    # ═════════════════════════════════════════════════════════
    def _setup_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # ── Header ──
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(12)

        # Back Button (Header)
        btn_back_text = "🔙 بازگشت به برنامه هفتگی" if self._is_fa else "🔙 Back to Weekly Schedule"
        self.btn_back_header = QtWidgets.QPushButton(btn_back_text)
        self.btn_back_header.setObjectName("btnBackHeader")
        self.btn_back_header.setCursor(Qt.PointingHandCursor)
        self.btn_back_header.setToolTip("بازگشت به صفحه جدول برنامه کلاسی (Esc)" if self._is_fa else "Return to schedule table (Esc)")
        self.btn_back_header.clicked.connect(self.back_requested.emit)
        header.addWidget(self.btn_back_header)

        header_title = "👨‍🏫 نظرسنجی و مقایسه اساتید" if self._is_fa else "👨‍🏫 Professor Reviews & Comparison"
        self.lbl_title = QtWidgets.QLabel(header_title)
        self.lbl_title.setObjectName("dialogTitle")
        header.addWidget(self.lbl_title)
        header.addStretch()
        badge_initial = "در حال دریافت وضعیت…" if self._is_fa else "Fetching status..."
        self.lbl_summary_badge = QtWidgets.QLabel(badge_initial)
        self.lbl_summary_badge.setObjectName("summaryBadge")
        header.addWidget(self.lbl_summary_badge)
        root.addLayout(header)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setLayoutDirection(Qt.RightToLeft if self._is_fa else Qt.LeftToRight)
        
        # Configure tab bar for full horizontal expansion so titles never clip
        tab_bar = self.tab_widget.tabBar()
        tab_bar.setElideMode(Qt.ElideNone)
        tab_bar.setUsesScrollButtons(True)
        tab_bar.setExpanding(True)
        tab_bar.setCursor(Qt.PointingHandCursor)

        self.tab_stats = QtWidgets.QWidget(); self._setup_stats_tab()
        self.tab_submit = QtWidgets.QWidget(); self._setup_submit_tab()
        self.tab_compare = QtWidgets.QWidget(); self._setup_compare_tab()
        self.tab_popular = QtWidgets.QWidget(); self._setup_popular_tab()
        self.tab_suggest = QtWidgets.QWidget(); self._setup_suggest_tab()

        tab1_t = "🔍 جستجو و آمار اساتید" if self._is_fa else "🔍 Search & Stats"
        tab2_t = "✍️ ثبت نظر و نمره‌دهی" if self._is_fa else "✍️ Submit Review"
        tab3_t = "⚔️ مقایسه اساتید" if self._is_fa else "⚔️ Compare Professors"
        tab4_t = "🔥 برترین اساتید" if self._is_fa else "🔥 Top Rated"
        tab5_t = "💡 پیشنهاد استاد جدید" if self._is_fa else "💡 Suggest New Professor"

        self.tab_widget.addTab(self.tab_stats, tab1_t)
        self.tab_widget.addTab(self.tab_submit, tab2_t)
        self.tab_widget.addTab(self.tab_compare, tab3_t)
        self.tab_widget.addTab(self.tab_popular, tab4_t)
        self.tab_widget.addTab(self.tab_suggest, tab5_t)

        tt1 = "جستجو، مشخصات و آمار تفصیلی عملکرد اساتید" if self._is_fa else "Search and view detailed professor stats"
        tt2 = "ثبت یا ویرایش نظر و نمره‌دهی به استاد" if self._is_fa else "Rate professor and submit review"
        tt3 = "مقایسه همزمان اساتید در شاخص‌های مختلف" if self._is_fa else "Compare multiple professors side-by-side"
        tt4 = "رتبه‌بندی برترین و محبوب‌ترین اساتید دانشگاه" if self._is_fa else "Rankings of top professors"
        tt5 = "پیشنهاد ثبت استاد جدید در سامانه" if self._is_fa else "Suggest a new professor to be added"

        self.tab_widget.setTabToolTip(0, tt1)
        self.tab_widget.setTabToolTip(1, tt2)
        self.tab_widget.setTabToolTip(2, tt3)
        self.tab_widget.setTabToolTip(3, tt4)
        self.tab_widget.setTabToolTip(4, tt5)

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tab_widget)

        # ── Footer Bar ──
        footer = QtWidgets.QHBoxLayout()
        footer.setContentsMargins(4, 4, 4, 0)
        footer.setSpacing(10)
        
        btn_footer_text = "🔙 بازگشت به صفحه اصلی (برنامه هفتگی)" if self._is_fa else "🔙 Back to Schedule Planner"
        self.btn_back_footer = QtWidgets.QPushButton(btn_footer_text)
        self.btn_back_footer.setObjectName("btnBackFooter")
        self.btn_back_footer.setCursor(Qt.PointingHandCursor)
        self.btn_back_footer.clicked.connect(self.back_requested.emit)
        footer.addStretch()
        footer.addWidget(self.btn_back_footer)
        root.addLayout(footer)

    def keyPressEvent(self, event) -> None:
        """Handle Escape key to return to main schedule table."""
        if event.key() == Qt.Key_Escape:
            self.back_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    # ── helper: department selector (non-editable) ──
    def _make_dept_combo(self, with_all: bool = False) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        combo.setMinimumWidth(240)
        if with_all:
            combo.addItem("همه گروه‌ها" if self._is_fa else "All Departments", "")
        for dept in self._departments:
            combo.addItem(dept, dept)
        combo.currentIndexChanged.connect(lambda _i, c=combo: self._on_dept_combo_changed(c))
        return combo

    # ── helper: instructor selector (non-editable + filter) ──
    def _make_inst_picker(self) -> Dict[str, Any]:
        """Returns a dict with filter box + non-editable combo wired together."""
        picker: Dict[str, Any] = {"filter": QtWidgets.QLineEdit(), "combo": QtWidgets.QComboBox()}
        picker["filter"].setPlaceholderText("🔎 فیلتر نام استاد (اختیاری)…")
        picker["filter"].setClearButtonEnabled(True)
        picker["combo"].setMinimumWidth(260)
        picker["filter"].textChanged.connect(lambda _t, p=picker: self._refill_inst_combo(p))
        return picker

    # ═════════════════════════════════════════════════════════
    # Tab 1: Search & Stats
    # ═════════════════════════════════════════════════════════
    def _setup_stats_tab(self) -> None:
        lay = QtWidgets.QVBoxLayout(self.tab_stats)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        grp_t = "۱) استاد موردنظر را انتخاب کنید" if self._is_fa else "1) Select Instructor"
        selector_group = QtWidgets.QGroupBox(grp_t)
        grid = QtWidgets.QGridLayout(selector_group)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        dept_lbl = "گروه آموزشی:" if self._is_fa else "Department:"
        grid.addWidget(QtWidgets.QLabel(dept_lbl), 0, 0)
        self.cmb_stats_dept = self._make_dept_combo()
        grid.addWidget(self.cmb_stats_dept, 0, 1)

        inst_lbl = "نام استاد:" if self._is_fa else "Instructor:"
        grid.addWidget(QtWidgets.QLabel(inst_lbl), 1, 0)
        inst_row = QtWidgets.QHBoxLayout()
        self.stats_picker = self._make_inst_picker()
        inst_row.addWidget(self.stats_picker["filter"])
        inst_row.addWidget(self.stats_picker["combo"], stretch=1)
        grid.addLayout(inst_row, 1, 1)
        lay.addWidget(selector_group)

        init_status = "برای شروع، یک گروه و سپس یک استاد انتخاب کنید." if self._is_fa else "Select a department and instructor to begin."
        self.lbl_stats_status = QtWidgets.QLabel(init_status)
        self.lbl_stats_status.setObjectName("statusLabel")
        self.lbl_stats_status.setWordWrap(True)
        lay.addWidget(self.lbl_stats_status)

        # Give-to-Get lock card
        self.gate_card = QtWidgets.QFrame()
        self.gate_card.setObjectName("gateCard")
        gate_lay = QtWidgets.QVBoxLayout(self.gate_card)
        gate_title_t = "🔒 این بخش قفل است — «نظر بده تا ببینی»" if self._is_fa else "🔒 Locked — Give-to-Get"
        gate_title = QtWidgets.QLabel(gate_title_t)
        gate_title.setObjectName("gateTitle")
        gate_lay.addWidget(gate_title)
        gate_desc_t = (
            "برای باز شدن آمار و مقایسه اساتید، ابتدا برای یک استاد نظر ثبت کنید. "
            "نظرات کاملاً ناشناس است و فقط چند ثانیه زمان می‌برد."
            if self._is_fa else
            "Submit an anonymous review for an instructor to unlock full statistics and comparisons."
        )
        gate_text = QtWidgets.QLabel(gate_desc_t)
        gate_text.setWordWrap(True)
        gate_lay.addWidget(gate_text)
        gate_btn_row = QtWidgets.QHBoxLayout()
        gate_btn_row.addStretch()
        gate_btn_t = "➕ می‌خواهم نظر بدهم" if self._is_fa else "➕ Submit a Review"
        gate_btn = QtWidgets.QPushButton(gate_btn_t)
        gate_btn.setObjectName("primaryButton")
        gate_btn.setMinimumWidth(200)
        gate_btn.clicked.connect(lambda: self.tab_widget.setCurrentWidget(self.tab_submit))
        gate_btn_row.addWidget(gate_btn)
        gate_lay.addLayout(gate_btn_row)
        self.gate_card.hide()
        lay.addWidget(self.gate_card)

        # Stats area (scrollable)
        self.stats_scroll = QtWidgets.QScrollArea()
        self.stats_scroll.setWidgetResizable(True)
        self.stats_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.stats_container = QtWidgets.QWidget()
        self.stats_lay = QtWidgets.QVBoxLayout(self.stats_container)
        self.stats_lay.setContentsMargins(0, 0, 0, 0)
        self.stats_lay.setSpacing(8)
        self.stats_scroll.setWidget(self.stats_container)
        lay.addWidget(self.stats_scroll, stretch=1)

        self.stats_picker["combo"].currentIndexChanged.connect(self._on_stats_inst_selected)

    # ═════════════════════════════════════════════════════════
    # Tab 2: My review
    # ═════════════════════════════════════════════════════════
    def _setup_submit_tab(self) -> None:
        lay = QtWidgets.QVBoxLayout(self.tab_submit)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        grp1_t = "۱) استاد موردنظر را انتخاب کنید" if self._is_fa else "1) Select Instructor"
        sel_group = QtWidgets.QGroupBox(grp1_t)
        grid = QtWidgets.QGridLayout(sel_group)
        dept_lbl = "گروه آموزشی:" if self._is_fa else "Department:"
        grid.addWidget(QtWidgets.QLabel(dept_lbl), 0, 0)
        self.cmb_submit_dept = self._make_dept_combo()
        grid.addWidget(self.cmb_submit_dept, 0, 1)

        inst_lbl = "نام استاد:" if self._is_fa else "Instructor:"
        grid.addWidget(QtWidgets.QLabel(inst_lbl), 1, 0)
        submit_row = QtWidgets.QHBoxLayout()
        self.submit_picker = self._make_inst_picker()
        submit_row.addWidget(self.submit_picker["filter"])
        submit_row.addWidget(self.submit_picker["combo"], stretch=1)
        grid.addLayout(submit_row, 1, 1)
        lay.addWidget(sel_group)

        grp2_t = "۲) امتیازها (۰ تا ۱۰۰)" if self._is_fa else "2) Ratings (0 - 100)"
        scores_group = QtWidgets.QGroupBox(grp2_t)
        scores_lay = QtWidgets.QVBoxLayout(scores_group)
        scores_lay.setSpacing(4)
        s1_t = "کیفیت تدریس:" if self._is_fa else "Teaching Quality:"
        s2_t = "نمره‌دهی و ارفاق:" if self._is_fa else "Grading & Leniency:"
        s3_t = "حجم تکالیف و پروژه:" if self._is_fa else "Assignments & Projects:"
        s4_t = "سختی امتحان:" if self._is_fa else "Exam Difficulty:"
        self.slider_teaching = self._add_slider_row(scores_lay, s1_t, "teaching", 75)
        self.slider_grading = self._add_slider_row(scores_lay, s2_t, "grading", 70)
        self.slider_assign = self._add_slider_row(scores_lay, s3_t, "assignments", 60)
        self.slider_exam = self._add_slider_row(scores_lay, s4_t, "exam", 50)
        lay.addWidget(scores_group)

        grp3_t = "۳) حساسیت حضور و غیاب" if self._is_fa else "3) Attendance Policy"
        att_group = QtWidgets.QGroupBox(grp3_t)
        att_lay = QtWidgets.QHBoxLayout(att_group)
        self.radio_att: Dict[str, QtWidgets.QRadioButton] = {}
        att_labels = get_attendance_labels()
        for value in ATTENDANCE_VALUES:
            radio = QtWidgets.QRadioButton(att_labels.get(value, value))
            if value == "normal":
                radio.setChecked(True)
            self.radio_att[value] = radio
            att_lay.addWidget(radio)
        att_lay.addStretch()
        lay.addWidget(att_group)

        self.lbl_myreview_state = QtWidgets.QLabel("")
        self.lbl_myreview_state.setObjectName("statusLabel")
        self.lbl_myreview_state.setWordWrap(True)
        lay.addWidget(self.lbl_myreview_state)

        btn_row = QtWidgets.QHBoxLayout()
        load_t = "📥 بارگذاری نظر قبلی من" if self._is_fa else "📥 Load Previous Review"
        btn_load = QtWidgets.QPushButton(load_t)
        btn_load.setObjectName("secondaryButton")
        btn_load.setMinimumWidth(190)
        btn_load.clicked.connect(self._on_load_my_review_clicked)
        del_t = "🗑️ حذف نظر من" if self._is_fa else "🗑️ Delete Review"
        btn_delete = QtWidgets.QPushButton(del_t)
        btn_delete.setObjectName("secondaryButton")
        btn_delete.setMinimumWidth(160)
        btn_delete.clicked.connect(self._on_delete_my_review_clicked)
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        submit_t = "🚀 ثبت نظر (کاملاً ناشناس)" if self._is_fa else "🚀 Submit Review (Anonymous)"
        btn_submit = QtWidgets.QPushButton(submit_t)
        btn_submit.setObjectName("primaryButton")
        btn_submit.setMinimumHeight(44)
        btn_submit.setCursor(Qt.PointingHandCursor)
        btn_submit.clicked.connect(self._on_submit_review_clicked)
        lay.addWidget(btn_submit)
        lay.addStretch()

    def _add_slider_row(self, parent_lay, title: str, kind: str, default: int) -> QtWidgets.QSlider:
        p = theme_manager.palette()
        row = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(title)
        lbl.setFixedWidth(150)
        row.addWidget(lbl)
        slider = QtWidgets.QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(default)
        row.addWidget(slider, stretch=1)

        def _color_for(v: int) -> str:
            if kind == "exam":
                return get_inverse_score_color_hex(v)
            if kind == "assignments":
                return get_inverse_score_color_hex(v)
            return get_score_color_hex(v)

        val_lbl = QtWidgets.QLabel()
        val_lbl.setFixedWidth(130)
        val_lbl.setAlignment(Qt.AlignCenter)

        def _update(v: int) -> None:
            val_lbl.setText(f"{v} · {_preset_for(kind, v)}")
            val_lbl.setStyleSheet(
                f"color: {_color_for(v)}; font-weight: bold; border: none; background: transparent;"
            )

        slider.valueChanged.connect(_update)
        _update(default)
        row.addWidget(val_lbl)
        parent_lay.addLayout(row)
        return slider

    # ═════════════════════════════════════════════════════════
    # Tab 3: Compare
    # ═════════════════════════════════════════════════════════
    def _setup_compare_tab(self) -> None:
        lay = QtWidgets.QVBoxLayout(self.tab_compare)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        hint_t = "برای مقایسه، در دو یا سه ردیف زیر گروه و استاد انتخاب کنید:" if self._is_fa else "Select 2 or 3 instructors below to compare side-by-side:"
        hint = QtWidgets.QLabel(hint_t)
        hint.setObjectName("statusLabel")
        lay.addWidget(hint)

        self.cmp_rows: List[Dict[str, Any]] = []
        for i in range(3):
            row = QtWidgets.QHBoxLayout()
            prof_lbl = f"استاد {i + 1}:" if self._is_fa else f"Prof {i + 1}:"
            num_lbl = QtWidgets.QLabel(prof_lbl)
            num_lbl.setFixedWidth(60)
            dept = self._make_dept_combo()
            picker = self._make_inst_picker()
            row.addWidget(num_lbl)
            row.addWidget(dept, 1)
            row.addWidget(picker["filter"])
            row.addWidget(picker["combo"], 2)
            lay.addLayout(row)
            self.cmp_rows.append({"dept": dept, "picker": picker})

        cmp_btn_t = "⚔️ مقایسه کن" if self._is_fa else "⚔️ Compare"
        btn_cmp = QtWidgets.QPushButton(cmp_btn_t)
        btn_cmp.setObjectName("primaryButton")
        btn_cmp.setMinimumHeight(40)
        btn_cmp.clicked.connect(self._on_compare_clicked)
        lay.addWidget(btn_cmp)

        self.lbl_cmp_status = QtWidgets.QLabel("")
        self.lbl_cmp_status.setObjectName("statusLabel")
        lay.addWidget(self.lbl_cmp_status)

        self.cmp_table = QtWidgets.QTableWidget()
        self.cmp_table.setColumnCount(4)
        cmp_headers = ["معیار", "استاد ۱", "استاد ۲", "استاد ۳"] if self._is_fa else ["Metric", "Professor 1", "Professor 2", "Professor 3"]
        self.cmp_table.setHorizontalHeaderLabels(cmp_headers)
        self.cmp_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.cmp_table.verticalHeader().setVisible(False)
        self.cmp_table.setAlternatingRowColors(True)
        lay.addWidget(self.cmp_table, stretch=1)

    # ═════════════════════════════════════════════════════════
    # Tab 4: Popular
    # ═════════════════════════════════════════════════════════
    def _setup_popular_tab(self) -> None:
        lay = QtWidgets.QVBoxLayout(self.tab_popular)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        filter_row = QtWidgets.QHBoxLayout()
        sort_lbl = "مرتب‌سازی بر اساس:" if self._is_fa else "Sort by:"
        filter_row.addWidget(QtWidgets.QLabel(sort_lbl))
        self.cmb_popular_kind = QtWidgets.QComboBox()
        s1 = "⭐ بیشترین امتیاز" if self._is_fa else "⭐ Highest Rating"
        s2 = "👁️ بیشترین بازدید" if self._is_fa else "👁️ Most Viewed"
        s3 = "🗳️ بیشترین رأی" if self._is_fa else "🗳️ Most Votes"
        self.cmb_popular_kind.addItem(s1, "score")
        self.cmb_popular_kind.addItem(s2, "views")
        self.cmb_popular_kind.addItem(s3, "voters")
        filter_row.addWidget(self.cmb_popular_kind)
        dept_lbl = "گروه:" if self._is_fa else "Department:"
        filter_row.addWidget(QtWidgets.QLabel(dept_lbl))
        self.cmb_popular_dept = self._make_dept_combo(with_all=True)
        filter_row.addWidget(self.cmb_popular_dept)
        load_t = "🔄 بارگذاری" if self._is_fa else "🔄 Load"
        btn_load = QtWidgets.QPushButton(load_t)
        btn_load.setObjectName("primaryButton")
        btn_load.setMinimumWidth(120)
        btn_load.clicked.connect(self._on_load_popular_clicked)
        filter_row.addWidget(btn_load)
        filter_row.addStretch()
        lay.addLayout(filter_row)

        hint_t = "💡 روی هر ردیف دوبار کلیک کنید تا آمار همان استاد باز شود." if self._is_fa else "💡 Double-click any row to view full stats."
        hint = QtWidgets.QLabel(hint_t)
        hint.setObjectName("statusLabel")
        lay.addWidget(hint)

        self.popular_table = QtWidgets.QTableWidget()
        self.popular_table.setColumnCount(5)
        pop_headers = ["رتبه", "استاد", "گروه", "امتیاز", "تعداد رأی"] if self._is_fa else ["Rank", "Professor", "Department", "Rating", "Votes"]
        self.popular_table.setHorizontalHeaderLabels(pop_headers)
        self.popular_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.popular_table.verticalHeader().setVisible(False)
        self.popular_table.setAlternatingRowColors(True)
        self.popular_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.popular_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.popular_table.cellDoubleClicked.connect(self._on_popular_row_activated)
        lay.addWidget(self.popular_table, stretch=1)

    # ═════════════════════════════════════════════════════════
    # Tab 5: Suggest
    # ═════════════════════════════════════════════════════════
    def _setup_suggest_tab(self) -> None:
        lay = QtWidgets.QVBoxLayout(self.tab_suggest)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        grp_t = "استاد موردنظر در فهرست نیست؟" if self._is_fa else "Professor not listed?"
        group = QtWidgets.QGroupBox(grp_t)
        grid = QtWidgets.QGridLayout(group)
        dept_lbl = "گروه آموزشی:" if self._is_fa else "Department:"
        grid.addWidget(QtWidgets.QLabel(dept_lbl), 0, 0)
        self.cmb_suggest_dept = self._make_dept_combo()
        grid.addWidget(self.cmb_suggest_dept, 0, 1)
        inst_lbl = "نام استاد:" if self._is_fa else "Professor Name:"
        grid.addWidget(QtWidgets.QLabel(inst_lbl), 1, 0)
        self.txt_suggest_inst = QtWidgets.QLineEdit()
        self.txt_suggest_inst.setPlaceholderText("مثال: دکتر مریم حسینی" if self._is_fa else "e.g. Dr. John Smith")
        grid.addWidget(self.txt_suggest_inst, 1, 1)
        lay.addWidget(group)

        note_t = "پیشنهاد شما پس از بررسی مسئولین به فهرست اضافه می‌شود. با تشکر از کمک شما 🌸" if self._is_fa else "Your suggestion will be reviewed and added to the directory. Thank you! 🌸"
        note = QtWidgets.QLabel(note_t)
        note.setObjectName("statusLabel")
        note.setWordWrap(True)
        lay.addWidget(note)

        sug_btn_t = "💡 ارسال پیشنهاد" if self._is_fa else "💡 Submit Suggestion"
        btn = QtWidgets.QPushButton(sug_btn_t)
        btn.setObjectName("primaryButton")
        btn.setMinimumHeight(40)
        btn.clicked.connect(self._on_suggest_clicked)
        lay.addWidget(btn)
        lay.addStretch()

    # ═════════════════════════════════════════════════════════
    # Data bootstrap & selectors
    # ═════════════════════════════════════════════════════════
    def _bootstrap_data(self) -> None:
        """Load departments + full instructor directory + summary in parallel."""
        def _deps_success(departments: List[str]):
            self._departments = departments or []
            # (Re)fill every department combo in the dialog
            for combo in (self.cmb_stats_dept, self.cmb_submit_dept,
                          self.cmb_suggest_dept, self.cmb_popular_dept):
                current = combo.currentData()
                combo.blockSignals(True)
                combo.clear()
                if combo is self.cmb_popular_dept:
                    combo.addItem("همه گروه‌ها", "")
                for d in self._departments:
                    combo.addItem(d, d)
                if current is not None:
                    idx = combo.findData(current)
                    combo.setCurrentIndex(max(0, idx))
                combo.blockSignals(False)
            for row in self.cmp_rows:
                current = row["dept"].currentData()
                row["dept"].blockSignals(True)
                row["dept"].clear()
                for d in self._departments:
                    row["dept"].addItem(d, d)
                if current is not None:
                    idx = row["dept"].findData(current)
                    row["dept"].setCurrentIndex(max(0, idx))
                row["dept"].blockSignals(False)
            self.lbl_stats_status.setText(
                f"✅ {len(self._departments)} گروه دریافت شد — اکنون یک گروه و استاد انتخاب کنید."
            )

        def _deps_error(err: str):
            self.lbl_stats_status.setText(f"⚠️ دریافت فهرست گروه‌ها ناموفق بود: {err}")

        self._manager.fetch_departments(_deps_success, _deps_error)

        def _dir_success(rows: List[Dict[str, Any]]):
            self._directory = rows or []
            self._reload_stats_instructors()
            self._refill_inst_combo(self.submit_picker)

        def _dir_error(err: str):
            logger.warning("Instructor directory load failed: %s", err)

        self._manager.search_directory(query="", department="", on_success=_dir_success, on_error=_dir_error)
        self._refresh_summary()

    def _dept_of_row(self, row: Dict[str, Any]) -> str:
        return str(row.get("department_name", "") or "")

    def _instructor_names_for(self, dept: str, filter_text: str = "") -> List[str]:
        """Distinct instructor names for a department, optionally filtered."""
        def _norm(s: str) -> str:
            return (s or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ").strip()

        names = set()
        for row in self._directory:
            if dept and self._dept_of_row(row) != dept:
                continue
            name = str(row.get("instructor_name", "") or "").strip()
            if name:
                names.add(name)
        result = sorted(names)
        if filter_text:
            q = _norm(filter_text)
            result = [n for n in result if q in _norm(n)]
        return result

    def _refill_inst_combo(self, picker: Dict[str, Any]) -> None:
        """Refill an instructor combo for its (own) department context."""
        combo: QtWidgets.QComboBox = picker["combo"]
        combo.blockSignals(True)
        combo.clear()
        dept = self._combo_dept_for(picker)
        filter_text = picker["filter"].text().strip()
        names = self._instructor_names_for(dept, filter_text)
        if names:
            for name in names:
                combo.addItem(name, name)  # userData=name distinguishes real items
        else:
            combo.addItem("— استادی یافت نشد —", None)
        combo.blockSignals(False)

    def _combo_dept_for(self, picker: Dict[str, Any]) -> str:
        """Resolve which department combo belongs to a picker (by identity)."""
        if picker is self.stats_picker:
            return str(self.cmb_stats_dept.currentData() or "")
        if picker is self.submit_picker:
            return str(self.cmb_submit_dept.currentData() or "")
        for row in self.cmp_rows:
            if picker is row["picker"]:
                return str(row["dept"].currentData() or "")
        return ""

    def _on_dept_combo_changed(self, combo: QtWidgets.QComboBox) -> None:
        """Department changed anywhere → refresh dependent instructor combos."""
        if combo is self.cmb_stats_dept:
            self._reload_stats_instructors()
        elif combo is self.cmb_submit_dept:
            self._refill_inst_combo(self.submit_picker)
        elif combo is self.cmb_popular_dept:
            return  # refreshed on demand
        else:
            for row in self.cmp_rows:
                if row["dept"] is combo:
                    self._refill_inst_combo(row["picker"])
                    return

    def _reload_stats_instructors(self) -> None:
        self._refill_inst_combo(self.stats_picker)
        combo = self.stats_picker["combo"]
        if combo.count() > 0 and combo.currentData() is not None:
            # Auto-fetch stats for the (auto-selected) first instructor so the
            # panel is never blank after a department switch.
            self._on_stats_inst_selected()
        elif combo.count() > 0:
            self.lbl_stats_status.setText("در این گروه استادی ثبت نشده است؛ گروه دیگری را انتخاب کنید.")

    def _refresh_summary(self) -> None:
        def _ok(res: Dict[str, Any]):
            self._user_review_count = int(res.get("userReviewCount", 0) or 0)
            self._has_contributed = bool(res.get("hasContributed", self._user_review_count > 0))
            self.lbl_summary_badge.setText(
                f"✨ {res.get('departmentCount', '—')} گروه · {res.get('instructorCount', '—')} استاد"
                f" · نظرات شما: {self._user_review_count}"
            )
            self._apply_gate()

        def _err(_err: str):
            self._has_contributed = None  # unknown → open access
            self.lbl_summary_badge.setText("✨ نظرسنجی زنده دانشجوها")
            self._apply_gate()

        self._manager.fetch_summary(_ok, _err)

    def _apply_gate(self) -> None:
        locked = self._has_contributed is False
        self.gate_card.setVisible(locked)
        self.stats_scroll.setVisible(not locked)
        self.lbl_stats_status.setVisible(not locked)

    # ═════════════════════════════════════════════════════════
    # Tab-switch syncing
    # ═════════════════════════════════════════════════════════
    def _on_tab_changed(self, index: int) -> None:
        if self.tab_widget.widget(index) is self.tab_submit:
            # Mirror the current search-tab selection into the submit tab
            dept = str(self.cmb_stats_dept.currentData() or "")
            if dept:
                idx = self.cmb_submit_dept.findData(dept)
                if idx >= 0:
                    self.cmb_submit_dept.setCurrentIndex(idx)
            inst = self.stats_picker["combo"].currentText()
            if inst and not inst.startswith("—"):
                idx = self.submit_picker["combo"].findText(inst)
                if idx >= 0:
                    self.submit_picker["combo"].setCurrentIndex(idx)
            self.lbl_myreview_state.setText(
                "اگر قبلاً برای این استاد نظر داده‌اید، با «بارگذاری نظر قبلی من» آن را ویرایش کنید."
            )

    # ═════════════════════════════════════════════════════════
    # Stats flow
    # ═════════════════════════════════════════════════════════
    def _on_stats_inst_selected(self) -> None:
        inst = self.stats_picker["combo"].currentText()
        if not inst or inst.startswith("—"):
            return
        dept = str(self.cmb_stats_dept.currentData() or "")
        self._fetch_stats(dept, inst)

    def _fetch_stats(self, dept: str, inst: str) -> None:
        self.lbl_stats_status.setText(f"⏳ در حال دریافت آمار «{inst}»…")

        def _ok(stats: Optional[ProfessorStats]):
            self._last_stats = stats
            if stats is None:
                self._clear_stats_area()
                self.lbl_stats_status.setText(
                    f"برای «{inst}» هنوز آماری ثبت نشده. می‌توانید اولین نظر را شما ثبت کنید!"
                )
                return
            self._render_stats(stats, dept or stats.department_name, inst)
            self.lbl_stats_status.setText(
                f"✅ آمار «{inst}» بر اساس {stats.total_voters} رأی نمایش داده شد."
            )
            self._manager.track_view(department=dept or stats.department_name, instructor=inst)

        def _err(err: str):
            self._clear_stats_area()
            self.lbl_stats_status.setText(f"⚠️ دریافت آمار ناموفق بود: {err}")

        self._manager.fetch_stats(department=dept, instructor=inst, on_success=_ok, on_error=_err)

    def _clear_stats_area(self) -> None:
        while self.stats_lay.count():
            item = self.stats_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_stats(self, stats: ProfessorStats, dept: str, inst: str) -> None:
        self._clear_stats_area()
        p = theme_manager.palette()

        # Header card with big overall score
        head = QtWidgets.QFrame()
        head.setObjectName("statHeadCard")
        head_lay = QtWidgets.QHBoxLayout(head)
        head_lay.setContentsMargins(14, 10, 14, 10)

        name_col = QtWidgets.QVBoxLayout()
        name_lbl = QtWidgets.QLabel(f"👤 {inst}")
        name_lbl.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {p['text']}; border: none;")
        dept_lbl = QtWidgets.QLabel(f"🏫 {dept}" if dept else "")
        dept_lbl.setStyleSheet(f"color: {p['muted']}; font-size: 10pt; border: none;")
        name_col.addWidget(name_lbl)
        name_col.addWidget(dept_lbl)
        head_lay.addLayout(name_col, stretch=1)

        score = calc_display_score(stats)
        color = get_score_color_hex(score)
        score_lbl = QtWidgets.QLabel(f"{score:.1f}")
        score_lbl.setStyleSheet(f"font-size: 30pt; font-weight: bold; color: {color}; border: none;")
        score_cap_t = "امتیاز کلی" if self._is_fa else "Overall Rating"
        score_cap = QtWidgets.QLabel(score_cap_t)
        score_cap.setStyleSheet(f"color: {p['muted']}; font-size: 8.5pt; border: none;")
        score_col = QtWidgets.QVBoxLayout()
        score_col.addWidget(score_lbl, alignment=Qt.AlignCenter)
        score_col.addWidget(score_cap, alignment=Qt.AlignCenter)
        head_lay.addLayout(score_col)
        self.stats_lay.addWidget(head)

        # Score bars
        sb1 = "🎙️ کیفیت تدریس" if self._is_fa else "🎙️ Teaching Quality"
        sb2 = "📝 نمره‌دهی و ارفاق" if self._is_fa else "📝 Grading & Leniency"
        sb3 = "📚 حجم تکالیف" if self._is_fa else "📚 Assignments"
        sb4 = "🔥 سختی امتحان" if self._is_fa else "🔥 Exam Difficulty"
        self.stats_lay.addWidget(ScoreBar(sb1, stats.teaching_avg))
        self.stats_lay.addWidget(ScoreBar(sb2, stats.grading_avg))
        self.stats_lay.addWidget(ScoreBar(sb3, stats.assignments_avg))
        self.stats_lay.addWidget(ScoreBar(sb4, stats.exam_difficulty_avg, inverse=True))

        # Meta info line
        votes_lbl = f"🗳️ {stats.total_voters} رأی" if self._is_fa else f"🗳️ {stats.total_voters} votes"
        views_lbl = f"👁️ {stats.view_count} بازدید" if self._is_fa else f"👁️ {stats.view_count} views"
        meta_parts = [votes_lbl, views_lbl]
        if stats.telegram_has_data and stats.telegram_effective_voters:
            tg_lbl = f"📊 شامل {stats.telegram_effective_voters} رأی تلگرام (وزن ۰٫۴)" if self._is_fa else f"📊 Includes {stats.telegram_effective_voters} Telegram votes"
            meta_parts.append(tg_lbl)
        meta = QtWidgets.QLabel("   ·   ".join(meta_parts))
        meta.setStyleSheet(f"color: {p['muted']}; font-size: 9.5pt; border: none;")
        self.stats_lay.addWidget(meta)

        # Jump to review button
        review_row = QtWidgets.QHBoxLayout()
        review_row.addStretch()
        btn_rev_t = f"✍️ ثبت / ویرایش نظر من برای «{inst}»" if self._is_fa else f"✍️ Review '{inst}'"
        btn_review = QtWidgets.QPushButton(btn_rev_t)
        btn_review.setObjectName("primaryButton")
        btn_review.setMinimumWidth(300)
        btn_review.setMinimumHeight(38)
        btn_review.clicked.connect(lambda: self.tab_widget.setCurrentWidget(self.tab_submit))
        review_row.addWidget(btn_review)
        self.stats_lay.addLayout(review_row)
        self.stats_lay.addStretch()

    # ═════════════════════════════════════════════════════════
    # Cloud auth helper
    # ═════════════════════════════════════════════════════════
    def _ensure_cloud_auth(self) -> bool:
        if self._token_manager is not None:
            try:
                if self._token_manager.has_valid_token():
                    return True
            except Exception:  # noqa: BLE001
                pass
        try:
            from app.ui.account_auth_dialog import AccountAuthDialog
            if self._auth_client is not None:
                dialog = AccountAuthDialog(
                    auth_client=self._auth_client,
                    token_manager=self._token_manager,
                    parent=self,
                )
                dialog.exec_()
                if self._token_manager is not None and self._token_manager.has_valid_token():
                    return True
        except Exception as err:  # noqa: BLE001
            logger.warning("Cloud auth prompt failed: %s", err)
        QtWidgets.QMessageBox.warning(
            self, "ورود لازم است",
            "برای ثبت نظر ابتدا باید به حساب کاربری گلستون وارد شوید."
        )
        return False

    def _selected_attendance(self) -> str:
        for value, radio in self.radio_att.items():
            if radio.isChecked():
                return value
        return "normal"

    def _submit_selection(self) -> Optional[tuple]:
        dept = str(self.cmb_submit_dept.currentData() or "").strip()
        inst = self.submit_picker["combo"].currentText().strip()
        if not dept or not inst or inst.startswith("—"):
            QtWidgets.QMessageBox.warning(
                self, "انتخاب ناقص",
                "لطفاً ابتدا گروه آموزشی و نام استاد را از فهرست‌ها انتخاب کنید."
            )
            return None
        return (dept, inst)

    # ═════════════════════════════════════════════════════════
    # My-review actions
    # ═════════════════════════════════════════════════════════
    def _on_submit_review_clicked(self) -> None:
        if not self._ensure_cloud_auth():
            return
        selection = self._submit_selection()
        if selection is None:
            return
        dept, inst = selection

        def _ok(_res: dict):
            QtWidgets.QMessageBox.information(
                self, "ثبت شد 🎉",
                "نظر شما به‌صورت کاملاً ناشناس ثبت شد.\n"
                "با ثبت نظر، آمار و مقایسه اساتید برایتان باز می‌شود."
            )
            self._manager._cache_stats.clear()
            self._refresh_summary()
            if self.stats_picker["combo"].currentText() == inst:
                self._fetch_stats(dept, inst)

        def _err(err: str):
            QtWidgets.QMessageBox.critical(self, "خطا در ثبت نظر", f"ثبت نظر ناموفق بود:\n{err}")

        self._manager.submit_review(
            department_name=dept,
            instructor_name=inst,
            teaching_score=self.slider_teaching.value(),
            assignments_score=self.slider_assign.value(),
            grading_score=self.slider_grading.value(),
            exam_difficulty_score=self.slider_exam.value(),
            attendance_sensitivity=self._selected_attendance(),
            on_success=_ok,
            on_error=_err,
        )

    def _on_load_my_review_clicked(self) -> None:
        if not self._ensure_cloud_auth():
            return
        selection = self._submit_selection()
        if selection is None:
            return
        dept, inst = selection

        def _ok(review):
            if review is None:
                self.lbl_myreview_state.setText(
                    f"برای «{inst}» هنوز نظری از شما ثبت نشده است."
                )
                return
            self.slider_teaching.setValue(int(review.teaching_score))
            self.slider_assign.setValue(int(review.assignments_score))
            self.slider_grading.setValue(int(review.grading_score))
            self.slider_exam.setValue(int(review.exam_difficulty_score))
            for value, radio in self.radio_att.items():
                radio.setChecked(review.attendance_sensitivity == value)
            updated = (review.updated_at or "")[:19].replace("T", " ")
            self.lbl_myreview_state.setText(
                f"✅ نظر قبلی بارگذاری شد (آخرین به‌روزرسانی: {updated or '—'}). "
                "با ثبت مجدد، نظر قبلی جایگزین می‌شود."
            )

        def _err(err: str):
            QtWidgets.QMessageBox.critical(self, "خطا", f"دریافت نظر شما ناموفق بود:\n{err}")

        self._manager.fetch_my_review(department=dept, instructor=inst, on_success=_ok, on_error=_err)

    def _on_delete_my_review_clicked(self) -> None:
        if not self._ensure_cloud_auth():
            return
        selection = self._submit_selection()
        if selection is None:
            return
        dept, inst = selection
        confirm = QtWidgets.QMessageBox.question(
            self, "حذف نظر",
            f"نظر شما برای «{inst}» حذف شود؟",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        def _ok(_res: dict):
            QtWidgets.QMessageBox.information(self, "موفقیت", "نظر شما حذف شد.")
            self._manager._cache_stats.clear()
            self._refresh_summary()

        def _err(err: str):
            QtWidgets.QMessageBox.critical(self, "خطا", f"حذف نظر ناموفق بود:\n{err}")

        self._manager.delete_my_review(department=dept, instructor=inst, on_success=_ok, on_error=_err)

    # ═════════════════════════════════════════════════════════
    # Compare
    # ═════════════════════════════════════════════════════════
    def _on_compare_clicked(self) -> None:
        targets = []
        for row in self.cmp_rows:
            dept = str(row["dept"].currentData() or "")
            inst = row["picker"]["combo"].currentText().strip()
            if inst and not inst.startswith("—"):
                targets.append({"department": dept, "instructor": inst})
        if len(targets) < 2:
            QtWidgets.QMessageBox.warning(
                self, "تعداد ناکافی",
                "برای مقایسه، حداقل در دو ردیف استاد انتخاب کنید."
            )
            return

        self.lbl_cmp_status.setText("⏳ در حال دریافت آمار اساتید انتخاب‌شده…")

        def _ok(results: List[ProfessorStats]):
            self.lbl_cmp_status.setText(f"✅ مقایسه {len(results)} استاد آماده است.")
            self._render_compare_table(results)

        def _err(err: str):
            self.lbl_cmp_status.setText(f"⚠️ مقایسه ناموفق بود: {err}")

        self._manager.compare_professors(targets, on_success=_ok, on_error=_err)

    def _render_compare_table(self, results: List[ProfessorStats]) -> None:
        if not results:
            self.lbl_cmp_status.setText("برای اساتید انتخاب‌شده آماری یافت نشد.")
            return
        headers = ["معیار"] + [s.instructor_name or "—" for s in results]
        self.cmp_table.setColumnCount(len(headers))
        self.cmp_table.setHorizontalHeaderLabels(headers)
        rows = [
            ("امتیاز کلی", [f"{calc_display_score(s):.1f}" for s in results]),
            ("کیفیت تدریس", [f"{s.teaching_avg:.1f}" for s in results]),
            ("نمره‌دهی", [f"{s.grading_avg:.1f}" for s in results]),
            ("حجم تکالیف", [f"{s.assignments_avg:.1f}" for s in results]),
            ("سختی امتحان", [f"{s.exam_difficulty_avg:.1f}" for s in results]),
            ("تعداد رأی", [str(s.total_voters) for s in results]),
        ]
        self.cmp_table.setRowCount(len(rows))
        for r, (criteria, vals) in enumerate(rows):
            c0 = QtWidgets.QTableWidgetItem(criteria)
            c0.setTextAlignment(Qt.AlignCenter)
            self.cmp_table.setItem(r, 0, c0)
            for c, val in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.cmp_table.setItem(r, c + 1, item)

    # ═════════════════════════════════════════════════════════
    # Popular
    # ═════════════════════════════════════════════════════════
    def _on_load_popular_clicked(self) -> None:
        kind = self.cmb_popular_kind.currentData() or "score"
        dept = str(self.cmb_popular_dept.currentData() or "")

        def _ok(rows: List[ProfessorStats]):
            self.popular_table.setRowCount(len(rows))
            for idx, row_stat in enumerate(rows):
                rank = QtWidgets.QTableWidgetItem(f"{idx + 1}")
                rank.setTextAlignment(Qt.AlignCenter)
                self.popular_table.setItem(idx, 0, rank)
                self.popular_table.setItem(idx, 1, QtWidgets.QTableWidgetItem(row_stat.instructor_name))
                self.popular_table.setItem(idx, 2, QtWidgets.QTableWidgetItem(row_stat.department_name))
                score_item = QtWidgets.QTableWidgetItem(f"{calc_display_score(row_stat):.1f}")
                score_item.setTextAlignment(Qt.AlignCenter)
                self.popular_table.setItem(idx, 3, score_item)
                voters_item = QtWidgets.QTableWidgetItem(str(row_stat.total_voters))
                voters_item.setTextAlignment(Qt.AlignCenter)
                self.popular_table.setItem(idx, 4, voters_item)
            if not rows:
                QtWidgets.QMessageBox.information(self, "محبوب‌ها", "موردی یافت نشد.")

        def _err(err: str):
            QtWidgets.QMessageBox.critical(self, "خطا", f"دریافت اساتید محبوب ناموفق بود:\n{err}")

        self._manager.fetch_popular(kind=kind, department=dept, on_success=_ok, on_error=_err)

    def _on_popular_row_activated(self, row: int, _col: int) -> None:
        """Double-click a leaderboard row → open that instructor's stats."""
        inst_item = self.popular_table.item(row, 1)
        dept_item = self.popular_table.item(row, 2)
        if not inst_item or not dept_item:
            return
        inst, dept = inst_item.text(), dept_item.text()

        idx = self.cmb_stats_dept.findData(dept)
        if idx >= 0:
            self.cmb_stats_dept.setCurrentIndex(idx)
        # Wait a tick so the instructor combo refills for the department
        QtCore.QTimer.singleShot(60, lambda: self._select_instructor_and_show(inst))

    def _select_instructor_and_show(self, inst: str) -> None:
        combo = self.stats_picker["combo"]
        idx = combo.findText(inst)
        if idx >= 0:
            combo.setCurrentIndex(idx)  # triggers _on_stats_inst_selected
        else:
            self.lbl_stats_status.setText(f"«{inst}» در فهرست این گروه پیدا نشد.")
        self.tab_widget.setCurrentWidget(self.tab_stats)

    # ═════════════════════════════════════════════════════════
    # Suggest
    # ═════════════════════════════════════════════════════════
    def _on_suggest_clicked(self) -> None:
        if not self._ensure_cloud_auth():
            return
        dept = str(self.cmb_suggest_dept.currentData() or "").strip()
        inst = self.txt_suggest_inst.text().strip()
        if not dept or not inst:
            QtWidgets.QMessageBox.warning(self, "خطا", "لطفاً گروه و نام استاد را وارد کنید.")
            return

        def _after_check(exists_info: Dict[str, Any]):
            if exists_info.get("exists"):
                QtWidgets.QMessageBox.warning(
                    self, "استاد تکراری",
                    exists_info.get("message") or "این استاد قبلاً در سیستم ثبت یا پیشنهاد شده است."
                )
                return

            def _ok(_res: dict):
                QtWidgets.QMessageBox.information(
                    self, "پیشنهاد ثبت شد 🌸",
                    "پیشنهاد شما ثبت شد و پس از بررسی مسئولین اضافه می‌شود."
                )
                self.txt_suggest_inst.clear()

            def _err(err: str):
                QtWidgets.QMessageBox.critical(self, "خطا", f"ارسال پیشنهاد ناموفق بود:\n{err}")

            self._manager.suggest_instructor(department_name=dept, instructor_name=inst,
                                             on_success=_ok, on_error=_err)

        def _check_err(err: str):
            QtWidgets.QMessageBox.critical(self, "خطا", f"بررسی تکراری‌بودن ناموفق بود:\n{err}")

        self._manager.check_instructor_exists(department_name=dept, instructor_name=inst,
                                              on_success=_after_check, on_error=_check_err)

    # ═════════════════════════════════════════════════════════
    # Styling
    # ═════════════════════════════════════════════════════════
    def _apply_styles(self) -> None:
        p = theme_manager.palette()
        self.setStyleSheet(f"""
            ProfessorReviewDialog, QWidget {{
                background-color: {p['bg']};
                color: {p['text']};
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
                font-size: 10pt;
            }}
            QPushButton#btnBackHeader {{
                background-color: {p['tint']};
                color: {p['primary']};
                border: 1.5px solid {p['primary']};
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 9.5pt;
            }}
            QPushButton#btnBackHeader:hover {{
                background-color: {p['primary']};
                color: #ffffff;
            }}
            QPushButton#btnBackFooter {{
                background-color: {p['surface']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton#btnBackFooter:hover {{
                background-color: {p['tint']};
                color: {p['primary']};
                border-color: {p['primary']};
            }}
            QLabel#dialogTitle {{ font-size: 15pt; font-weight: bold; color: {p['text']}; }}
            QLabel#statusLabel {{ color: {p['muted']}; font-size: 9.5pt; }}
            QLabel#summaryBadge {{
                background-color: {p['tint']};
                color: {p['primary']};
                border-radius: 13px;
                padding: 5px 14px;
                font-size: 9.5pt;
                font-weight: bold;
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {p['border']};
                border-radius: 10px;
                margin-top: 12px;
                padding: 14px 10px 10px 10px;
                background-color: {p['surface']};
                color: {p['text_mid']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                right: 12px; padding: 0 6px;
                color: {p['primary']};
            }}
            QComboBox {{
                background-color: {p['surface']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 8px;
                padding: 8px 12px;
                min-height: 18px;
                font-size: 10pt;
            }}
            QComboBox:focus {{ border: 2px solid {p['primary']}; }}
            QComboBox::drop-down {{ border: none; width: 26px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 7px solid {p['muted']};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {p['surface']};
                color: {p['text']};
                selection-background-color: {p['tint']};
                selection-color: {p['text']};
                border: 1px solid {p['border']};
                outline: none;
            }}
            QLineEdit {{
                background-color: {p['surface']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 8px;
                padding: 8px 12px;
                min-height: 18px;
                font-size: 10pt;
            }}
            QLineEdit:focus {{ border: 2px solid {p['primary']}; }}
            QPushButton {{
                background-color: {p['surface']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 8px;
                padding: 9px 16px;
                min-height: 20px;
                font-size: 10pt;
            }}
            QPushButton:hover {{ border-color: {p['primary']}; color: {p['primary']}; }}
            QPushButton:disabled {{ color: {p['muted']}; }}
            QPushButton#primaryButton {{
                background-color: {p['primary']};
                color: {p['primary_text']};
                border: none;
                font-weight: bold;
            }}
            QPushButton#primaryButton:hover {{ background-color: {p['primary_hover']}; }}
            QPushButton#primaryButton:disabled {{ background-color: {p['border']}; color: {p['muted']}; }}
            QPushButton#secondaryButton {{
                background-color: {p['surface']};
                color: {p['text']};
                border: 1px solid {p['border']};
            }}
            QPushButton#secondaryButton:hover {{ border-color: {p['primary']}; color: {p['primary']}; }}
            QTabWidget::pane {{
                border: 1px solid {p['border']};
                background-color: {p['surface']};
                border-radius: 10px;
                margin-top: -1px;
            }}
            QTabBar {{
                qproperty-drawBase: 0;
            }}
            QTabBar::tab {{
                background: {p['bg']};
                color: {p['text_mid']};
                padding: 9px 18px;
                margin-left: 3px;
                margin-right: 3px;
                min-width: 140px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border: 1px solid {p['border']};
                border-bottom: none;
                font-size: 9.5pt;
                font-weight: bold;
                min-height: 24px;
            }}
            QTabBar::tab:hover:!selected {{
                background: {p['surface']};
                color: {p['text']};
            }}
            QTabBar::tab:selected {{
                background: {p['primary']};
                color: {p['primary_text']};
                border-color: {p['primary']};
            }}
            QTabBar::scroller {{
                width: 24px;
            }}
            QSlider::groove:horizontal {{
                height: 8px; border-radius: 4px; background: {p['border']};
            }}
            QSlider::sub-page:horizontal {{
                background: {p['primary']}; border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {p['surface']}; border: 2px solid {p['primary']};
                width: 18px; margin: -7px 0; border-radius: 9px;
            }}
            QRadioButton {{ color: {p['text']}; font-size: 10pt; spacing: 6px; }}
            QTableWidget {{
                background-color: {p['surface']};
                color: {p['text']};
                gridline-color: {p['border']};
                border: 1px solid {p['border']};
                border-radius: 8px;
                alternate-background-color: {p['bg']};
                font-size: 10pt;
            }}
            QHeaderView::section {{
                background-color: {p['bg']};
                color: {p['muted']};
                padding: 9px;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid {p['border']};
                font-size: 10pt;
            }}
            QFrame#gateCard {{
                background-color: {p['tint']};
                border: 2px dashed {p['primary']};
                border-radius: 12px;
            }}
            QLabel#gateTitle {{
                font-size: 13pt;
                font-weight: bold;
                color: {p['primary']};
                border: none;
                background: transparent;
            }}
            QFrame#statHeadCard {{
                background-color: {p['bg']};
                border: 1px solid {p['border']};
                border-radius: 12px;
            }}
            QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{
                background: transparent;
                border: none;
            }}
        """)

    def _retranslate_ui(self) -> None:
        """Retranslate dialog title, buttons, tabs and tooltips to match current language."""
        self._is_fa = (language_manager.get_current_language() == "fa")
        self.setLayoutDirection(Qt.RightToLeft if self._is_fa else Qt.LeftToRight)
        self.setWindowTitle("👨‍🏫 نظرسنجی و مقایسه اساتید" if self._is_fa else "👨‍🏫 Professor Reviews & Comparison")

        if hasattr(self, "btn_back_header") and self.btn_back_header:
            self.btn_back_header.setText("🔙 بازگشت به برنامه هفتگی" if self._is_fa else "🔙 Back to Weekly Schedule")
            self.btn_back_header.setToolTip("بازگشت به صفحه جدول برنامه کلاسی (Esc)" if self._is_fa else "Return to schedule table (Esc)")

        if hasattr(self, "btn_back_footer") and self.btn_back_footer:
            self.btn_back_footer.setText("🔙 بازگشت به صفحه اصلی (برنامه هفتگی)" if self._is_fa else "🔙 Back to Schedule Planner")

        if hasattr(self, "lbl_title") and self.lbl_title:
            self.lbl_title.setText("👨‍🏫 نظرسنجی و مقایسه اساتید" if self._is_fa else "👨‍🏫 Professor Reviews & Comparison")

        if hasattr(self, "tab_widget") and self.tab_widget:
            self.tab_widget.setLayoutDirection(Qt.RightToLeft if self._is_fa else Qt.LeftToRight)
            tab1_t = "🔍 جستجو و آمار اساتید" if self._is_fa else "🔍 Search & Stats"
            tab2_t = "✍️ ثبت نظر و نمره‌دهی" if self._is_fa else "✍️ Submit Review"
            tab3_t = "⚔️ مقایسه اساتید" if self._is_fa else "⚔️ Compare Professors"
            tab4_t = "🔥 برترین اساتید" if self._is_fa else "🔥 Top Rated"
            tab5_t = "💡 پیشنهاد استاد جدید" if self._is_fa else "💡 Suggest New Professor"

            self.tab_widget.setTabText(0, tab1_t)
            self.tab_widget.setTabText(1, tab2_t)
            self.tab_widget.setTabText(2, tab3_t)
            self.tab_widget.setTabText(3, tab4_t)
            self.tab_widget.setTabText(4, tab5_t)

            tt1 = "جستجو، مشخصات و آمار تفصیلی عملکرد اساتید" if self._is_fa else "Search and view detailed professor stats"
            tt2 = "ثبت یا ویرایش نظر و نمره‌دهی به استاد" if self._is_fa else "Rate professor and submit review"
            tt3 = "مقایسه همزمان اساتید در شاخص‌های مختلف" if self._is_fa else "Compare multiple professors side-by-side"
            tt4 = "رتبه‌بندی برترین و محبوب‌ترین اساتید دانشگاه" if self._is_fa else "Rankings of top professors"
            tt5 = "پیشنهاد ثبت استاد جدید در سامانه" if self._is_fa else "Suggest a new professor to be added"

            self.tab_widget.setTabToolTip(0, tt1)
            self.tab_widget.setTabToolTip(1, tt2)
            self.tab_widget.setTabToolTip(2, tt3)
            self.tab_widget.setTabToolTip(3, tt4)
            self.tab_widget.setTabToolTip(4, tt5)

        self._apply_styles()

    def _on_language_changed(self, lang_code: Optional[str] = None) -> None:
        """Live language switch: re-apply widget translations and refresh views."""
        self._retranslate_ui()
        if hasattr(self, "_on_tab_changed") and hasattr(self, "tab_widget"):
            self._on_tab_changed(self.tab_widget.currentIndex())

    def _on_theme_changed(self, theme_name: Optional[str] = None) -> None:
        """Live theme switch: re-apply widget styles and refresh views."""
        self._apply_styles()
        if hasattr(self, "_on_tab_changed") and hasattr(self, "tab_widget"):
            self._on_tab_changed(self.tab_widget.currentIndex())


