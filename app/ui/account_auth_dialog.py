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
from app.core.network.config import is_api_configured
from app.core.error_humanizer import humanize_error
from app.core.language_manager import language_manager

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
    Fully supports bilingual i18n (Persian / English) and dynamic RTL/LTR layouts.
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
        self._is_fa = (language_manager.get_current_language() == 'fa')

        self.setWindowTitle("حساب کاربری گلستون" if self._is_fa else "Golestoon User Account")
        self.resize(480, 420)
        self.setLayoutDirection(Qt.RightToLeft if self._is_fa else Qt.LeftToRight)

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

        header_text = "ورود و مدیریت حساب کاربری گلستون" if self._is_fa else "Golestoon Account Center"
        title_lbl = QtWidgets.QLabel(header_text)
        title_lbl.setStyleSheet("font-size: 13pt; font-weight: bold; color: #f8fafc;")
        title_box.addWidget(title_lbl)
        title_box.addStretch()
        main_layout.addLayout(title_box)

        # Subtitle description
        desc_text = (
            "با ورود به حساب گلستون، برنامه‌های کلاسی شما به صورت ابری ذخیره شده "
            "و امکان مشاهده نظرات اساتید و همگام‌سازی بین دستگاه‌ها فراهم می‌شود."
            if self._is_fa else
            "Sign in to your Golestoon account to sync schedules across devices and unlock professor reviews."
        )
        desc_lbl = QtWidgets.QLabel(desc_text)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        main_layout.addWidget(desc_lbl)

        if not is_api_configured():
            offline_msg = (
                "💡 برنامه در حالت آفلاین (بدون سرور ابری) است. برای استفاده از برنامه، گزینه «ورود به عنوان مهمان (آفلاین)» را انتخاب کنید."
                if self._is_fa else
                "💡 Running in offline mode (no cloud server). Click 'Continue as Guest (Offline)' below to use the app."
            )
            self.lbl_offline_banner = QtWidgets.QLabel(offline_msg)
            self.lbl_offline_banner.setWordWrap(True)
            self.lbl_offline_banner.setStyleSheet("background-color: #1e293b; color: #fbbf24; border: 1px dashed #d97706; border-radius: 6px; padding: 7px 10px; font-size: 9pt;")
            main_layout.addWidget(self.lbl_offline_banner)

        # Tabs for Login / Signup / Profile
        self.tab_widget = QtWidgets.QTabWidget()
        
        self.tab_login = QtWidgets.QWidget()
        self.tab_signup = QtWidgets.QWidget()
        self.tab_profile = QtWidgets.QWidget()

        tab1_t = "ورود به حساب" if self._is_fa else "Sign In"
        tab2_t = "ثبت‌نام کاربر جدید" if self._is_fa else "Sign Up"
        tab3_t = "وضعیت سشن" if self._is_fa else "Session Status"

        self.tab_widget.addTab(self.tab_login, tab1_t)
        self.tab_widget.addTab(self.tab_signup, tab2_t)
        self.tab_widget.addTab(self.tab_profile, tab3_t)

        main_layout.addWidget(self.tab_widget)

        self._setup_login_tab()
        self._setup_signup_tab()
        self._setup_profile_tab()

        # Guest button / Footer
        footer_layout = QtWidgets.QHBoxLayout()
        guest_t = "ورود به عنوان مهمان (آفلاین)" if self._is_fa else "Continue as Guest (Offline)"
        self.btn_guest = QtWidgets.QPushButton(guest_t)
        self.btn_guest.setStyleSheet("background: transparent; color: #94a3b8; border: none; text-decoration: underline;")
        self.btn_guest.setCursor(Qt.PointingHandCursor)
        self.btn_guest.clicked.connect(self.reject)
        footer_layout.addWidget(self.btn_guest)
        footer_layout.addStretch()

        close_t = "بستن" if self._is_fa else "Close"
        btn_close = QtWidgets.QPushButton(close_t)
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
        self.txt_login_email.setPlaceholderText("student@example.com" if not self._is_fa else "ایمیل خود را وارد کنید...")
        email_lbl = "ایمیل کاربر:" if self._is_fa else "Email:"
        form.addRow(email_lbl, self.txt_login_email)

        self.txt_login_pass = QtWidgets.QLineEdit()
        self.txt_login_pass.setEchoMode(QtWidgets.QLineEdit.Password)
        self.txt_login_pass.setPlaceholderText("••••••••" if not self._is_fa else "رمز عبور...")
        pass_lbl = "رمز عبور:" if self._is_fa else "Password:"
        form.addRow(pass_lbl, self.txt_login_pass)

        layout.addLayout(form)
        layout.addSpacing(10)

        btn_t = "🔑 ورود به حساب گلستون" if self._is_fa else "🔑 Sign In"
        self.btn_login = QtWidgets.QPushButton(btn_t)
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
        self.txt_signup_name.setPlaceholderText("John Doe" if not self._is_fa else "نام و نام خانوادگی...")
        name_lbl = "نام کامل:" if self._is_fa else "Full Name:"
        form.addRow(name_lbl, self.txt_signup_name)

        self.txt_signup_email = QtWidgets.QLineEdit()
        self.txt_signup_email.setPlaceholderText("student@uni.ac.ir" if not self._is_fa else "ایمیل معتبر (مثال: student@uni.ac.ir)...")
        email_lbl = "ایمیل کاربر:" if self._is_fa else "Email:"
        form.addRow(email_lbl, self.txt_signup_email)

        self.txt_signup_pass = QtWidgets.QLineEdit()
        self.txt_signup_pass.setEchoMode(QtWidgets.QLineEdit.Password)
        self.txt_signup_pass.setPlaceholderText("At least 6 characters..." if not self._is_fa else "رمز عبور حداقل ۶ کاراکتر...")
        pass_lbl = "رمز عبور:" if self._is_fa else "Password:"
        form.addRow(pass_lbl, self.txt_signup_pass)

        layout.addLayout(form)
        layout.addSpacing(10)

        signup_t = "🚀 ساخت حساب کاربری جدید" if self._is_fa else "🚀 Create Account"
        btn_signup = QtWidgets.QPushButton(signup_t)
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

        initial_lbl = "در حال حاضر وارد حساب کاربری نشده‌اید." if self._is_fa else "You are currently not signed in."
        self.lbl_profile_info = QtWidgets.QLabel(initial_lbl)
        self.lbl_profile_info.setWordWrap(True)
        self.lbl_profile_info.setStyleSheet("color: #94a3b8; font-size: 10pt;")
        layout.addWidget(self.lbl_profile_info)

        logout_t = "🚪 خروج از حساب کاربری" if self._is_fa else "🚪 Sign Out"
        self.btn_logout = QtWidgets.QPushButton(logout_t)
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
            active_t = (
                "🟢 حساب کاربری شما فعال است.\nاطلاعات ورود شما به‌صورت ایمن ذخیره شده است."
                if self._is_fa else
                "🟢 Your account is active.\nYour login session is securely stored on this device."
            )
            self.lbl_profile_info.setText(active_t)
            self.tab_widget.setTabEnabled(0, False)
            self.tab_widget.setTabEnabled(1, False)
            self.tab_widget.setCurrentIndex(2)
        else:
            inactive_t = "⚪ شما در حال حاضر وارد حساب کاربری نشده‌اید." if self._is_fa else "⚪ You are currently not signed in."
            self.lbl_profile_info.setText(inactive_t)
            self.btn_logout.hide()

    def _on_login_clicked(self) -> None:
        if not is_api_configured():
            title_t = "حالت آفلاین" if self._is_fa else "Offline Mode"
            msg_t = (
                "آدرس سرور ابری (API_URL) در فایل تنظیمات (.env) مشخص نشده است، بنابراین امکان ورود به حساب ابری وجود ندارد.\n\n"
                "• برای استفاده از برنامه، دکمه «ورود به عنوان مهمان (آفلاین)» را انتخاب کنید.\n"
                "• یا آدرس سرور ابری را در فایل app/.env مقداردهی فرمایید."
                if self._is_fa else
                "Cloud server URL (API_URL) is not configured in .env.\n\n"
                "• Click 'Continue as Guest (Offline)' below to use the app.\n"
                "• Or configure API_URL in app/.env to enable cloud sign-in."
            )
            QtWidgets.QMessageBox.information(self, title_t, msg_t)
            return

        email = self.txt_login_email.text().strip()
        password = self.txt_login_pass.text().strip()
        if not email or not password:
            title_t = "تکمیل اطلاعات" if self._is_fa else "Missing Information"
            msg_t = "لطفاً ایمیل و رمز عبور را وارد کنید." if self._is_fa else "Please enter both email and password."
            QtWidgets.QMessageBox.warning(self, title_t, msg_t)
            return

        worker = CloudLoginWorker(auth_client=self._auth_client, email=email, password=password)

        def _on_success(auth_res: AuthResponseModel):
            self._token_manager.save_token(auth_res.token)
            display_name = getattr(auth_res.user, 'email', 'User' if not self._is_fa else 'کاربر گرامی')
            if hasattr(auth_res.user, 'user_metadata') and auth_res.user.user_metadata and auth_res.user.user_metadata.full_name:
                display_name = auth_res.user.user_metadata.full_name
            
            suc_t = "موفقیت" if self._is_fa else "Success"
            welcome_t = f"خوش آمدید، {display_name}!\nورود با موفقیت انجام شد." if self._is_fa else f"Welcome, {display_name}!\nSigned in successfully."
            QtWidgets.QMessageBox.information(self, suc_t, welcome_t)
            self.account_changed.emit()
            self.accept()

        def _on_error(err_msg: str):
            def_msg = "ورود به حساب انجام نشد. لطفاً ایمیل و رمز عبور خود را بررسی کرده و مجدداً تلاش کنید." if self._is_fa else "Login failed. Please check your credentials and try again."
            user_friendly = humanize_error(err_msg, def_msg)
            err_t = "خطا در ورود" if self._is_fa else "Login Error"
            QtWidgets.QMessageBox.critical(self, err_t, user_friendly)

        worker.finished_signal.connect(_on_success)
        worker.error_signal.connect(_on_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

    def _on_signup_clicked(self) -> None:
        if not is_api_configured():
            title_t = "حالت آفلاین" if self._is_fa else "Offline Mode"
            msg_t = (
                "آدرس سرور ابری (API_URL) در فایل تنظیمات (.env) مشخص نشده است، بنابراین امکان ثبت‌نام حساب ابری وجود ندارد.\n\n"
                "• برای استفاده از برنامه، دکمه «ورود به عنوان مهمان (آفلاین)» را انتخاب کنید.\n"
                "• یا آدرس سرور ابری را در فایل app/.env مقداردهی فرمایید."
                if self._is_fa else
                "Cloud server URL (API_URL) is not configured in .env.\n\n"
                "• Click 'Continue as Guest (Offline)' below to use the app.\n"
                "• Or configure API_URL in app/.env to enable cloud registration."
            )
            QtWidgets.QMessageBox.information(self, title_t, msg_t)
            return

        name = self.txt_signup_name.text().strip()
        email = self.txt_signup_email.text().strip()
        password = self.txt_signup_pass.text().strip()

        if not email or not password:
            title_t = "خطا" if self._is_fa else "Error"
            msg_t = "لطفاً ایمیل و رمز عبور را وارد کنید." if self._is_fa else "Please enter email and password."
            QtWidgets.QMessageBox.warning(self, title_t, msg_t)
            return

        worker = CloudSignupWorker(auth_client=self._auth_client, full_name=name, email=email, password=password)

        def _on_success(auth_res: AuthResponseModel):
            self._token_manager.save_token(auth_res.token)
            suc_t = "موفقیت" if self._is_fa else "Success"
            created_t = "حساب کاربری جدید با موفقیت ساخته شد." if self._is_fa else "New account created successfully."
            QtWidgets.QMessageBox.information(self, suc_t, created_t)
            self.account_changed.emit()
            self.accept()

        def _on_error(err_msg: str):
            def_msg = "ساخت حساب کاربری انجام نشد. لطفاً اتصال اینترنت خود را بررسی کرده یا ایمیل دیگری انتخاب کنید." if self._is_fa else "Signup failed. Please check your internet or try another email."
            user_friendly = humanize_error(err_msg, def_msg)
            err_t = "خطا در ثبت‌نام" if self._is_fa else "Signup Error"
            QtWidgets.QMessageBox.critical(self, err_t, user_friendly)

        worker.finished_signal.connect(_on_success)
        worker.error_signal.connect(_on_error)
        if hasattr(worker, 'finished'): worker.finished.connect(worker.deleteLater)
        worker.start()
        self._active_worker = worker

    def _on_logout_clicked(self) -> None:
        self._token_manager.clear_token()
        title_t = "خروج از حساب" if self._is_fa else "Signed Out"
        msg_t = "از حساب کاربری با موفقیت خارج شدید." if self._is_fa else "Signed out of account successfully."
        QtWidgets.QMessageBox.information(self, title_t, msg_t)
        self.account_changed.emit()
        self.accept()

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 10pt;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #1e293b;
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
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 10pt;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                background-color: #0f172a;
                color: #f8fafc;
            }
            QPushButton#primaryButton {
                background-color: #3b82f6;
                color: #ffffff;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton#primaryButton:hover {
                background-color: #2563eb;
            }
        """)
