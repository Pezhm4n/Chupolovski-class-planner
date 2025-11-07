#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Course dialogs module for Schedule Planner
Contains dialog windows for adding and editing courses
"""

import sys
import os

from PyQt5 import QtWidgets, QtCore

# Import from core modules
from app.core.config import EXTENDED_TIME_SLOTS, COURSES, get_day_label_map
from app.core.logger import setup_logging
from app.core.data_manager import save_user_data
from app.core.translator import translator
from app.core.language_manager import language_manager

logger = setup_logging()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PARITY_VALUES = [
    ("", "parity.none"),
    ("ز", "parity.even"),
    ("ف", "parity.odd"),
]


def _populate_day_combo(combo: QtWidgets.QComboBox, selected=None):
    mapping = get_day_label_map()
    current = selected if selected is not None else combo.currentData()
    combo.clear()
    for canonical, label in mapping:
        combo.addItem(label, canonical)
    if current:
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)


def _populate_parity_combo(combo: QtWidgets.QComboBox, selected=None):
    current = selected if selected is not None else combo.currentData()
    combo.clear()
    for value, key in _PARITY_VALUES:
        combo.addItem(translator.t(key), value)
    if current is not None:
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)


def _set_widget_direction(direction, *widgets):
    for widget in widgets:
        if hasattr(widget, "setLayoutDirection"):
            widget.setLayoutDirection(direction)


# ---------------------- Add Course Dialog ----------------------

class AddCourseDialog(QtWidgets.QDialog):
    """Dialog for adding new courses"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.resize(500, 400)

        self._language_connected = False

        main_layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        form.setFormAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)

        self.name_label = QtWidgets.QLabel()
        self.code_label = QtWidgets.QLabel()
        self.instructor_label = QtWidgets.QLabel()
        self.location_label = QtWidgets.QLabel()
        self.capacity_label = QtWidgets.QLabel()
        self.description_label = QtWidgets.QLabel()
        self.exam_time_label = QtWidgets.QLabel()
        self.credits_label = QtWidgets.QLabel()

        self.name_edit = QtWidgets.QLineEdit()
        self.code_edit = QtWidgets.QLineEdit()
        self.instructor_edit = QtWidgets.QLineEdit()
        self.location_edit = QtWidgets.QLineEdit()
        self.capacity_edit = QtWidgets.QLineEdit()
        self.description_edit = QtWidgets.QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.exam_time_edit = QtWidgets.QLineEdit()
        self.credits_spin = QtWidgets.QSpinBox()
        self.credits_spin.setRange(0, 10)
        self.credits_spin.setValue(3)

        form.addRow(self.name_label, self.name_edit)
        form.addRow(self.code_label, self.code_edit)
        form.addRow(self.instructor_label, self.instructor_edit)
        form.addRow(self.location_label, self.location_edit)
        form.addRow(self.capacity_label, self.capacity_edit)
        form.addRow(self.description_label, self.description_edit)
        form.addRow(self.exam_time_label, self.exam_time_edit)
        form.addRow(self.credits_label, self.credits_spin)

        main_layout.addLayout(form)

        self.sessions_layout = QtWidgets.QVBoxLayout()
        self.sessions_heading = QtWidgets.QLabel()
        main_layout.addWidget(self.sessions_heading)
        main_layout.addLayout(self.sessions_layout)

        btn_row = QtWidgets.QHBoxLayout()
        self.add_session_btn = QtWidgets.QPushButton()
        self.add_session_btn.clicked.connect(self.add_session_row)
        self.remove_session_btn = QtWidgets.QPushButton()
        self.remove_session_btn.clicked.connect(self.remove_session_row)
        btn_row.addWidget(self.add_session_btn)
        btn_row.addWidget(self.remove_session_btn)
        main_layout.addLayout(btn_row)

        self.button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.session_rows = []
        self.add_session_row()

        self._connect_language_signal()
        self._apply_translations()

    def showEvent(self, event):
        super().showEvent(event)
        self._connect_language_signal()
        self._apply_translations()

    def add_session_row(self):
        """Add a new session row to the dialog"""
        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        day_cb = QtWidgets.QComboBox()
        start_cb = QtWidgets.QComboBox()
        end_cb = QtWidgets.QComboBox()
        start_cb.addItems(EXTENDED_TIME_SLOTS)
        end_cb.addItems(EXTENDED_TIME_SLOTS)
        parity_cb = QtWidgets.QComboBox()
        _populate_day_combo(day_cb)
        _populate_parity_combo(parity_cb)
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
        capacity = self.capacity_edit.text().strip()  # Get capacity
        description = self.description_edit.toPlainText().strip()
        exam_time = self.exam_time_edit.text().strip()
        credits = self.credits_spin.value()
        
        # Validation: Course name and instructor are mandatory
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                translator.t("common.error"),
                translator.t("common.required_course_fields")
            )
            return None
        if not instructor:
            QtWidgets.QMessageBox.warning(
                self,
                translator.t("common.error"),
                translator.t("common.required_course_fields")
            )
            return None
        if not code:
            # Generate a unique code if not provided
            import time
            code = f"user_{int(time.time())}"
            
        sessions = []
        for (_, day_cb, start_cb, end_cb, parity_cb) in self.session_rows:
            day = day_cb.currentData() or day_cb.currentText()
            start = start_cb.currentText()
            end = end_cb.currentText()
            parity = parity_cb.currentData() or ""
            # validate times
            try:
                si = EXTENDED_TIME_SLOTS.index(start)
                ei = EXTENDED_TIME_SLOTS.index(end)
            except ValueError:
                QtWidgets.QMessageBox.warning(
                    self,
                    translator.t("common.error"),
                    translator.t("common.invalid_session_time")
                )
                return None
            if ei <= si:
                QtWidgets.QMessageBox.warning(
                    self,
                    translator.t("common.error"),
                    translator.t("common.invalid_session_order")
                )
                return None
            sessions.append({'day': day, 'start': start, 'end': end, 'parity': parity})
        
        # Create course data with capacity field
        course = {
            'code': code,
            'name': name,
            'credits': credits,
            'instructor': instructor,
            'schedule': sessions,
            'location': location,
            'capacity': capacity,  # Add capacity to course data
            'description': description or translator.t("common.no_description"),
            'exam_time': exam_time or translator.t("common.no_exam_time"),
            'major': 'دروس اضافه‌شده توسط کاربر'  # Add to correct category
        }
        return course

    # ------------------------------------------------------------------
    # Translation handling
    # ------------------------------------------------------------------

    def _connect_language_signal(self):
        if not self._language_connected:
            language_manager.language_changed.connect(self._on_language_changed)
            self._language_connected = True

    def _disconnect_language_signal(self):
        if self._language_connected:
            try:
                language_manager.language_changed.disconnect(self._on_language_changed)
            except TypeError:
                pass
            self._language_connected = False

    def _on_language_changed(self, _lang):
        self._apply_translations()

    def _apply_translations(self):
        language_manager.apply_layout_direction(self)
        direction = language_manager.get_layout_direction()

        _set_widget_direction(
            direction,
            self,
            self.name_edit,
            self.code_edit,
            self.instructor_edit,
            self.location_edit,
            self.capacity_edit,
            self.description_edit,
            self.exam_time_edit,
        )

        self.setWindowTitle(translator.t("dialogs.add_course.title"))
        self.name_label.setText(translator.t("dialogs.add_course.course_name"))
        self.code_label.setText(translator.t("dialogs.add_course.course_code"))
        self.instructor_label.setText(translator.t("dialogs.add_course.instructor"))
        self.location_label.setText(translator.t("dialogs.add_course.location"))
        self.capacity_label.setText(translator.t("dialogs.add_course.capacity"))
        self.description_label.setText(translator.t("dialogs.add_course.description"))
        self.exam_time_label.setText(translator.t("dialogs.add_course.exam_time"))
        self.credits_label.setText(translator.t("dialogs.add_course.credits"))

        self.sessions_heading.setText(translator.t("dialogs.add_course.sessions_hint"))
        self.add_session_btn.setText(translator.t("buttons.add"))
        self.remove_session_btn.setText(translator.t("buttons.remove"))

        self.exam_time_edit.setPlaceholderText(translator.t("dialogs.add_course.exam_placeholder"))

        ok_btn = self.button_box.button(QtWidgets.QDialogButtonBox.Ok)
        cancel_btn = self.button_box.button(QtWidgets.QDialogButtonBox.Cancel)
        if ok_btn:
            ok_btn.setText(translator.t("common.ok"))
        if cancel_btn:
            cancel_btn.setText(translator.t("common.cancel"))

        for (_, day_cb, _, _, parity_cb) in self.session_rows:
            _populate_day_combo(day_cb)
            _populate_parity_combo(parity_cb)

    def closeEvent(self, event):
        self._disconnect_language_signal()
        super().closeEvent(event)


