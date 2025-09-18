#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schedule Planner - PyQt5
"""

import itertools
import sys
import os
import json
import logging
from itertools import product
from PyQt5 import QtWidgets, QtGui, QtCore
import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QPushButton, QVBoxLayout, QWidget,
QFileDialog, QMessageBox, QInputDialog, QLineEdit, QLabel, QDialog, QDialogButtonBox, QFormLayout)
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtCore import Qt

# Configure logging
def setup_logging():
    """Setup application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        handlers=[
            logging.FileHandler('app.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# Initialize logger
logger = setup_logging()

USER_DATA_FILE = 'user_data.json'
COURSES_DATA_FILE = 'courses_data.json'

# Global COURSES dictionary - will be loaded from JSON
COURSES = {}

# ---------------------- ذخیره و بارگذاری داده‌های درس ----------------------

def load_courses_from_json():
    """Load all courses from JSON file"""
    global COURSES
    logger.info(f"Loading courses from {COURSES_DATA_FILE}")
    
    if not os.path.exists(COURSES_DATA_FILE):
        logger.warning(f"{COURSES_DATA_FILE} not found. Creating empty course data.")
        print(f"Warning: {COURSES_DATA_FILE} not found. Creating empty course data.")
        COURSES = {}
        return
    
    try:
        with open(COURSES_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            COURSES = data.get('courses', {})
            logger.info(f"Successfully loaded {len(COURSES)} courses from {COURSES_DATA_FILE}")
            print(f"Loaded {len(COURSES)} courses from {COURSES_DATA_FILE}")
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading courses from {COURSES_DATA_FILE}: {e}", exc_info=True)
        print(f"Error loading courses from {COURSES_DATA_FILE}: {e}")
        COURSES = {}

def save_courses_to_json():
    """Save all courses to JSON file"""
    try:
        # Load existing data first
        existing_data = {'courses': {}, 'custom_courses': [], 'saved_combos': []}
        if os.path.exists(COURSES_DATA_FILE):
            with open(COURSES_DATA_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        
        # Update courses section
        existing_data['courses'] = COURSES
        
        # Save back to file
        with open(COURSES_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Error saving courses to {COURSES_DATA_FILE}: {e}")

# Load courses at module level
load_courses_from_json()

# OPTIONS برای چیدن خودکار (فقط دروس تخصصی)
OPTIONS = {
    'database': ['database_29', 'database_30'],
    'micro': ['micro_30', 'micro_31'],
    'software': ['software_29'],
    'micro_lab': ['micro_lab_30', 'micro_lab_31'],
    'ai': ['ai_29', 'ai_30'],
    'compiler': ['compiler_29', 'compiler_30']
}

# روزها و اسلات‌ها
DAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه']
TIME_SLOTS = []
start_minutes = 7 * 60 + 30
end_minutes = 18 * 60
m = start_minutes
while m <= end_minutes:
    hh = m // 60
    mm = m % 60
    TIME_SLOTS.append(f"{hh:02d}:{mm:02d}")
    m += 30

# رنگ‌ها
COLOR_MAP = [
    QtGui.QColor(219, 234, 254), QtGui.QColor(235, 233, 255), QtGui.QColor(237, 247, 237),
    QtGui.QColor(255, 249, 230), QtGui.QColor(255, 235, 238), QtGui.QColor(232, 234, 246)
]


# ---------------------- ذخیره و بارگذاری دادهٔ کاربر ----------------------

def load_user_data():
    """Load user data from JSON file with error handling"""
    data = {'custom_courses': [], 'saved_combos': []}
    if not os.path.exists(USER_DATA_FILE):
        return data
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            data.update(loaded_data)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load user data - {e}")
        return data
    
    # Load custom courses into COURSES dictionary
    try:
        for c in data.get('custom_courses', []):
            if isinstance(c, dict) and 'code' in c and 'name' in c:
                key = generate_unique_key(c.get('code', 'custom'), COURSES)
                COURSES[key] = c
    except Exception as e:
        print(f"Warning: Error loading custom courses - {e}")
    
    return data


def save_user_data(data):
    """Save user data to JSON file with error handling"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(USER_DATA_FILE)), exist_ok=True)
        
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (IOError, OSError) as e:
        print(f'Error saving user data: {e}')
        raise


def generate_unique_key(base_code, store):
    # base_code may contain invalid chars; make a safe key
    safe = base_code.replace(' ', '_')
    if safe not in store:
        return safe
    i = 1
    while f"{safe}_u{i}" in store:
        i += 1
    return f"{safe}_u{i}"


# ---------------------- توابع کمکی زمان‌بندی ----------------------

def to_minutes(tstr):
    h, mm = map(int, tstr.split(':'))
    return h * 60 + mm


def overlap(s1, e1, s2, e2):
    return not (e1 <= s2 or e2 <= s1)


def schedules_conflict(sch1, sch2):
    for a in sch1:
        for b in sch2:
            if a['day'] != b['day']:
                continue
            if a.get('parity') and b.get('parity') and a['parity'] != b['parity']:
                continue
            if overlap(to_minutes(a['start']), to_minutes(a['end']), to_minutes(b['start']), to_minutes(b['end'])):
                return True
    return False


def calculate_days_needed_for_combo(combo_keys):
    days = set()
    for key in combo_keys:
        for item in COURSES[key]['schedule']:
            days.add(item['day'])
    return len(days)


def calculate_empty_time_for_combo(combo_keys):
    daily = {}
    for key in combo_keys:
        for item in COURSES[key]['schedule']:
            day = item['day']
            if day not in daily:
                daily[day] = []
            daily[day].append((to_minutes(item['start']), to_minutes(item['end'])))
    penalty = 0.0
    for intervals in daily.values():
        intervals.sort()
        for i in range(len(intervals) - 1):
            gap = intervals[i + 1][0] - intervals[i][1]
            if gap > 15:
                penalty += gap / 60.0
    return penalty


# ---------------------- الگوریتم "کمترین روز" برای دروس انتخاب‌شده ----------------------

def generate_best_combinations_for_groups(group_keys):
    # group_keys: list of group_key strings (base code)
    # build candidate lists for each group: course keys in COURSES whose code startswith group_key
    groups = []
    for g in group_keys:
        candidates = [k for k, v in COURSES.items() if v.get('code', '').split('_')[0] == g]
        if not candidates:
            # fallback: try match by name contains g
            candidates = [k for k, v in COURSES.items() if v.get('code', '') == g or g in v.get('name', '')]
        if not candidates:
            # can't produce combos
            return []
        groups.append(candidates)

    combos = []
    for pick in product(*groups):
        # pick is a tuple of course keys (one per group)
        keys = list(pick)
        # check conflicts pairwise
        ok = True
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                if schedules_conflict(COURSES[keys[i]]['schedule'], COURSES[keys[j]]['schedule']):
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        days = calculate_days_needed_for_combo(keys)
        empty = calculate_empty_time_for_combo(keys)
        score = days + 0.5 * empty
        combos.append({'courses': keys, 'days': days, 'empty': empty, 'score': score})
    combos.sort(key=lambda x: (x['days'], x['empty'], x['score']))
    return combos


# ---------------------- لیست دروس قابل کشیدن ----------------------
class CourseListWidget(QtWidgets.QWidget):
    """Custom widget for course list items with delete functionality"""
    def __init__(self, course_key, course_info, parent_list, parent=None):
        super().__init__(parent)
        self.course_key = course_key
        self.course_info = course_info
        self.parent_list = parent_list
        self.setup_ui()
        
    def setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Enable mouse tracking for hover events
        self.setMouseTracking(True)
        
        # Course info label
        display = f"{self.course_info['name']} — {self.course_info['code']} — {self.course_info.get('instructor', 'نامشخص')}"
        self.course_label = QtWidgets.QLabel(display)
        self.course_label.setWordWrap(True)
        # Enable mouse tracking on the label too
        self.course_label.setMouseTracking(True)
        layout.addWidget(self.course_label, 1)
        
        # Button container
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(2)
        
        # Edit button (pencil icon)
        self.edit_btn = QtWidgets.QPushButton("✏️")
        self.edit_btn.setFixedSize(24, 24)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        self.edit_btn.setToolTip(f"ویرایش درس {self.course_info['name']}")
        self.edit_btn.clicked.connect(self.edit_course)
        button_layout.addWidget(self.edit_btn)
        
        # Delete button (only for custom courses)
        if self.is_custom_course():
            self.delete_btn = QtWidgets.QPushButton("✕")
            self.delete_btn.setFixedSize(24, 24)
            self.delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff4444;
                    color: white;
                    border: none;
                    border-radius: 12px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #cc0000;
                }
            """)
            self.delete_btn.setToolTip(f"حذف درس {self.course_info['name']}")
            self.delete_btn.clicked.connect(self.delete_course)
            button_layout.addWidget(self.delete_btn)
            
        layout.addLayout(button_layout)
            
    def is_custom_course(self):
        """Check if this course should show delete button (all JSON courses can be deleted)"""
        # With JSON storage, we can allow deletion of all courses
        # Optionally, you might want to protect some system courses
        return True  # Allow deletion for all courses
                                       
    def delete_course(self):
        """Handle course deletion with confirmation"""
        course_name = self.course_info.get('name', 'نامشخص')
        instructor = self.course_info.get('instructor', 'نامشخص')
        
        # Confirmation dialog
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle('حذف درس')
        msg.setText(f'آیا مطمئن هستید که می‌خواهید درس زیر را حذف کنید؟')
        msg.setInformativeText(f'نام درس: {course_name}\nاستاد: {instructor}')
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg.setDefaultButton(QtWidgets.QMessageBox.No)
        
        if msg.exec_() == QtWidgets.QMessageBox.Yes:
            # Get main window reference properly
            main_window = self.get_main_window()
            if not main_window:
                QtWidgets.QMessageBox.warning(self, 'خطا', 'خطا در دسترسی به پنجره اصلی')
                return
            
            # Remove from COURSES dictionary
            if self.course_key in COURSES:
                del COURSES[self.course_key]
            
            # Save courses to JSON
            save_courses_to_json()
            
            # Remove from user_data
            user_data = main_window.user_data
            custom_courses = user_data.get('custom_courses', [])
            user_data['custom_courses'] = [c for c in custom_courses 
                                          if c.get('code') != self.course_info.get('code')]
            
            # Save updated user data
            save_user_data(user_data)
            
            # Remove from any placed schedules
            main_window.remove_course_from_schedule(self.course_key)
            
            # Refresh the course list and info panel - FIXED
            main_window.populate_course_list()
            main_window.update_course_info_panel()  # Update info panel
            
            # Update status
            main_window.update_status()
            
            QtWidgets.QMessageBox.information(
                self, 'حذف شد', 
                f'درس "{course_name}" با موفقیت حذف شد.'
            )
            
    def edit_course(self):
        """Handle course editing"""
        main_window = self.get_main_window()
        if not main_window:
            QtWidgets.QMessageBox.warning(self, 'خطا', 'خطا در دسترسی به پنجره اصلی')
            return
            
        # Open edit dialog for this specific course
        main_window.open_edit_course_dialog_for_course(self.course_key)
            
    def get_main_window(self):
        """Get reference to main window"""
        parent = self.parent()
        while parent:
            if isinstance(parent, QtWidgets.QMainWindow):
                return parent
            parent = parent.parent()
        return None
    
    def mousePressEvent(self, event):
        """Handle mouse clicks to select item and emit itemClicked signal"""
        # Only handle left-click, ignore right-click and other buttons
        if event.button() != QtCore.Qt.LeftButton:
            super().mousePressEvent(event)
            return
            
        # Find the corresponding QListWidgetItem
        for i in range(self.parent_list.count()):
            item = self.parent_list.item(i)
            if self.parent_list.itemWidget(item) == self:
                # Set this item as current
                self.parent_list.setCurrentItem(item)
                # Emit itemClicked signal to trigger course addition
                self.parent_list.itemClicked.emit(item)
                break
        
        # Call parent implementation for any buttons (edit/delete)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Forward mouse move events to enable hover preview"""
        # Get the main window
        main_window = self.get_main_window()
        if main_window:
            # Find the corresponding QListWidgetItem
            for i in range(self.parent_list.count()):
                item = self.parent_list.item(i)
                if self.parent_list.itemWidget(item) == self:
                    # Get the course key and trigger preview
                    key = item.data(QtCore.Qt.UserRole)
                    if key and getattr(main_window, 'last_hover_key', None) != key:
                        main_window.clear_preview()
                        main_window.last_hover_key = key
                        main_window.preview_course(key)
                    break
        
        # Call parent implementation
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        """Clear preview when mouse leaves the widget"""
        main_window = self.get_main_window()
        if main_window:
            main_window.clear_preview()
            main_window.last_hover_key = None
        
        super().leaveEvent(event)

class DraggableCourseList(QtWidgets.QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return
        course_key = item.data(QtCore.Qt.UserRole)
        mime = QtCore.QMimeData()
        mime.setText(course_key)
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        pix = QtGui.QPixmap(self.visualItemRect(item).size())
        pix.fill(QtGui.QColor(220, 220, 220))
        drag.setPixmap(pix)
        drag.exec_(QtCore.Qt.MoveAction)


# ---------------------- جدول ----------------------
class ScheduleTable(QtWidgets.QTableWidget):
    def __init__(self, rows, cols, parent=None):
        super().__init__(rows, cols, parent)
        self.setAcceptDrops(True)
        self.parent_window = parent

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasText():
            course_key = event.mimeData().text()
            self.parent_window.add_course_to_table(course_key, ask_on_conflict=True)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


# ---------------------- دیالوگ افزودن درس ----------------------
class AddCourseDialog(QtWidgets.QDialog):
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
        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        day_cb = QtWidgets.QComboBox()
        day_cb.addItems(DAYS)
        start_cb = QtWidgets.QComboBox()
        end_cb = QtWidgets.QComboBox()
        start_cb.addItems(TIME_SLOTS)
        end_cb.addItems(TIME_SLOTS)
        parity_cb = QtWidgets.QComboBox()
        parity_cb.addItems(['', 'ز', 'ف'])
        row_layout.addWidget(day_cb)
        row_layout.addWidget(start_cb)
        row_layout.addWidget(end_cb)
        row_layout.addWidget(parity_cb)
        self.sessions_layout.addWidget(row_widget)
        self.session_rows.append((row_widget, day_cb, start_cb, end_cb, parity_cb))

    def remove_session_row(self):
        if not self.session_rows:
            return
        widget, *_ = self.session_rows.pop()
        widget.setParent(None)

    def get_course_data(self):
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
                si = TIME_SLOTS.index(start)
                ei = TIME_SLOTS.index(end)
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
        start_cb.addItems(TIME_SLOTS)
        end_cb.addItems(TIME_SLOTS)
        parity_cb = QtWidgets.QComboBox()
        parity_cb.addItems(['', 'ز', 'ف'])
        
        # Pre-fill if data provided
        if session_data:
            if session_data.get('day') in DAYS:
                day_cb.setCurrentText(session_data['day'])
            if session_data.get('start') in TIME_SLOTS:
                start_cb.setCurrentText(session_data['start'])
            if session_data.get('end') in TIME_SLOTS:
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
                si = TIME_SLOTS.index(start)
                ei = TIME_SLOTS.index(end)
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








# ---------------------- پنجره اطلاعات تفصیلی ----------------------
class DetailedInfoWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle('برنامه امتحانات')
        self.resize(1000, 700)
        self.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        self.init_ui()
        self.update_content()
        
    def init_ui(self):
        """Initialize the detailed information UI"""
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(main_widget)
        
        # Create toolbar
        toolbar = QtWidgets.QToolBar()
        self.addToolBar(toolbar)
        
        # Add refresh button
        refresh_action = QtWidgets.QAction('🔄 بروزرسانی', self)
        refresh_action.triggered.connect(self.update_content)
        toolbar.addAction(refresh_action)
        
        # Add export button
        export_action = QtWidgets.QAction('📤 صدور برنامه امتحانات', self)
        export_action.triggered.connect(self.export_exam_schedule)
        toolbar.addAction(export_action)
        
        # Create splitter for exam section only
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # Bottom section: Exam Schedule (now the only section)
        self.create_exam_schedule_section(splitter)
        
    # COMMENTED OUT: Course descriptions section - can be restored if needed
    # def create_course_descriptions_section(self, parent):
    #     """Create the course descriptions section"""
    #     desc_widget = QtWidgets.QWidget()
    #     desc_layout = QtWidgets.QVBoxLayout(desc_widget)
    #     
    #     # Title
    #     title_label = QtWidgets.QLabel('<h2 style="color: #2c3e50; margin: 0;">📚 اطلاعات عمومی دروس</h2>')
    #     title_label.setAlignment(QtCore.Qt.AlignCenter)
    #     desc_layout.addWidget(title_label)
    #     
    #     # Course descriptions text area
    #     self.course_desc_text = QtWidgets.QTextEdit()
    #     self.course_desc_text.setReadOnly(True)
    #     self.course_desc_text.setStyleSheet("""
    #         QTextEdit {
    #             background-color: #f8f9fa;
    #             border: 2px solid #e9ecef;
    #             border-radius: 8px;
    #             font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    #             font-size: 12px;
    #             padding: 15px;
    #             line-height: 1.6;
    #         }
    #     """)
    #     desc_layout.addWidget(self.course_desc_text)
    #     
    #     parent.addWidget(desc_widget)
        
    def create_exam_schedule_section(self, parent):
        """Create the exam schedule section with improved visual design"""
        exam_widget = QtWidgets.QWidget()
        exam_layout = QtWidgets.QVBoxLayout(exam_widget)
        
        # Enhanced title with better styling
        title_label = QtWidgets.QLabel(
            '<h2 style="color: #d35400; margin: 0; text-shadow: 0 1px 2px rgba(0,0,0,0.1);">' 
            '📅 برنامه امتحانات (فقط دروس انتخابی)</h2>'
        )
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        exam_layout.addWidget(title_label)
        
        # Improved info label with better contrast
        info_label = QtWidgets.QLabel(
            '<p style="color: #34495e; font-style: italic; text-align: center; ' 
            'background: linear-gradient(135deg, #ecf0f1 0%, #bdc3c7 100%); ' 
            'padding: 8px; border-radius: 6px; margin: 5px;">' 
            'فقط دروسی که در جدول اصلی قرار داده‌اید نمایش داده می‌شوند</p>'
        )
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        exam_layout.addWidget(info_label)
        
        # Separator line after info
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setStyleSheet("QFrame { color: #bdc3c7; margin: 10px 0; }")
        exam_layout.addWidget(separator)
        
        # Enhanced exam schedule table
        self.exam_table = QtWidgets.QTableWidget()
        self.exam_table.setColumnCount(5)
        self.exam_table.setHorizontalHeaderLabels([
            'نام درس', 'کد درس', 'استاد', 'زمان امتحان', 'محل برگزاری'
        ])
        
        # Enhanced table styling with subtle backgrounds
        self.exam_table.setStyleSheet("""
            QTableWidget {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #ffffff, stop: 1 #f8f9fa);
                border: 2px solid #e9ecef;
                border-radius: 10px;
                gridline-color: #dee2e6;
                font-size: 11px;
                selection-background-color: #fff3cd;
            }
            QTableWidget::item {
                padding: 10px 8px;
                border-bottom: 1px solid #f1f3f4;
                border-right: 1px solid #f1f3f4;
            }
            QTableWidget::item:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #fff3cd, stop: 1 #ffeaa7);
                color: #856404;
            }
            QTableWidget::item:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #e3f2fd, stop: 1 #bbdefb);
            }
            QHeaderView::section {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #fd7e14, stop: 1 #e8590c);
                color: white;
                padding: 12px 8px;
                border: none;
                font-weight: bold;
                font-size: 12px;
                text-align: center;
            }
            QHeaderView::section:first {
                border-top-left-radius: 8px;
            }
            QHeaderView::section:last {
                border-top-right-radius: 8px;
            }
        """)
        
        # Configure table properties with better spacing
        header = self.exam_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)  # Course name
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Code
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # Instructor
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)  # Exam time
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)  # Location
        
        self.exam_table.setAlternatingRowColors(True)
        self.exam_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.exam_table.setSortingEnabled(True)
        self.exam_table.verticalHeader().setVisible(False)  # Hide row numbers for cleaner look
        
        exam_layout.addWidget(self.exam_table)
        
        # Add bottom separator and spacing
        bottom_separator = QtWidgets.QFrame()
        bottom_separator.setFrameShape(QtWidgets.QFrame.HLine)
        bottom_separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        bottom_separator.setStyleSheet("QFrame { color: #bdc3c7; margin: 10px 0; }")
        exam_layout.addWidget(bottom_separator)
        
        parent.addWidget(exam_widget)
        
    def update_content(self):
        """Update exam schedule content only"""
        # self.update_course_descriptions()  # COMMENTED OUT - UI removed
        self.update_exam_schedule()
        
    # COMMENTED OUT: Course descriptions update method - can be restored if needed
    # def update_course_descriptions(self):
    #     """Update the course descriptions section with improved visual design"""
    #     # ... (original implementation commented out for UI removal)
        
    def update_course_descriptions(self):
        """Update the course descriptions section with improved visual design"""
        html_content = """
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Arial, sans-serif; 
                line-height: 1.8; 
                margin: 0; 
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #2c3e50;
            }
            .container {
                max-width: 100%;
                margin: 0 auto;
            }
            .course-card {
                margin-bottom: 25px;
                padding: 20px;
                background: linear-gradient(145deg, #ffffff 0%, #f8f9fa 100%);
                border-radius: 15px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                border-left: 5px solid;
                transition: transform 0.3s ease;
                position: relative;
                overflow: hidden;
            }
            .course-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: linear-gradient(90deg, #667eea, #764ba2, #f093fb, #f5576c);
            }
            .course-card:hover {
                transform: translateY(-3px);
                box-shadow: 0 12px 35px rgba(0,0,0,0.2);
            }
            .course-title {
                font-size: 18px;
                font-weight: bold;
                margin: 0 0 12px 0;
                color: #2c3e50;
                text-shadow: 0 1px 2px rgba(0,0,0,0.1);
                border-bottom: 2px solid #ecf0f1;
                padding-bottom: 8px;
            }
            .course-meta {
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                margin-bottom: 15px;
                font-size: 12px;
                color: #7f8c8d;
            }
            .meta-item {
                background: #ecf0f1;
                padding: 6px 12px;
                border-radius: 20px;
                font-weight: 500;
            }
            .meta-item strong {
                color: #34495e;
            }
            .course-description {
                font-size: 13px;
                color: #2c3e50;
                background: linear-gradient(135deg, #e8f4fd 0%, #f1f8ff 100%);
                padding: 15px;
                border-radius: 10px;
                margin: 15px 0;
                border-left: 4px solid #3498db;
                font-style: italic;
                line-height: 1.6;
            }
            .schedule-info {
                background: linear-gradient(135deg, #fff3cd 0%, #fef9e7 100%);
                padding: 12px;
                border-radius: 8px;
                border-left: 4px solid #f39c12;
                margin-top: 12px;
            }
            .schedule-title {
                font-weight: bold;
                color: #d35400;
                margin-bottom: 8px;
                font-size: 12px;
            }
            .schedule-sessions {
                font-size: 11px;
                color: #8b5a00;
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }
            .session-item {
                background: rgba(255,255,255,0.7);
                padding: 4px 8px;
                border-radius: 12px;
                white-space: nowrap;
            }
            .separator {
                height: 2px;
                background: linear-gradient(90deg, transparent, #bdc3c7, transparent);
                margin: 30px 0;
                border-radius: 1px;
            }
            .section-header {
                text-align: center;
                background: linear-gradient(135deg, #34495e 0%, #2c3e50 100%);
                color: white;
                padding: 15px;
                border-radius: 12px;
                margin-bottom: 25px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }
            .course-count {
                text-align: center;
                color: #7f8c8d;
                font-style: italic;
                margin-top: 20px;
                padding: 10px;
                background: rgba(255,255,255,0.8);
                border-radius: 8px;
            }
        </style>
        <div class="container">
            <div class="section-header">
                <h2 style="margin: 0; font-size: 20px;">📚 اطلاعات جامع دروس موجود</h2>
                <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">مجموعه‌ای کامل از دروس قابل ارائه در سیستم</p>
            </div>
        """
        
        course_count = 0
        # Color themes for course cards
        color_themes = [
            {'border': '#e74c3c', 'accent': '#c0392b'},
            {'border': '#3498db', 'accent': '#2980b9'},
            {'border': '#2ecc71', 'accent': '#27ae60'},
            {'border': '#f39c12', 'accent': '#e67e22'},
            {'border': '#9b59b6', 'accent': '#8e44ad'},
            {'border': '#1abc9c', 'accent': '#16a085'},
            {'border': '#e67e22', 'accent': '#d35400'},
            {'border': '#34495e', 'accent': '#2c3e50'}
        ]
        
        for course_key, course in COURSES.items():
            if course_count >= 25:  # Limit to avoid overwhelming display
                html_content += "<div class='course-count'>✨ و دروس دیگر موجود در سیستم... (جمعاً " + str(len(COURSES)) + " درس)</div>"
                break
                
            # Select color theme
            theme = color_themes[course_count % len(color_themes)]
            
            html_content += f"""
            <div class="course-card" style="border-left-color: {theme['border']};">
                <div class="course-title">{course.get('name', 'نامشخص')}</div>
                
                <div class="course-meta">
                    <div class="meta-item"><strong>کد:</strong> {course.get('code', 'نامشخص')}</div>
                    <div class="meta-item"><strong>استاد:</strong> {course.get('instructor', 'نامشخص')}</div>
                    <div class="meta-item"><strong>واحد:</strong> {course.get('credits', 0)}</div>
                    <div class="meta-item"><strong>محل:</strong> {course.get('location', 'نامشخص')}</div>
                </div>
            """
            
            # Add schedule information with better formatting
            if course.get('schedule'):
                html_content += "<div class='schedule-info'>"
                html_content += "<div class='schedule-title'>🗺️ جلسات درس:</div>"
                html_content += "<div class='schedule-sessions'>"
                
                for sess in course['schedule']:
                    parity = ''
                    if sess.get('parity') == 'ز':
                        parity = ' (زوج)'
                    elif sess.get('parity') == 'ف':
                        parity = ' (فرد)'
                    
                    html_content += f"<div class='session-item'>{sess['day']} {sess['start']}-{sess['end']}{parity}</div>"
                
                html_content += "</div></div>"
            
            html_content += f"""
                <div class="course-description">
                    <strong>📝 توضیحات:</strong> {course.get('description', 'توضیحی ارائه نشده است.')}
                </div>
            </div>
            """
            
            # Add separator between courses
            if course_count < len(COURSES) - 1 and course_count < 24:
                html_content += "<div class='separator'></div>"
            
            course_count += 1
            
        html_content += "</div>"
        self.course_desc_text.setHtml(html_content)
        
    def update_exam_schedule(self):
        """Update the exam schedule table with only selected courses"""
        if not self.parent_window:
            return
            
        # Get currently placed courses from the main window
        placed_courses = set()
        if hasattr(self.parent_window, 'placed'):
            for info in self.parent_window.placed.values():
                placed_courses.add(info['course'])
        
        # Prepare table data
        exam_data = []
        for course_key in placed_courses:
            course = COURSES.get(course_key)
            if course:
                exam_data.append({
                    'name': course.get('name', 'نامشخص'),
                    'code': course.get('code', 'نامشخص'),
                    'instructor': course.get('instructor', 'نامشخص'),
                    'exam_time': course.get('exam_time', 'اعلام نشده'),
                    'location': course.get('location', 'نامشخص')
                })
        
        # Sort by exam time (basic sorting)
        exam_data.sort(key=lambda x: x['exam_time'])
        
        # Update table with enhanced styling
        self.exam_table.setRowCount(len(exam_data))
        
        for row, data in enumerate(exam_data):
            # Course name with enhanced styling
            name_item = QtWidgets.QTableWidgetItem(data['name'])
            name_item.setFont(QtGui.QFont('Arial', 10, QtGui.QFont.Bold))
            name_item.setForeground(QtGui.QBrush(QtGui.QColor('#2c3e50')))
            self.exam_table.setItem(row, 0, name_item)
            
            # Course code with monospace styling
            code_item = QtWidgets.QTableWidgetItem(data['code'])
            code_item.setFont(QtGui.QFont('Courier New', 9, QtGui.QFont.Bold))
            code_item.setTextAlignment(QtCore.Qt.AlignCenter)
            code_item.setBackground(QtGui.QBrush(QtGui.QColor('#ecf0f1')))
            self.exam_table.setItem(row, 1, code_item)
            
            # Instructor with regular styling
            instructor_item = QtWidgets.QTableWidgetItem(data['instructor'])
            instructor_item.setForeground(QtGui.QBrush(QtGui.QColor('#34495e')))
            self.exam_table.setItem(row, 2, instructor_item)
            
            # Exam time with special highlighting
            exam_item = QtWidgets.QTableWidgetItem(data['exam_time'])
            exam_item.setFont(QtGui.QFont('Arial', 10, QtGui.QFont.Bold))
            if data['exam_time'] != 'اعلام نشده':
                exam_item.setForeground(QtGui.QBrush(QtGui.QColor('#e74c3c')))
                exam_item.setBackground(QtGui.QBrush(QtGui.QColor('#fff5f5')))
            else:
                exam_item.setForeground(QtGui.QBrush(QtGui.QColor('#95a5a6')))
                exam_item.setBackground(QtGui.QBrush(QtGui.QColor('#f8f9fa')))
            exam_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.exam_table.setItem(row, 3, exam_item)
            
            # Location with subtle styling
            location_item = QtWidgets.QTableWidgetItem(data['location'])
            location_item.setForeground(QtGui.QBrush(QtGui.QColor('#7f8c8d')))
            location_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.exam_table.setItem(row, 4, location_item)
            
            # Add subtle alternating row backgrounds manually for better control
            if row % 2 == 1:
                for col in range(5):
                    item = self.exam_table.item(row, col)
                    if item:
                        current_bg = item.background().color()
                        if current_bg == QtGui.QColor():
                            item.setBackground(QtGui.QBrush(QtGui.QColor('#f8f9fa')))
        
        # Update section title with count
        if hasattr(self, 'parent') and self.parent():
            exam_count = len(exam_data)
            # We can't easily update the title label, but we could add a status
        
    def export_exam_schedule(self):
        """Export the exam schedule to various formats"""
        if self.exam_table.rowCount() == 0:
            QtWidgets.QMessageBox.information(
                self, 'هیچ داده‌ای', 
                'هیچ درسی برای صدور برنامه امتحانات انتخاب نشده است.\n'
                'لطفا ابتدا در پنجره اصلی دروس مورد نظر را به جدول اضافه کنید.'
            )
            return
            
        # Ask user for export format
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle('صدور برنامه امتحانات')
        msg.setText('فرمت مورد نظر برای صدور را انتخاب کنید:')
        
        txt_btn = msg.addButton('فایل متنی (TXT)', QtWidgets.QMessageBox.ActionRole)
        html_btn = msg.addButton('فایل HTML', QtWidgets.QMessageBox.ActionRole)
        csv_btn = msg.addButton('فایل CSV', QtWidgets.QMessageBox.ActionRole)
        pdf_btn = msg.addButton('فایل PDF', QtWidgets.QMessageBox.ActionRole)
        cancel_btn = msg.addButton('لغو', QtWidgets.QMessageBox.RejectRole)
        
        msg.exec_()
        clicked_button = msg.clickedButton()
        
        if clicked_button == cancel_btn:
            return
        elif clicked_button == txt_btn:
            self.export_as_text()
        elif clicked_button == html_btn:
            self.export_as_html()
        elif clicked_button == csv_btn:
            self.export_as_csv()
        elif clicked_button == pdf_btn:
            self.export_as_pdf()
    
    def export_as_text(self):
        """Export exam schedule as plain text"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.txt', 'Text Files (*.txt)'
        )
        if not filename:
            return
            
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write('🗓️ برنامه امتحانات\n')
                f.write('='*50 + '\n\n')
                
                for row in range(self.exam_table.rowCount()):
                    name = self.exam_table.item(row, 0).text()
                    code = self.exam_table.item(row, 1).text()
                    instructor = self.exam_table.item(row, 2).text()
                    exam_time = self.exam_table.item(row, 3).text()
                    location = self.exam_table.item(row, 4).text()
                    
                    f.write(f'📚 درس: {name}\n')
                    f.write(f'🔢 کد: {code}\n')
                    f.write(f'👨‍🏫 استاد: {instructor}\n')
                    f.write(f'⏰ زمان امتحان: {exam_time}\n')
                    f.write(f'📍 محل: {location}\n')
                    f.write('-'*30 + '\n\n')
                    
            QtWidgets.QMessageBox.information(self, 'صدور موفق', f'برنامه امتحانات در فایل زیر ذخیره شد:\n{filename}')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در ذخیره فایل:\n{str(e)}')
    
    def export_as_html(self):
        """Export exam schedule as HTML"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.html', 'HTML Files (*.html)'
        )
        if not filename:
            return
            
        try:
            html_content = """
            <!DOCTYPE html>
            <html dir="rtl" lang="fa">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>برنامه امتحانات</title>
                <style>
                    body { font-family: 'Segoe UI', Tahoma, Arial, sans-serif; margin: 20px; background: #f5f5f5; }
                    .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.1); }
                    h1 { color: #d35400; text-align: center; margin-bottom: 30px; }
                    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                    th, td { padding: 12px; text-align: center; border: 1px solid #ddd; }
                    th { background: #f39c12; color: white; font-weight: bold; }
                    tr:nth-child(even) { background: #f8f9fa; }
                    .exam-time { font-weight: bold; color: #e74c3c; }
                    .footer { text-align: center; margin-top: 30px; color: #7f8c8d; font-size: 12px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>📅 برنامه امتحانات</h1>
                    <table>
                        <thead>
                            <tr>
                                <th>نام درس</th>
                                <th>کد درس</th>
                                <th>استاد</th>
                                <th>زمان امتحان</th>
                                <th>محل برگزاری</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            for row in range(self.exam_table.rowCount()):
                name = self.exam_table.item(row, 0).text()
                code = self.exam_table.item(row, 1).text()
                instructor = self.exam_table.item(row, 2).text()
                exam_time = self.exam_table.item(row, 3).text()
                location = self.exam_table.item(row, 4).text()
                
                html_content += f"""
                            <tr>
                                <td>{name}</td>
                                <td>{code}</td>
                                <td>{instructor}</td>
                                <td class="exam-time">{exam_time}</td>
                                <td>{location}</td>
                            </tr>
                """
            
            html_content += """
                        </tbody>
                    </table>
                    <div class="footer">
                        تولید شده توسط برنامه‌ریز انتخاب واحد - Schedule Planner v2.0
                    </div>
                </div>
            </body>
            </html>
            """
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            QtWidgets.QMessageBox.information(self, 'صدور موفق', f'برنامه امتحانات در فایل زیر ذخیره شد:\n{filename}')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در ذخیره فایل:\n{str(e)}')
    
    def export_as_csv(self):
        """Export exam schedule as CSV"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.csv', 'CSV Files (*.csv)'
        )
        if not filename:
            return
            
        try:
            import csv
            with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow(['نام درس', 'کد درس', 'استاد', 'زمان امتحان', 'محل برگزاری'])
                
                # Write data
                for row in range(self.exam_table.rowCount()):
                    row_data = []
                    for col in range(5):
                        item = self.exam_table.item(row, col)
                        row_data.append(item.text() if item else '')
                    writer.writerow(row_data)
                    
            QtWidgets.QMessageBox.information(self, 'صدور موفق', f'برنامه امتحانات در فایل زیر ذخیره شد:\n{filename}')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در ذخیره فایل:\n{str(e)}')
    
    def export_as_pdf(self):
        """Export exam schedule as PDF with robust error handling"""
        logger.info("Starting PDF export process")
        
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.pdf', 'PDF Files (*.pdf)'
        )
        if not filename:
            logger.info("PDF export cancelled by user")
            return
            
        try:
            exam_count = self.exam_table.rowCount()
            logger.info(f"Exporting {exam_count} exam entries to PDF")
            
            if exam_count == 0:
                QtWidgets.QMessageBox.warning(
                    self, 'هیچ داده‌ای', 
                    'هیچ درسی برای صدور پیدا نشد. لطفاً ابتدا دروس مورد نظر را به جدول اضافه کنید.'
                )
                return
                
            # Try native Qt PDF export first
            if self._export_pdf_native(filename, exam_count):
                return
                
            # Fallback to HTML with detailed instructions
            self._export_pdf_fallback(filename, exam_count)
            
        except Exception as e:
            error_msg = f"Error during PDF export: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, 'خطا در صدور PDF', 
                f'متأسفانه خطایی در صدور PDF رخ داد:\n{str(e)}\n\n'
                f'لطفاً فایل app.log را بررسی کنید.'
            )
    
    def _export_pdf_native(self, filename, exam_count):
        """Try native Qt PDF export using QPrinter"""
        try:
            from PyQt5.QtPrintSupport import QPrinter
            from PyQt5.QtWebEngineWidgets import QWebEngineView
            
            logger.info("Attempting native Qt PDF export")
            
            # Create HTML content with proper Persian fonts
            html_content = self._generate_pdf_html(exam_count)
            
            # Create web view for rendering
            web_view = QWebEngineView()
            web_view.setHtml(html_content)
            
            # Create printer with proper settings for RTL
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(filename)
            printer.setPageSize(QPrinter.A4)
            printer.setPageMargins(20, 20, 20, 20, QPrinter.Millimeter)
            
            # Set up completion handler
            def on_load_finished(success):
                if success:
                    logger.info("Web view loaded successfully, generating PDF")
                    web_view.page().printToPdf(filename)
                else:
                    logger.error("Web view failed to load content")
                    self._export_pdf_fallback(filename, exam_count)
            
            def on_pdf_finished(file_path, success):
                web_view.deleteLater()
                if success and os.path.exists(filename) and os.path.getsize(filename) > 0:
                    logger.info(f"PDF successfully generated: {filename}")
                    QtWidgets.QMessageBox.information(
                        self, 'صدور موفق PDF', 
                        f'برنامه امتحانات با موفقیت در فایل PDF ذخیره شد:\n{filename}\n\n'
                        f'تعداد دروس: {exam_count}'
                    )
                else:
                    logger.error("PDF generation failed, falling back to HTML")
                    self._export_pdf_fallback(filename, exam_count)
            
            web_view.loadFinished.connect(on_load_finished)
            web_view.page().pdfPrintingFinished.connect(on_pdf_finished)
            
            return True
            
        except ImportError as e:
            logger.warning(f"Qt WebEngine not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Native PDF export failed: {e}", exc_info=True)
            return False
    
    def _export_pdf_fallback(self, filename, exam_count):
        """Fallback HTML export with PDF conversion instructions"""
        logger.info("Using HTML fallback for PDF export")
        
        try:
            html_content = self._generate_pdf_html(exam_count)
            html_filename = filename.replace('.pdf', '_exam_schedule.html')
            
            with open(html_filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML file generated successfully: {html_filename}")
            
            QtWidgets.QMessageBox.information(
                self, 'صدور HTML (آماده برای PDF)', 
                f'فایل HTML با قابلیت تبدیل به PDF ذخیره شد.\n\n'
                f'راهنمای تبدیل به PDF:\n'
                f'۱. فایل HTML را در مرورگر باز کنید\n'
                f'۲. Ctrl+P یا کلید ترکیبی پرینت را فشار دهید\n'
                f'۳. در بخش مقصد، "Save as PDF" را انتخاب کنید\n'
                f'۴. فایل PDF را ذخیره کنید\n\n'
                f'فایل HTML: {html_filename}'
            )
            
        except Exception as e:
            logger.error(f"HTML fallback export failed: {e}", exc_info=True)
            raise
    
    def _generate_pdf_html(self, exam_count):
        """Generate HTML content optimized for PDF export with Persian support"""
        from datetime import datetime
        current_date = datetime.now().strftime('%Y/%m/%d - %H:%M')
        
        # Collect exam data
        exam_data = []
        for row in range(exam_count):
            exam_data.append({
                'name': self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else '',
                'code': self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else '',
                'instructor': self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else '',
                'exam_time': self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else '',
                'location': self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
            })
        
        # Generate table rows
        table_rows = ""
        for i, exam in enumerate(exam_data):
            row_class = "even-row" if i % 2 == 0 else "odd-row"
            table_rows += f"""
                <tr class="{row_class}">
                    <td class="course-name">{exam['name']}</td>
                    <td class="course-code">{exam['code']}</td>
                    <td class="instructor">{exam['instructor']}</td>
                    <td class="exam-time">{exam['exam_time']}</td>
                    <td class="location">{exam['location']}</td>
                </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="fa">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>برنامه امتحانات - Schedule Planner</title>
            <style>
                @page {{
                    size: A4;
                    margin: 15mm;
                    @bottom-center {{
                        content: "صفحه " counter(page) " از " counter(pages);
                        font-size: 10px;
                        color: #666;
                    }}
                }}
                
                * {{
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Tahoma', 'Arial Unicode MS', 'Segoe UI', sans-serif;
                    background: white;
                    color: #2c3e50;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    font-size: 14px;
                }}
                
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                
                .header h1 {{
                    margin: 0 0 10px 0;
                    font-size: 24px;
                    font-weight: bold;
                }}
                
                .header p {{
                    margin: 5px 0;
                    font-size: 16px;
                    opacity: 0.9;
                }}
                
                .exam-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    border-radius: 8px;
                    overflow: hidden;
                }}
                
                .exam-table th {{
                    background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
                    color: white;
                    padding: 15px 12px;
                    text-align: center;
                    font-weight: bold;
                    font-size: 14px;
                    border: none;
                }}
                
                .exam-table td {{
                    padding: 12px;
                    text-align: center;
                    border-bottom: 1px solid #ecf0f1;
                    vertical-align: middle;
                }}
                
                .even-row {{
                    background-color: #f8f9fa;
                }}
                
                .odd-row {{
                    background-color: white;
                }}
                
                .course-name {{
                    font-weight: bold;
                    color: #2c3e50;
                    text-align: right;
                    padding-right: 15px;
                }}
                
                .course-code {{
                    font-family: 'Courier New', monospace;
                    background: #ecf0f1;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-weight: bold;
                }}
                
                .exam-time {{
                    font-weight: bold;
                    color: #e74c3c;
                    background: #fff5f5;
                    border-radius: 4px;
                    padding: 6px;
                }}
                
                .instructor {{
                    color: #34495e;
                }}
                
                .location {{
                    color: #7f8c8d;
                    font-size: 12px;
                }}
                
                .footer {{
                    margin-top: 40px;
                    padding: 15px;
                    text-align: center;
                    background: #ecf0f1;
                    border-radius: 8px;
                    color: #7f8c8d;
                    font-size: 12px;
                    border-top: 3px solid #3498db;
                }}
                
                .stats {{
                    display: flex;
                    justify-content: space-around;
                    margin: 20px 0;
                    padding: 15px;
                    background: #e8f6f3;
                    border-radius: 8px;
                    border: 2px solid #1abc9c;
                }}
                
                .stat-item {{
                    text-align: center;
                }}
                
                .stat-number {{
                    font-size: 20px;
                    font-weight: bold;
                    color: #1abc9c;
                }}
                
                .stat-label {{
                    font-size: 12px;
                    color: #2c3e50;
                    margin-top: 5px;
                }}
                
                @media print {{
                    body {{
                        print-color-adjust: exact;
                        -webkit-print-color-adjust: exact;
                    }}
                    
                    .header, .exam-table th {{
                        background: #667eea !important;
                        color: white !important;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📅 برنامه امتحانات</h1>
                <p>برنامه‌ریز انتخاب واحد - Schedule Planner v2.0</p>
            </div>
            
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-number">{exam_count}</div>
                    <div class="stat-label">تعداد دروس</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{current_date}</div>
                    <div class="stat-label">تاریخ تولید</div>
                </div>
            </div>
            
            <table class="exam-table">
                <thead>
                    <tr>
                        <th>نام درس</th>
                        <th>کد درس</th>
                        <th>استاد</th>
                        <th>زمان امتحان</th>
                        <th>محل برگزاری</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            
            <div class="footer">
                <strong>تولید شده توسط برنامه‌ریز انتخاب واحد</strong><br>
                Schedule Planner v2.0 - Course Selection System<br>
                تاریخ و زمان تولید: {current_date}
            </div>
        </body>
        </html>
        """
        
        return html_content


# ---------------------- پنجرهٔ اصلی ----------------------
class SchedulerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('برنامه‌ریز انتخاب واحد - Schedule Planner v2.0')
        self.resize(1300, 850)
        self.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        # Initialize status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage('آماده - برای شروع، درسی را از لیست انتخاب کنید')
        
        self.courses = []
        # load user data (custom courses, saved combos)
        self.user_data = load_user_data()
        # ensure saved combos list exists
        if 'saved_combos' not in self.user_data:
            self.user_data['saved_combos'] = []

        # combinations used for presets
        self.combinations = []

        # placed courses
        self.placed = {}
        self.preview_cells = []
        self.last_hover_key = None

        # Initialize UI
        self.init_ui()
        
        # populate UI with data
        self.populate_course_list()
        self.load_saved_combos_ui()
        
        # Update status
        self.update_status()
        
        # Initialize detailed info window reference
        self.detailed_info_window = None
        
        # Create menu bar
        self.create_menu_bar()
        
    def create_menu_bar(self):
        """Create menu bar with navigation options"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('📁 فایل')
        
        import_action = QtWidgets.QAction('📎 بارگذاری داده‌ها', self)
        import_action.triggered.connect(self.import_json)
        file_menu.addAction(import_action)
        
        export_action = QtWidgets.QAction('📎 صدور داده‌ها', self)
        export_action.triggered.connect(self.export_json)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        save_image_action = QtWidgets.QAction('🖼️ ذخیره تصویر جدول', self)
        save_image_action.triggered.connect(self.save_table_image)
        file_menu.addAction(save_image_action)
        
        # View menu
        view_menu = menubar.addMenu('👁️ نمایش')
        
        detailed_info_action = QtWidgets.QAction('📊 اطلاعات تفصیلی و برنامه امتحانات', self)
        detailed_info_action.setShortcut('Ctrl+D')
        detailed_info_action.triggered.connect(self.open_detailed_info_window)
        view_menu.addAction(detailed_info_action)
        
        # Course menu
        course_menu = menubar.addMenu('📚 دروس')
        
        add_course_action = QtWidgets.QAction('➕ افزودن درس جدید', self)
        add_course_action.triggered.connect(self.open_add_course_dialog)
        course_menu.addAction(add_course_action)
        
        edit_course_action = QtWidgets.QAction('✏️ ویرایش درس', self)
        edit_course_action.triggered.connect(self.open_edit_course_dialog)
        course_menu.addAction(edit_course_action)
        
        course_menu.addSeparator()
        
        clear_table_action = QtWidgets.QAction('🧹 پاک کردن جدول', self)
        clear_table_action.triggered.connect(self.clear_table)
        course_menu.addAction(clear_table_action)
        
    def open_detailed_info_window(self):
        """Open the detailed information window"""
        # Create window if it doesn't exist or was closed
        if not self.detailed_info_window or not self.detailed_info_window.isVisible():
            self.detailed_info_window = DetailedInfoWindow(self)
            
        # Show and raise the window
        self.detailed_info_window.show()
        self.detailed_info_window.raise_()
        self.detailed_info_window.activateWindow()
        
        # Update content with latest data
        self.detailed_info_window.update_content()
        
    def update_detailed_info_if_open(self):
        """Update detailed info window if it's open and visible"""
        if (hasattr(self, 'detailed_info_window') and 
            self.detailed_info_window and 
            self.detailed_info_window.isVisible()):
            self.detailed_info_window.update_content()
        
    def init_ui(self):
        """Initialize the user interface"""
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtWidgets.QHBoxLayout(main_widget)

        # left panel: controls
        left_v = QtWidgets.QVBoxLayout()

        # presets box
        presets_box = QtWidgets.QGroupBox('پیشنهادهای خودکار (پِرزِت)')
        self.presets_layout = QtWidgets.QVBoxLayout()  # Store reference
        presets_box.setLayout(self.presets_layout)
        self.preset_buttons = []
        self.update_preset_buttons()
        for btn in self.preset_buttons:
            self.presets_layout.addWidget(btn)
        left_v.addWidget(presets_box)

        # generate best schedule from selected groups
        gen_box = QtWidgets.QGroupBox('چیدن خودکار (بر اساس دروس انتخاب‌شده)')
        gen_layout = QtWidgets.QVBoxLayout()
        gen_box.setLayout(gen_layout)
        self.auto_select_list = QtWidgets.QListWidget()
        self.auto_select_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        gen_layout.addWidget(QtWidgets.QLabel(
            'برای اضافه به لیست، از بین دروس سمت پایین انتخاب کنید و دکمه "افزودن به لیست خودکار" را بزنید.'))
        
        # Auto list management buttons
        auto_btn_layout = QtWidgets.QHBoxLayout()
        add_to_auto_btn = QtWidgets.QPushButton('افزودن به لیست خودکار')
        add_to_auto_btn.clicked.connect(self.add_selected_to_auto)
        remove_from_auto_btn = QtWidgets.QPushButton('حذف از لیست')
        remove_from_auto_btn.clicked.connect(self.remove_selected_from_auto)
        remove_from_auto_btn.setStyleSheet("QPushButton { background-color: #ff6b6b; }")
        auto_btn_layout.addWidget(add_to_auto_btn)
        auto_btn_layout.addWidget(remove_from_auto_btn)
        gen_layout.addLayout(auto_btn_layout)
        
        gen_layout.addWidget(QtWidgets.QLabel('دوره‌های انتخاب‌شده برای خودکارسازی (گروه‌ها):'))
        gen_layout.addWidget(self.auto_select_list)
        gen_btn = QtWidgets.QPushButton('تولید بهترین برنامه (کمترین روز)')
        gen_btn.clicked.connect(self.generate_best_for_auto_list)
        gen_btn.setStyleSheet("QPushButton { background-color: #28a745; font-weight: bold; }")
        gen_layout.addWidget(gen_btn)
        left_v.addWidget(gen_box)

        # saved combos
        saved_box = QtWidgets.QGroupBox('ترکیب‌های ذخیره‌شده (آرشیو کاربر)')
        saved_layout = QtWidgets.QVBoxLayout()
        saved_box.setLayout(saved_layout)
        self.saved_combos_list = QtWidgets.QListWidget()
        self.saved_combos_list.itemDoubleClicked.connect(self.load_saved_combo)
        saved_layout.addWidget(self.saved_combos_list)
        save_current_btn = QtWidgets.QPushButton('ذخیرهٔ ترکیب فعلی')
        save_current_btn.clicked.connect(self.save_current_combo)
        del_saved_btn = QtWidgets.QPushButton('حذف ترکیب انتخاب‌شده')
        del_saved_btn.clicked.connect(self.delete_selected_saved_combo)
        saved_layout.addWidget(save_current_btn)
        saved_layout.addWidget(del_saved_btn)
        left_v.addWidget(saved_box)

        # Add course management buttons
        course_mgmt_layout = QtWidgets.QHBoxLayout()
        add_course_btn = QtWidgets.QPushButton('افزودن درس جدید')
        add_course_btn.clicked.connect(self.open_add_course_dialog)
        course_mgmt_layout.addWidget(add_course_btn)
        left_v.addLayout(course_mgmt_layout)

        # save image button
        save_img_btn = QtWidgets.QPushButton('ذخیرهٔ تصویر جدول (فقط جدول)')
        save_img_btn.clicked.connect(self.save_table_image)
        left_v.addWidget(save_img_btn)
        
        # Clear table button
        clear_btn = QtWidgets.QPushButton('پاک کردن کل جدول')
        clear_btn.clicked.connect(self.clear_table)
        clear_btn.setStyleSheet("QPushButton { background-color: #ff6b6b; color: white; font-weight: bold; }")
        left_v.addWidget(clear_btn)
        
        # Detailed Information button
        detailed_info_btn = QtWidgets.QPushButton('📊 اطلاعات تفصیلی و برنامه امتحانات')
        detailed_info_btn.clicked.connect(self.open_detailed_info_window)
        detailed_info_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #667eea, stop: 1 #764ba2);
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #764ba2, stop: 1 #667eea);
            }
            QPushButton:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #5a4b9a, stop: 1 #5a72d2);
            }
        """)
        left_v.addWidget(detailed_info_btn)

        left_v.addStretch()

        # right panel: course list and table
        right_v = QtWidgets.QVBoxLayout()

        self.course_list = DraggableCourseList()
        self.course_list.itemClicked.connect(self.on_course_clicked)
        self.course_list.setMouseTracking(True)
        self.course_list.viewport().installEventFilter(self)
        self.course_list.installEventFilter(self)  # Also install on the widget itself
        right_v.addWidget(QtWidgets.QLabel('<b>لیست دروس (Hover=پیش‌نمایش, Click=اضافه)</b>'))
        right_v.addWidget(self.course_list, 2)

        # table
        self.table = ScheduleTable(len(TIME_SLOTS), len(DAYS), parent=self)
        self.table.setHorizontalHeaderLabels(DAYS)
        self.table.setVerticalHeaderLabels(TIME_SLOTS)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(self.on_table_double_clicked)
        right_v.addWidget(self.table, 4)

        main_layout.addLayout(left_v, 0)
        main_layout.addLayout(right_v, 1)
        
    def create_course_info_panel(self, parent_layout):
        """Create the course information and exam schedule panel"""
        info_widget = QtWidgets.QTabWidget()
        info_widget.setMaximumHeight(200)
        
        # Course Descriptions Tab
        desc_tab = QtWidgets.QWidget()
        desc_layout = QtWidgets.QVBoxLayout(desc_tab)
        
        self.course_desc_text = QtWidgets.QTextEdit()
        self.course_desc_text.setReadOnly(True)
        self.course_desc_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 4px;
                font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
                font-size: 11px;
                padding: 8px;
            }
        """)
        desc_layout.addWidget(QtWidgets.QLabel('<b>اطلاعات عمومی دروس:</b>'))
        desc_layout.addWidget(self.course_desc_text)
        
        # Exam Schedule Tab
        exam_tab = QtWidgets.QWidget()
        exam_layout = QtWidgets.QVBoxLayout(exam_tab)
        
        self.exam_schedule_text = QtWidgets.QTextEdit()
        self.exam_schedule_text.setReadOnly(True)
        self.exam_schedule_text.setStyleSheet("""
            QTextEdit {
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
                font-size: 11px;
                padding: 8px;
            }
        """)
        exam_layout.addWidget(QtWidgets.QLabel('<b>برنامه امتحانات:</b>'))
        exam_layout.addWidget(self.exam_schedule_text)
        
        # Add tabs
        info_widget.addTab(desc_tab, 'توضیحات دروس')
        info_widget.addTab(exam_tab, 'برنامه امتحانات')
        
        parent_layout.addWidget(info_widget, 2)
        
        # Initialize with current course data
        self.update_course_info_panel()
        
    def update_course_info_panel(self):
        """Update the course information and exam schedule panels"""
        if not hasattr(self, 'course_desc_text') or not hasattr(self, 'exam_schedule_text'):
            return
            
        # Course descriptions
        desc_html = "<style>body { font-family: Arial, sans-serif; line-height: 1.4; }</style>"
        desc_html += "<h3 style='color: #2c3e50; margin-top: 0;'>اطلاعات عمومی دروس</h3>"
        
        course_count = 0
        for course_key, course in COURSES.items():
            if course_count >= 10:  # Limit display to avoid clutter
                desc_html += "<p style='color: #7f8c8d; font-style: italic;'>و دروس دیگر...</p>"
                break
                
            desc_html += f"<div style='margin-bottom: 15px; padding: 10px; background-color: #ecf0f1; border-radius: 5px;'>"
            desc_html += f"<h4 style='color: #34495e; margin: 0 0 5px 0;'>{course.get('name', 'نامشخص')}</h4>"
            desc_html += f"<p style='margin: 0; color: #7f8c8d; font-size: 12px;'><strong>کد:</strong> {course.get('code', 'نامشخص')} | "
            desc_html += f"<strong>استاد:</strong> {course.get('instructor', 'نامشخص')} | "
            desc_html += f"<strong>واحد:</strong> {course.get('credits', 0)}</p>"
            desc_html += f"<p style='margin: 5px 0 0 0; font-size: 11px; color: #2c3e50;'>{course.get('description', 'توضیحی ارائه نشده')}</p>"
            desc_html += "</div>"
            course_count += 1
            
        self.course_desc_text.setHtml(desc_html)
        
        # Exam schedules
        exam_html = "<style>body { font-family: Arial, sans-serif; line-height: 1.4; }</style>"
        exam_html += "<h3 style='color: #d35400; margin-top: 0;'>برنامه امتحانات (فقط دروس انتخابی)</h3>"
        
        # Get currently placed courses
        placed_courses = set()
        if hasattr(self, 'placed'):
            for info in self.placed.values():
                placed_courses.add(info['course'])
        
        if not placed_courses:
            exam_html += "<p style='color: #7f8c8d; font-style: italic; text-align: center;'>هیچ درسی در جدول قرار نداده شده است.</p>"
        else:
            exam_html += "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
            exam_html += "<tr style='background-color: #f39c12; color: white;'>"
            exam_html += "<th style='padding: 8px; border: 1px solid #ddd; text-align: center;'>نام درس</th>"
            exam_html += "<th style='padding: 8px; border: 1px solid #ddd; text-align: center;'>استاد</th>"
            exam_html += "<th style='padding: 8px; border: 1px solid #ddd; text-align: center;'>زمان امتحان</th>"
            exam_html += "</tr>"
            
            exam_count = 0
            for course_key in placed_courses:
                course = COURSES.get(course_key)
                if course:
                    bg_color = "#fff" if exam_count % 2 == 0 else "#f8f9fa"
                    exam_html += f"<tr style='background-color: {bg_color};'>"
                    exam_html += f"<td style='padding: 6px; border: 1px solid #ddd; font-size: 10px; font-weight: bold;'>{course.get('name', 'نامشخص')}</td>"
                    exam_html += f"<td style='padding: 6px; border: 1px solid #ddd; font-size: 10px;'>{course.get('instructor', 'نامشخص')}</td>"
                    exam_html += f"<td style='padding: 6px; border: 1px solid #ddd; font-size: 10px; font-weight: bold; color: #e74c3c;'>{course.get('exam_time', 'اعلام نشده')}</td>"
                    exam_html += "</tr>"
                    exam_count += 1
                    
            exam_html += "</table>"
            
            if exam_count > 0:
                exam_html += f"<p style='color: #27ae60; font-weight: bold; margin-top: 10px; font-size: 11px; text-align: center;'>جمعاً {exam_count} درس انتخاب شده</p>"
            
        self.exam_schedule_text.setHtml(exam_html)
        
    def update_course_info_panel(self):
        """Placeholder method for backward compatibility"""
        # This method was removed from main interface but kept for compatibility
        # with other parts of the code that may call it
        pass
        
    def update_status(self):
        """Update status bar with current schedule info"""
        if not self.placed:
            self.status_bar.showMessage('آماده - برای شروع، درسی را از لیست انتخاب کنید')
            return
            
        # Calculate schedule statistics
        unique_courses = set(info['course'] for info in self.placed.values())
        total_credits = sum(COURSES.get(course, {}).get('credits', 0) for course in unique_courses)
        days_used = set()
        for course_key in unique_courses:
            course = COURSES.get(course_key, {})
            for sess in course.get('schedule', []):
                days_used.add(sess['day'])
                
        status_text = f'دروس: {len(unique_courses)} | واحدها: {total_credits} | روزهای حضور: {len(days_used)}'
        self.status_bar.showMessage(status_text)

    # ---------------------- presets ----------------------
    def refresh_preset_buttons_layout(self):
        """Refresh the preset buttons layout to show new options"""
        self.update_preset_buttons()
        
        # Find and update the presets layout
        if hasattr(self, 'presets_layout') and self.presets_layout:
            # Clear existing buttons
            for i in reversed(range(self.presets_layout.count())):
                item = self.presets_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setParent(None)
            
            # Add new buttons
            for btn in self.preset_buttons:
                self.presets_layout.addWidget(btn)
        else:
            # Fallback: try to find presets box and update
            self.update_preset_buttons()
    
    def update_preset_buttons(self):
        """Create or update 4 preset buttons based on current combinations"""
        # create or update 4 preset buttons based on current self.combinations
        self.preset_buttons = []
        top4 = self.combinations[:4]
        for i in range(4):
            if i < len(top4):
                combo = top4[i]
                # Create more detailed button text
                course_names = []
                for course_key in combo['courses']:
                    if course_key in COURSES:
                        name = COURSES[course_key]['name']
                        # Shorten long names
                        if len(name) > 20:
                            name = name[:17] + "..."
                        course_names.append(name)
                
                text = f"گزینه {i + 1} — روز: {combo['days']} — خالی: {combo['empty']:.1f}h\n"
                text += f"دروس: {', '.join(course_names[:2])}"
                if len(course_names) > 2:
                    text += f" و {len(course_names)-2} درس دیگر"
                
                btn = QtWidgets.QPushButton(text)
                btn.clicked.connect(lambda checked, idx=i: self.apply_preset(idx))
                btn.setMinimumHeight(60)
                # QPushButton doesn't have setWordWrap, but we can use setSizePolicy and style
                btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
                btn.setStyleSheet("QPushButton { text-align: left; padding: 8px; }")
            else:
                btn = QtWidgets.QPushButton(f"گزینه {i + 1} (غیرفعال)")
                btn.setEnabled(False)
            self.preset_buttons.append(btn)

    def apply_preset(self, idx):
        """Apply a preset schedule combination"""
        if idx >= len(self.combinations):
            return
        combo = self.combinations[idx]
        
        # Clear current schedule
        self.clear_table_silent()  # Silent clear for preset application
        
        # Apply new combination
        success_count = 0
        for course_key in combo['courses']:
            if course_key in COURSES:
                self.add_course_to_table(course_key, ask_on_conflict=False)
                success_count += 1
        
        # Update status and show result
        self.update_status()
        QtWidgets.QMessageBox.information(
            self, 'پیشنهاد اعمال شد', 
            f'گزینه {idx + 1} با موفقیت اعمال شد.\n'
            f'تعداد دروس: {success_count}\n'
            f'روزهای حضور: {combo["days"]}\n'
            f'زمان خالی: {combo["empty"]:.1f} ساعت'
        )
        
    def clear_table_silent(self):
        """Clear table without confirmation dialog (for internal use)"""
        # Clear all placed courses
        for (srow, scol), info in list(self.placed.items()):
            span = info['rows']
            self.table.removeCellWidget(srow, scol)
            for r in range(srow, srow + span):
                self.table.setItem(r, scol, QtWidgets.QTableWidgetItem(''))
            self.table.setSpan(srow, scol, 1, 1)
        self.placed.clear()
        
        # Clear any preview cells
        self.clear_preview()

    def clear_table(self):
        """Clear all courses from the table"""
        if not self.placed:
            QtWidgets.QMessageBox.information(self, 'اطلاع', 'جدول خالی است.')
            return
            
        # Ask for confirmation
        res = QtWidgets.QMessageBox.question(
            self, 'پاک کردن جدول', 
            'آیا مطمئن هستید که می‌خواهید تمام دروس را از جدول حذف کنید؟',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if res != QtWidgets.QMessageBox.Yes:
            return
            
        # Clear all placed courses
        for (srow, scol), info in list(self.placed.items()):
            span = info['rows']
            self.table.removeCellWidget(srow, scol)
            for r in range(srow, srow + span):
                self.table.setItem(r, scol, QtWidgets.QTableWidgetItem(''))
            self.table.setSpan(srow, scol, 1, 1)
        self.placed.clear()
        
        # Clear any preview cells
        self.clear_preview()
        
        # Update status
        self.update_status()
        
        # Update course info panel
        self.update_course_info_panel()
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()
        
        QtWidgets.QMessageBox.information(self, 'پاک شد', 'تمام دروس از جدول حذف شدند.')

    # ---------------------- eventFilter for hover ----------------------
    def eventFilter(self, obj, event):
        """Handle hover events for course preview with improved position mapping"""
        if obj == self.course_list.viewport() or obj == self.course_list:
            if event.type() == QtCore.QEvent.MouseMove:
                # Map position correctly whether from viewport or list widget
                if obj == self.course_list:
                    # Map global position to viewport coordinates
                    global_pos = obj.mapToGlobal(event.pos())
                    pos = self.course_list.viewport().mapFromGlobal(global_pos)
                else:
                    pos = event.pos()
                
                item = self.course_list.itemAt(pos)
                if item:
                    key = item.data(QtCore.Qt.UserRole)
                    if key and getattr(self, 'last_hover_key', None) != key:
                        self.clear_preview()
                        self.last_hover_key = key
                        self.preview_course(key)
                else:
                    self.clear_preview()
                    self.last_hover_key = None
            elif event.type() == QtCore.QEvent.Leave:
                self.clear_preview()
                self.last_hover_key = None
        return super().eventFilter(obj, event)

    # ---------------------- populate UI ----------------------
    def populate_course_list(self):
        """Populate the course list with all available courses"""
        self.course_list.clear()
        used = 0
        
        for key, course in COURSES.items():
            # Create list item
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, key)
            
            # Set background color
            color = COLOR_MAP[used % len(COLOR_MAP)]
            item.setBackground(QtGui.QBrush(color))
            
            # Create tooltip with detailed info
            tooltip = f"نام: {course['name']}\nکد: {course['code']}\nاستاد: {course.get('instructor', 'نامشخص')}\nمحل: {course.get('location', 'نامشخص')}\nواحد: {course.get('credits', 'نامشخص')}"
            if course.get('schedule'):
                tooltip += "\nجلسات:"
                for sess in course['schedule']:
                    parity_text = ''
                    if sess.get('parity') == 'ز':
                        parity_text = ' (زوج)'
                    elif sess.get('parity') == 'ف':
                        parity_text = ' (فرد)'
                    tooltip += f"\n  {sess['day']}: {sess['start']}-{sess['end']}{parity_text}"
            item.setToolTip(tooltip)
            
            # Add item to list
            self.course_list.addItem(item)
            
            # Create custom widget for the item
            course_widget = CourseListWidget(key, course, self.course_list, self)
            course_widget.setStyleSheet(f"background-color: rgba({color.red()},{color.green()},{color.blue()},100);")
            
            # Set the custom widget for this item
            item.setSizeHint(course_widget.sizeHint())
            self.course_list.setItemWidget(item, course_widget)
            
            used += 1

    # ---------------------- saved combos management ----------------------
    def load_saved_combos_ui(self):
        self.saved_combos_list.clear()
        for sc in self.user_data.get('saved_combos', []):
            name = sc.get('name', 'بدون نام')
            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, sc)
            self.saved_combos_list.addItem(item)

    def save_current_combo(self):
        # collect currently placed course keys
        keys = list({info['course'] for info in self.placed.values()})
        if not keys:
            QtWidgets.QMessageBox.information(self, 'ذخیره', 'هیچ درسی در جدول قرار داده نشده است.')
            return
        name, ok = QtWidgets.QInputDialog.getText(self, 'نام ترکیب', 'نام ترکیب را وارد کنید:')
        if not ok or not name.strip():
            return
        sc = {'name': name.strip(), 'courses': keys}
        self.user_data.setdefault('saved_combos', []).append(sc)
        save_user_data(self.user_data)
        self.load_saved_combos_ui()
        QtWidgets.QMessageBox.information(self, 'ذخیره', 'ترکیب شما ذخیره شد.')

    def delete_selected_saved_combo(self):
        item = self.saved_combos_list.currentItem()
        if not item:
            return
        sc = item.data(QtCore.Qt.UserRole)
        res = QtWidgets.QMessageBox.question(self, 'حذف', f"آیا از حذف ترکیب '{sc.get('name')}' مطمئن هستید؟",
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if res != QtWidgets.QMessageBox.Yes:
            return
        self.user_data['saved_combos'] = [x for x in self.user_data.get('saved_combos', []) if x != sc]
        save_user_data(self.user_data)
        self.load_saved_combos_ui()

    def load_saved_combo(self, item):
        """Load a saved schedule combination"""
        sc = item.data(QtCore.Qt.UserRole)
        course_keys = sc.get('courses', [])
        
        # Clear current schedule
        self.clear_table_silent()
        
        # Load courses
        loaded_count = 0
        for k in course_keys:
            if k in COURSES:
                self.add_course_to_table(k, ask_on_conflict=False)
                loaded_count += 1
                
        self.update_status()
        QtWidgets.QMessageBox.information(
            self, 'بارگذاری', 
            f"ترکیب '{sc.get('name')}' بارگذاری شد.\n"
            f"تعداد دروس بارگذاری شده: {loaded_count}"
        )
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()

    # ---------------------- auto list helpers ----------------------
    def add_selected_to_auto(self):
        """Add selected courses to auto-scheduling list"""
        items = self.course_list.selectedItems()
        if not items:
            QtWidgets.QMessageBox.information(self, 'انتخاب', 'لطفا حداقل یک درس را از لیست انتخاب کنید.')
            return
            
        added_count = 0
        for item in items:
            key = item.data(QtCore.Qt.UserRole)
            if not key or key not in COURSES:
                continue
                
            # group key based on code prefix
            code = COURSES[key].get('code', '')
            base = code.split('_')[0] if '_' in code else code
            # represent as 'base — name'
            entry_text = f"{base} — {COURSES[key]['name']}"
            
            # avoid duplicates
            existing = [self.auto_select_list.item(i).text() for i in range(self.auto_select_list.count())]
            if entry_text not in existing:
                auto_item = QtWidgets.QListWidgetItem(entry_text)
                auto_item.setData(QtCore.Qt.UserRole, base)
                self.auto_select_list.addItem(auto_item)
                added_count += 1
                
        if added_count > 0:
            QtWidgets.QMessageBox.information(
                self, 'افزوده شد', 
                f'{added_count} دوره به لیست خودکار اضافه شدند.'
            )
        else:
            QtWidgets.QMessageBox.information(
                self, 'هیچ موردی', 
                'هیچ دوره جدیدی برای اضافه کردن پیدا نشد (ممکن است تکراری باشند).'
            )
            
    def remove_selected_from_auto(self):
        """Remove selected courses from auto-scheduling list"""
        selected_items = self.auto_select_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(
                self, 'انتخاب', 
                'لطفا حداقل یک مورد را برای حذف انتخاب کنید.'
            )
            return
            
        # Confirm deletion
        course_names = [item.text().split(' — ')[1] if ' — ' in item.text() else item.text() 
                       for item in selected_items]
        
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle('حذف از لیست خودکار')
        msg.setText(f'آیا مطمئن هستید که می‌خواهید موارد زیر را از لیست حذف کنید؟')
        msg.setDetailedText('\n'.join([f"• {name}" for name in course_names]))
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg.setDefaultButton(QtWidgets.QMessageBox.No)
        
        if msg.exec_() == QtWidgets.QMessageBox.Yes:
            # Remove selected items
            for item in selected_items:
                row = self.auto_select_list.row(item)
                self.auto_select_list.takeItem(row)
                
            QtWidgets.QMessageBox.information(
                self, 'حذف شد', 
                f'{len(selected_items)} مورد از لیست خودکار حذف شدند.'
            )

    def generate_best_for_auto_list(self):
        """Generate best schedule combinations for selected course groups - FIXED"""
        # collect base keys from auto_select_list
        group_keys = [self.auto_select_list.item(i).data(QtCore.Qt.UserRole) for i in
                      range(self.auto_select_list.count())]
        if not group_keys:
            QtWidgets.QMessageBox.information(self, 'هیچی انتخاب نشده',
                                              'لطفا حداقل یک دوره برای چیدن خودکار انتخاب کنید.')
            return
        
        # Show progress dialog
        progress = QtWidgets.QProgressDialog('در حال تولید ترکیبات...', 'لغو', 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.show()
        
        try:
            # FIXED: Debug output to check what we're working with
            print(f"Debug: Processing group keys: {group_keys}")
            print(f"Debug: Available COURSES keys: {list(COURSES.keys())[:10]}...")  # Show first 10
            
            combos = generate_best_combinations_for_groups(group_keys)
            progress.setValue(50)
            
            print(f"Debug: Generated {len(combos)} combinations")
            
            if not combos:
                QtWidgets.QMessageBox.warning(
                    self, 'نتیجه', 
                    f'هیچ ترکیب بدون تداخل پیدا نشد.\n\n'
                    f'دروس انتخابی: {", ".join(group_keys)}\n\n'
                    f'لطفا بررسی کنید که دروس مورد نظر در لیست موجود باشند.'
                )
                return
            
            # FIXED: update presets with these new combos
            old_count = len(self.combinations)
            self.combinations = combos + self.combinations
            progress.setValue(75)
            
            # keep unique by courses set to avoid duplicates
            seen = set()
            uniq = []
            for c in self.combinations:
                key = tuple(sorted(c['courses']))
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(c)
            self.combinations = uniq
            progress.setValue(90)
            
            # FIXED: Force update of preset buttons
            self.refresh_preset_buttons_layout()
            progress.setValue(100)
            
            # Show results dialog
            new_count = len(self.combinations) - old_count + len(combos)
            msg = f"{len(combos)} ترکیب جدید تولید شد!\n\n"
            if combos:
                msg += "بهترین گزینه:\n"
                best = combos[0]
                msg += f"تعداد روز حضور: {best['days']}\n"
                msg += f"زمان خالی: {best['empty']:.1f} ساعت\n"
                msg += f"دروس: {len(best['courses'])} درس\n\n"
                msg += "برای اعمال گزینه‌های پیشنهادی، دکمه‌های گزینه را کلیک کنید."
            
            QtWidgets.QMessageBox.information(self, 'تولید موفق', msg)
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, 'خطا', 
                f'خطا در تولید ترکیبات:\n{str(e)}'
            )
            print(f"Error in generate_best_for_auto_list: {e}")
        finally:
            progress.close()

    # ---------------------- پیش‌نمایش و اضافه‌کردن به جدول ----------------------
    def can_place_preview(self, srow, col, span):
        for r in range(srow, srow + span):
            if self.table.cellWidget(r, col) is not None:
                return False
            it = self.table.item(r, col)
            if it and it.text().strip() != '':
                return False
        return True

    def preview_course(self, course_key):
        """Show enhanced preview of course schedule with grey dashed borders"""
        course = COURSES.get(course_key)
        if not course:
            return
            
        for sess in course['schedule']:
            if sess['day'] not in DAYS:
                continue
            col = DAYS.index(sess['day'])
            try:
                srow = TIME_SLOTS.index(sess['start'])
                erow = TIME_SLOTS.index(sess['end'])
            except ValueError:
                continue
            span = max(1, erow - srow)
            
            if self.can_place_preview(srow, col, span):
                # Create preview label with enhanced styling
                parity_text = ''
                if sess.get('parity') == 'ز':
                    parity_text = 'زوج'
                elif sess.get('parity') == 'ف':
                    parity_text = 'فرد'
                else:
                    parity_text = 'همه هفته‌ها'
                
                preview_text = f"{course['name']}\n{course.get('instructor', 'نامشخص')}\n{parity_text}\n{course.get('code', '')}\n{course.get('location', '')}"
                
                lbl = QtWidgets.QLabel(preview_text)
                lbl.setAlignment(QtCore.Qt.AlignCenter)
                lbl.setWordWrap(True)
                lbl.setAutoFillBackground(True)
                
                # Enhanced preview styling - grey with dashed borders and semi-transparency
                lbl.setStyleSheet("""
                    QLabel {
                        background-color: rgba(180, 180, 180, 120);
                        border: 3px dashed rgba(100, 100, 100, 180);
                        border-radius: 8px;
                        padding: 6px;
                        font-size: 9px;
                        font-weight: bold;
                        color: rgba(50, 50, 50, 200);
                    }
                """)
                
                self.table.setCellWidget(srow, col, lbl)
                if span > 1:
                    self.table.setSpan(srow, col, span, 1)
                self.preview_cells.append((srow, col, span))

    def clear_preview(self):
        for (srow, col, span) in list(self.preview_cells):
            self.table.removeCellWidget(srow, col)
            self.table.setSpan(srow, col, 1, 1)
            for r in range(srow, srow + span):
                self.table.setItem(r, col, QtWidgets.QTableWidgetItem(''))
        self.preview_cells.clear()

    def on_course_clicked(self, item):
        """Handle course selection from the list"""
        if item is None:
            return
        key = item.data(QtCore.Qt.UserRole)
        if key:
            self.clear_preview()
            self.add_course_to_table(key, ask_on_conflict=True)

    def on_course_double_clicked(self, item):
        """Handle double-click on course (same as single click)"""
        if item is None:
            return
        key = item.data(QtCore.Qt.UserRole)
        if key:
            self.clear_preview()
            self.add_course_to_table(key, ask_on_conflict=True)

    def add_course_to_table(self, course_key, ask_on_conflict=True):
        """Add a course to the schedule table"""
        course = COURSES.get(course_key)
        if not course:
            QtWidgets.QMessageBox.warning(self, 'خطا', f'درس با کلید {course_key} یافت نشد.')
            return
            
        # Check if course is already placed
        already_placed = any(info['course'] == course_key for info in self.placed.values())
        if already_placed:
            QtWidgets.QMessageBox.information(self, 'اطلاع', f'درس "{course["name"]}" قبلاً در جدول قرار داده شده است.')
            return
        
        placements = []
        for sess in course['schedule']:
            if sess['day'] not in DAYS:
                continue
            col = DAYS.index(sess['day'])
            try:
                srow = TIME_SLOTS.index(sess['start'])
                erow = TIME_SLOTS.index(sess['end'])
            except ValueError:
                QtWidgets.QMessageBox.warning(self, 'خطا', f'زمان نامعتبر برای درس {course["name"]}: {sess["start"]}-{sess["end"]}')
                continue
            span = max(1, erow - srow)
            placements.append((srow, col, span, sess))

        # Check for conflicts
        conflicts = []
        for (srow, col, span, sess) in placements:
            for (prow, pcol), info in list(self.placed.items()):
                if pcol != col:
                    continue
                prow_start = prow
                prow_span = info['rows']
                if not (srow + span <= prow_start or prow_start + prow_span <= srow):
                    conflict_course = COURSES.get(info['course'], {})
                    conflicts.append(((srow, col), (prow_start, pcol), info['course'], conflict_course.get('name', 'نامشخص')))

        # Handle conflicts with better warning messages
        if conflicts and ask_on_conflict:
            conflict_details = []
            for conf in conflicts:
                (_, _), (_, _), _, conflict_name = conf
                conflict_details.append(conflict_name)
            
            conflict_list = '\n'.join([f"• {name}" for name in conflict_details])
            
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle('تداخل زمان‌بندی دروس')
            msg.setText(f'درس "{course["name"]}" با دروس زیر تداخل دارد:')
            msg.setDetailedText(f'دروس متداخل:\n{conflict_list}')
            msg.setInformativeText('آیا می‌خواهید دروس متداخل حذف شوند و این درس اضافه گردد؟')
            msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
            msg.setDefaultButton(QtWidgets.QMessageBox.No)
            
            res = msg.exec_()
            if res == QtWidgets.QMessageBox.Cancel:
                return
            elif res != QtWidgets.QMessageBox.Yes:
                # Show warning instead of adding conflicting course
                warning_msg = QtWidgets.QMessageBox()
                warning_msg.setIcon(QtWidgets.QMessageBox.Warning)
                warning_msg.setWindowTitle('تداخل دروس')
                warning_msg.setText(f'درس "{course["name"]}" به دلیل تداخل با دروس زیر اضافه نشد:')
                warning_msg.setDetailedText(conflict_list)
                warning_msg.exec_()
                return
            
            # Remove conflicting courses if user confirmed
            for conf in conflicts:
                (_, _), (rstart, rcol), rcourse, _ = conf
                self.remove_placed_by_start((rstart, rcol))

        # Clear preview
        self.clear_preview()

        # Place course sessions
        color_idx = len(self.placed) % len(COLOR_MAP)
        bg = COLOR_MAP[color_idx]
        for (srow, col, span, sess) in placements:
            parity_text = ''
            if sess.get('parity') == 'ز':
                parity_text = 'زوج'
            elif sess.get('parity') == 'ف':
                parity_text = 'فرد'
            else:
                parity_text = 'همه هفته‌ها'
                
            text = f"{course['name']}\n{course.get('instructor', 'نامشخص')}\n{parity_text}\n{course.get('code', '')}\n{course.get('location', '')}"
            lbl = QtWidgets.QLabel(text)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setAutoFillBackground(True)
            lbl.setStyleSheet(
                f"background-color: rgba({bg.red()},{bg.green()},{bg.blue()},230); "
                f"border: 2px solid rgba({bg.red()//2},{bg.green()//2},{bg.blue()//2},255); "
                f"border-radius: 8px; padding: 6px; font-size: 10px; font-weight: bold;"
            )
            self.table.setCellWidget(srow, col, lbl)
            if span > 1:
                self.table.setSpan(srow, col, span, 1)
            self.placed[(srow, col)] = {'course': course_key, 'rows': span, 'widget': lbl}
            
        # Update status after adding course
        self.update_status()
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()

    def remove_course_from_schedule(self, course_key):
        """Remove all instances of a course from the current schedule"""
        to_remove = []
        for (srow, scol), info in self.placed.items():
            if info['course'] == course_key:
                to_remove.append((srow, scol))
        
        for start_tuple in to_remove:
            self.remove_placed_by_start(start_tuple)
    
    def remove_placed_by_start(self, start_tuple):
        """Remove a placed course session by its starting position"""
        info = self.placed.get(start_tuple)
        if not info:
            return
        srow, col = start_tuple
        span = info['rows']
        self.table.removeCellWidget(srow, col)
        for r in range(srow, srow + span):
            self.table.setItem(r, col, QtWidgets.QTableWidgetItem(''))
        self.table.setSpan(srow, col, 1, 1)
        del self.placed[start_tuple]

    def on_table_double_clicked(self, row, col):
        """Handle double-click on table cells to remove entire courses"""
        found = None
        course_key = None
        
        # Find which course this cell belongs to
        for (srow, scol), info in list(self.placed.items()):
            if scol != col:
                continue
            if srow <= row < srow + info['rows']:
                found = (srow, scol)
                course_key = info['course']
                break
                
        if found and course_key:
            course_name = COURSES.get(course_key, {}).get('name', 'نامشخص')
            instructor = COURSES.get(course_key, {}).get('instructor', 'نامشخص')
            
            res = QtWidgets.QMessageBox.question(
                self, 'حذف کل درس', 
                f'آیا مایل به حذف کل درس "{course_name}" (استاد: {instructor}) هستید؟\n'
                f'تمام جلسات این درس از جدول حذف خواهد شد.',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            if res == QtWidgets.QMessageBox.Yes:
                self.remove_entire_course(course_key)

    def remove_entire_course(self, course_key):
        """Remove all sessions of a specific course from the table"""
        # Find all placements for this course
        to_remove = []
        for (srow, scol), info in self.placed.items():
            if info['course'] == course_key:
                to_remove.append((srow, scol))
        
        # Remove all sessions of this course
        for start_tuple in to_remove:
            self.remove_placed_by_start(start_tuple)
        
        # Update status bar
        self.update_status()
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()
        
        # Show confirmation
        course_name = COURSES.get(course_key, {}).get('name', 'نامشخص')
        QtWidgets.QMessageBox.information(
            self, 'حذف شد', 
            f'تمام جلسات درس "{course_name}" با موفقیت حذف شدند.'
        )

    # ---------------------- افزودن درس سفارشی و ذخیره دیتا ----------------------
    def open_edit_course_dialog(self):
        """Open dialog to edit an existing course (legacy method)"""
        # First, let user select which course to edit
        selected_items = self.course_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(
                self, 'انتخاب درس', 
                'لطفا ابتدا درسی را از لیست انتخاب کنید.'
            )
            return
            
        selected_item = selected_items[0]
        course_key = selected_item.data(QtCore.Qt.UserRole)
        self.open_edit_course_dialog_for_course(course_key)
        
    def open_edit_course_dialog_for_course(self, course_key):
        """Open dialog to edit a specific course by course key"""
        if not course_key or course_key not in COURSES:
            QtWidgets.QMessageBox.warning(
                self, 'خطا', 
                'درس انتخابی یافت نشد.'
            )
            return
            
        course = COURSES[course_key]
        
        # Check if it's a built-in course
        if not self.is_editable_course(course_key):
            QtWidgets.QMessageBox.warning(
                self, 'غیر قابل ویرایش', 
                'دروس پیش‌فرض قابل ویرایش نیستند. فقط دروس سفارشی را می‌توان ویرایش کرد.'
            )
            return
            
        # Open edit dialog with pre-filled data
        dlg = EditCourseDialog(course, self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
            
        updated_course = dlg.get_course_data()
        if not updated_course:
            return
            
        # Update the course
        COURSES[course_key] = updated_course
        
        # Save courses to JSON
        save_courses_to_json()
        
        # Update user_data
        custom_courses = self.user_data.get('custom_courses', [])
        for i, c in enumerate(custom_courses):
            if c.get('code') == course.get('code'):
                custom_courses[i] = updated_course
                break
        
        save_user_data(self.user_data)
        
        # Remove from schedule if placed
        self.remove_course_from_schedule(course_key)
        
        # Refresh UI
        self.populate_course_list()
        self.update_course_info_panel()
        self.update_status()
        
        QtWidgets.QMessageBox.information(
            self, 'ویرایر شد', 
            f'درس "{updated_course["name"]}" با موفقیت ویرایش شد.'
        )
        
    def is_editable_course(self, course_key):
        """Check if a course can be edited (all courses from JSON are now editable)"""
        # With JSON storage, all courses can be edited
        # Only restriction could be based on user permissions or course type
        course = COURSES.get(course_key, {})
        
        # Optional: Add logic to restrict editing of certain courses
        # For now, all courses are editable since they come from JSON
        return True
        
    def open_add_course_dialog(self):
        """Open dialog to add a new custom course"""
        dlg = AddCourseDialog(self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        course = dlg.get_course_data()
        if not course:
            return
        # generate key and store
        key = generate_unique_key(course['code'], COURSES)
        COURSES[key] = course
        
        # Save courses to JSON
        save_courses_to_json()
        
        # save to user data
        self.user_data.setdefault('custom_courses', []).append(course)
        save_user_data(self.user_data)
        
        # refresh list and info panel
        self.populate_course_list()
        self.update_course_info_panel()  # Update info panel
        QtWidgets.QMessageBox.information(self, 'افزودن درس', f'درس "{course["name"]}" با موفقیت اضافه شد و ذخیره شد.')

    # ---------------------- ذخیره تصویر جدول (فقط جدول) ----------------------
    def save_table_image(self):
        """Save table as image (table only, not entire window)"""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "ذخیره تصویر", "schedule_table.png", "PNG Files (*.png)")
        if path:
            # Grab only the table widget
            pixmap = self.table.grab()
            if pixmap.save(path):
                QtWidgets.QMessageBox.information(self, "ذخیره تصویر", "تصویر جدول با موفقیت ذخیره شد.")
            else:
                QtWidgets.QMessageBox.warning(self, "خطا", "خطا در ذخیره تصویر.")

    def export_json(self):
        """Export user data to JSON file"""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export JSON", "backup.json", "JSON Files (*.json)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.user_data, f, indent=2, ensure_ascii=False)
                QtWidgets.QMessageBox.information(self, "خروجی", "فایل با موفقیت ذخیره شد.")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "خطا", f"خطا در ذخیره فایل: {str(e)}")

    def import_json(self):
        """Import user data from JSON file"""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import JSON", "", "JSON Files (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    imported_data = json.load(f)
                # Merge with existing data
                self.user_data.update(imported_data)
                save_user_data(self.user_data)
                # Refresh UI
                self.populate_course_list()
                self.load_saved_combos_ui()
                QtWidgets.QMessageBox.information(self, "ورودی", "فایل با موفقیت بارگذاری شد.")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "خطا", f"خطا در بارگذاری فایل: {str(e)}")


# ---------------------- اجرای برنامه ----------------------

def main():
    """Main function to run the application"""
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('Schedule Planner')
    app.setApplicationVersion('2.0')
    app.setOrganizationName('University Schedule Tools')
    
    # Set application icon if available
    try:
        app.setWindowIcon(QtGui.QIcon('icon.png'))
    except:
        pass  # Icon file not found, continue without it
    
    # Apply a modern stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f0f0f0;
        }
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #106ebe;
        }
        QPushButton:pressed {
            background-color: #005a9e;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            color: #666666;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #cccccc;
            border-radius: 8px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QListWidget {
            border: 1px solid #cccccc;
            border-radius: 4px;
            background-color: white;
        }
        QTableWidget {
            border: 1px solid #cccccc;
            gridline-color: #e0e0e0;
            background-color: white;
        }
        QStatusBar {
            background-color: #e8e8e8;
            border-top: 1px solid #cccccc;
        }
    """)
    
    win = SchedulerWindow()
    win.show()
    
    return app.exec_()


if __name__ == '__main__':
    # Error handling for the main application
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Critical error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


