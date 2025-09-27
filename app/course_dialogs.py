#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Course dialogs for Schedule Planner
Contains dialogs for adding and editing courses
"""

import os
import sys

# Add the app directory to the Python path to enable imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5 import QtWidgets, QtGui, QtCore
from config import DAYS, TIME_SLOTS, EXTENDED_TIME_SLOTS, COURSES, logger
from data_manager import save_courses_to_json, save_user_data
from course_utils import to_minutes

# ---------------------- Add Course Dialog ----------------------

class AddCourseDialog(QtWidgets.QDialog):
    """Dialog for adding new courses"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('افزودن درس جدید')
        self.setModal(True)
        self.resize(500, 400)

        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.name_edit = QtWidgets.QLineEdit()
        self.code_edit = QtWidgets.QLineEdit()
        self.instructor_edit = QtWidgets.QLineEdit()
        self.location_edit = QtWidgets.QLineEdit()
        self.description_edit = QtWidgets.QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.exam_time_edit = QtWidgets.QLineEdit()
        self.exam_time_edit.setPlaceholderText('مثال: 1403/10/15 - 09:00-11:00')
        self.credits_spin = QtWidgets.QSpinBox()
        self.credits_spin.setRange(0, 10)
        self.credits_spin.setValue(3)

        form.addRow('نام درس:', self.name_edit)
        form.addRow('کد درس (مثال 1142207_01):', self.code_edit)
        form.addRow('نام استاد:', self.instructor_edit)
        form.addRow('محل/کلاس:', self.location_edit)
        form.addRow('توضیحات درس:', self.description_edit)
        form.addRow('زمان امتحان:', self.exam_time_edit)
        form.addRow('تعداد واحد:', self.credits_spin)

        layout.addLayout(form)

        # جلسات: هر جلسه شامل day + start + end + parity
        self.sessions_layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel('جلسات درس (اضافه/حذف کنید):'))
        layout.addLayout(self.sessions_layout)

        btn_row = QtWidgets.QHBoxLayout()
        add_session_btn = QtWidgets.QPushButton('افزودن جلسه')
        add_session_btn.clicked.connect(self.add_session_row)
        remove_session_btn = QtWidgets.QPushButton('حذف جلسه')
        remove_session_btn.clicked.connect(self.remove_session_row)
        btn_row.addWidget(add_session_btn)
        btn_row.addWidget(remove_session_btn)
        layout.addLayout(btn_row)

        # ناحیهٔ پایین برای دکمه‌ها
        dlg_btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        dlg_btns.accepted.connect(self.accept)
        dlg_btns.rejected.connect(self.reject)
        layout.addWidget(dlg_btns)

        # اضافه کردن یک جلسه پیش‌فرض
        self.session_rows = []
        self.add_session_row()

    def add_session_row(self):
        """Add a new session row to the dialog"""
        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        day_cb = QtWidgets.QComboBox()
        day_cb.addItems(DAYS)
        start_cb = QtWidgets.QComboBox()
        end_cb = QtWidgets.QComboBox()
        start_cb.addItems(EXTENDED_TIME_SLOTS)
        end_cb.addItems(EXTENDED_TIME_SLOTS)
        parity_cb = QtWidgets.QComboBox()
        parity_cb.addItems(['', 'ز', 'ف'])
        row_layout.addWidget(day_cb)
        row_layout.addWidget(start_cb)
        row_layout.addWidget(end_cb)
        row_layout.addWidget(parity_cb)
        self.sessions_layout.addWidget(row_widget)
        self.session_rows.append((row_widget, day_cb, start_cb, end_cb, parity_cb))

    def remove_session_row(self):
        """Remove the last session row"""
        if not self.session_rows:
            return
        widget, *_ = self.session_rows.pop()
        widget.setParent(None)

    def get_course_data(self):
        """Get the course data from the dialog inputs"""
        name = self.name_edit.text().strip()
        code = self.code_edit.text().strip()
        instructor = self.instructor_edit.text().strip()
        location = self.location_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        exam_time = self.exam_time_edit.text().strip()
        credits = self.credits_spin.value()
        if not name or not code:
            QtWidgets.QMessageBox.warning(self, 'خطا', 'لطفا نام درس و کد درس را وارد کنید.')
            return None
        sessions = []
        for (_, day_cb, start_cb, end_cb, parity_cb) in self.session_rows:
            day = day_cb.currentText()
            start = start_cb.currentText()
            end = end_cb.currentText()
            parity = parity_cb.currentText()
            # validate times
            try:
                si = EXTENDED_TIME_SLOTS.index(start)
                ei = EXTENDED_TIME_SLOTS.index(end)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, 'خطا', 'ساعت نامعتبر در یکی از جلسات.')
                return None
            if ei <= si:
                QtWidgets.QMessageBox.warning(self, 'خطا', 'زمان پایان باید بعد از شروع باشد.')
                return None
            sessions.append({'day': day, 'start': start, 'end': end, 'parity': parity})
        course = {
            'code': code,
            'name': name,
            'credits': credits,
            'instructor': instructor,
            'schedule': sessions,
            'location': location,
            'description': description or 'توضیحی ارائه نشده',
            'exam_time': exam_time or 'اعلام نشده'
        }
        return course


# ---------------------- Edit Course Dialog ----------------------

