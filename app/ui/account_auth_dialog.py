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

logger = logging.getLogger("golestoon.ui.account_dialog")


class CloudLoginWorker(QThread):
    """Background worker thread for cloud login."""

    finished_signal = pyqtSignal(object)  # AuthResponseModel
    error_signal = pyqtSignal(str)

    def __init__(self, auth_client: AuthClient, username: str, password: str, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._client: AuthClient = auth_client
        self._username: str = username
        self._password: str = password

    def run(self) -> None:
        try:
            res = self._client.login(username=self._username, password=self._password)
            self.finished_signal.emit(res)
        except GolestoonNetworkError as err:
            self.error_signal.emit(err.message)
        except Exception as err:
            self.error_signal.emit(str(err))


class CloudSignupWorker(QThread):
    """Background worker thread for cloud account signup."""

    finished_signal = pyqtSignal(object)  # AuthResponseModel
    error_signal = pyqtSignal(str)

    def __init__(self, auth_client: AuthClient, username: str, password: str, name: str = "", parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._client: AuthClient = auth_client
        self._username: str = username
        self._password: str = password
        self._name: str = name

    def run(self) -> None:
        try:
            res = self._client.signup(username=self._username, password=self._password, name=self._name)
            self.finished_signal.emit(res)
        except GolestoonNetworkError as err:
            self.error_signal.emit(err.message)
        except Exception as err:
            self.error_signal.emit(str(err))


class AccountAuthDialog(QtWidgets.QDialog):
    """
    Main PyQt5 Dialog for Golestoon Cloud Account Authentication & Session Management.
    """

    account_changed = pyqtSignal()  # Emitted when user logs in or out

    def __init__(self, auth_client: AuthClient, token_manager: TokenManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._auth_client: AuthClient = auth_client
        self._token_manager: TokenManager = token_manager
        self._active_worker: Optional[QThread] = None

        self.setWindowTitle("حساب کاربری ابری گلستون (Golestoon Account Center)")
        self.resize(480, 420)
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()
        self._apply_styles()
        self._check_initial_auth_state()

    def _setup_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Title
        title_lbl = QtWidgets.QLabel("🔐 مدیریت حساب کاربری ابری گلستون")
        title_lbl.setStyleSheet("font-size: 13pt; font-weight: bold; color: #f8fafc;")
        main_layout.addWidget(title_lbl)

        # Main Tab Widget
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setLayoutDirection(Qt.RightToLeft)

        # Tab 1: Login
        self.tab_login = QtWidgets.QWidget()
        self._setup_login_tab()
        self.tab_widget.addTab(self.tab_login, "🔑 ورود به حساب")

        # Tab 2: Signup
        self.tab_signup = QtWidgets.QWidget()
        self._setup_signup_tab()
        self.tab_widget.addTab(self.tab_signup, "📝 ثبت‌نام جدید")

        # Tab 3: Active Profile
        self.tab_profile = QtWidgets.QWidget()
        self._setup_profile_tab()
        self.tab_widget.addTab(self.tab_profile, "👤 پروفایل من")

        main_layout.addWidget(self.tab_widget)

    # ─────────────────────────────────────────────────────────
    # Tab 1: Login
    # ─────────────────────────────────────────────────────────
    def _setup_login_tab(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_login)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        self.txt_login_user = QtWidgets.QLineEdit()
        self.txt_login_user.setPlaceholderText("نام کاربری یا ایمیل...")
        form.addRow("نام کاربری:", self.txt_login_user)

        self.txt_login_pass = QtWidgets.QLineEdit()
        self.txt_login_pass.setEchoMode(QtWidgets.QLineEdit.Password)
        self.txt_login_pass.setPlaceholderText("رمز عبور...")
        form.addRow("رمز عبور:", self.txt_login_pass)

        layout.addLayout(form)
        layout.addSpacing(10)

        btn_login = QtWidgets.QPushButton("🔑 ورود به حساب ابری")
        btn_login.setObjectName("primaryButton")
        btn_login.setCursor(Qt.PointingHandCursor)
        btn_login.clicked.connect(self._on_login_clicked)
        layout.addWidget(btn_login)
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

        self.txt_signup_user = QtWidgets.QLineEdit()
        self.txt_signup_user.setPlaceholderText("نام کاربری دلخواه...")
        form.addRow("نام کاربری:", self.txt_signup_user)

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

        self.lbl_profile_info = QtWidgets.QLabel("در حال حاضر هیچ حساب ابری فعالی وارد نشده است.")
        self.lbl_profile_info.setWordWrap(True)
        self.lbl_profile_info.setStyleSheet("color: #94a3b8; font-size: 10pt;")
        layout.addWidget(self.lbl_profile_info)

        self.btn_logout = QtWidgets.QPushButton("🚪 خروج از حساب ابری")
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
            self.lbl_profile_info.setText("🟢 حساب کاربری ابری شما فعال است.\nتوکن امنیتی در Keyring سیستم‌عامل ذخیره گردیده است.")
            self.tab_widget.setTabEnabled(0, False)
            self.tab_widget.setTabEnabled(1, False)
            self.tab_widget.setCurrentIndex(2)
        else:
            self.lbl_profile_info.setText("⚪ شما در حال حاضر وارد حساب کاربری ابری نشده‌اید.")
            self.btn_logout.hide()

    def _on_login_clicked(self) -> None:
        username = self.txt_login_user.text().strip()
        password = self.txt_login_pass.text().strip()
        if not username or not password:
            QtWidgets.QMessageBox.warning(self, "خطا", "لطفاً نام کاربری و رمز عبور را وارد کنید.")
            return

        worker = CloudLoginWorker(auth_client=self._auth_client, username=username, password=password)

        def _on_success(auth_res: AuthResponseModel):
            self._token_manager.save_token(auth_res.token)
            QtWidgets.QMessageBox.information(self, "موفقیت", f"خوش آمدید، {auth_res.user.username}!\nورود با موفقیت انجام شد.")
            self.account_changed.emit()
            self.accept()

        def _on_error(err_msg: str):
            QtWidgets.QMessageBox.critical(self, "خطا در ورود", f"ورود با خطا مواجه شد:\n{err_msg}")

        worker.finished_signal.connect(_on_success)
        worker.error_signal.connect(_on_error)
        worker.start()
        self._active_worker = worker

    def _on_signup_clicked(self) -> None:
        name = self.txt_signup_name.text().strip()
        username = self.txt_signup_user.text().strip()
        password = self.txt_signup_pass.text().strip()

        if not username or not password:
            QtWidgets.QMessageBox.warning(self, "خطا", "لطفاً نام کاربری و رمز عبور را وارد کنید.")
            return

        worker = CloudSignupWorker(auth_client=self._auth_client, username=username, password=password, name=name)

        def _on_success(auth_res: AuthResponseModel):
            self._token_manager.save_token(auth_res.token)
            QtWidgets.QMessageBox.information(self, "موفقیت", "حساب ابری جدید با موفقیت ساخته و فعال گردید.")
            self.account_changed.emit()
            self.accept()

        def _on_error(err_msg: str):
            QtWidgets.QMessageBox.critical(self, "خطا در ثبت‌نام", f"ثبت‌نام با خطا مواجه شد:\n{err_msg}")

        worker.finished_signal.connect(_on_success)
        worker.error_signal.connect(_on_error)
        worker.start()
        self._active_worker = worker

    def _on_logout_clicked(self) -> None:
        self._token_manager.clear_token()
        QtWidgets.QMessageBox.information(self, "خروج", "از حساب کاربری ابری با موفقیت خارج شدید.")
        self.account_changed.emit()
        self.accept()

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
