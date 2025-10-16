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

class GolestanCredentialsDialog(QDialog):
    """Dialog for entering Golestan credentials securely."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ورود به گلستان")
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedSize(450, 280)  # Wider and taller dialog to accommodate show password checkbox
        self.setLayoutDirection(Qt.RightToLeft)  # RTL layout
        
        # Initialize UI components
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)  # Expand margins
        
        # Title
        title_label = QLabel("ورود به سامانه گلستان")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel("لطفاً اطلاعات ورود به گلستان را وارد کنید:")
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)
        
        # Student number input
        student_layout = QHBoxLayout()
        student_layout.setSpacing(12)
        student_label = QLabel("شماره دانشجویی:")
        self.student_input = QLineEdit()
        self.student_input.setPlaceholderText("شماره دانشجویی خود را وارد کنید")
        self.student_input.setStyleSheet("""
            QLineEdit {
                font-size: 12px;
                padding: 4px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                color: black;
            }
        """)
        student_layout.addWidget(student_label)
        student_layout.addWidget(self.student_input)
        layout.addLayout(student_layout)
        
        # Password input
        password_layout = QHBoxLayout()
        password_layout.setSpacing(12)
        password_label = QLabel("رمز عبور:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("رمز عبور گلستان خود را وارد کنید")
        self.password_input.setStyleSheet("""
            QLineEdit {
                font-size: 12px;
                padding: 4px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                color: black;
            }
        """)
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        layout.addLayout(password_layout)
        
        # Show password checkbox
        self.show_password_checkbox = QCheckBox("نمایش رمز عبور")
        self.show_password_checkbox.setChecked(False)
        self.show_password_checkbox.stateChanged.connect(self.toggle_password_visibility)
        layout.addWidget(self.show_password_checkbox)
        
        # Remember credentials checkbox
        self.remember_checkbox = QCheckBox("ذخیره اطلاعات ورود برای واکشی خودکار")
        self.remember_checkbox.setChecked(True)
        layout.addWidget(self.remember_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.cancel_button = QPushButton("انصراف")
        self.ok_button = QPushButton("تایید")
        self.ok_button.setDefault(True)
        self.ok_button.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 8px 16px;")
        self.cancel_button.setStyleSheet("padding: 8px 16px;")
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Connect signals
        self.cancel_button.clicked.connect(self.reject)
        self.ok_button.clicked.connect(self.validate_and_accept)
        self.student_input.returnPressed.connect(self.focus_password)
        self.password_input.returnPressed.connect(self.validate_and_accept)
        
    def toggle_password_visibility(self, state):
        """Toggle password visibility based on checkbox state."""
        if state == Qt.Checked:
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
        
    def focus_password(self):
        """Focus on password input when Enter is pressed in student number field."""
        self.password_input.setFocus()
        
    def validate_and_accept(self):
        """Validate inputs and accept dialog if valid."""
        student_number = self.student_input.text().strip()
        password = self.password_input.text()
        
        # Validate student number
        if not student_number:
            QMessageBox.warning(self, "خطا", "لطفاً شماره دانشجویی را وارد کنید.")
            self.student_input.setFocus()
            return
            
        # Check if student number is numeric and at least 5 digits
        if not re.match(r'^\d{5,}$', student_number):
            QMessageBox.warning(self, "خطا", "شماره دانشجویی باید عددی و حداقل ۵ رقم باشد.")
            self.student_input.setFocus()
            self.student_input.selectAll()
            return
            
        if not password:
            QMessageBox.warning(self, "خطا", "لطفاً رمز عبور را وارد کنید.")
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
        Save credentials if user requested to remember them.
        
        Args:
            student_number: Golestan student number
            password: Golestan password
            remember: Whether to save credentials
            
        Returns:
            bool: True if saved successfully or not requested to save, False on error
        """
        if remember:
            success = save_local_credentials(student_number, password, remember)
            if success:
                QMessageBox.information(
                    self, 
                    "موفقیت", 
                    "اطلاعات ورود گلستان با موفقیت ذخیره شد. این اطلاعات فقط روی این دستگاه نگهداری می‌شود."
                )
            else:
                QMessageBox.warning(
                    self, 
                    "خطا", 
                    "خطا در ذخیره اطلاعات ورود. لطفاً دوباره تلاش کنید."
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
    
    if result[0] is not None:  # Not cancelled
        student_number, password, remember = result
        # Try to save credentials if requested
        if dialog.save_credentials(student_number, password, remember):
            return (student_number, password)
        else:
            # If saving failed, return None to indicate failure
            return (None, None)
    
    # Cancelled or saving failed
    return (None, None)