# -*- coding: utf-8 -*-
"""
Golestoon Cloud Account Auth Center PyQt5 Dialog.

This module provides the AccountAuthDialog for logging into Golestoon Cloud Account,
creating new student accounts, inspecting current session tokens, and logging out.

Architecture Layer: Layer 5 (Presentation & UI)
Dependencies: `PyQt5`, `AuthClient`, `TokenManager`, `DESIGN.md` Tokens.
"""

import logging
from typing import Optional, Dict, Any
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QThread

from app.core.network.clients.auth_client import AuthClient
from app.core.auth.token_manager import TokenManager
from app.core.network.models import AuthResponseModel, UserModel
from app.core.network.exceptions import GolestoonNetworkError
from app.core.error_humanizer import humanize_error

logger = logging.getLogger("golestoon.ui.account_auth_dialog")
class CloudLoginWorker(QThread):
    """Background worker thread for cloud login."""
    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, auth_client: AuthClient, email: str, password: str) -> None:
        super().__init__()
        self._client = auth_client
        self._email = email
        self._pass = password

    def run(self) -> None:
        try:
            res = self._client.login(email=self._email, password=self._pass)
            self.finished_signal.emit(res)
        except Exception as err:
            self.error_signal.emit(str(err))
class CloudSignupWorker(QThread):
    """Background worker thread for cloud account signup."""
    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, auth_client: AuthClient, full_name: str, email: str, password: str) -> None:
        super().__init__()
        self._client = auth_client
        self._full_name = full_name
        self._email = email
        self._pass = password

    def run(self) -> None:
        try:
            res = self._client.signup(full_name=self._full_name, email=self._email, password=self._pass)
            self.finished_signal.emit(res)
        except Exception as err:
            self.error_signal.emit(str(err))