class EditCourseDialog(QtWidgets.QDialog):
    """Dialog for editing existing course information"""
    def __init__(self, course_data, parent=None):
        super().__init__(parent)
        self.course_data = course_data
        self.setWindowTitle('ویرایش اطلاعات درس')
        self.setModal(True)
        self.resize(500, 400)

        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        # Pre-fill with existing data
        self.name_edit = QtWidgets.QLineEdit(course_data.get('name', ''))
        self.code_edit = QtWidgets.QLineEdit(course_data.get('code', ''))
        self.instructor_edit = QtWidgets.QLineEdit(course_data.get('instructor', ''))
        self.location_edit = QtWidgets.QLineEdit(course_data.get('location', ''))
        self.description_edit = QtWidgets.QTextEdit()
        self.description_edit.setPlainText(course_data.get('description', ''))
        self.description_edit.setMaximumHeight(80)
        self.exam_time_edit = QtWidgets.QLineEdit(course_data.get('exam_time', ''))
        self.exam_time_edit.setPlaceholderText('مثال: 1403/10/15 - 09:00-11:00')
        self.credits_spin = QtWidgets.QSpinBox()
        self.credits_spin.setRange(0, 10)
        self.credits_spin.setValue(course_data.get('credits', 3))

        form.addRow('نام درس:', self.name_edit)
        form.addRow('کد درس:', self.code_edit)
        form.addRow('نام استاد:', self.instructor_edit)
        form.addRow('محل/کلاس:', self.location_edit)
        form.addRow('توضیحات درس:', self.description_edit)
        form.addRow('زمان امتحان:', self.exam_time_edit)
        form.addRow('تعداد واحد:', self.credits_spin)

        layout.addLayout(form)

        # Sessions
        self.sessions_layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel('جلسات درس:'))
        layout.addLayout(self.sessions_layout)

        btn_row = QtWidgets.QHBoxLayout()
        add_session_btn = QtWidgets.QPushButton('افزودن جلسه')
        add_session_btn.clicked.connect(self.add_session_row)
        remove_session_btn = QtWidgets.QPushButton('حذف جلسه')
        remove_session_btn.clicked.connect(self.remove_session_row)
        btn_row.addWidget(add_session_btn)
        btn_row.addWidget(remove_session_btn)
        layout.addLayout(btn_row)

        # Dialog buttons
        dlg_btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        dlg_btns.accepted.connect(self.accept)
        dlg_btns.rejected.connect(self.reject)
        layout.addWidget(dlg_btns)

        # Load existing sessions
        self.session_rows = []
        for session in course_data.get('schedule', []):
            self.add_session_row(session)
            
        # Add at least one session if none exist
        if not self.session_rows:
            self.add_session_row()

    def add_session_row(self, session_data=None):
        """Add a session row, optionally with pre-filled data"""
        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        
        day_cb = QtWidgets.QComboBox()
        day_cb.addItems(DAYS)
        start_cb = QtWidgets.QComboBox()
        end_cb = QtWidgets.QComboBox()
        start_cb.addItems(EXTENDED_TIME_SLOTS)
        end_cb.addItems(EXTENDED_TIME_SLOTS)
        parity_cb = QtWidgets.QComboBox()
        parity_cb.addItems(['', 'ز', 'ف'])
        
        # Pre-fill if data provided
        if session_data:
            if session_data.get('day') in DAYS:
                day_cb.setCurrentText(session_data['day'])
            if session_data.get('start') in EXTENDED_TIME_SLOTS:
                start_cb.setCurrentText(session_data['start'])
            if session_data.get('end') in EXTENDED_TIME_SLOTS:
                end_cb.setCurrentText(session_data['end'])
            if session_data.get('parity') in ['', 'ز', 'ف']:
                parity_cb.setCurrentText(session_data.get('parity', ''))
        
        row_layout.addWidget(day_cb)
        row_layout.addWidget(start_cb)
        row_layout.addWidget(end_cb)
        row_layout.addWidget(parity_cb)
        
        self.sessions_layout.addWidget(row_widget)
        self.session_rows.append((row_widget, day_cb, start_cb, end_cb, parity_cb))

    def remove_session_row(self):
        """Remove the last session row"""
        if not self.session_rows:
            return
        widget, *_ = self.session_rows.pop()
        widget.setParent(None)

    def get_course_data(self):
        """Get the updated course data"""
        name = self.name_edit.text().strip()
        code = self.code_edit.text().strip()
        instructor = self.instructor_edit.text().strip()
        location = self.location_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        exam_time = self.exam_time_edit.text().strip()
        credits = self.credits_spin.value()
        
        if not name or not code:
            QtWidgets.QMessageBox.warning(self, 'خطا', 'لطفا نام درس و کد درس را وارد کنید.')
            return None
            
        sessions = []
        for (_, day_cb, start_cb, end_cb, parity_cb) in self.session_rows:
            day = day_cb.currentText()
            start = start_cb.currentText()
            end = end_cb.currentText()
            parity = parity_cb.currentText()
            
            # Validate times
            try:
                si = EXTENDED_TIME_SLOTS.index(start)
                ei = EXTENDED_TIME_SLOTS.index(end)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, 'خطا', 'ساعت نامعتبر در یکی از جلسات.')
                return None
                
            if ei <= si:
                QtWidgets.QMessageBox.warning(self, 'خطا', 'زمان پایان باید بعد از شروع باشد.')
                return None
                
            sessions.append({'day': day, 'start': start, 'end': end, 'parity': parity})
        
        course = {
            'code': code,
            'name': name,
            'credits': credits,
            'instructor': instructor,
            'schedule': sessions,
            'location': location,
            'description': description or 'توضیحی ارائه نشده',
            'exam_time': exam_time or 'اعلام نشده'
        }
        
        return course