# ---------------------- Edit Course Dialog ----------------------

class EditCourseDialog(QtWidgets.QDialog):
    """Dialog for editing existing course information"""
    def __init__(self, course_data, parent=None):
        super().__init__(parent)
        self.course_data = course_data
        self.setModal(True)
        self.resize(500, 400)
        self._language_connected = False

        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        form.setFormAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)

        self.name_label = QtWidgets.QLabel()
        self.code_label = QtWidgets.QLabel()
        self.instructor_label = QtWidgets.QLabel()
        self.location_label = QtWidgets.QLabel()
        self.capacity_label = QtWidgets.QLabel()
        self.description_label = QtWidgets.QLabel()
        self.exam_time_label = QtWidgets.QLabel()
        self.credits_label = QtWidgets.QLabel()

        self.name_edit = QtWidgets.QLineEdit(course_data.get('name', ''))
        self.code_edit = QtWidgets.QLineEdit(course_data.get('code', ''))
        self.instructor_edit = QtWidgets.QLineEdit(course_data.get('instructor', ''))
        self.location_edit = QtWidgets.QLineEdit(course_data.get('location', ''))
        self.capacity_edit = QtWidgets.QLineEdit(course_data.get('capacity', ''))
        self.description_edit = QtWidgets.QTextEdit()
        self.description_edit.setPlainText(course_data.get('description', ''))
        self.description_edit.setMaximumHeight(80)
        self.exam_time_edit = QtWidgets.QLineEdit(course_data.get('exam_time', ''))
        self.credits_spin = QtWidgets.QSpinBox()
        self.credits_spin.setRange(0, 10)
        self.credits_spin.setValue(course_data.get('credits', 3))

        form.addRow(self.name_label, self.name_edit)
        form.addRow(self.code_label, self.code_edit)
        form.addRow(self.instructor_label, self.instructor_edit)
        form.addRow(self.location_label, self.location_edit)
        form.addRow(self.capacity_label, self.capacity_edit)
        form.addRow(self.description_label, self.description_edit)
        form.addRow(self.exam_time_label, self.exam_time_edit)
        form.addRow(self.credits_label, self.credits_spin)

        layout.addLayout(form)

        self.sessions_layout = QtWidgets.QVBoxLayout()
        self.sessions_heading = QtWidgets.QLabel()
        layout.addWidget(self.sessions_heading)
        layout.addLayout(self.sessions_layout)

        btn_row = QtWidgets.QHBoxLayout()
        self.add_session_btn = QtWidgets.QPushButton()
        self.add_session_btn.clicked.connect(self.add_session_row)
        self.remove_session_btn = QtWidgets.QPushButton()
        self.remove_session_btn.clicked.connect(self.remove_session_row)
        btn_row.addWidget(self.add_session_btn)
        btn_row.addWidget(self.remove_session_btn)
        layout.addLayout(btn_row)

        self.button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Load existing sessions
        self.session_rows = []
        for session in course_data.get('schedule', []):
            self.add_session_row(session)
            
        # Add at least one session if none exist
        if not self.session_rows:
            self.add_session_row()

        self._connect_language_signal()
        self._apply_translations()

    def add_session_row(self, session_data=None):
        """Add a session row, optionally with pre-filled data"""
        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        
        day_cb = QtWidgets.QComboBox()
        start_cb = QtWidgets.QComboBox()
        end_cb = QtWidgets.QComboBox()
        start_cb.addItems(EXTENDED_TIME_SLOTS)
        end_cb.addItems(EXTENDED_TIME_SLOTS)
        parity_cb = QtWidgets.QComboBox()
        _populate_day_combo(day_cb, selected=session_data.get('day') if session_data else None)
        _populate_parity_combo(parity_cb, selected=session_data.get('parity') if session_data else None)
        
        # Pre-fill if data provided
        if session_data:
            if session_data.get('start') in EXTENDED_TIME_SLOTS:
                start_cb.setCurrentText(session_data['start'])
            if session_data.get('end') in EXTENDED_TIME_SLOTS:
                end_cb.setCurrentText(session_data['end'])
        
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
        capacity = self.capacity_edit.text().strip()  # Get capacity
        description = self.description_edit.toPlainText().strip()
        exam_time = self.exam_time_edit.text().strip()
        credits = self.credits_spin.value()
        
        # Validation: Course name and instructor are mandatory
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                translator.t("common.error"),
                translator.t("common.required_course_fields")
            )
            return None
        if not instructor:
            QtWidgets.QMessageBox.warning(
                self,
                translator.t("common.error"),
                translator.t("common.required_course_fields")
            )
            return None
        if not code:
            # Generate a unique code if not provided
            import time
            code = f"user_{int(time.time())}"
            
        sessions = []
        for (_, day_cb, start_cb, end_cb, parity_cb) in self.session_rows:
            day = day_cb.currentData() or day_cb.currentText()
            start = start_cb.currentText()
            end = end_cb.currentText()
            parity = parity_cb.currentData() or ""
            
            # Validate times
            try:
                si = EXTENDED_TIME_SLOTS.index(start)
                ei = EXTENDED_TIME_SLOTS.index(end)
            except ValueError:
                QtWidgets.QMessageBox.warning(
                    self,
                    translator.t("common.error"),
                    translator.t("common.invalid_session_time")
                )
                return None
                
            if ei <= si:
                QtWidgets.QMessageBox.warning(
                    self,
                    translator.t("common.error"),
                    translator.t("common.invalid_session_order")
                )
                return None
                
            sessions.append({'day': day, 'start': start, 'end': end, 'parity': parity})
        
        # Create course data with capacity field
        course = {
            'code': code,
            'name': name,
            'credits': credits,
            'instructor': instructor,
            'schedule': sessions,
            'location': location,
            'capacity': capacity,  # Add capacity to course data
            'description': description or translator.t("common.no_description"),
            'exam_time': exam_time or translator.t("common.no_exam_time"),
            'major': 'دروس اضافه‌شده توسط کاربر'  # Keep in correct category
        }
        
        return course

    # ------------------------------------------------------------------
    # Translation handling
    # ------------------------------------------------------------------

    def _connect_language_signal(self):
        if not self._language_connected:
            language_manager.language_changed.connect(self._on_language_changed)
            self._language_connected = True

    def _disconnect_language_signal(self):
        if self._language_connected:
            try:
                language_manager.language_changed.disconnect(self._on_language_changed)
            except TypeError:
                pass
            self._language_connected = False

    def _on_language_changed(self, _lang):
        self._apply_translations()

    def _apply_translations(self):
        language_manager.apply_layout_direction(self)
        direction = language_manager.get_layout_direction()

        _set_widget_direction(
            direction,
            self,
            self.name_edit,
            self.code_edit,
            self.instructor_edit,
            self.location_edit,
            self.capacity_edit,
            self.description_edit,
            self.exam_time_edit,
        )

        self.setWindowTitle(translator.t("dialogs.edit_course.title"))
        self.name_label.setText(translator.t("dialogs.add_course.course_name"))
        self.code_label.setText(translator.t("dialogs.add_course.course_code"))
        self.instructor_label.setText(translator.t("dialogs.add_course.instructor"))
        self.location_label.setText(translator.t("dialogs.add_course.location"))
        self.capacity_label.setText(translator.t("dialogs.add_course.capacity"))
        self.description_label.setText(translator.t("dialogs.add_course.description"))
        self.exam_time_label.setText(translator.t("dialogs.add_course.exam_time"))
        self.credits_label.setText(translator.t("dialogs.add_course.credits"))

        self.sessions_heading.setText(translator.t("dialogs.add_course.sessions_hint"))
        self.add_session_btn.setText(translator.t("buttons.add"))
        self.remove_session_btn.setText(translator.t("buttons.remove"))
        self.exam_time_edit.setPlaceholderText(translator.t("dialogs.add_course.exam_placeholder"))

        ok_btn = self.button_box.button(QtWidgets.QDialogButtonBox.Ok)
        cancel_btn = self.button_box.button(QtWidgets.QDialogButtonBox.Cancel)
        if ok_btn:
            ok_btn.setText(translator.t("common.ok"))
        if cancel_btn:
            cancel_btn.setText(translator.t("common.cancel"))

        for (_, day_cb, _, _, parity_cb) in self.session_rows:
            _populate_day_combo(day_cb)
            _populate_parity_combo(parity_cb)

    def showEvent(self, event):
        super().showEvent(event)
        self._connect_language_signal()
        self._apply_translations()

    def closeEvent(self, event):
        self._disconnect_language_signal()
        super().closeEvent(event)