class AccountAuthDialog(QtWidgets.QDialog):
    """
    Main PyQt5 Dialog for Golestoon Cloud Account Authentication & Session Management.
    """

    account_changed = pyqtSignal()

    def __init__(
        self,
        auth_client: AuthClient,
        token_manager: TokenManager,
        parent: Optional[QtWidgets.QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._auth_client: AuthClient = auth_client
        self._token_manager: TokenManager = token_manager
        self._active_worker: Optional[QThread] = None

        self.setWindowTitle("حساب کاربری گلستون")
        self.resize(480, 420)
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()
        self._apply_styles()
        self._check_initial_auth_state()

    def _setup_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Header Title
        title_box = QtWidgets.QHBoxLayout()
        icon_lbl = QtWidgets.QLabel("🔐")
        icon_lbl.setStyleSheet("font-size: 20pt;")
        title_box.addWidget(icon_lbl)

        title_lbl = QtWidgets.QLabel("ورود و مدیریت حساب کاربری گلستون")
        title_lbl.setStyleSheet("font-size: 13pt; font-weight: bold; color: #f8fafc;")
        title_box.addWidget(title_lbl)
        title_box.addStretch()
        main_layout.addLayout(title_box)

        # Subtitle description
        desc_lbl = QtWidgets.QLabel(
            "با ورود به حساب گلستون، برنامه‌های کلاسی شما به صورت ابری ذخیره شده "
            "و امکان مشاهده نظرات اساتید و همگام‌سازی بین دستگاه‌ها فراهم می‌شود."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        main_layout.addWidget(desc_lbl)

        # Tabs for Login / Signup / Profile
        self.tab_widget = QtWidgets.QTabWidget()
        
        self.tab_login = QtWidgets.QWidget()
        self.tab_signup = QtWidgets.QWidget()
        self.tab_profile = QtWidgets.QWidget()

        self.tab_widget.addTab(self.tab_login, "ورود به حساب")
        self.tab_widget.addTab(self.tab_signup, "ثبت‌نام کاربر جدید")
        self.tab_widget.addTab(self.tab_profile, "وضعیت سشن")

        main_layout.addWidget(self.tab_widget)

        self._setup_login_tab()
        self._setup_signup_tab()
        self._setup_profile_tab()

        # Guest button / Footer
        footer_layout = QtWidgets.QHBoxLayout()
        self.btn_guest = QtWidgets.QPushButton("ورود به عنوان مهمان (آفلاین)")
        self.btn_guest.setStyleSheet("background: transparent; color: #94a3b8; border: none; text-decoration: underline;")
        self.btn_guest.setCursor(Qt.PointingHandCursor)
        self.btn_guest.clicked.connect(self.reject)
        footer_layout.addWidget(self.btn_guest)
        footer_layout.addStretch()

        btn_close = QtWidgets.QPushButton("بستن")
        btn_close.clicked.connect(self.reject)
        footer_layout.addWidget(btn_close)
        main_layout.addLayout(footer_layout)

    # ─────────────────────────────────────────────────────────
    # Tab 1: Login
    # ─────────────────────────────────────────────────────────
    def _setup_login_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_login)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        self.txt_login_email = QtWidgets.QLineEdit()
        self.txt_login_email.setPlaceholderText("ایمیل خود را وارد کنید...")
        form.addRow("ایمیل کاربر:", self.txt_login_email)

        self.txt_login_pass = QtWidgets.QLineEdit()
        self.txt_login_pass.setEchoMode(QtWidgets.QLineEdit.Password)
        self.txt_login_pass.setPlaceholderText("رمز عبور...")
        form.addRow("رمز عبور:", self.txt_login_pass)

        layout.addLayout(form)
        layout.addSpacing(10)

        self.btn_login = QtWidgets.QPushButton("🔑 ورود به حساب گلستون")
        self.btn_login.setObjectName("primaryButton")
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.clicked.connect(self._on_login_clicked)
        layout.addWidget(self.btn_login)
        layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # Tab 2: Signup
    # ─────────────────────────────────────────────────────────
    def _setup_signup_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_signup)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        self.txt_signup_name = QtWidgets.QLineEdit()
        self.txt_signup_name.setPlaceholderText("نام و نام خانوادگی...")
        form.addRow("نام کامل:", self.txt_signup_name)

        self.txt_signup_email = QtWidgets.QLineEdit()
        self.txt_signup_email.setPlaceholderText("ایمیل معتبر (مثال: student@uni.ac.ir)...")
        form.addRow("ایمیل کاربر:", self.txt_signup_email)

        self.txt_signup_pass = QtWidgets.QLineEdit()
        self.txt_signup_pass.setEchoMode(QtWidgets.QLineEdit.Password)
        self.txt_signup_pass.setPlaceholderText("رمز عبور حداقل ۶ کاراکتر...")
        form.addRow("رمز عبور:", self.txt_signup_pass)

        layout.addLayout(form)
        layout.addSpacing(10)

        btn_signup = QtWidgets.QPushButton("🚀 ساخت حساب کاربری جدید")
        btn_signup.setObjectName("primaryButton")
        btn_signup.setCursor(Qt.PointingHandCursor)
        btn_signup.clicked.connect(self._on_signup_clicked)
        layout.addWidget(btn_signup)
        layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # Tab 3: Active Profile
    # ─────────────────────────────────────────────────────────
    def _setup_profile_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_profile)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.lbl_profile_info = QtWidgets.QLabel("در حال حاضر وارد حساب کاربری نشده‌اید.")
        self.lbl_profile_info.setWordWrap(True)
        self.lbl_profile_info.setStyleSheet("color: #94a3b8; font-size: 10pt;")
        layout.addWidget(self.lbl_profile_info)

        self.btn_logout = QtWidgets.QPushButton("🚪 خروج از حساب کاربری")
        self.btn_logout.setStyleSheet("background-color: #ef4444; color: #ffffff; border-radius: 6px; padding: 8px 14px; font-weight: bold;")
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.clicked.connect(self._on_logout_clicked)
        layout.addWidget(self.btn_logout)
        layout.addStretch()

    # ─────────────────────────────────────────────────────────
    # Business Logic Slots
    # ─────────────────────────────────────────────────────────
    def _check_initial_auth_state(self) -> None:
        if self._token_manager.has_token():
            self.lbl_profile_info.setText("🟢 حساب کاربری شما فعال است.\nاطلاعات ورود شما به‌صورت ایمن ذخیره شده است.")
            self.tab_widget.setTabEnabled(0, False)
            self.tab_widget.setTabEnabled(1, False)
            self.tab_widget.setCurrentIndex(2)
        else:
            self.lbl_profile_info.setText("⚪ شما در حال حاضر وارد حساب کاربری نشده‌اید.")
            self.btn_logout.hide()

    def _on_login_clicked(self) -> None:
        email = self.txt_login_email.text().strip()
        password = self.txt_login_pass.text().strip()
        if not email or not password:
            QtWidgets.QMessageBox.warning(self, "تکمیل اطلاعات", "لطفاً ایمیل و رمز عبور را وارد کنید.")
            return

        worker = CloudLoginWorker(auth_client=self._auth_client, email=email, password=password)

        def _on_success(auth_res: AuthResponseModel):
            self._token_manager.save_token(auth_res.token)
            display_name = getattr(auth_res.user, 'email', 'کاربر گرامی')
            if hasattr(auth_res.user, 'user_metadata') and auth_res.user.user_metadata and auth_res.user.user_metadata.full_name:
                display_name = auth_res.user.user_metadata.full_name
            QtWidgets.QMessageBox.information(self, "موفقیت", f"خوش آمدید، {display_name}!\nورود با موفقیت انجام شد.")
            self.account_changed.emit()
            self.accept()

        def _on_error(err_msg: str):
            user_friendly = humanize_error(err_msg, "ورود به حساب انجام نشد. لطفاً ایمیل و رمز عبور خود را بررسی کرده و مجدداً تلاش کنید.")
            QtWidgets.QMessageBox.critical(self, "خطا در ورود", user_friendly)

        worker.finished_signal.connect(_on_success)
        worker.error_signal.connect(_on_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

    def _on_signup_clicked(self) -> None:
        name = self.txt_signup_name.text().strip()
        email = self.txt_signup_email.text().strip()
        password = self.txt_signup_pass.text().strip()

        if not email or not password:
            QtWidgets.QMessageBox.warning(self, "خطا", "لطفاً ایمیل و رمز عبور را وارد کنید.")
            return

        worker = CloudSignupWorker(auth_client=self._auth_client, full_name=name, email=email, password=password)

        def _on_success(auth_res: AuthResponseModel):
            self._token_manager.save_token(auth_res.token)
            QtWidgets.QMessageBox.information(self, "موفقیت", "حساب کاربری جدید با موفقیت ساخته شد.")
            self.account_changed.emit()
            self.accept()

        def _on_error(err_msg: str):
            user_friendly = humanize_error(err_msg, "ساخت حساب کاربری انجام نشد. لطفاً اتصال اینترنت خود را بررسی کرده یا ایمیل دیگری انتخاب کنید.")
            QtWidgets.QMessageBox.critical(self, "خطا در ثبت‌نام", user_friendly)

        worker.finished_signal.connect(_on_success)
        worker.error_signal.connect(_on_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

    def _on_logout_clicked(self) -> None:
        self._token_manager.clear_token()
        QtWidgets.QMessageBox.information(self, "خروج از حساب", "از حساب کاربری با موفقیت خارج شدید.")
        self.account_changed.emit()
        self.accept()

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-
                color: #f8fafc;
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                background-
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #1e293b;
                color: #94a3b8;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 9.5pt;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #3b82f6;
                color: #ffffff;
            }
            QLineEdit {
                background-
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
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton#primaryButton:hover {
                background-color: #2563eb;
            }
        """)
