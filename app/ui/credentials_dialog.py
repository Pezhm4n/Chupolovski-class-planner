#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Credentials dialog for Golestan integration in Golestoon Class Planner.

This module provides a secure dialog for entering Golestan credentials
with masked password input and optional credential saving.
"""

import sys
import re
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QCheckBox, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt
from app.core.credentials import save_local_credentials
from app.core.translator import translator
from app.core.language_manager import language_manager
from app.core.theme_manager import theme_manager
from app.core.credential_validator import validate_student_number, validate_password

class GolestanCredentialsDialog(QDialog):
    """Dialog for entering Golestan credentials securely with full theme and i18n support."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedSize(600, 470)
        self._language_connected = False
        
        # Initialize UI components first
        self.init_ui()
        self._connect_language_signal()
        self._apply_translations()
        self._apply_theme()
        
        try:
            theme_manager.theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass

    def _on_theme_changed(self, theme_name=None):
        """Handle live theme switch."""
        self._apply_theme()

    def _connect_language_signal(self):
        """Connect to language change signal."""
        if not self._language_connected:
            language_manager.language_changed.connect(self._on_language_changed)
            self._language_connected = True
    
    def _on_language_changed(self, _lang):
        """Handle language change."""
        self._apply_translations()
    
    def closeEvent(self, event):
        """Clean up on close."""
        if self._language_connected:
            try:
                language_manager.language_changed.disconnect(self._on_language_changed)
            except (TypeError, RuntimeError):
                pass
            self._language_connected = False
        super().closeEvent(event)
    
    def _apply_translations(self):
        """Apply translations to UI elements."""
        language_manager.apply_layout_direction(self)
        if hasattr(self, 'title_label'):
            self._update_ui_texts()
        
    def _t(self, key, **kwargs):
        """Shortcut for translating credentials dialog strings."""
        return translator.t(f"credentials_dialog.{key}", **kwargs)

    def _is_dark(self) -> bool:
        return theme_manager.get_current_theme() == 'dark'

    def _apply_theme(self):
        """Apply full theme palette to dialog and all child widgets."""
        is_dark = self._is_dark()
        bg_col = "#0f172a" if is_dark else "#ffffff"
        text_col = "#f8fafc" if is_dark else "#0f172a"
        muted_col = "#94a3b8" if is_dark else "#64748b"
        border_col = "#334155" if is_dark else "#cbd5e1"
        check_bg = "#1e293b" if is_dark else "#ffffff"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_col};
                color: {text_col};
                font-family: "Vazirmatn", "Segoe UI", sans-serif;
            }}
            QLabel {{
                color: {text_col};
                font-size: 13px;
            }}
            QCheckBox {{
                color: {text_col};
                font-size: 12px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {border_col};
                border-radius: 4px;
                background-color: {check_bg};
            }}
            QCheckBox::indicator:checked {{
                background-color: #3b82f6;
                border: 2px solid #2563eb;
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid #3b82f6;
            }}
        """)

        if hasattr(self, 'title_label'):
            self.title_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {text_col};")
        if hasattr(self, 'desc_label'):
            self.desc_label.setStyleSheet(f"font-size: 11px; color: {muted_col};")
        if hasattr(self, 'student_label'):
            self.student_label.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {text_col};")
        if hasattr(self, 'password_label'):
            self.password_label.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {text_col};")
        if hasattr(self, 'student_input'):
            self._update_input_style(self.student_input, not self.student_error_label.isVisible())
        if hasattr(self, 'password_input'):
            self._update_input_style(self.password_input, not self.password_error_label.isVisible())
        if hasattr(self, 'cancel_button'):
            btn_bg = "#1e293b" if is_dark else "#f1f5f9"
            btn_border = "#475569" if is_dark else "#cbd5e1"
            self.cancel_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {btn_bg};
                    color: {text_col};
                    border: 1px solid {btn_border};
                    border-radius: 6px;
                    padding: 8px 20px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    border: 1px solid #3b82f6;
                }}
            """)
        if hasattr(self, '_update_ok_button_state'):
            self._update_ok_button_state()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)
        
        # Title
        title_label = QLabel()
        title_label.setAlignment(Qt.AlignCenter)
        self.title_label = title_label
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel()
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        self.desc_label = desc_label
        layout.addWidget(desc_label)
        
        # Add spacing
        layout.addSpacing(6)
        
        student_container = QVBoxLayout()
        student_container.setSpacing(6)
        student_label = QLabel()
        self.student_label = student_label
        student_container.addWidget(student_label)
        
        self.student_input = QLineEdit()
        self.student_input.setMinimumHeight(40)
        self.student_input.setMinimumWidth(400)
        student_container.addWidget(self.student_input)
        
        # Error label for student number
        self.student_error_label = QLabel()
        self.student_error_label.setStyleSheet("""
            color: #e74c3c;
            font-size: 11px;
            padding: 0px;
            margin: 0px;
            min-height: 16px;
        """)
        self.student_error_label.setWordWrap(True)
        self.student_error_label.hide()
        student_container.addWidget(self.student_error_label)
        
        layout.addLayout(student_container)
        
        layout.addSpacing(12)
        
        password_container = QVBoxLayout()
        password_container.setSpacing(6)
        password_container.setContentsMargins(0, 0, 0, 0)
        password_label = QLabel()
        password_label.setStyleSheet("""
             
            font-weight: 600; 
            font-size: 12px;
            padding: 0px;
            margin: 0px;
        """)
        self.password_label = password_label
        password_container.addWidget(password_label)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(40)
        self.password_input.setMinimumWidth(400)
        self.password_input.setStyleSheet("""
            QLineEdit {
                font-size: 13px;
                padding: 10px 14px;
                border: 2px solid #e1e8ed;
                border-radius: 6px;
                background-color: white;
                
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
                background-color: #fefefe;
            }
            QLineEdit:hover {
                
            }
        """)
        password_container.addWidget(self.password_input)
        
        # Error label for password
        self.password_error_label = QLabel()
        self.password_error_label.setStyleSheet("""
            color: #e74c3c;
            font-size: 11px;
            padding: 0px;
            margin: 0px;
            min-height: 16px;
        """)
        self.password_error_label.setWordWrap(True)
        self.password_error_label.hide()
        password_container.addWidget(self.password_error_label)
        
        layout.addLayout(password_container)
        
        layout.addSpacing(12)
        
        checkboxes_layout = QVBoxLayout()
        checkboxes_layout.setSpacing(10)
        checkboxes_layout.setContentsMargins(0, 0, 0, 0)
        
        show_password_container = QHBoxLayout()
        show_password_container.setSpacing(8)
        show_password_container.setContentsMargins(0, 0, 0, 0)
        self.show_password_checkbox = QCheckBox()
        self.show_password_checkbox.setChecked(False)
        self.show_password_checkbox.setStyleSheet("""
            QCheckBox {
                
                font-size: 12px;
                spacing: 0px;
                padding: 0px;
                margin: 0px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border: 2px solid #2980b9;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #3498db;
            }
        """)
        self.show_password_checkbox.setText("")
        show_password_label = QLabel()
        show_password_label.setWordWrap(True)
        show_password_label.setStyleSheet("""
            
            font-size: 12px;
            padding: 0px;
            margin: 0px;
        """)
        self.show_password_label = show_password_label
        self.show_password_checkbox.stateChanged.connect(self.toggle_password_visibility)
        show_password_container.addWidget(self.show_password_checkbox)
        show_password_container.addWidget(show_password_label)
        show_password_container.addStretch()
        checkboxes_layout.addLayout(show_password_container)
        
        remember_container = QHBoxLayout()
        remember_container.setSpacing(8)
        remember_container.setContentsMargins(0, 0, 0, 0)
        self.remember_checkbox = QCheckBox()
        self.remember_checkbox.setChecked(True)
        self.remember_checkbox.setStyleSheet("""
            QCheckBox {
                
                font-size: 12px;
                spacing: 0px;
                padding: 0px;
                margin: 0px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border: 2px solid #2980b9;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #3498db;
            }
        """)
        self.remember_checkbox.setText("")
        remember_label = QLabel()
        remember_label.setWordWrap(True)
        remember_label.setStyleSheet("""
            
            font-size: 12px;
            padding: 0px;
            margin: 0px;
        """)
        self.remember_label = remember_label
        remember_container.addWidget(self.remember_checkbox)
        remember_container.addWidget(remember_label)
        remember_container.addStretch()
        checkboxes_layout.addLayout(remember_container)
        
        layout.addLayout(checkboxes_layout)
        
        layout.addSpacing(12)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        
        self.cancel_button = QPushButton()
        self.cancel_button.setMinimumHeight(38)
        self.cancel_button.setMinimumWidth(90)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                
                border: 2px solid #95a5a6;
                
            }
            QPushButton:pressed {
                
                border: 2px solid #7f8c8d;
            }
        """)
        
        self.ok_button = QPushButton()
        self.ok_button.setDefault(True)
        self.ok_button.setMinimumHeight(38)
        self.ok_button.setMinimumWidth(100)
        self.ok_button.setEnabled(False)  # Initially disabled until validation passes
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #bdc3c7;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-
            }
        """)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Connect signals
        self.cancel_button.clicked.connect(self.reject)
        self.ok_button.clicked.connect(self.validate_and_accept)
        self.student_input.returnPressed.connect(self.focus_password)
        self.password_input.returnPressed.connect(self.validate_and_accept)
        
        # Connect real-time validation
        self.student_input.textChanged.connect(self.validate_student_number_realtime)
        self.password_input.textChanged.connect(self.validate_password_realtime)
        
        # Apply translations to UI elements
        self._update_ui_texts()
    
    def _update_ui_texts(self):
        """Update all UI texts with translations."""
        self.setWindowTitle(self._t("window_title"))
        self.title_label.setText(self._t("title"))
        self.desc_label.setText(self._t("description"))
        self.student_label.setText(self._t("student_number_label"))
        self.student_input.setPlaceholderText(self._t("student_number_placeholder"))
        self.password_label.setText(self._t("password_label"))
        self.password_input.setPlaceholderText(self._t("password_placeholder"))
        if hasattr(self, 'show_password_label'):
            self.show_password_label.setText(self._t("show_password"))
        if hasattr(self, 'remember_label'):
            self.remember_label.setText(self._t("remember_credentials"))
        self.cancel_button.setText(self._t("cancel_button"))
        self.ok_button.setText(self._t("ok_button"))
        
    def toggle_password_visibility(self, state):
        """Toggle password visibility based on checkbox state."""
        if state == Qt.Checked:
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
        
    def focus_password(self):
        """Focus on password input when Enter is pressed in student number field."""
        self.password_input.setFocus()
    
    def validate_student_number_realtime(self, text):
        """Validate student number in real-time as user types."""
        student_number = text.strip()
        
        # Don't show error if field is empty (user is still typing)
        if not student_number:
            self.student_error_label.hide()
            self._update_input_style(self.student_input, is_valid=True)
            self._update_ok_button_state()
            return
        
        is_valid, error_message = validate_student_number(student_number)
        
        if is_valid:
            self.student_error_label.hide()
            self._update_input_style(self.student_input, is_valid=True)
        else:
            self.student_error_label.setText(error_message)
            self.student_error_label.show()
            self._update_input_style(self.student_input, is_valid=False)
        
        self._update_ok_button_state()
    
    def validate_password_realtime(self, text):
        """Validate password in real-time as user types."""
        password = text
        
        # Don't show error if field is empty (user is still typing)
        if not password:
            self.password_error_label.hide()
            self._update_input_style(self.password_input, is_valid=True)
            self._update_ok_button_state()
            return
        
        is_valid, error_message = validate_password(password)
        
        if is_valid:
            self.password_error_label.hide()
            self._update_input_style(self.password_input, is_valid=True)
        else:
            self.password_error_label.setText(error_message)
            self.password_error_label.show()
            self._update_input_style(self.password_input, is_valid=False)
        
        self._update_ok_button_state()
    
    def _update_input_style(self, input_widget, is_valid):
        """Update input widget style based on validation state with explicit text colors."""
        is_dark = self._is_dark()
        if is_valid:
            bg_col = "#1e293b" if is_dark else "#ffffff"
            text_col = "#f8fafc" if is_dark else "#0f172a"
            border_col = "#475569" if is_dark else "#cbd5e1"
            focus_bg = "#0f172a" if is_dark else "#ffffff"

            input_widget.setStyleSheet(f"""
                QLineEdit {{
                    font-size: 13px;
                    padding: 10px 14px;
                    border: 1.5px solid {border_col};
                    border-radius: 6px;
                    background-color: {bg_col};
                    color: {text_col};
                    selection-background-color: #3b82f6;
                    selection-color: #ffffff;
                }}
                QLineEdit:focus {{
                    border: 2px solid #3b82f6;
                    background-color: {focus_bg};
                    color: {text_col};
                }}
            """)
        else:
            bg_col = "#3a1d28" if is_dark else "#fff5f5"
            text_col = "#f8fafc" if is_dark else "#0f172a"
            input_widget.setStyleSheet(f"""
                QLineEdit {{
                    font-size: 13px;
                    padding: 10px 14px;
                    border: 2px solid #ef4444;
                    border-radius: 6px;
                    background-color: {bg_col};
                    color: {text_col};
                    selection-background-color: #ef4444;
                    selection-color: #ffffff;
                }}
                QLineEdit:focus {{
                    border: 2px solid #dc2626;
                    background-color: {bg_col};
                    color: {text_col};
                }}
            """)
    
    def _update_ok_button_state(self):
        """Enable/disable OK button based on validation state."""
        student_number = self.student_input.text().strip()
        password = self.password_input.text()
        
        student_valid, _ = validate_student_number(student_number)
        password_valid, _ = validate_password(password)
        
        is_dark = self._is_dark()
        self.ok_button.setEnabled(student_valid and password_valid)
        
        if not (student_valid and password_valid):
            disabled_bg = "#334155" if is_dark else "#cbd5e1"
            disabled_text = "#64748b" if is_dark else "#94a3b8"
            self.ok_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {disabled_bg};
                    color: {disabled_text};
                    border: none;
                    border-radius: 6px;
                    padding: 8px 20px;
                    font-size: 12px;
                    font-weight: bold;
                }}
            """)
        else:
            self.ok_button.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 20px;
                    font-size: 12px;
                    font-weight: bold;
                }}
                QPushButton:hover {
                    background-color: #2563eb;
                }
                QPushButton:pressed {
                    background-color: #1d4ed8;
                }
            """)
        
    def validate_and_accept(self):
        """Validate inputs and accept dialog if valid."""
        student_number = self.student_input.text().strip()
        password = self.password_input.text()
        
        # Validate using the same validators as real-time validation
        student_valid, student_error = validate_student_number(student_number)
        password_valid, password_error = validate_password(password)
        
        if not student_valid:
            # Show error in label if not already visible
            if not self.student_error_label.isVisible():
                self.student_error_label.setText(student_error)
                self.student_error_label.show()
                self._update_input_style(self.student_input, is_valid=False)
            self.student_input.setFocus()
            self.student_input.selectAll()
            return
            
        if not password_valid:
            # Show error in label if not already visible
            if not self.password_error_label.isVisible():
                self.password_error_label.setText(password_error)
                self.password_error_label.show()
                self._update_input_style(self.password_input, is_valid=False)
            self.password_input.setFocus()
            return
            
        # If validation passes, accept the dialog
        self.accept()
        
    def get_credentials(self):
        """
        Get the entered credentials.
        
        Returns:
            tuple: (student_number, password, remember) or (None, None, None) if cancelled
        """
        if self.exec_() == QDialog.Accepted:
            student_number = self.student_input.text().strip()
            password = self.password_input.text()
            remember = self.remember_checkbox.isChecked()
            return (student_number, password, remember)
        else:
            return (None, None, None)
            
    def save_credentials(self, student_number, password, remember):
        """
        Save credentials if requested.
        
        Args:
            student_number: Golestan student number
            password: Golestan password
            remember: Whether to save credentials
            
        Returns:
            bool: True if saved successfully, False on error
        """
        if remember:
            success = save_local_credentials(student_number, password, remember)
            if success:
                QMessageBox.information(
                    self, 
                    self._t("success_title"), 
                    self._t("success_message")
                )
            else:
                QMessageBox.warning(
                    self, 
                    self._t("save_error_title"), 
                    self._t("save_error_message")
                )
                return False
        return True

# Convenience function to show the dialog
def get_golestan_credentials(parent=None):
    """
    Show the Golestan credentials dialog and return entered credentials.
    
    Args:
        parent: Parent widget for the dialog
        
    Returns:
        tuple: (student_number, password) or (None, None) if cancelled
    """
    dialog = GolestanCredentialsDialog(parent)
    result = dialog.get_credentials()
    
    if result[0] is not None:
        student_number, password, remember = result
        if dialog.save_credentials(student_number, password, remember):
            return (student_number, password)
        else:
            return (None, None)
    
    return (None, None)