# -*- coding: utf-8 -*-
"""
Golestoon Unified Student & Academic Dashboard.

Consolidates student identity, real Golestan transcript sync (via the cloud
backend `POST /api/transcript/sync`), per-semester grades, GPA analytics and
Report 272 degree progress into a single PyQt5 dialog — the desktop
counterpart of golestan-web's Transcript / StudentProfileView pages.

Architecture Layer: Layer 5 (Presentation & UI)
Dependencies: `AcademicManager`, `StudentDatabase`, `AccountAuthDialog`,
`GolestanCredentialsDialog`, `translator`.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QFont, QBrush, QPolygonF

from app.core.translator import translator
from app.core.language_manager import language_manager
from app.core.theme_manager import theme_manager
from app.core.logger import setup_logging
from app.core.rate_limiter import rate_limiter
from app.core.time_utils import format_iran_datetime, get_elapsed_minutes, to_iran_datetime

logger = setup_logging()

# Accent colors (theme-stable, used for chart lines & progress bars)
ACCENT_BLUE = "#2563eb"
ACCENT_GREEN = "#10b981"
ACCENT_PURPLE = "#8b5cf6"
ACCENT_AMBER = "#f59e0b"
ACCENT_CYAN = "#06b6d4"
ACCENT_RED = "#ef4444"


def _darken_if_dark(hex_color: str) -> str:
    """Return the dark-theme counterpart for a light accent color."""
    return {
        ACCENT_BLUE: "#7c86f5",
        ACCENT_GREEN: "#34d399",
        ACCENT_PURPLE: "#b39dfb",
        ACCENT_AMBER: "#fbbf24",
        ACCENT_CYAN: "#22d3ee",
        ACCENT_RED: "#f87171",
    }.get(hex_color, hex_color) if theme_manager.effective_theme() == "dark" else hex_color


class GpaTrendChart(QtWidgets.QWidget):
    """Lightweight painted line chart for per-semester GPA (no extra deps)."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._points: List[Tuple[str, float]] = []
        self.setMinimumHeight(190)

    def set_data(self, points: List[Tuple[str, float]]) -> None:
        self._points = points or []
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        from app.core.theme_manager import theme_manager as _tm
        pal = _tm.palette()
        is_dark = _tm.effective_theme() == "dark"
        chart_bg = pal["surface"]
        grid_color = pal["border"]
        axis_text = pal["muted"]
        line_color = "#7c86f5" if is_dark else "#2563eb"

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width, height = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(chart_bg))

        if len(self._points) < 2:
            painter.setPen(QColor(axis_text))
            painter.drawText(self.rect(), Qt.AlignCenter, translator.t("dashboard.chart.no_data"))
            painter.end()
            return

        margin_l, margin_r, margin_t, margin_b = 44, 20, 16, 34
        plot_w = width - margin_l - margin_r
        plot_h = height - margin_t - margin_b
        values = [v for _, v in self._points]
        v_min, v_max = min(values), max(values)
        if v_max - v_min < 2:
            mid = (v_max + v_min) / 2.0
            v_min, v_max = mid - 1.0, mid + 1.0
        pad = (v_max - v_min) * 0.12
        v_min, v_max = max(0.0, v_min - pad), min(20.0, v_max + pad)

        # Horizontal gridlines (0-20 scale ticks)
        painter.setPen(QPen(QColor(grid_color), 1))
        grid_font = QFont("Vazirmatn", 8)
        painter.setFont(grid_font)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = margin_t + plot_h * (1.0 - frac)
            painter.drawLine(margin_l, int(y), width - margin_r, int(y))
            val = v_min + (v_max - v_min) * frac
            painter.setPen(QColor(axis_text))
            painter.drawText(4, int(y) - 6, 38, 14, Qt.AlignRight, f"{val:.1f}")
            painter.setPen(QPen(QColor(grid_color), 1))

        # GPA line
        n = len(self._points)
        step_x = plot_w / (n - 1)
        polygon = QPolygonF()
        for i, (_, val) in enumerate(self._points):
            x = margin_l + step_x * i
            y = margin_t + plot_h * (1.0 - (val - v_min) / (v_max - v_min))
            polygon.append(QPointF(x, y))

        painter.setPen(QPen(QColor(line_color), 2))
        fill_alpha = 30 if is_dark else 40
        fill_color = QColor(line_color)
        fill_color.setAlpha(fill_alpha)
        fill = QPolygonF(polygon)
        fill.append(QPointF(margin_l + step_x * (n - 1), margin_t + plot_h))
        fill.append(QPointF(margin_l, margin_t + plot_h))
        painter.setBrush(QBrush(fill_color))
        painter.drawPolygon(fill)
        painter.setBrush(Qt.NoBrush)
        painter.drawPolyline(polygon)

        # Points + first/last labels
        painter.setBrush(QBrush(QColor(line_color)))
        for i in range(n):
            painter.drawEllipse(polygon[i], 3.5, 3.5)

        painter.setPen(QColor(axis_text))
        label_step = max(1, n // 6)
        for i in range(0, n, label_step):
            x = margin_l + step_x * i
            painter.drawText(int(x - 34), height - 26, 68, 20,
                             Qt.AlignHCenter, self._points[i][0])

        # Latest value badge
        last_x, last_y = polygon[n - 1].x(), polygon[n - 1].y()
        badge = f"{self._points[n - 1][1]:.2f}"
        painter.setPen(QColor(line_color))
        painter.drawText(QRectF(last_x - 40, max(0.0, last_y - 24), 80, 16),
                         Qt.AlignCenter, badge)
        painter.end()


class UnifiedStudentDashboard(QtWidgets.QWidget):
    """
    Unified Student Dashboard widget embedded directly in the main window:
    real transcript sync, GPA analytics, and Report 272 degree progress.
    """

    back_requested = QtCore.pyqtSignal()

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        network_session: Optional[Any] = None,
        token_manager: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self.student_data = None  # app.scrapers...models.Student | None

        self.setWindowTitle(translator.t("dashboard.title"))
        self.setMinimumSize(760, 540)

        current_lang = language_manager.get_current_language()
        self.setLayoutDirection(Qt.RightToLeft if current_lang == 'fa' else Qt.LeftToRight)

        self._init_networking(network_session, token_manager)
        self._load_cached_student_data()
        self._setup_ui()
        self._apply_styles()
        self._refresh_all()

        # Re-style everything when the global theme changes while open
        try:
            theme_manager.theme_changed.connect(self._on_theme_changed)
            language_manager.language_changed.connect(self._on_language_changed)
        except Exception as err:  # noqa: BLE001 — defensive UI boundary
            logger.warning("Could not subscribe to theme or language changes: %s", err)

    def _on_theme_changed(self) -> None:
        """Live theme switch: re-apply dialog styles and rebuild data widgets."""
        self._apply_styles()
        self._refresh_all()

    def _on_language_changed(self, lang_code: Optional[str] = None) -> None:
        """Live language switch: re-apply translations, layout direction, and refresh."""
        is_fa = (language_manager.get_current_language() == "fa")
        self.setLayoutDirection(Qt.RightToLeft if is_fa else Qt.LeftToRight)
        self.setWindowTitle(translator.t("dashboard.title"))

        if hasattr(self, "btn_back_header") and self.btn_back_header:
            back_header_t = "🔙 بازگشت به برنامه هفتگی" if is_fa else "🔙 Back to Schedule"
            self.btn_back_header.setText(back_header_t)

        if hasattr(self, "btn_back_footer") and self.btn_back_footer:
            back_footer_t = "🔙 بازگشت به صفحه اصلی" if is_fa else "🔙 Back to Main View"
            self.btn_back_footer.setText(back_footer_t)

        if hasattr(self, "btn_sync_golestan") and self.btn_sync_golestan:
            self.btn_sync_golestan.setText(translator.t("dashboard.sync.button"))

        if hasattr(self, "btn_logout_golestan") and self.btn_logout_golestan:
            self.btn_logout_golestan.setText("🚪 خروج از گلستان" if is_fa else "🚪 Logout from Golestan")

        if hasattr(self, "tab_widget") and self.tab_widget:
            self.tab_widget.setLayoutDirection(Qt.RightToLeft if is_fa else Qt.LeftToRight)
            self.tab_widget.setTabText(0, translator.t("dashboard.tab.profile"))
            self.tab_widget.setTabText(1, translator.t("dashboard.tab.transcript"))
            self.tab_widget.setTabText(2, translator.t("dashboard.tab.report272"))

        if hasattr(self, "transcript_table") and self.transcript_table:
            self.transcript_table.setHorizontalHeaderLabels([
                translator.t("dashboard.course.code"),
                translator.t("dashboard.course.name"),
                translator.t("dashboard.course.units"),
                translator.t("dashboard.course.grade"),
                translator.t("dashboard.course.status"),
            ])

        self._apply_styles()
        self._refresh_all()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.back_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    # ─────────────────────────────────────────────────────────
    # Networking setup (reuses the main window session when provided)
    # ─────────────────────────────────────────────────────────
    def _init_networking(self, network_session: Optional[Any], token_manager: Optional[Any]) -> None:
        from app.core import network as net
        from app.core.network.clients.transcript_client import TranscriptClient
        from app.core.academic_manager import AcademicManager

        if network_session is not None:
            self.network_session = network_session
            self.token_manager = token_manager
        else:
            from app.core.auth.token_manager import TokenManager
            self.token_manager = token_manager or TokenManager()
            self.network_session = net.SessionFactory.create_session(
                token_manager=self.token_manager
            )

        self.transcript_client = TranscriptClient(session=self.network_session)
        self.auth_client = net.AuthClient(session=self.network_session)
        self.academic_manager = AcademicManager(client=self.transcript_client, parent=self)
        self._sync_running = False

    def _load_cached_student_data(self) -> None:
        """Load student record from local SQLite cache if available."""
        try:
            from app.core.credentials import load_local_credentials
            from app.data.student_db import StudentDatabase
            creds = load_local_credentials()
            if creds and 'student_number' in creds:
                db = StudentDatabase(creds['student_number'])
                if db.student_exists():
                    self.student_data = db.load_student()
        except Exception as e:
            logger.warning(f"Could not load cached student record: {e}")
            self.student_data = None

    # ─────────────────────────────────────────────────────────
    # UI skeleton
    # ─────────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # 1. Header Banner & Identity Bar
        header_widget = QtWidgets.QWidget()
        header_widget.setObjectName("headerCard")
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(14, 12, 14, 12)

        # Back to Main Schedule Button in Header
        is_fa = (language_manager.get_current_language() == 'fa')
        back_header_t = "🔙 بازگشت به برنامه هفتگی" if is_fa else "🔙 Back to Schedule"
        self.btn_back_header = QtWidgets.QPushButton(back_header_t)
        self.btn_back_header.setObjectName("secondaryButton")
        self.btn_back_header.setCursor(Qt.PointingHandCursor)
        self.btn_back_header.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.btn_back_header)

        avatar_lbl = QtWidgets.QLabel("🎓")
        avatar_lbl.setStyleSheet("font-size: 28pt; padding: 4px;")
        header_layout.addWidget(avatar_lbl)

        text_layout = QtWidgets.QVBoxLayout()
        self.lbl_name = QtWidgets.QLabel()
        self.lbl_name.setStyleSheet("font-size: 13pt; font-weight: bold; background: transparent;")
        self.lbl_sub = QtWidgets.QLabel()
        self.lbl_sub.setStyleSheet("font-size: 10pt; background: transparent;")
        text_layout.addWidget(self.lbl_name)
        text_layout.addWidget(self.lbl_sub)
        header_layout.addLayout(text_layout)
        header_layout.addStretch()

        self.btn_sync_golestan = QtWidgets.QPushButton(translator.t("dashboard.sync.button"))
        self.btn_sync_golestan.setObjectName("primaryButton")
        self.btn_sync_golestan.setCursor(Qt.PointingHandCursor)
        self.btn_sync_golestan.clicked.connect(self._on_sync_clicked)
        header_layout.addWidget(self.btn_sync_golestan)

        logout_golestan_t = "🚪 خروج از گلستان" if is_fa else "🚪 Logout from Golestan"
        self.btn_logout_golestan = QtWidgets.QPushButton(logout_golestan_t)
        self.btn_logout_golestan.setObjectName("dangerButton")
        self.btn_logout_golestan.setCursor(Qt.PointingHandCursor)
        self.btn_logout_golestan.setToolTip("حذف اطلاعات ذخیره‌شده و خروج از سامانه گلستان" if is_fa else "Remove saved credentials and log out of Golestan")
        self.btn_logout_golestan.clicked.connect(self._on_logout_golestan_clicked)
        header_layout.addWidget(self.btn_logout_golestan)

        main_layout.addWidget(header_widget)

        # Stale Transcript Warning Banner (shown when data is >= 30 minutes old)
        self.stale_warning_banner = QtWidgets.QLabel()
        self.stale_warning_banner.setWordWrap(True)
        self.stale_warning_banner.hide()
        main_layout.addWidget(self.stale_warning_banner)

        # 2. Main Tabbed Content
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_profile = QtWidgets.QWidget()
        self.tab_transcript = QtWidgets.QWidget()
        self.tab_report272 = QtWidgets.QWidget()
        self.tab_widget.addTab(self.tab_profile, translator.t("dashboard.tab.profile"))
        self.tab_widget.addTab(self.tab_transcript, translator.t("dashboard.tab.transcript"))
        self.tab_widget.addTab(self.tab_report272, translator.t("dashboard.tab.report272"))
        main_layout.addWidget(self.tab_widget)

        self._setup_profile_tab()
        self._setup_transcript_tab()
        self._setup_report272_tab()

        # 3. Footer
        footer_layout = QtWidgets.QHBoxLayout()
        self.lbl_sync_status = QtWidgets.QLabel("")
        self.lbl_sync_status.setStyleSheet("font-size: 9pt;")
        footer_layout.addWidget(self.lbl_sync_status)
        footer_layout.addStretch()
        
        back_footer_t = "🔙 بازگشت به صفحه اصلی" if is_fa else "🔙 Back to Main View"
        btn_back_footer = QtWidgets.QPushButton(back_footer_t)
        btn_back_footer.setObjectName("secondaryButton")
        btn_back_footer.setCursor(Qt.PointingHandCursor)
        btn_back_footer.clicked.connect(self.back_requested.emit)
        footer_layout.addWidget(btn_back_footer)
        main_layout.addLayout(footer_layout)

    # ─────────────────────────────────────────────────────────
    # Tab 1: Profile & Identity
    # ─────────────────────────────────────────────────────────
    def _setup_profile_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_profile)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        self.profile_group = QtWidgets.QGroupBox(translator.t("dashboard.profile.group"))
        self.profile_grid = QtWidgets.QGridLayout(self.profile_group)
        self.profile_grid.setSpacing(12)
        self.profile_grid.setContentsMargins(14, 18, 14, 14)
        layout.addWidget(self.profile_group)

        self.conn_group = QtWidgets.QGroupBox(translator.t("dashboard.profile.connection"))
        conn_layout = QtWidgets.QVBoxLayout(self.conn_group)
        self.conn_status_lbl = QtWidgets.QLabel()
        self.conn_status_lbl.setWordWrap(True)
        self.conn_status_lbl.setStyleSheet("font-size: 10pt;")
        conn_layout.addWidget(self.conn_status_lbl)
        layout.addWidget(self.conn_group)
        layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # Tab 2: Transcript & GPA Analytics
    # ─────────────────────────────────────────────────────────
    def _setup_transcript_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_transcript)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # GPA Stats cards (populated in _refresh_transcript)
        self.stats_layout = QtWidgets.QHBoxLayout()
        self.stats_layout.setSpacing(10)
        layout.addLayout(self.stats_layout)

        # GPA trend chart
        trend_header = QtWidgets.QHBoxLayout()
        trend_lbl = QtWidgets.QLabel(f"<b>{translator.t('dashboard.chart.title')}</b>")
        trend_header.addWidget(trend_lbl)
        trend_header.addStretch()
        layout.addLayout(trend_header)

        self.gpa_chart = GpaTrendChart()
        layout.addWidget(self.gpa_chart)

        # Semester filter + table
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.addWidget(QtWidgets.QLabel(translator.t("dashboard.transcript.semester")))
        self.semester_combo = QtWidgets.QComboBox()
        self.semester_combo.setMinimumWidth(240)
        self.semester_combo.currentIndexChanged.connect(self._on_semester_changed)
        filter_row.addWidget(self.semester_combo)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.transcript_table = QtWidgets.QTableWidget()
        self.transcript_table.setColumnCount(5)
        self.transcript_table.setHorizontalHeaderLabels([
            translator.t("dashboard.course.code"),
            translator.t("dashboard.course.name"),
            translator.t("dashboard.course.units"),
            translator.t("dashboard.course.grade"),
            translator.t("dashboard.course.status"),
        ])
        self.transcript_table.horizontalHeader().setStretchLastSection(True)
        self.transcript_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.transcript_table.setAlternatingRowColors(True)
        self.transcript_table.verticalHeader().setVisible(False)
        layout.addWidget(self.transcript_table, stretch=1)

    # ─────────────────────────────────────────────────────────
    # Tab 3: Degree Progress (Report 272)
    # ─────────────────────────────────────────────────────────
    def _setup_report272_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_report272)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        self.report272_header = QtWidgets.QLabel()
        self.report272_header.setStyleSheet("font-weight: bold; font-size: 10pt;")
        self.report272_header.setWordWrap(True)
        layout.addWidget(self.report272_header)

        self.report272_summary = QtWidgets.QLabel()
        self.report272_summary.setStyleSheet("font-size: 10pt;")
        self.report272_summary.setWordWrap(True)
        layout.addWidget(self.report272_summary)

        self.report272_container = QtWidgets.QVBoxLayout()
        layout.addLayout(self.report272_container)
        layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # Refresh logic (all tabs)
    # ─────────────────────────────────────────────────────────
    def _refresh_all(self) -> None:
        student = self.student_data
        has_data = student is not None

        # Header
        name_str = getattr(student, 'name', '') if has_data else ''
        id_str = getattr(student, 'student_id', '') if has_data else ''
        self.lbl_name.setText(f"<b>{name_str or translator.t('dashboard.profile.guest')}</b>")
        self.lbl_sub.setText(
            translator.t("dashboard.profile.id_label", id=id_str or "—")
        )

        self._refresh_profile()
        self._refresh_transcript()
        self._refresh_report272()

    def _clear_layout(self, layout: QtWidgets.QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_profile(self) -> None:
        student = self.student_data
        p = theme_manager.palette()
        is_dark = theme_manager.is_dark()
        is_fa = (language_manager.get_current_language() == 'fa')
        grid = self.profile_grid
        self._clear_layout(grid)

        if student is None:
            items: List[Tuple[str, str]] = []
            self.conn_status_lbl.setText(translator.t("dashboard.profile.empty"))
            self.conn_status_lbl.setStyleSheet(f"color: {p['muted']}; font-size: 10pt;")
            if hasattr(self, 'stale_warning_banner'):
                self.stale_warning_banner.hide()
        else:
            updated = getattr(student, 'updated_at', None)
            updated_str = format_iran_datetime(updated, is_persian=is_fa) if updated else '—'
            probation = int(getattr(student, 'total_probation', 0) or 0)
            items = [
                (translator.t("dashboard.profile.faculty"), getattr(student, 'faculty', '') or '—'),
                (translator.t("dashboard.profile.department"), getattr(student, 'department', '') or '—'),
                (translator.t("dashboard.profile.major"), getattr(student, 'major', '') or '—'),
                (translator.t("dashboard.profile.degree"), getattr(student, 'degree_level', '') or '—'),
                (translator.t("dashboard.profile.study_type"), getattr(student, 'study_type', '') or '—'),
                (translator.t("dashboard.profile.enrollment_status"), getattr(student, 'enrollment_status', '') or '—'),
                (translator.t("dashboard.profile.probation"), str(probation)),
                (translator.t("dashboard.profile.last_update"), updated_str),
            ]
            self.conn_status_lbl.setText(
                translator.t("dashboard.profile.synced_ok", date=updated_str)
            )
            self.conn_status_lbl.setStyleSheet(f"color: {p['success']}; font-size: 10pt;")

            # Check for stale transcript data (>= 30 minutes)
            if hasattr(self, 'stale_warning_banner'):
                elapsed_min = get_elapsed_minutes(updated)
                if elapsed_min >= 30:
                    min_int = int(elapsed_min)
                    time_desc = f"{min_int} دقیقه پیش" if is_fa else f"{min_int} minutes ago"
                    stale_msg = (
                        f"⚠️ <b>اطلاعات کارنامه قدیمی و مربوط به {time_desc} است.</b><br/>"
                        f"پیشنهاد می‌شود جهت دریافت آخرین وضعیت و نمرات، روی دکمه <b>«🔄 به‌روزرسانی از گلستان»</b> در بالای صفحه کلیک کنید."
                        if is_fa else
                        f"⚠️ <b>Transcript data is outdated (from {time_desc}).</b><br/>"
                        f"It is recommended to click <b>'🔄 Update from Golestan'</b> above to fetch latest grades."
                    )
                    banner_bg = "#2a1c06" if is_dark else "#fffbeb"
                    banner_border = "#f59e0b"
                    banner_text = "#fde68a" if is_dark else "#92400e"
                    self.stale_warning_banner.setText(stale_msg)
                    self.stale_warning_banner.setStyleSheet(
                        f"background-color: {banner_bg}; color: {banner_text}; border: 1.5px solid {banner_border}; "
                        f"border-radius: 8px; padding: 10px 14px; font-size: 9.5pt;"
                    )
                    self.stale_warning_banner.show()
                else:
                    self.stale_warning_banner.hide()

        row, col = 0, 0
        for title, value in items:
            t_lbl = QtWidgets.QLabel(f"<b>{title}</b>")
            t_lbl.setStyleSheet(f"color: {p['text_mid']}; background: transparent;")
            v_lbl = QtWidgets.QLabel(str(value))
            v_lbl.setStyleSheet(f"color: {p['text']}; font-weight: bold; background: transparent;")
            grid.addWidget(t_lbl, row, col * 2)
            grid.addWidget(v_lbl, row, col * 2 + 1)
            col += 1
            if col > 1:
                col = 0
                row += 1

    def _stat_card(self, title: str, value: str, color: str) -> QtWidgets.QFrame:
        p = theme_manager.palette()
        color = _darken_if_dark(color)
        card = QtWidgets.QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {p['surface']};
                border: 1px solid {p['border']};
                border-right: 4px solid {color};
                border-radius: 8px;
            }}
            QLabel {{ background: transparent; border: none; }}
        """)
        c_lay = QtWidgets.QVBoxLayout(card)
        c_lay.setContentsMargins(14, 10, 14, 10)
        t_lbl = QtWidgets.QLabel(title)
        t_lbl.setStyleSheet(f"color: {p['muted']}; font-size: 9.5pt; border: none;")
        v_lbl = QtWidgets.QLabel(value)
        v_lbl.setStyleSheet(f"color: {color}; font-size: 14pt; font-weight: bold; border: none;")
        c_lay.addWidget(t_lbl)
        c_lay.addWidget(v_lbl)
        return card

    def _refresh_transcript(self) -> None:
        student = self.student_data

        # Stat cards
        self._clear_layout(self.stats_layout)
        if student is None:
            self.stats_layout.addWidget(QtWidgets.QLabel(translator.t("dashboard.transcript.empty")))
            self.gpa_chart.set_data([])
            self.semester_combo.clear()
            self.transcript_table.setRowCount(0)
            return

        overall_gpa = getattr(student, 'overall_gpa', None)
        gpa_str = f"{float(overall_gpa):.2f}" if overall_gpa is not None else "—"
        units_passed = float(getattr(student, 'total_units_passed', 0) or 0)

        from app.core.academic_manager import AcademicManager
        sem_dicts = [self._semester_to_dict(s) for s in student.semesters]
        analytics = AcademicManager.calculate_gpa_analytics(sem_dicts)
        best = analytics.get("best_term")
        best_str = f"{best[1]:.2f}" if best else "—"

        self.stats_layout.addWidget(self._stat_card(translator.t("dashboard.stats.gpa"), gpa_str, ACCENT_BLUE))
        self.stats_layout.addWidget(self._stat_card(
            translator.t("dashboard.stats.units_passed"), f"{units_passed:g}", ACCENT_GREEN))
        self.stats_layout.addWidget(self._stat_card(translator.t("dashboard.stats.best_term"), best_str, ACCENT_PURPLE))

        # GPA chart
        self.gpa_chart.set_data(analytics.get("gpa_trend", []))

        # Semester combo (index 0 = all)
        self.semester_combo.blockSignals(True)
        self.semester_combo.clear()
        self.semester_combo.addItem(translator.t("dashboard.transcript.all_semesters"), None)
        for sem in student.semesters:
            label = sem.semester_description or f"ترم {sem.semester_id}"
            self.semester_combo.addItem(label, sem.semester_id)
        self.semester_combo.blockSignals(False)

        self._fill_transcript_table()

    @staticmethod
    def _semester_to_dict(sem) -> Dict[str, Any]:
        return {
            "semester_id": sem.semester_id,
            "semester_description": sem.semester_description,
            "semester_gpa": float(sem.semester_gpa or 0),
            "units_passed": float(sem.units_passed or 0),
            "units_failed": float(sem.units_failed or 0),
        }

    def _fill_transcript_table(self) -> None:
        student = self.student_data
        table = self.transcript_table
        table.setRowCount(0)
        if student is None:
            return

        selected = self.semester_combo.currentData() if self.semester_combo.count() else None
        rows: List[Tuple[Any, Any]] = []
        for sem in student.semesters:
            if selected is not None and sem.semester_id != selected:
                continue
            for course in sem.courses:
                rows.append((sem, course))

        if not rows:
            table.setRowCount(1)
            table.setItem(0, 1, QtWidgets.QTableWidgetItem(
                translator.t("dashboard.transcript.no_rows")))
            return

        table.setRowCount(len(rows))
        p = theme_manager.palette()
        is_dark = theme_manager.effective_theme() == "dark"
        passed_brush = QtGui.QColor("#6ee7b7" if is_dark else "#065f46")
        failed_brush = QtGui.QColor("#f87171" if is_dark else "#b91c1c")
        for r, (sem, course) in enumerate(rows):
            grade_val = course.grade
            grade_str = f"{float(grade_val):g}" if grade_val is not None else "—"
            state = course.grade_state or ""

            code_item = QtWidgets.QTableWidgetItem(str(course.course_code or '—'))
            name_item = QtWidgets.QTableWidgetItem(str(course.course_name or '—'))
            units_item = QtWidgets.QTableWidgetItem(f"{float(course.course_units or 0):g}")
            grade_item = QtWidgets.QTableWidgetItem(grade_str)
            state_item = QtWidgets.QTableWidgetItem(state or '—')
            code_item.setTextAlignment(Qt.AlignCenter)
            units_item.setTextAlignment(Qt.AlignCenter)
            grade_item.setTextAlignment(Qt.AlignCenter)
            state_item.setTextAlignment(Qt.AlignCenter)

            # Color-code the grade by outcome
            if grade_val is not None:
                g = float(grade_val)
                grade_item.setForeground((passed_brush if g >= 10 else failed_brush))
                state_item.setForeground((passed_brush if g >= 10 else failed_brush))

            table.setItem(r, 0, code_item)
            table.setItem(r, 1, name_item)
            table.setItem(r, 2, units_item)
            table.setItem(r, 3, grade_item)
            table.setItem(r, 4, state_item)

    def _on_semester_changed(self) -> None:
        self._fill_transcript_table()

    # ─────────────────────────────────────────────────────────
    # Report 272 rendering (real server data)
    # ─────────────────────────────────────────────────────────
    def _refresh_report272(self) -> None:
        self._clear_layout(self.report272_container)
        p = theme_manager.palette()
        student = self.student_data
        ds = getattr(student, 'degree_status', None) if student else None

        if ds is None:
            self.report272_header.setText(translator.t("dashboard.report272.title"))
            self.report272_summary.setText(translator.t("dashboard.report272.empty"))
            empty_lbl = QtWidgets.QLabel(translator.t("dashboard.report272.empty_hint"))
            empty_lbl.setWordWrap(True)
            empty_lbl.setStyleSheet(f"color: {p['muted']}; font-size: 10pt;")
            self.report272_container.addWidget(empty_lbl)
            return

        self.report272_header.setText(translator.t("dashboard.report272.title"))
        total_passed = float(ds.total_passed or 0)
        req_min = float(ds.total_required_min or 0)
        req_max = float(ds.total_required_max or 0)
        remaining = float(ds.remaining_units or 0)
        req_label = f"{req_min:g}" if req_min == req_max else f"{req_min:g}–{req_max:g}"
        self.report272_summary.setText(
            translator.t(
                "dashboard.report272.summary",
                passed=f"{total_passed:g}", required=req_label, remaining=f"{remaining:g}",
            )
        )

        palette = [ACCENT_BLUE, ACCENT_GREEN, ACCENT_PURPLE, ACCENT_AMBER, ACCENT_CYAN]
        for ix, cat in enumerate(ds.categories or []):
            passed = float(cat.passed_units or 0)
            cmin = float(cat.min_units or 0)
            cmax = float(cat.max_units or 0)
            target = cmax if cmax > 0 else cmin
            pct = min(100.0, (passed / target * 100.0)) if target > 0 else 0.0
            req_txt = f"{cmin:g}" if cmin == cmax else f"{cmin:g}–{cmax:g}"
            color = palette[ix % len(palette)]

            cat_box = QtWidgets.QWidget()
            c_lay = QtWidgets.QVBoxLayout(cat_box)
            c_lay.setContentsMargins(0, 2, 0, 2)
            c_lay.setSpacing(4)

            header_box = QtWidgets.QHBoxLayout()
            lbl_cat = QtWidgets.QLabel(f"<b>{cat.category_name or '—'}</b>")
            lbl_cat.setStyleSheet(f"color: {p['text_mid']}; background: transparent;")
            lbl_val = QtWidgets.QLabel(
                translator.t("dashboard.report272.category_progress",
                             passed=f"{passed:g}", required=req_txt, pct=int(pct))
            )
            lbl_val.setStyleSheet(f"color: {p['muted']}; font-size: 9.5pt; background: transparent;")
            header_box.addWidget(lbl_cat)
            header_box.addStretch()
            header_box.addWidget(lbl_val)
            c_lay.addLayout(header_box)

            bar_color = _darken_if_dark(color)
            pbar = QtWidgets.QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(int(pct))
            pbar.setTextVisible(False)
            pbar.setFixedHeight(8)
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {p['border']};
                    border-radius: 4px;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: 4px;
                }}
            """)
            c_lay.addWidget(pbar)
            self.report272_container.addWidget(cat_box)

    # ─────────────────────────────────────────────────────────
    # Sync flow
    # ─────────────────────────────────────────────────────────
    def _on_sync_clicked(self) -> None:
        """Real sync: cloud JWT → Golestan credentials → background worker."""
        if self._sync_running:
            return

        if not self._ensure_cloud_auth():
            return

        creds = self._ensure_golestan_credentials()
        if creds is None:
            return
        username, password = creds
        is_fa = (language_manager.get_current_language() == 'fa')

        # 1. Check Distinct Accounts Rate Limiter (Max 3 distinct accounts per 10-minute window)
        allowed_acc, wait_acc_sec = rate_limiter.check_distinct_account_allowed(username)
        if not allowed_acc:
            mins = int(wait_acc_sec // 60)
            secs = int(wait_acc_sec % 60)
            title_t = "محدودیت تعداد اکانت" if is_fa else "Account Limit Exceeded"
            msg_t = (
                f"شما در ۱۰ دقیقه گذشته با ۳ اکانت مجزای گلستان وارد شده‌اید.\n\n"
                f"برای دریافت کارنامه با اکانت جدید، لطفاً {mins} دقیقه و {secs} ثانیه دیگر صبر کنید."
                if is_fa else
                f"You have accessed 3 distinct Golestan accounts in the last 10 minutes.\n\n"
                f"To sync a new account, please wait {mins}m {secs}s."
            )
            QtWidgets.QMessageBox.warning(self, title_t, msg_t)
            return

        # 2. Check Per-Account Refresh Cooldown (Minimum 10 minutes between syncs for the same account)
        allowed_ref, wait_ref_sec = rate_limiter.check_student_refresh_allowed(username)
        if not allowed_ref:
            mins = int(wait_ref_sec // 60)
            secs = int(wait_ref_sec % 60)
            title_t = "محدودیت زمانی به‌روزرسانی" if is_fa else "Refresh Rate Limit"
            msg_t = (
                f"برای جلوگیری از مسدود شدن درخواست‌ها توسط سامانه گلستان، فاصله هر دو به‌روزرسانی باید حداقل ۱۰ دقیقه باشد.\n\n"
                f"زمان باقی‌مانده تا امکان به‌روزرسانی مجدد: {mins} دقیقه و {secs} ثانیه"
                if is_fa else
                f"To prevent request limits on Golestan, updates must be at least 10 minutes apart.\n\n"
                f"Time remaining until next refresh: {mins}m {secs}s"
            )
            QtWidgets.QMessageBox.information(self, title_t, msg_t)
            return

        self._sync_running = True
        self.btn_sync_golestan.setEnabled(False)
        self.btn_sync_golestan.setText(translator.t("dashboard.sync.in_progress"))
        self.lbl_sync_status.setText(translator.t("dashboard.sync.status_running"))
        QtWidgets.QApplication.processEvents()

        try:
            self.academic_manager.sync_transcript(
                golestan_username=username,
                golestan_password=password,
                on_success=lambda s: self._on_sync_success(s, username),
                on_error=self._on_sync_error,
                on_status=self._on_sync_status,
                mode="full",
                force=True,
            )
        except Exception as err:  # noqa: BLE001 — UI boundary
            logger.exception("Failed to start transcript sync")
            self._sync_finished()
            QtWidgets.QMessageBox.critical(
                self, translator.t("dashboard.sync.error_title"), str(err))

    def _ensure_cloud_auth(self) -> bool:
        """Guarantee a valid cloud JWT, prompting login when needed."""
        try:
            tm = self.token_manager
            if tm is not None and tm.has_valid_token():
                return True
        except Exception as err:  # noqa: BLE001 — defensive UI boundary
            logger.warning("Token validation failed: %s", err)

        from app.ui.account_auth_dialog import AccountAuthDialog
        dialog = AccountAuthDialog(
            auth_client=self.auth_client,
            token_manager=self.token_manager,
            parent=self,
        )
        dialog.exec_()

        try:
            if self.token_manager is not None and self.token_manager.has_valid_token():
                return True
        except Exception:  # noqa: BLE001
            pass
        QtWidgets.QMessageBox.warning(
            self,
            translator.t("dashboard.sync.auth_required_title"),
            translator.t("dashboard.sync.auth_required"),
        )
        return False

    def _ensure_golestan_credentials(self) -> Optional[Tuple[str, str]]:
        """Return stored Golestan credentials, prompting the dialog when missing."""
        try:
            from app.core.credentials import load_local_credentials
            creds = load_local_credentials()
            if creds and creds.get('student_number') and creds.get('password'):
                return (creds['student_number'], creds['password'])
        except Exception as err:  # noqa: BLE001 — defensive UI boundary
            logger.warning("Could not load local credentials: %s", err)

        from app.ui.credentials_dialog import get_golestan_credentials
        result = get_golestan_credentials(parent=self)
        if result and result[0]:
            return (result[0], result[1])
        QtWidgets.QMessageBox.warning(
            self,
            translator.t("dashboard.sync.creds_required_title"),
            translator.t("dashboard.sync.creds_required"),
        )
        return None

    def _sync_finished(self) -> None:
        self._sync_running = False
        self.btn_sync_golestan.setEnabled(True)
        self.btn_sync_golestan.setText(translator.t("dashboard.sync.button"))

    def _on_sync_success(self, student, requested_username: str = "") -> None:
        """Worker success callback (main thread via signal)."""
        sid = getattr(student, 'student_id', None) or requested_username
        if sid:
            rate_limiter.record_account_sync(sid)

        self.student_data = student
        self._refresh_all()
        self._sync_finished()
        is_fa = (language_manager.get_current_language() == 'fa')
        updated = getattr(student, 'updated_at', None)
        date_str = format_iran_datetime(updated, is_persian=is_fa) if updated else '—'
        self.lbl_sync_status.setText(
            translator.t("dashboard.sync.status_done", date=date_str or '—'))
        QtWidgets.QMessageBox.information(
            self,
            translator.t("dashboard.sync.done_title"),
            translator.t("dashboard.sync.done_body"),
        )

    def _on_sync_status(self, status: str, message: str) -> None:
        """Non-terminal sync statuses (too_recent / needs_login / queued...)."""
        self._sync_finished()
        self.lbl_sync_status.setText(message)
        QtWidgets.QMessageBox.information(
            self, translator.t("dashboard.sync.status_title"), message)

    def _on_sync_error(self, message: str) -> None:
        """Worker failure callback."""
        self._sync_finished()
        logger.error("Transcript sync failed: %s", message)

        if message.startswith("AUTH_REQUIRED"):
            QtWidgets.QMessageBox.warning(
                self,
                translator.t("dashboard.sync.auth_required_title"),
                translator.t("dashboard.sync.auth_required"),
            )
            return

        if "LOGIN_FAILED" in message or "Invalid" in message:
            retry = QtWidgets.QMessageBox.question(
                self,
                translator.t("dashboard.sync.login_failed_title"),
                translator.t("dashboard.sync.login_failed_body"),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes,
            )
            if retry == QtWidgets.QMessageBox.Yes:
                from app.ui.credentials_dialog import get_golestan_credentials
                get_golestan_credentials(parent=self)
            return

        QtWidgets.QMessageBox.critical(
            self, translator.t("dashboard.sync.error_title"), message)

    def _on_logout_golestan_clicked(self) -> None:
        """Clear saved Golestan student credentials and reset dashboard."""
        is_fa = (language_manager.get_current_language() == 'fa')
        reply = QtWidgets.QMessageBox.question(
            self,
            "خروج از سامانه گلستان" if is_fa else "Logout from Golestan",
            "آیا مایلید اطلاعات ورود گلستان ذخیره‌شده از روی این سیستم پاک شده و از سامانه خارج شوید؟"
            if is_fa else
            "Are you sure you want to remove stored Golestan credentials and log out?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                from app.core.credentials import delete_local_credentials
                delete_local_credentials()
            except Exception as e:
                logger.warning("Error deleting local credentials: %s", e)

            self.student_data = None
            self._refresh_all()
            title_t = "موفقیت" if is_fa else "Success"
            msg_t = "اطلاعات ورود گلستان با موفقیت حذف شد و از سامانه خارج شدید." if is_fa else "Golestan credentials removed successfully."
            QtWidgets.QMessageBox.information(self, title_t, msg_t)

    # ─────────────────────────────────────────────────────────
    # Styling
    # ─────────────────────────────────────────────────────────
    def _apply_styles(self) -> None:
        p = theme_manager.palette()
        self.setStyleSheet(f"""
            UnifiedStudentDashboard {{
                background-color: {p['bg']};
                color: {p['text']};
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
            }}
            QWidget#headerCard {{
                background-color: {p['surface']};
                border: 1px solid {p['border']};
                border-radius: 10px;
            }}
            QLabel {{ color: {p['text']}; background: transparent; }}
            QTabWidget::pane {{
                border: 1px solid {p['border']};
                background-color: {p['surface']};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: {p['bg']};
                color: {p['muted']};
                padding: 10px 20px;
                margin-left: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 10pt;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {p['surface']};
                color: {p['primary']};
                border-bottom: 3px solid {p['primary']};
            }}
            QGroupBox {{
                background-color: {p['surface']};
                border: 1px solid {p['border']};
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: {p['text_mid']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top right;
                padding: 0 8px;
                color: {p['primary']};
            }}
            QTableWidget {{
                background-color: {p['surface']};
                color: {p['text']};
                gridline-color: {p['border']};
                alternate-background-color: {p['bg']};
                border: 1px solid {p['border']};
                border-radius: 6px;
            }}
            QHeaderView::section {{
                background-color: {p['bg']};
                color: {p['muted']};
                border: none;
                border-bottom: 1px solid {p['border']};
                padding: 8px;
                font-weight: bold;
            }}
            QComboBox {{
                background-color: {p['surface']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {p['surface']};
                color: {p['text']};
                selection-background-color: {p['tint']};
                selection-color: {p['text']};
            }}
            QPushButton {{
                background-color: {p['surface']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 9.5pt;
            }}
            QPushButton:hover {{ 
                border-color: {p['primary']}; 
                background-color: {p['tint']};
            }}
            QPushButton#secondaryButton {{
                background-color: {p['surface']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: bold;
            }}
            QPushButton#secondaryButton:hover {{
                border-color: {p['primary']};
                background-color: {p['tint']};
                color: {p['primary']};
            }}
            QPushButton#primaryButton {{
                background-color: {p['primary']};
                color: {p['primary_text']};
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }}
            QPushButton#primaryButton:hover {{
                background-color: {p['primary_hover']};
            }}
            QPushButton#primaryButton:disabled {{
                background-color: {p['border']};
                color: {p['muted']};
            }}
        """)
