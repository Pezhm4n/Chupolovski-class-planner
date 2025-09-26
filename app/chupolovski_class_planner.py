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

# Get script directory for absolute paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_FILE = os.path.join(SCRIPT_DIR, 'user_data.json')
COURSES_DATA_FILE = os.path.join(SCRIPT_DIR, 'courses_data.json')
STYLES_FILE = os.path.join(SCRIPT_DIR, 'styles.qss')

# ---------------------- QSS Style Loading ----------------------

def load_qss_styles():
    """Load QSS styles from external file with fallback"""
    try:
        if os.path.exists(STYLES_FILE):
            with open(STYLES_FILE, 'r', encoding='utf-8') as f:
                qss_content = f.read()
                logger.info(f"Successfully loaded styles from {STYLES_FILE}")
                return qss_content
        else:
            logger.warning(f"QSS file not found: {STYLES_FILE}")
    except Exception as e:
        logger.error(f"Error loading QSS file: {e}")
    
    # Return empty string if no QSS file - app will use default styles
    logger.info("Using default Qt styles")
    return ""

# Global COURSES dictionary - will be loaded from JSON
COURSES = {}

# ---------------------- ذخیره و بارگذاری داده‌های درس ----------------------

def load_courses_from_json():
    """Load all courses from JSON file with enhanced error handling"""
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
            
        # Validate JSON structure
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON structure: Root must be a dictionary")
            
        courses_data = data.get('courses', {})
        if not isinstance(courses_data, dict):
            raise ValueError("Invalid JSON structure: 'courses' must be a dictionary")
            
        # Validate each course entry
        valid_courses = {}
        invalid_count = 0
        
        for course_id, course_info in courses_data.items():
            try:
                # Check required fields
                required_fields = ['code', 'name', 'credits', 'instructor', 'schedule']
                for field in required_fields:
                    if field not in course_info:
                        raise ValueError(f"Missing required field '{field}'")
                        
                # Validate schedule structure
                if not isinstance(course_info['schedule'], list):
                    raise ValueError("Schedule must be a list")
                    
                for schedule_item in course_info['schedule']:
                    if not isinstance(schedule_item, dict):
                        raise ValueError("Schedule item must be a dictionary")
                    if 'day' not in schedule_item or 'start' not in schedule_item or 'end' not in schedule_item:
                        raise ValueError("Schedule item missing required fields")
                        
                valid_courses[course_id] = course_info
                logger.debug(f"Successfully validated course: {course_id}")
                
            except Exception as e:
                logger.warning(f"Invalid course data for {course_id}: {e}")
                invalid_count += 1
                continue
                
        COURSES = valid_courses
        logger.info(f"Successfully loaded {len(COURSES)} valid courses from {COURSES_DATA_FILE}")
        if invalid_count > 0:
            logger.warning(f"Skipped {invalid_count} invalid course entries")
            print(f"Warning: Skipped {invalid_count} invalid course entries")
        print(f"Loaded {len(COURSES)} courses from {COURSES_DATA_FILE}")
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {COURSES_DATA_FILE}: {e}", exc_info=True)
        print(f"Error: Invalid JSON format in {COURSES_DATA_FILE}: {e}")
        COURSES = {}
    except (IOError, OSError) as e:
        logger.error(f"File I/O error loading {COURSES_DATA_FILE}: {e}", exc_info=True)
        print(f"Error: Cannot read {COURSES_DATA_FILE}: {e}")
        COURSES = {}
    except Exception as e:
        logger.error(f"Unexpected error loading courses from {COURSES_DATA_FILE}: {e}", exc_info=True)
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
        
        # Conflict indicator label (hidden by default) with enhanced styling
        self.conflict_indicator = QtWidgets.QLabel("⚠ تداخل!")
        self.conflict_indicator.setStyleSheet("""
            color: #e74c3c; 
            font-weight: bold; 
            font-size: 14px;
            background-color: rgba(231, 76, 60, 0.1);
            border: 1px solid #e74c3c;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        self.conflict_indicator.hide()
        layout.addWidget(self.conflict_indicator)
        
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
        self.edit_btn.setObjectName("edit_btn")
        self.edit_btn.setFixedSize(24, 24)
        self.edit_btn.setToolTip(f"ویرایش درس {self.course_info['name']}")
        self.edit_btn.clicked.connect(self.edit_course)
        button_layout.addWidget(self.edit_btn)
        
        # Delete button (only for custom courses)
        if self.is_custom_course():
            self.delete_btn = QtWidgets.QPushButton("✕")
            self.delete_btn.setObjectName("delete_btn")
            self.delete_btn.setFixedSize(24, 24)
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
        """Forward mouse move events to enable hover preview and conflict checking"""
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
                        
                        # Check for conflicts and update indicator
                        self.update_conflict_indicator(main_window, key)
                    break
        
        # Call parent implementation
        super().mouseMoveEvent(event)
    
    def update_conflict_indicator(self, main_window, course_key):
        """Update the conflict indicator based on current schedule"""
        course = COURSES.get(course_key)
        if not course or not main_window.placed:
            self.conflict_indicator.hide()
            return
            
        # Check for conflicts with currently placed courses
        has_conflict = False
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
            
            # Check for conflicts in the same day/time slot
            for (prow, pcol), info in main_window.placed.items():
                if pcol != col:
                    continue
                # Skip conflict check with the same course
                if info['course'] == course_key:
                    continue
                prow_start = prow
                prow_span = info['rows']
                if not (srow + span <= prow_start or prow_start + prow_span <= srow):
                    has_conflict = True
                    break
            
            if has_conflict:
                break
        
        # Update indicator visibility
        if has_conflict:
            self.conflict_indicator.show()
            self.conflict_indicator.setToolTip("این درس با دروس انتخابی شما تداخل دارد")
            # Also highlight the entire widget
            self.setStyleSheet("""
                background-color: rgba(231, 76, 60, 0.1);
                border: 2px solid #e74c3c;
                border-radius: 6px;
                padding: 2px;
            """)
        else:
            self.conflict_indicator.hide()
            # Reset widget styling
            self.setStyleSheet("")
    
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
class AnimatedCourseWidget(QtWidgets.QFrame):
    """Course cell widget with smooth hover effects and conflict visualization"""
    
    def __init__(self, course_key, original_style, has_conflicts=False, parent=None):
        super().__init__(parent)
        self.course_key = course_key
        self.has_conflicts = has_conflicts
        # Handle both string styles and QColor objects
        if isinstance(original_style, QtGui.QColor):
            # Convert QColor to CSS string
            self.original_style = f"background-color: rgba({original_style.red()}, {original_style.green()}, {original_style.blue()}, {original_style.alpha()});"
        else:
            self.original_style = original_style or ""
        
        # Modify style for conflicts
        if self.has_conflicts:
            # Add conflict styling
            if self.original_style:
                # Insert conflict border into existing style
                self.original_style = self.original_style.replace(
                    'border:', 'border: 3px solid #E53935 !important; /* conflict */ border-width: 3px !important;'
                )
                # Add background color for conflicts
                if 'background-color:' not in self.original_style:
                    self.original_style = self.original_style.replace(
                        'border:', 'background-color: rgba(229, 57, 53, 0.2) !important; border:'
                    )
            else:
                self.original_style = "border: 3px solid #E53935 !important; background-color: rgba(229, 57, 53, 0.2) !important;"
        
        # Set frame style for visible borders
        self.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Raised)
        self.setLineWidth(3)
        # Only apply inline style if provided (for background color)
        if self.original_style:
            self.setStyleSheet(self.original_style)
        
        # Set object name for QSS styling
        self.setObjectName('course-cell')
        
        # Set properties for styling based on course type and conflicts
        if self.has_conflicts:
            self.setProperty('conflict', True)
        else:
            self.setProperty('conflict', False)
        
    def enterEvent(self, event):
        """Handle mouse enter event for hover effects"""
        # Apply hover styling
        if self.has_conflicts:
            self.setStyleSheet("""
                QWidget#course-cell[conflict="true"] {
                    border: 4px solid #ff0000 !important;
                    border-radius: 10px !important;
                    background-color: rgba(255, 0, 0, 0.3) !important;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3) !important;
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget#course-cell {
                    border: 4px solid #ff0000 !important;
                    border-radius: 10px !important;
                    background-color: rgba(255, 0, 0, 0.1) !important;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2) !important;
                }
            """)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Handle mouse leave event to restore normal styling"""
        # Restore original styling
        if self.original_style:
            self.setStyleSheet(self.original_style)
        else:
            if self.has_conflicts:
                self.setStyleSheet("""
                    QWidget#course-cell[conflict="true"] {
                        border: 3px solid #E53935 !important;
                        border-radius: 10px !important;
                        background-color: rgba(229, 57, 53, 0.2) !important;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QWidget#course-cell {
                        border: 3px solid #1976D2 !important;
                        border-radius: 10px !important;
                        background-color: rgba(25, 118, 210, 0.15) !important;
                    }
                """)
        super().leaveEvent(event)
        
    def _animate_hover(self):
        """Animate hover effect"""
        if self.animation_steps < self.max_steps:
            self.animation_steps += 1
            progress = self.animation_steps / self.max_steps
            
            # Interpolate border color from original to red
            if hasattr(self, 'border_color') and hasattr(self, 'bg_color'):
                # Calculate interpolated colors
                r1, g1, b1 = self.border_color.red(), self.border_color.green(), self.border_color.blue()
                r2, g2, b2 = 231, 76, 60  # Red color
                
                new_r = int(r1 + (r2 - r1) * progress)
                new_g = int(g1 + (g2 - g1) * progress)
                new_b = int(b1 + (b2 - b1) * progress)
                
                self.setStyleSheet(f"""
                    QWidget#course-cell {{
                        border: 2px solid rgb({new_r}, {new_g}, {new_b}) !important;
                        border-radius: 6px !important;
                        background-color: rgba({new_r}, {new_g}, {new_b}, 20) !important;
                    }}
                """)
        elif self.animation_steps >= self.max_steps:
            # Animation finished - set hover state (red border)
            self.animation_steps = self.max_steps
            self.animation_timer.stop()
            # Apply hover state by modifying only the border color
            if self.original_style:
                # Find and replace border color with red
                import re
                hover_style = self.original_style
                match = re.search(r'border: 2px solid rgba\((\d+),(\d+),(\d+),', self.original_style)
                if match:
                    r, g, b = map(int, match.groups())
                    hover_style = self.original_style.replace(
                        f'border: 2px solid rgba({r},{g},{b},',
                        'border: 2px solid rgba(231,76,60,'
                    )
                self.setStyleSheet(hover_style)
            else:
                # Get current background and apply with red border
                current_style = self.styleSheet()
                if 'background-color:' in current_style:
                    import re
                    bg_match = re.search(r'background-color: rgba\((\d+),(\d+),(\d+),', current_style)
                    if bg_match:
                        bg_r, bg_g, bg_b = map(int, bg_match.groups())
                        self.setStyleSheet(f"""
                            AnimatedCourseWidget#course-cell {{
                                background-color: rgba({bg_r},{bg_g},{bg_b},230);
                                border: 3px solid rgba(231,76,60,255) !important;
                                border-radius: 4px !important;
                                padding: 3px !important;
                                margin: 2px !important;
                                font-family: 'Nazanin', 'Tahoma', sans-serif;
                            }}
                            QWidget#course-cell {{
                                background-color: rgba({bg_r},{bg_g},{bg_b},230);
                                border: 3px solid rgba(231,76,60,255) !important;
                                border-radius: 4px !important;
                                padding: 3px !important;
                                margin: 2px !important;
                                font-family: 'Nazanin', 'Tahoma', sans-serif;
                            }}
                        """)
        else:
            # Interpolate between original and hover state
            progress = self.animation_steps / self.max_steps
            
            current_style = self.styleSheet()
            if 'background-color:' in current_style:
                # Interpolate border color from original to red
                import re
                bg_match = re.search(r'background-color: rgba\((\d+),(\d+),(\d+),', current_style)
                border_match = re.search(r'border: 2px solid rgba\((\d+),(\d+),(\d+),', current_style)
                if bg_match and border_match:
                    bg_r, bg_g, bg_b = map(int, bg_match.groups())
                    r, g, b = map(int, border_match.groups())
                    # Interpolate to red color (231, 76, 60)
                    new_r = max(0, min(255, int(r + (231 - r) * progress)))
                    new_g = max(0, min(255, int(g + (76 - g) * progress)))
                    new_b = max(0, min(255, int(b + (60 - b) * progress)))
                    
                    self.setStyleSheet(f"""
                        AnimatedCourseWidget#course-cell {{
                            background-color: rgba({bg_r},{bg_g},{bg_b},230);
                            border: 3px solid rgba({new_r},{new_g},{new_b},255) !important;
                            border-radius: 4px !important;
                            padding: 3px !important;
                            margin: 2px !important;
                            font-family: 'Nazanin', 'Tahoma', sans-serif;
                        }}
                        QWidget#course-cell {{
                            background-color: rgba({bg_r},{bg_g},{bg_b},230);
                            border: 3px solid rgba({new_r},{new_g},{new_b},255) !important;
                            border-radius: 4px !important;
                            padding: 3px !important;
                            margin: 2px !important;
                            font-family: 'Nazanin', 'Tahoma', sans-serif;
                        }}
                    """)

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
        
        # Add export button only
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
        
        # Enhanced title with better styling and typography hierarchy
        title_label = QtWidgets.QLabel(
            '<h1 style="color: #2c3e50; margin: 0; font-family: \'IRANSans UI\', \'Shabnam\', Tahoma, Arial, sans-serif; '
            'font-size: 20px; font-weight: bold; text-shadow: 0 1px 2px rgba(0,0,0,0.1);">' 
            '📅 برنامه امتحانات (فقط دروس انتخابی)</h1>'
        )
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        exam_layout.addWidget(title_label)
        
        # Improved info label with better contrast and typography
        info_label = QtWidgets.QLabel(
            '<p style="color: #7f8c8d; font-style: italic; text-align: center; ' 
            'background: linear-gradient(135deg, #ecf0f1 0%, #bdc3c7 100%); ' 
            'padding: 10px; border-radius: 8px; margin: 6px; font-family: \'IRANSans UI\', \'Shabnam\', Tahoma, Arial, sans-serif; '
            'font-size: 14px;">' 
            'فقط دروسی که در جدول اصلی قرار داده‌اید نمایش داده می‌شوند</p>'
        )
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        exam_layout.addWidget(info_label)
        
        # Separator line after info
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setObjectName("separator")
        exam_layout.addWidget(separator)
        
        # Enhanced exam schedule table
        self.exam_table = QtWidgets.QTableWidget()
        self.exam_table.setColumnCount(5)
        self.exam_table.setHorizontalHeaderLabels([
            'نام درس', 'کد درس', 'استاد', 'زمان امتحان', 'محل برگزاری'
        ])
        
        # Enhanced table styling with subtle backgrounds
        self.exam_table.setObjectName("exam_table")
        
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
        
        # Add statistics panel
        self.stats_label = QtWidgets.QLabel()
        self.stats_label.setObjectName("stats_label")
        self.stats_label.setAlignment(QtCore.Qt.AlignCenter)
        exam_layout.addWidget(self.stats_label)
        
        # Add bottom separator and spacing
        bottom_separator = QtWidgets.QFrame()
        bottom_separator.setFrameShape(QtWidgets.QFrame.HLine)
        bottom_separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        bottom_separator.setObjectName("bottom_separator")
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
            # Course name with enhanced styling and typography
            name_item = QtWidgets.QTableWidgetItem(data['name'])
            name_item.setFont(QtGui.QFont('IRANSans UI', 13, QtGui.QFont.Bold))
            name_item.setForeground(QtGui.QBrush(QtGui.QColor('#2c3e50')))
            self.exam_table.setItem(row, 0, name_item)
            
            # Course code with monospace styling
            code_item = QtWidgets.QTableWidgetItem(data['code'])
            code_item.setFont(QtGui.QFont('Courier New', 11, QtGui.QFont.Bold))
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
        
        # Calculate and display statistics
        if hasattr(self, 'stats_label'):
            if placed_courses:
                # Calculate total units
                total_units = 0
                days_used = set()
                total_sessions = len(self.parent_window.placed) if hasattr(self.parent_window, 'placed') else 0
                
                for course_key in placed_courses:
                    course = COURSES.get(course_key, {})
                    total_units += course.get('credits', 0)
                    # Get days from schedule
                    for session in course.get('schedule', []):
                        days_used.add(session.get('day', ''))
                
                # Create statistics text
                stats_text = f"📊 آمار برنامه: دروس: {len(placed_courses)} | جلسات: {total_sessions} | واحدها: {total_units} | روزهای حضور: {len(days_used)}"
                
                if days_used:
                    days_list = ', '.join(sorted([day for day in days_used if day]))
                    stats_text += f" ({days_list})"
                
                self.stats_label.setText(stats_text)
                self.stats_label.setVisible(True)
            else:
                self.stats_label.setText("📊 هیچ درسی انتخاب نشده است")
                self.stats_label.setVisible(True)
        
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
        """Export exam schedule as plain text with comprehensive information"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.txt', 'Text Files (*.txt)'
        )
        if not filename:
            return
            
        try:
            from datetime import datetime
            current_date = datetime.now().strftime('%Y/%m/%d - %H:%M')
            
            with open(filename, 'w', encoding='utf-8-sig') as f:
                # Add BOM for proper RTL display in text editors
                f.write('\ufeff')
                
                f.write('📅 برنامه امتحانات دانشگاهی\n')
                f.write('='*60 + '\n\n')
                f.write(f'🕒 تاریخ تولید: {current_date}\n')
                f.write(f'📚 تولید شده توسط: برنامه‌ریز انتخاب واحد v2.0\n\n')
                
                # Calculate and display statistics
                total_courses = self.exam_table.rowCount()
                total_units = 0
                total_sessions = 0
                days_used = set()
                instructors = set()
                
                # Get placed courses for statistics
                if hasattr(self.parent_window, 'placed'):
                    placed_courses = set()
                    for info in self.parent_window.placed.values():
                        placed_courses.add(info['course'])
                    
                    for course_key in placed_courses:
                        course = COURSES.get(course_key, {})
                        total_units += course.get('credits', 0)
                        instructors.add(course.get('instructor', 'نامشخص'))
                        for session in course.get('schedule', []):
                            days_used.add(session.get('day', ''))
                    
                    total_sessions = len(self.parent_window.placed)
                
                f.write('📊 خلاصه اطلاعات برنامه:\n')
                f.write('-' * 40 + '\n')
                f.write(f'• تعداد دروس: {total_courses}\n')
                f.write(f'• مجموع واحدها: {total_units}\n')
                f.write(f'• تعداد جلسات: {total_sessions}\n')
                f.write(f'• روزهای حضور: {len(days_used)} روز\n')
                f.write(f'• تعداد اساتید: {len(instructors)}\n\n')
                
                if days_used:
                    days_list = ', '.join(sorted([day for day in days_used if day]))
                    f.write(f'• روزهای حضور: {days_list}\n\n')
                
                f.write('📄 جزئیات برنامه امتحانات:\n')
                f.write('='*60 + '\n\n')
                
                for row in range(self.exam_table.rowCount()):
                    name = self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else ''
                    code = self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else ''
                    instructor = self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else ''
                    exam_time = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                    location = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                    
                    # Get additional course information
                    course_credits = 0
                    parity_info = 'همه هفته‌ها'
                    schedule_info = []
                    
                    # Find course by code to get additional info
                    for key, course in COURSES.items():
                        if course.get('code') == code:
                            course_credits = course.get('credits', 0)
                            # Check for parity and schedule from course data
                            for session in course.get('schedule', []):
                                day = session.get('day', '')
                                start = session.get('start', '')
                                end = session.get('end', '')
                                parity = session.get('parity', '')
                                
                                if parity == 'ز':
                                    parity_text = ' (زوج)'
                                    if parity_info == 'همه هفته‌ها':
                                        parity_info = 'زوج'
                                elif parity == 'ف':
                                    parity_text = ' (فرد)'
                                    if parity_info == 'همه هفته‌ها':
                                        parity_info = 'فرد'
                                else:
                                    parity_text = ''
                                
                                schedule_info.append(f'{day} {start}-{end}{parity_text}')
                            break
                    
                    f.write(f'📚 درس {row + 1}:\n')
                    f.write(f'   نام: {name}\n')
                    f.write(f'   کد: {code}\n')
                    f.write(f'   استاد: {instructor}\n')
                    f.write(f'   تعداد واحد: {course_credits}\n')
                    f.write(f'   نوع هفته: {parity_info}\n')
                    f.write(f'   زمان امتحان: {exam_time}\n')
                    f.write(f'   محل برگزاری: {location}\n')
                    
                    if schedule_info:
                        f.write(f'   جلسات درس:\n')
                        for session in schedule_info:
                            f.write(f'     • {session}\n')
                    
                    f.write('-'*50 + '\n\n')
                
                f.write('\n' + '='*60 + '\n')
                f.write('📝 توضیحات علائم:\n')
                f.write('• زوج: دروس هفته‌های زوج (در جدول با علامت ز نشان داده شده)\n')
                f.write('• فرد: دروس هفته‌های فرد (در جدول با علامت ف نشان داده شده)\n')
                f.write('• همه هفته‌ها: دروسی که هر هفته تشکیل می‌شوند\n\n')
                
                f.write(f'💡 این برنامه با استفاده از فناوری PyQt5 و Python توسعه یافته است\n')
                    
            QtWidgets.QMessageBox.information(self, 'صدور موفق', f'برنامه امتحانات در فایل زیر ذخیره شد:\n{filename}\n\nنکته: برای نمایش صحیح متن راست به چپ، فایل را با یک ویرایشگر متن که از UTF-8 و RTL پشتیبانی می‌کند باز کنید.')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در ذخیره فایل:\n{str(e)}')
    
    def export_as_html(self):
        """Export exam schedule as HTML with improved styling and complete information"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.html', 'HTML Files (*.html)'
        )
        if not filename:
            return
            
        try:
            # Create HTML content with RTL support and enhanced styling
            from datetime import datetime
            current_date = datetime.now().strftime('%Y/%m/%d - %H:%M')
            
            # Calculate comprehensive statistics
            total_courses = self.exam_table.rowCount()
            total_units = 0
            total_sessions = 0
            days_used = set()
            instructors = set()
            
            # Get placed courses for statistics
            if hasattr(self.parent_window, 'placed'):
                placed_courses = set()
                for info in self.parent_window.placed.values():
                    placed_courses.add(info['course'])
                
                for course_key in placed_courses:
                    course = COURSES.get(course_key, {})
                    total_units += course.get('credits', 0)
                    instructors.add(course.get('instructor', 'نامشخص'))
                    for session in course.get('schedule', []):
                        days_used.add(session.get('day', ''))
                
                total_sessions = len(self.parent_window.placed)
            
            # Generate table rows
            table_rows = ""
            for row in range(self.exam_table.rowCount()):
                name = self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else ''
                code = self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else ''
                instructor = self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else ''
                exam_time = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                location = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                
                # Get additional course information
                course_key = None
                course_credits = 0
                parity_info = 'همه هفته‌ها'
                parity_class = 'parity-all'
                
                # Find course by code to get additional info
                for key, course in COURSES.items():
                    if course.get('code') == code:
                        course_key = key
                        course_credits = course.get('credits', 0)
                        # Check for parity from schedule
                        for session in course.get('schedule', []):
                            if session.get('parity') == 'ز':
                                parity_info = 'زوج'
                                parity_class = 'parity-even'
                                break
                            elif session.get('parity') == 'ف':
                                parity_info = 'فرد'
                                parity_class = 'parity-odd'
                                break
                        break
                
                table_rows += f"""
                            <tr>
                                <td class="course-name">{name}</td>
                                <td class="course-code">{code}</td>
                                <td class="instructor">{instructor}</td>
                                <td style="font-weight: bold; color: #e67e22; text-align: center;">{course_credits}</td>
                                <td class="exam-time">{exam_time}</td>
                                <td class="location">{location}</td>
                                <td style="text-align: center;"><span class="parity {parity_class}">{parity_info}</span></td>
                            </tr>
                """
            
            # Create complete HTML document with RTL support
            html_content = f"""<!DOCTYPE html>
            <html dir="rtl" lang="fa">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>برنامه امتحانات</title>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;700&display=swap');
                    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
                    
                    body {{ 
                        font-family: 'Tajawal', 'Nazanin', 'Noto Sans Arabic', 'Tahoma', Arial, sans-serif; 
                        margin: 20px; 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        color: #2c3e50;
                        direction: rtl;
                        text-align: right;
                    }}
                    
                    .container {{ 
                        max-width: 900px; 
                        margin: 0 auto; 
                        background: white; 
                        padding: 40px; 
                        border-radius: 15px; 
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                        direction: rtl;
                        text-align: right;
                    }}
                    
                    h1 {{ 
                        color: #d35400; 
                        text-align: center; 
                        margin-bottom: 30px;
                        font-size: 28px;
                        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
                        font-family: 'Tajawal', 'Nazanin', 'Noto Sans Arabic', 'Tahoma', Arial, sans-serif;
                    }}
                    
                    .stats {{
                        display: flex;
                        justify-content: space-around;
                        margin: 20px 0;
                        flex-wrap: wrap;
                        direction: rtl;
                    }}
                    
                    .stat-item {{
                        text-align: center;
                        margin: 10px;
                        padding: 15px;
                        background: white;
                        border-radius: 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        min-width: 120px;
                        direction: rtl;
                    }}
                    
                    .stat-number {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #e74c3c;
                        margin-bottom: 5px;
                    }}
                    
                    .stat-label {{
                        font-size: 12px;
                        color: #7f8c8d;
                        font-weight: normal;
                    }}
                    
                    table {{ 
                        width: 100%; 
                        border-collapse: collapse; 
                        margin-top: 20px;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                        border-radius: 10px;
                        overflow: hidden;
                        direction: rtl;
                        text-align: right;
                    }}
                    
                    th, td {{ 
                        padding: 15px 10px; 
                        text-align: right; 
                        border-bottom: 1px solid #ecf0f1;
                        font-size: 13px;
                    }}
                    
                    th {{ 
                        background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
                        color: white; 
                        font-weight: bold;
                        font-size: 14px;
                        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
                        text-align: right;
                    }}
                    
                    tr:nth-child(even) {{ 
                        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                    }}
                    
                    .course-name {{
                        font-weight: bold;
                        color: #2c3e50;
                        font-size: 14px;
                        text-align: right;
                    }}
                    
                    .course-code {{
                        font-family: 'Courier New', monospace;
                        background: #e8f4fd;
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-weight: bold;
                        color: #2980b9;
                        text-align: right;
                    }}
                    
                    .exam-time {{ 
                        font-weight: bold; 
                        color: #e74c3c;
                        background: #fff5f5;
                        padding: 6px;
                        border-radius: 4px;
                        text-align: right;
                    }}
                    
                    .instructor {{
                        color: #34495e;
                        font-size: 12px;
                        text-align: right;
                    }}
                    
                    .location {{
                        color: #7f8c8d;
                        font-size: 11px;
                        font-style: italic;
                        text-align: right;
                    }}
                    
                    .parity {{
                        font-weight: bold;
                        padding: 2px 6px;
                        border-radius: 12px;
                        font-size: 10px;
                        color: white;
                        text-align: center;
                    }}
                    
                    .parity-even {{
                        background: #27ae60;
                    }}
                    
                    .parity-odd {{
                        background: #3498db;
                    }}
                    
                    .parity-all {{
                        background: #95a5a6;
                    }}
                    
                    .footer {{ 
                        text-align: center; 
                        margin-top: 40px; 
                        color: #7f8c8d; 
                        font-size: 12px;
                        padding: 20px;
                        background: #ecf0f1;
                        border-radius: 8px;
                        border-right: 3px solid #3498db;
                        direction: rtl;
                    }}
                    
                    @media print {{
                        body {{ 
                            background: white !important; 
                            direction: rtl;
                            text-align: right;
                        }}
                        .container {{ 
                            box-shadow: none !important; 
                            direction: rtl;
                            text-align: right;
                        }}
                        table, th, td {{
                            text-align: right;
                            direction: rtl;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>📅 برنامه امتحانات دانشگاهی</h1>
                    
                    <div class="info-section">
                        <h3 style="color: #27ae60; margin-top: 0;">📊 خلاصه اطلاعات برنامه</h3>
                        <div class="stats">
            """
            
            # Calculate comprehensive statistics
            total_courses = self.exam_table.rowCount()
            total_units = 0
            total_sessions = 0
            days_used = set()
            instructors = set()
            
            # Get placed courses for statistics
            if hasattr(self.parent_window, 'placed'):
                placed_courses = set()
                for info in self.parent_window.placed.values():
                    placed_courses.add(info['course'])
                
                for course_key in placed_courses:
                    course = COURSES.get(course_key, {})
                    total_units += course.get('credits', 0)
                    instructors.add(course.get('instructor', 'نامشخص'))
                    for session in course.get('schedule', []):
                        days_used.add(session.get('day', ''))
                
                total_sessions = len(self.parent_window.placed)
            
            # Add statistics
            html_content += f"""
                            <div class="stat-item">
                                <div class="stat-number">{total_courses}</div>
                                <div class="stat-label">تعداد دروس</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">{total_units}</div>
                                <div class="stat-label">مجموع واحدها</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">{total_sessions}</div>
                                <div class="stat-label">تعداد جلسات</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">{len(days_used)}</div>
                                <div class="stat-label">روزهای حضور</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">{len(instructors)}</div>
                                <div class="stat-label">تعداد اساتید</div>
                            </div>
                        </div>
                    </div>
                    
                    <table>
                        <thead>
                            <tr>
                                <th>نام درس</th>
                                <th>کد درس</th>
                                <th>استاد</th>
                                <th>واحد</th>
                                <th>زمان امتحان</th>
                                <th>محل برگزاری</th>
                                <th>نوع هفته</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            for row in range(self.exam_table.rowCount()):
                name = self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else ''
                code = self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else ''
                instructor = self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else ''
                exam_time = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                location = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                
                # Get additional course information
                course_key = None
                course_credits = 0
                parity_info = 'همه هفته‌ها'
                parity_class = 'parity-all'
                
                # Find course by code to get additional info
                for key, course in COURSES.items():
                    if course.get('code') == code:
                        course_key = key
                        course_credits = course.get('credits', 0)
                        # Check for parity from schedule
                        for session in course.get('schedule', []):
                            if session.get('parity') == 'ز':
                                parity_info = 'زوج'
                                parity_class = 'parity-even'
                                break
                            elif session.get('parity') == 'ف':
                                parity_info = 'فرد'
                                parity_class = 'parity-odd'
                                break
                        break
                
                html_content += f"""
                            <tr>
                                <td class="course-name">{name}</td>
                                <td class="course-code">{code}</td>
                                <td class="instructor">{instructor}</td>
                                <td style="font-weight: bold; color: #e67e22;">{course_credits}</td>
                                <td class="exam-time">{exam_time}</td>
                                <td class="location">{location}</td>
                                <td><span class="parity {parity_class}">{parity_info}</span></td>
                            </tr>
                """
            
            from datetime import datetime
            current_date = datetime.now().strftime('%Y/%m/%d - %H:%M')
            
            html_content += f"""
                        </tbody>
                    </table>
                    
                    <div class="footer">
                        <strong>📚 برنامه‌ریز انتخاب واحد - Schedule Planner v2.0</strong><br>
                        🕒 تاریخ و زمان تولید: {current_date}<br>
                        💡 این برنامه با استفاده از فناوری PyQt5 و Python توسعه یافته است
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
        """Export exam schedule as CSV with comprehensive course information"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.csv', 'CSV Files (*.csv)'
        )
        if not filename:
            return
            
        try:
            import csv
            with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                
                # Enhanced header with more information
                writer.writerow([
                    'نام درس', 
                    'کد درس', 
                    'استاد', 
                    'تعداد واحد',
                    'زمان امتحان', 
                    'محل برگزاری',
                    'نوع هفته',
                    'جلسات درس',
                    'توضیحات'
                ])
                
                # Write enhanced data
                for row in range(self.exam_table.rowCount()):
                    name = self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else ''
                    code = self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else ''
                    instructor = self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else ''
                    exam_time = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                    location = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                    
                    # Get additional course information
                    course_credits = 0
                    parity_info = 'همه هفته‌ها'
                    schedule_info = []
                    description = ''
                    
                    # Find course by code to get additional info
                    for key, course in COURSES.items():
                        if course.get('code') == code:
                            course_credits = course.get('credits', 0)
                            description = course.get('description', '')
                            
                            # Check for parity and schedule from course data
                            for session in course.get('schedule', []):
                                day = session.get('day', '')
                                start = session.get('start', '')
                                end = session.get('end', '')
                                parity = session.get('parity', '')
                                
                                if parity == 'ز':
                                    parity_text = ' (زوج)'
                                    if parity_info == 'همه هفته‌ها':
                                        parity_info = 'زوج'
                                elif parity == 'ف':
                                    parity_text = ' (فرد)'
                                    if parity_info == 'همه هفته‌ها':
                                        parity_info = 'فرد'
                                else:
                                    parity_text = ''
                                
                                schedule_info.append(f'{day} {start}-{end}{parity_text}')
                            break
                    
                    # Combine schedule info
                    schedule_text = '; '.join(schedule_info) if schedule_info else 'اطلاعی موجود نیست'
                    
                    writer.writerow([
                        name,
                        code, 
                        instructor,
                        course_credits,
                        exam_time,
                        location,
                        parity_info,
                        schedule_text,
                        description[:100] + '...' if len(description) > 100 else description
                    ])
                    
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
        """Generate HTML content optimized for PDF export with Persian support and comprehensive information"""
        from datetime import datetime
        current_date = datetime.now().strftime('%Y/%m/%d - %H:%M')
        
        # Collect comprehensive exam data
        exam_data = []
        total_units = 0
        total_sessions = 0
        days_used = set()
        instructors = set()
        
        for row in range(exam_count):
            base_data = {
                'name': self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else '',
                'code': self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else '',
                'instructor': self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else '',
                'exam_time': self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else '',
                'location': self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else '',
                'credits': 0,
                'parity': 'همه هفته‌ها',
                'schedule': []
            }
            
            # Get additional course information
            for key, course in COURSES.items():
                if course.get('code') == base_data['code']:
                    base_data['credits'] = course.get('credits', 0)
                    total_units += base_data['credits']
                    instructors.add(base_data['instructor'])
                    
                    # Check for parity and schedule from course data
                    for session in course.get('schedule', []):
                        days_used.add(session.get('day', ''))
                        day = session.get('day', '')
                        start = session.get('start', '')
                        end = session.get('end', '')
                        parity = session.get('parity', '')
                        
                        if parity == 'ز':
                            parity_text = ' (زوج)'
                            if base_data['parity'] == 'همه هفته‌ها':
                                base_data['parity'] = 'زوج'
                        elif parity == 'ف':
                            parity_text = ' (فرد)'
                            if base_data['parity'] == 'همه هفته‌ها':
                                base_data['parity'] = 'فرد'
                        else:
                            parity_text = ''
                        
                        base_data['schedule'].append(f'{day} {start}-{end}{parity_text}')
                    break
            
            exam_data.append(base_data)
        
        # Get placed courses for additional statistics
        if hasattr(self.parent_window, 'placed'):
            total_sessions = len(self.parent_window.placed)
        
        # Generate table rows with enhanced information
        table_rows = ""
        for i, exam in enumerate(exam_data):
            row_class = "even-row" if i % 2 == 0 else "odd-row"
            
            # Determine parity styling
            parity_class = 'parity-all'
            if exam['parity'] == 'زوج':
                parity_class = 'parity-even'
            elif exam['parity'] == 'فرد':
                parity_class = 'parity-odd'
            
            schedule_text = '<br>'.join(exam['schedule'][:3])  # Show first 3 sessions
            if len(exam['schedule']) > 3:
                schedule_text += f'<br><small>+{len(exam["schedule"])-3} جلسه دیگر</small>'
            
            table_rows += f"""
                <tr class="{row_class}">
                    <td class="course-name" style="text-align: right;">{exam['name']}</td>
                    <td class="course-code" style="text-align: center;">{exam['code']}</td>
                    <td class="instructor" style="text-align: right;">{exam['instructor']}</td>
                    <td class="credits" style="text-align: center;">{exam['credits']}</td>
                    <td class="exam-time" style="text-align: center;">{exam['exam_time']}</td>
                    <td class="location" style="text-align: right;">{exam['location']}</td>
                    <td style="text-align: center;"><span class="parity {parity_class}">{exam['parity']}</span></td>
                    <td class="schedule" style="text-align: right;">{schedule_text}</td>
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
                @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;700&display=swap');
                @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
                
                @page {{
                    size: A4 landscape;
                    margin: 15mm;
                    @bottom-center {{
                        content: "صفحه " counter(page) " از " counter(pages);
                        font-size: 10px;
                        color: #666;
                        direction: rtl;
                        text-align: center;
                    }}
                }}
                
                * {{
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Tajawal', 'Nazanin', 'Noto Sans Arabic', 'Tahoma', 'Arial Unicode MS', 'Segoe UI', sans-serif;
                    background: white;
                    color: #2c3e50;
                    line-height: 1.4;
                    margin: 0;
                    padding: 15px;
                    font-size: 12px;
                    direction: rtl;
                    text-align: right;
                }}
                
                .header {{
                    text-align: center;
                    margin-bottom: 25px;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    direction: rtl;
                }}
                
                .header h1 {{
                    margin: 0 0 10px 0;
                    font-size: 22px;
                    font-weight: bold;
                    direction: rtl;
                }}
                
                .header p {{
                    margin: 5px 0;
                    font-size: 14px;
                    opacity: 0.9;
                    direction: rtl;
                }}
                
                .stats {{
                    display: flex;
                    justify-content: space-around;
                    margin: 15px 0;
                    padding: 15px;
                    background: #e8f6f3;
                    border-radius: 8px;
                    border: 2px solid #1abc9c;
                    direction: rtl;
                }}
                
                .stat-item {{
                    text-align: center;
                    direction: rtl;
                }}
                
                .stat-number {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #1abc9c;
                }}
                
                .stat-label {{
                    font-size: 10px;
                    color: #2c3e50;
                    margin-top: 3px;
                }}
                
                .exam-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    border-radius: 8px;
                    overflow: hidden;
                    font-size: 10px;
                    direction: rtl;
                    text-align: right;
                }}
                
                .exam-table th {{
                    background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
                    color: white;
                    padding: 12px 8px;
                    text-align: center;
                    font-weight: bold;
                    font-size: 11px;
                    border: none;
                }}
                
                .exam-table td {{
                    padding: 8px 6px;
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
                    font-size: 11px;
                }}
                
                .course-code {{
                    font-family: 'Courier New', monospace;
                    background: #ecf0f1;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-weight: bold;
                    font-size: 9px;
                    text-align: center;
                }}
                
                .exam-time {{
                    font-weight: bold;
                    color: #e74c3c;
                    background: #fff5f5;
                    border-radius: 4px;
                    padding: 4px;
                    font-size: 9px;
                    text-align: center;
                }}
                
                .instructor {{
                    color: #34495e;
                    font-size: 10px;
                    text-align: right;
                }}
                
                .location {{
                    color: #7f8c8d;
                    font-size: 9px;
                    text-align: right;
                }}
                
                .credits {{
                    font-weight: bold;
                    color: #e67e22;
                    font-size: 11px;
                    text-align: center;
                }}
                
                .schedule {{
                    font-size: 8px;
                    color: #34495e;
                    text-align: right;
                    line-height: 1.2;
                }}
                
                .parity {{
                    font-weight: bold;
                    padding: 2px 6px;
                    border-radius: 10px;
                    font-size: 8px;
                    color: white;
                    text-align: center;
                }}
                
                .parity-even {{
                    background: #27ae60;
                }}
                
                .parity-odd {{
                    background: #3498db;
                }}
                
                .parity-all {{
                    background: #95a5a6;
                }}
                
                .footer {{
                    margin-top: 30px;
                    padding: 15px;
                    text-align: center;
                    background: #ecf0f1;
                    border-radius: 8px;
                    color: #7f8c8d;
                    font-size: 10px;
                    border-top: 3px solid #3498db;
                    direction: rtl;
                }}
                
                @media print {{
                    body {{
                        print-color-adjust: exact;
                        -webkit-print-color-adjust: exact;
                        direction: rtl;
                        text-align: right;
                    }}
                    
                    .header, .exam-table th {{
                        background: #667eea !important;
                        color: white !important;
                    }}
                    
                    table, th, td {{
                        text-align: right;
                        direction: rtl;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📅 برنامه امتحانات دانشگاهی</h1>
                <p>برنامه‌ریز انتخاب واحد - Schedule Planner v2.0</p>
            </div>
            
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-number">{exam_count}</div>
                    <div class="stat-label">تعداد دروس</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{total_units}</div>
                    <div class="stat-label">مجموع واحدها</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{total_sessions}</div>
                    <div class="stat-label">تعداد جلسات</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{len(days_used)}</div>
                    <div class="stat-label">روزهای حضور</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{len(instructors)}</div>
                    <div class="stat-label">تعداد اساتید</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{current_date}</div>
                    <div class="stat-label">تاریخ تولید</div>
                </div>
            </div>
            
            <table class="exam-table">
                <thead>
                    <tr>
                        <th style="text-align: center;">نام درس</th>
                        <th style="text-align: center;">کد درس</th>
                        <th style="text-align: center;">استاد</th>
                        <th style="text-align: center;">واحد</th>
                        <th style="text-align: center;">زمان امتحان</th>
                        <th style="text-align: center;">محل</th>
                        <th style="text-align: center;">نوع هفته</th>
                        <th style="text-align: center;">جلسات</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            
            <div class="footer">
                <strong>📚 برنامه‌ریز انتخاب واحد</strong><br>
                Schedule Planner v2.0 - University Course Selection System<br>
                🕒 تاریخ و زمان تولید: {current_date}<br>
                💡 توسعه یافته با PyQt5 و Python
            </div>
        </body>
        </html>
        """
        
        return html_content


# ---------------------- پنجرهٔ اصلی ----------------------
class SchedulerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('🎓 برنامه‌ریز انتخاب واحد - Schedule Planner v2.1')
        self.resize(1400, 900)
        self.setMinimumSize(320, 480)  # Minimum size for mobile compatibility
        self.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        # Enable responsive design
        self.installEventFilter(self)
        
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
        
        # Menu bar is not implemented in this version
        
    def init_ui(self):
        """Initialize the user interface with improved organization"""
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        
        # Create main horizontal layout with stretch factors for balanced sizing
        main_layout = QtWidgets.QHBoxLayout(main_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Set font for the entire application
        app_font = QtGui.QFont('IRANSans UI', 12)
        self.setFont(app_font)

        # LEFT PANEL - Course controls and management
        self.left_panel = QtWidgets.QFrame()
        self.left_panel.setObjectName("left_panel")
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(12, 12, 12, 12)

        # Search section
        search_group = QtWidgets.QGroupBox("جستجوی درس")
        search_layout = QtWidgets.QVBoxLayout(search_group)
        
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("جستجو بر اساس نام، کد یا استاد...")
        self.search_box.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(self.search_box)
        
        # Clear search button
        clear_search_btn = QtWidgets.QPushButton("✖ پاک کردن جستجو")
        clear_search_btn.clicked.connect(self.clear_search)
        search_layout.addWidget(clear_search_btn)
        
        left_layout.addWidget(search_group)

        # Course list section
        course_list_group = QtWidgets.QGroupBox("لیست دروس")
        course_list_layout = QtWidgets.QVBoxLayout(course_list_group)
        
        self.course_list = DraggableCourseList()
        self.course_list.itemClicked.connect(self.on_course_clicked)
        self.course_list.setMouseTracking(True)
        self.course_list.viewport().installEventFilter(self)
        self.course_list.installEventFilter(self)
        course_list_layout.addWidget(self.course_list)
        
        left_layout.addWidget(course_list_group)

        # Saved combinations section
        saved_combos_group = QtWidgets.QGroupBox("ترکیب‌های ذخیره شده")
        saved_combos_layout = QtWidgets.QVBoxLayout(saved_combos_group)
        
        self.saved_combos_list = QtWidgets.QListWidget()
        self.saved_combos_list.itemDoubleClicked.connect(self.load_saved_combo)
        saved_combos_layout.addWidget(self.saved_combos_list)
        
        left_layout.addWidget(saved_combos_group)
        
        # Action buttons section
        actions_group = QtWidgets.QGroupBox("عملیات")
        actions_layout = QtWidgets.QVBoxLayout(actions_group)
        
        add_course_btn = QtWidgets.QPushButton("➕ افزودن درس")
        add_course_btn.setObjectName("success_btn")
        add_course_btn.clicked.connect(self.open_add_course_dialog)
        actions_layout.addWidget(add_course_btn)
        
        remove_course_btn = QtWidgets.QPushButton("➖ حذف درس")
        remove_course_btn.setObjectName("danger_btn")
        remove_course_btn.clicked.connect(self.remove_selected_course)
        actions_layout.addWidget(remove_course_btn)
        
        # Generate optimal schedule button
        generate_optimal_btn = QtWidgets.QPushButton("🤖 تولید بهترین برنامه")
        generate_optimal_btn.setObjectName("optimal_schedule_btn")
        generate_optimal_btn.clicked.connect(self.generate_optimal_schedule)
        actions_layout.addWidget(generate_optimal_btn)
        
        save_schedule_btn = QtWidgets.QPushButton("💾 ذخیره برنامه")
        save_schedule_btn.setObjectName("detailed_info_btn")
        save_schedule_btn.clicked.connect(self.save_current_combo)
        actions_layout.addWidget(save_schedule_btn)
        
        clear_schedule_btn = QtWidgets.QPushButton("🧹 پاک کردن کل برنامه")
        clear_schedule_btn.setObjectName("danger_btn")
        clear_schedule_btn.clicked.connect(self.clear_table)
        actions_layout.addWidget(clear_schedule_btn)
        
        left_layout.addWidget(actions_group)
        left_layout.addStretch()

        # Add left panel to main layout with stretch factor
        main_layout.addWidget(self.left_panel, 1)

        # CENTER PANEL - Weekly schedule grid
        self.center_panel = QtWidgets.QFrame()
        self.center_panel.setObjectName("center_panel")
        center_layout = QtWidgets.QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(6, 6, 6, 6)

        # Create schedule table with extended hours (7:00 to 19:00)
        # Generate time slots from 7:00 to 19:00
        extended_time_slots = []
        start_minutes = 7 * 60
        end_minutes = 19 * 60
        m = start_minutes
        while m <= end_minutes:
            hh = m // 60
            mm = m % 60
            extended_time_slots.append(f"{hh:02d}:{mm:02d}")
            m += 30

        self.table = ScheduleTable(len(extended_time_slots), len(DAYS), parent=self)
        self.table.setHorizontalHeaderLabels(DAYS)
        self.table.setVerticalHeaderLabels(extended_time_slots)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        
        # Set better font for table headers
        header_font = QtGui.QFont('IRANSans UI', 14, QtGui.QFont.Bold)
        self.table.horizontalHeader().setFont(header_font)
        self.table.verticalHeader().setFont(QtGui.QFont('IRANSans UI', 12))
        
        center_layout.addWidget(self.table)
        
        # Add center panel to main layout with stretch factor
        main_layout.addWidget(self.center_panel, 3)

        # RIGHT PANEL - Additional information and controls
        self.right_panel = QtWidgets.QFrame()
        self.right_panel.setObjectName("right_panel")
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        right_layout.setSpacing(15)
        right_layout.setContentsMargins(12, 12, 12, 12)

        # Course information section
        info_group = QtWidgets.QGroupBox("اطلاعات درس")
        info_layout = QtWidgets.QVBoxLayout(info_group)
        
        self.course_info_label = QtWidgets.QLabel("اطلاعات درس انتخابی در اینجا نمایش داده می‌شود")
        self.course_info_label.setWordWrap(True)
        self.course_info_label.setAlignment(QtCore.Qt.AlignTop)
        info_layout.addWidget(self.course_info_label)
        
        right_layout.addWidget(info_group)

        # Statistics section
        stats_group = QtWidgets.QGroupBox("آمار برنامه")
        stats_layout = QtWidgets.QVBoxLayout(stats_group)
        
        self.stats_label = QtWidgets.QLabel("آمار برنامه در اینجا نمایش داده می‌شود")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        
        right_layout.addWidget(stats_group)

        # Notifications section
        notifications_group = QtWidgets.QGroupBox("پیام‌ها")
        notifications_layout = QtWidgets.QVBoxLayout(notifications_group)
        
        self.notifications_label = QtWidgets.QLabel("پیام‌ها در اینجا نمایش داده می‌شود")
        self.notifications_label.setWordWrap(True)
        notifications_layout.addWidget(self.notifications_label)
        
        right_layout.addWidget(notifications_group)
        right_layout.addStretch()

        # Add right panel to main layout with stretch factor
        main_layout.addWidget(self.right_panel, 1)

    def update_status(self):
        """Update status bar with current schedule info and improved typography"""
        if not self.placed:
            self.status_bar.showMessage('آماده - برای شروع، درسی را از لیست انتخاب کنید')
            # Update stats panel
            if hasattr(self, 'stats_label'):
                self.stats_label.setText("هیچ درسی انتخاب نشده است")
            return
            
        # Calculate schedule statistics
        unique_courses = set(info['course'] for info in self.placed.values())
        total_credits = sum(COURSES.get(course, {}).get('credits', 0) for course in unique_courses)
        total_sessions = len(self.placed)
        
        # Calculate days used more accurately
        days_used = set()
        for (row, col), info in self.placed.items():
            if col < len(DAYS):
                days_used.add(DAYS[col])
        
        # Create detailed status text with better typography
        days_list = ', '.join(sorted(days_used)) if days_used else 'هیچ'
        status_text = f'دروس: {len(unique_courses)} | جلسات: {total_sessions} | واحدها: {total_credits} | روزهای حضور: {len(days_used)} ({days_list})'
        
        self.status_bar.showMessage(status_text)
        # Set font for status bar
        status_font = QtGui.QFont('IRANSans UI', 12, QtGui.QFont.Bold)
        self.status_bar.setFont(status_font)
        
        # Update stats panel
        if hasattr(self, 'stats_label'):
            stats_text = f"""تعداد دروس: {len(unique_courses)}
تعداد جلسات: {total_sessions}
مجموع واحدها: {total_credits}
روزهای حضور: {len(days_used)}
روزهای استفاده شده: {days_list}"""
            self.stats_label.setText(stats_text)

    def on_course_clicked(self, item):
        """Handle course selection from the list with enhanced debugging"""
        if item is None:
            logger.warning("on_course_clicked called with None item")
            return
            
        key = item.data(QtCore.Qt.UserRole)
        logger.debug(f"Course clicked - item: {item}, key: {key}")
        
        if key:
            logger.info(f"User clicked on course with key: {key}")
            self.clear_preview()
            self.add_course_to_table(key, ask_on_conflict=True)
            
            # Update course info panel
            if hasattr(self, 'course_info_label'):
                course = COURSES.get(key, {})
                info_text = f"""نام درس: {course.get('name', 'نامشخص')}
کد درس: {course.get('code', 'نامشخص')}
استاد: {course.get('instructor', 'نامشخص')}
تعداد واحد: {course.get('credits', 'نامشخص')}
محل برگزاری: {course.get('location', 'نامشخص')}"""
                self.course_info_label.setText(info_text)
        else:
            logger.warning(f"Course item clicked but no key found in UserRole data")
            QtWidgets.QMessageBox.warning(
                self, 'خطا', 
                'خطا در تشخیص درس انتخابی. لطفا دوباره تلاش کنید.'
            )

    def remove_selected_course(self):
        """Remove selected course from schedule"""
        # This is a placeholder - in a real implementation, you would
        # determine which course to remove based on selection
        QtWidgets.QMessageBox.information(self, 'حذف درس', 'برای حذف یک درس، روی دکمه X روی کارت درس در جدول کلیک کنید.')
    
    def create_combination_card(self, index, combo):
        """Create a card widget for a schedule combination"""
        card = QtWidgets.QFrame()
        card.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        card.setLineWidth(2)
        card.setObjectName("combination_card")
        card.setStyleSheet("""
            QFrame#combination_card {
                background-color: #ffffff;
                border: 2px solid #3498db;
                border-radius: 15px;
                margin: 12px;
                padding: 15px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
            QFrame#combination_card:hover {
                border: 2px solid #2980b9;
                background-color: #f8f9fa;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(card)
        layout.setSpacing(10)
        
        # Card header with enhanced styling
        header_widget = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title section
        title_section = QtWidgets.QWidget()
        title_layout = QtWidgets.QVBoxLayout(title_section)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QtWidgets.QLabel(f'ترکیب {index + 1}')
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        
        # Stats badges
        stats_widget = QtWidgets.QWidget()
        stats_layout = QtWidgets.QHBoxLayout(stats_widget)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        
        days_badge = QtWidgets.QLabel(f'روزها: {combo["days"]}')
        days_badge.setStyleSheet("""
            background-color: #3498db;
            color: white;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: bold;
        """)
        
        empty_badge = QtWidgets.QLabel(f'خالی: {combo["empty"]:.1f}h')
        empty_badge.setStyleSheet("""
            background-color: #2ecc71;
            color: white;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: bold;
        """)
        
        courses_badge = QtWidgets.QLabel(f'دروس: {len(combo["courses"])}')
        courses_badge.setStyleSheet("""
            background-color: #9b59b6;
            color: white;
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: bold;
        """)
        
        stats_layout.addWidget(days_badge)
        stats_layout.addWidget(empty_badge)
        stats_layout.addWidget(courses_badge)
        stats_layout.addStretch()
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(stats_widget)
        
        # Action buttons
        button_section = QtWidgets.QWidget()
        button_layout = QtWidgets.QVBoxLayout(button_section)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        apply_btn = QtWidgets.QPushButton('اعمال ترکیب')
        apply_btn.setObjectName("success_btn")
        apply_btn.setMinimumHeight(35)
        apply_btn.clicked.connect(lambda checked, idx=index: self.apply_preset(idx))
        
        details_btn = QtWidgets.QPushButton('جزئیات')
        details_btn.setObjectName("detailed_info_btn")
        details_btn.setMinimumHeight(35)
        details_btn.clicked.connect(lambda checked, c=combo: self.show_combination_details(c))
        
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(details_btn)
        
        header_layout.addWidget(title_section, 1)
        header_layout.addWidget(button_section)
        
        layout.addWidget(header_widget)
        
        # Course list with enhanced styling
        course_list = QtWidgets.QListWidget()
        course_list.setMaximumHeight(200)
        course_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #d5dbdb;
                border-radius: 10px;
                background-color: #ffffff;
                padding: 8px;
            }
            QListWidget::item {
                border-bottom: 1px solid #ecf0f1;
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #d6eaf8;
                color: #2980b9;
            }
        """)
        
        total_credits = 0
        for course_key in combo['courses']:
            if course_key in COURSES:
                course = COURSES[course_key]
                total_credits += course.get('credits', 0)
                item = QtWidgets.QListWidgetItem(
                    f"{course['name']} — {course['code']} — {course.get('instructor', 'نامشخص')}"
                )
                course_list.addItem(item)
        
        layout.addWidget(course_list)
        
        # Footer with total credits
        footer_widget = QtWidgets.QWidget()
        footer_layout = QtWidgets.QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        
        credits_label = QtWidgets.QLabel(f'مجموع واحدها: {total_credits}')
        credits_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e74c3c;")
        
        footer_layout.addStretch()
        footer_layout.addWidget(credits_label)
        
        layout.addWidget(footer_widget)
        
        return card

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
        
        # Course info panel is updated in on_course_clicked
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()
        
        # Auto-save user data
        self.auto_save_user_data()
        
        QtWidgets.QMessageBox.information(self, 'پاک شد', 'تمام دروس از جدول حذف شدند.')

    # ---------------------- eventFilter for hover ----------------------
    def eventFilter(self, obj, event):
        """Handle hover events for course preview with improved position mapping and responsive design"""
        # Check if course_list exists and is not None before accessing it
        if hasattr(self, 'course_list') and self.course_list is not None and (obj == self.course_list.viewport() or obj == self.course_list):
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
        
        # Handle window resize events for responsive design
        elif event.type() == QtCore.QEvent.Resize:
            if obj == self:
                self.handle_responsive_layout(event.size())
        
        return super().eventFilter(obj, event)
    
    def handle_responsive_layout(self, size):
        """Handle responsive layout changes based on window size"""
        width = size.width()
        
        # For smaller screens, adjust UI elements
        if width < 1280:
            # Reduce font sizes and padding for smaller screens
            self.setFont(QtGui.QFont('IRANSans UI', 11))
            
            # Adjust table row height
            self.table.verticalHeader().setDefaultSectionSize(28)
            
            # Adjust button sizes
            for btn in self.findChildren(QtWidgets.QPushButton):
                font = btn.font()
                font.setPointSize(11)
                btn.setFont(font)
                
            # Adjust group box titles
            for group_box in self.findChildren(QtWidgets.QGroupBox):
                font = group_box.font()
                font.setPointSize(14)
                group_box.setFont(font)
                
            # For very small screens, we could implement a mobile view
            if width < 768:
                self.apply_mobile_layout()
            else:
                self.apply_desktop_layout()
        else:
            # Reset to default sizes for larger screens
            self.setFont(QtGui.QFont('IRANSans UI', 12))
            
            # Reset table row height
            self.table.verticalHeader().setDefaultSectionSize(32)
            
            # Reset button sizes
            for btn in self.findChildren(QtWidgets.QPushButton):
                font = btn.font()
                font.setPointSize(12)
                btn.setFont(font)
                
            # Reset group box titles
            for group_box in self.findChildren(QtWidgets.QGroupBox):
                font = group_box.font()
                font.setPointSize(16)
                group_box.setFont(font)
                
            # Apply desktop layout
            self.apply_desktop_layout()
    
    def toggle_sidebar(self):
        """Toggle sidebar visibility for mobile/responsive design"""
        if self.left_panel.isVisible():
            self.left_panel.hide()
        else:
            self.left_panel.show()
    
    def apply_mobile_layout(self):
        """Apply mobile-friendly layout adjustments"""
        # Hide sidebar by default on mobile
        self.left_panel.hide()
        
        # Adjust font sizes
        self.setFont(QtGui.QFont('IRANSans UI', 10))
        
        # Adjust table for better mobile viewing
        self.table.verticalHeader().setDefaultSectionSize(24)
        
        # Adjust all buttons
        for btn in self.findChildren(QtWidgets.QPushButton):
            font = btn.font()
            font.setPointSize(10)
            btn.setFont(font)
            
        # Adjust group boxes
        for group_box in self.findChildren(QtWidgets.QGroupBox):
            font = group_box.font()
            font.setPointSize(12)
            group_box.setFont(font)
    
    def apply_desktop_layout(self):
        """Apply standard desktop layout"""
        # Show sidebar
        self.left_panel.show()
        
        # Reset font sizes
        self.setFont(QtGui.QFont('IRANSans UI', 12))
        
        # Reset table row height
        self.table.verticalHeader().setDefaultSectionSize(32)
        
        # Reset all buttons
        for btn in self.findChildren(QtWidgets.QPushButton):
            font = btn.font()
            font.setPointSize(12)
            btn.setFont(font)
            
        # Reset group boxes
        for group_box in self.findChildren(QtWidgets.QGroupBox):
            font = group_box.font()
            font.setPointSize(16)
            group_box.setFont(font)

    # ---------------------- populate UI ----------------------
    def populate_course_list(self, filter_text=""):
        """Populate the course list with all available courses - fixed widget lifecycle management"""
        # Clear existing widgets and cache when repopulating to prevent deleted widget issues
        self.course_list.clear()
        
        # Clear widget cache to prevent using deleted widgets
        if hasattr(self, '_course_widgets_cache'):
            self._course_widgets_cache.clear()
        else:
            self._course_widgets_cache = {}
        
        # Filter courses if search text provided
        courses_to_show = COURSES
        if filter_text.strip():
            filter_text = filter_text.strip().lower()
            courses_to_show = {
                key: course for key, course in COURSES.items()
                if (filter_text in course.get('name', '').lower() or
                    filter_text in course.get('code', '').lower() or
                    filter_text in course.get('instructor', '').lower())
            }
            
        # Process courses and create widgets
        used = 0
        
        # Pre-sort courses by name for consistent ordering
        sorted_courses = sorted(courses_to_show.items(), key=lambda x: x[1].get('name', ''))
        
        for key, course in sorted_courses:
            try:
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
                
                # Add item to list first
                self.course_list.addItem(item)
                
                # Create new custom widget for this item (no caching to avoid deleted widget issues)
                course_widget = CourseListWidget(key, course, self.course_list, self)
                # Set background color using QSS class
                color_index = used % len(COLOR_MAP)
                course_widget.setProperty('colorIndex', color_index)
                
                # Set the custom widget for this item
                item.setSizeHint(course_widget.sizeHint())
                self.course_list.setItemWidget(item, course_widget)
                
                # Cache tooltip only (not the widget)
                tooltip_key = f"{key}_tooltip"
                self._course_widgets_cache[tooltip_key] = tooltip
                
                used += 1
                
            except Exception as e:
                logger.error(f"Error creating widget for course {key}: {e}", exc_info=True)
                print(f"Warning: Could not create widget for course {key}: {e}")
                continue
            
        # Update status with count
        total_courses = len(COURSES)
        shown_courses = len(courses_to_show)
        if filter_text.strip():
            # Update status bar to show filtered results
            search_status = f"نمایش {shown_courses} از {total_courses} درس (فیلتر: '{filter_text}')"
            self.status_bar.showMessage(search_status)
        else:
            # Regular status update
            self.update_status()
            
        logger.info(f"Populated course list with {shown_courses} courses (filtered: {bool(filter_text.strip())})")
            
    def on_search_changed(self):
        """Handle search box text changes with debouncing for performance"""
        search_text = self.search_box.text()
        
        # Use a timer to debounce search for better performance
        if hasattr(self, '_search_timer'):
            self._search_timer.stop()
        
        self._search_timer = QtCore.QTimer()
        self._search_timer.timeout.connect(lambda: self.populate_course_list(search_text))
        self._search_timer.setSingleShot(True)
        self._search_timer.start(50)  # 50ms delay for even more responsive search
    
    def clear_search(self):
        """Clear the search box and reset the course list"""
        self.search_box.clear()
        self.populate_course_list()

    def auto_save_user_data(self):
        """Auto-save user data without user interaction with backup functionality"""
        try:
            # Collect currently placed course keys
            keys = list({info['course'] for info in self.placed.values()})
            
            # Update user data with current schedule
            self.user_data['current_schedule'] = keys
            
            # Create backup before saving
            import shutil
            import datetime
            backup_file = f"{USER_DATA_FILE}.backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists(USER_DATA_FILE):
                shutil.copy2(USER_DATA_FILE, backup_file)
                logger.info(f"Backup created: {backup_file}")
            
            # Save user data
            save_user_data(self.user_data)
            
            # Keep only last 5 backups
            self._cleanup_old_backups()
            
        except Exception as e:
            logger.error(f"Auto-save failed: {e}")
            # Don't show error to user for auto-save to keep it seamless
            
    def _cleanup_old_backups(self):
        """Clean up old backup files, keeping only the last 5"""
        try:
            import glob
            backup_files = glob.glob(f"{USER_DATA_FILE}.backup_*")
            backup_files.sort(key=os.path.getmtime, reverse=True)
            
            # Remove backups older than 5
            for old_backup in backup_files[5:]:
                try:
                    os.remove(old_backup)
                    logger.info(f"Removed old backup: {old_backup}")
                except Exception as e:
                    logger.error(f"Failed to remove backup {old_backup}: {e}")
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")

    def load_user_schedule(self):
        """Load previously saved user schedule on application startup"""
        try:
            # Check if there's a current schedule in user data
            current_schedule = self.user_data.get('current_schedule', [])
            
            if current_schedule:
                # Load each course in the schedule
                for course_key in current_schedule:
                    if course_key in COURSES:
                        self.add_course_to_table(course_key, ask_on_conflict=False)
                
                # Update UI
                self.update_status()
                self.update_detailed_info_if_open()
                
                logger.info(f"Loaded {len(current_schedule)} courses from saved schedule")
                
        except Exception as e:
            logger.error(f"Failed to load user schedule: {e}")
            # Don't show error to user to keep startup smooth

    def generate_optimal_schedule(self):
        """Generate optimal schedule combinations with enhanced algorithm"""
        # Get all available courses
        all_courses = list(COURSES.keys())
        
        if not all_courses:
            QtWidgets.QMessageBox.information(self, 'هیچ درسی', 'هیچ درسی برای برنامه‌ریزی وجود ندارد.')
            return
            
        # Show progress dialog
        progress = QtWidgets.QProgressDialog('در حال تولید بهترین ترکیبات...', 'لغو', 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.show()
        
        try:
            # Generate best combinations
            combos = self.generate_best_combinations(all_courses)
            progress.setValue(50)
            
            if not combos:
                QtWidgets.QMessageBox.warning(
                    self, 'نتیجه', 
                    'هیچ ترکیب بدون تداخل پیدا نشد.'
                )
                return
            
            # Display results in a dialog
            self.show_optimal_schedule_results(combos)
            progress.setValue(100)
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, 'خطا', 
                f'خطا در تولید ترکیبات:\n{str(e)}'
            )
            print(f"Error in generate_optimal_schedule: {e}")
        finally:
            progress.close()
    
    def generate_best_combinations(self, course_keys):
        """Generate best schedule combinations minimizing days and gaps"""
        # Generate all possible combinations
        best_combos = []
        
        # For demonstration, we'll use a simpler approach
        # In a real implementation, this would be more sophisticated
        for r in range(1, min(6, len(course_keys) + 1)):  # Limit to 5 courses for performance
            for combo in itertools.combinations(course_keys, r):
                # Check if combination has conflicts
                if not self.has_conflicts(combo):
                    # Calculate score (minimize days and gaps)
                    days = self.calculate_days_for_combo(combo)
                    gaps = self.calculate_gaps_for_combo(combo)
                    score = days + 0.5 * gaps
                    
                    best_combos.append({
                        'courses': list(combo),
                        'days': days,
                        'gaps': gaps,
                        'score': score
                    })
        
        # Sort by score (lower is better)
        best_combos.sort(key=lambda x: x['score'])
        return best_combos[:10]  # Return top 10 combinations
    
    def has_conflicts(self, course_combo):
        """Check if a combination of courses has scheduling conflicts"""
        for i, course_key1 in enumerate(course_combo):
            for course_key2 in course_combo[i+1:]:
                if schedules_conflict(COURSES[course_key1]['schedule'], COURSES[course_key2]['schedule']):
                    return True
        return False
    
    def calculate_days_for_combo(self, course_combo):
        """Calculate number of days needed for a combination of courses"""
        days = set()
        for course_key in course_combo:
            for session in COURSES[course_key]['schedule']:
                days.add(session['day'])
        return len(days)
    
    def calculate_gaps_for_combo(self, course_combo):
        """Calculate total gap hours for a combination of courses"""
        daily_sessions = {}
        for course_key in course_combo:
            for session in COURSES[course_key]['schedule']:
                day = session['day']
                if day not in daily_sessions:
                    daily_sessions[day] = []
                daily_sessions[day].append((to_minutes(session['start']), to_minutes(session['end'])))
        
        total_gaps = 0
        for day, sessions in daily_sessions.items():
            sessions.sort()
            for i in range(len(sessions) - 1):
                gap = sessions[i + 1][0] - sessions[i][1]
                if gap > 0:
                    total_gaps += gap / 60.0  # Convert to hours
        
        return total_gaps
    
    def show_optimal_schedule_results(self, combos):
        """Show optimal schedule results in a dialog"""
        if not combos:
            QtWidgets.QMessageBox.information(self, 'نتیجه', 'هیچ ترکیب بهینه‌ای پیدا نشد.')
            return
            
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle('ترکیب‌های بهینه پیشنهادی')
        dialog.resize(600, 400)
        dialog.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Title
        title_label = QtWidgets.QLabel('ترکیب‌های بهینه پیشنهادی')
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin: 10px;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Info label
        info_label = QtWidgets.QLabel('بهترین ترکیب‌ها بر اساس حداقل روزهای حضور و حداقل فاصله بین جلسات')
        info_label.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # Results list
        results_list = QtWidgets.QListWidget()
        layout.addWidget(results_list)
        
        # Add combinations to list
        for i, combo in enumerate(combos[:10]):  # Show top 10
            # Create item widget
            item_widget = QtWidgets.QWidget()
            item_layout = QtWidgets.QVBoxLayout(item_widget)
            item_layout.setContentsMargins(10, 10, 10, 10)
            
            # Header with rank and stats
            header_layout = QtWidgets.QHBoxLayout()
            
            rank_label = QtWidgets.QLabel(f'#{i+1}')
            rank_label.setStyleSheet("font-weight: bold; color: #1976D2; font-size: 14px;")
            rank_label.setFixedWidth(30)
            
            stats_label = QtWidgets.QLabel(f'روزها: {combo["days"]} | فاصله: {combo["gaps"]:.1f}h | امتیاز: {combo["score"]:.1f}')
            stats_label.setStyleSheet("color: #7f8c8d;")
            
            apply_btn = QtWidgets.QPushButton('اعمال')
            apply_btn.setObjectName("success_btn")
            apply_btn.setFixedWidth(80)
            apply_btn.clicked.connect(lambda checked, c=combo: self.apply_optimal_combo(c, dialog))
            
            header_layout.addWidget(rank_label)
            header_layout.addWidget(stats_label)
            header_layout.addStretch()
            header_layout.addWidget(apply_btn)
            
            item_layout.addLayout(header_layout)
            
            # Course list
            course_list = QtWidgets.QListWidget()
            course_list.setMaximumHeight(100)
            course_list.setStyleSheet("border: 1px solid #d5dbdb; border-radius: 5px;")
            
            for course_key in combo['courses']:
                if course_key in COURSES:
                    course = COURSES[course_key]
                    course_item = QtWidgets.QListWidgetItem(
                        f"{course['name']} - {course['code']} - {course.get('instructor', 'نامشخص')}"
                    )
                    course_list.addItem(course_item)
            
            item_layout.addWidget(course_list)
            
            # Add item to list
            list_item = QtWidgets.QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            results_list.addItem(list_item)
            results_list.setItemWidget(list_item, item_widget)
        
        # Close button
        close_btn = QtWidgets.QPushButton('بستن')
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec_()
    
    def apply_optimal_combo(self, combo, dialog):
        """Apply an optimal combination to the schedule"""
        # Clear current schedule
        self.clear_table_silent()
        
        # Add courses from combination
        for course_key in combo['courses']:
            if course_key in COURSES:
                self.add_course_to_table(course_key, ask_on_conflict=False)
        
        # Update UI
        self.update_status()
        self.update_detailed_info_if_open()
        
        # Close dialog
        dialog.close()
        
        QtWidgets.QMessageBox.information(
            self, 'اعمال شد', 
            f'ترکیب بهینه با {combo["days"]} روز حضور و {combo["gaps"]:.1f} ساعت فاصله اعمال شد.'
        )

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
            
        # Get existing combo names for duplicate checking
        existing_names = [combo.get('name', '') for combo in self.user_data.get('saved_combos', [])]
        
        while True:
            name, ok = QtWidgets.QInputDialog.getText(self, 'نام ترکیب', 'نام ترکیب را وارد کنید:')
            if not ok:
                return
            
            name = name.strip()
            if not name:
                QtWidgets.QMessageBox.warning(self, 'خطا', 'لطفا نامی وارد کنید.')
                continue
                
            # Check for duplicate names
            if name in existing_names:
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle('نام تکراری')
                msg.setText(f'ترکیبی با نام "{name}" قبلاً ذخیره شده است.')
                msg.setInformativeText('لطفا نام دیگری انتخاب کنید یا برای جایگزینی تأیید کنید.')
                msg.setStandardButtons(QtWidgets.QMessageBox.Retry | QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
                msg.setDefaultButton(QtWidgets.QMessageBox.Retry)
                msg.button(QtWidgets.QMessageBox.Retry).setText('نام جدید')
                msg.button(QtWidgets.QMessageBox.Yes).setText('جایگزینی')
                msg.button(QtWidgets.QMessageBox.Cancel).setText('لغو')
                
                result = msg.exec_()
                if result == QtWidgets.QMessageBox.Retry:
                    continue  # Ask for new name
                elif result == QtWidgets.QMessageBox.Yes:
                    # Replace existing combo
                    self.user_data['saved_combos'] = [combo for combo in self.user_data.get('saved_combos', []) if combo.get('name') != name]
                    break  # Proceed with saving
                else:
                    return  # Cancel
            else:
                break  # Name is unique, proceed
        
        # Save the combination
        sc = {'name': name, 'courses': keys}
        self.user_data.setdefault('saved_combos', []).append(sc)
        save_user_data(self.user_data)
        self.load_saved_combos_ui()
        QtWidgets.QMessageBox.information(self, 'ذخیره', f'ترکیب "{name}" ذخیره شد.')

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
        """Show enhanced preview of course schedule with improved styling"""
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
                # Create preview with improved layout matching main course cells
                preview_widget = QtWidgets.QWidget()
                preview_layout = QtWidgets.QVBoxLayout(preview_widget)
                preview_layout.setContentsMargins(4, 2, 4, 2)
                preview_layout.setSpacing(1)
                
                # Course Name (Bold)
                course_name_label = QtWidgets.QLabel(course['name'])
                course_name_label.setObjectName("course_name_label")
                course_name_label.setAlignment(QtCore.Qt.AlignCenter)
                course_name_label.setWordWrap(True)
                
                # Professor Name
                professor_label = QtWidgets.QLabel(course.get('instructor', 'نامشخص'))
                professor_label.setObjectName("professor_label")
                professor_label.setAlignment(QtCore.Qt.AlignCenter)
                professor_label.setWordWrap(True)
                
                # Course Code
                code_label = QtWidgets.QLabel(course.get('code', ''))
                code_label.setObjectName("code_label")
                code_label.setAlignment(QtCore.Qt.AlignCenter)
                code_label.setWordWrap(True)
                
                preview_layout.addWidget(course_name_label)
                preview_layout.addWidget(professor_label)
                preview_layout.addWidget(code_label)
                
                # Parity indicator if applicable
                parity_indicator = ''
                if sess.get('parity') == 'ز':
                    parity_indicator = 'ز'
                elif sess.get('parity') == 'ف':
                    parity_indicator = 'ف'
                
                if parity_indicator:
                    bottom_layout = QtWidgets.QHBoxLayout()
                    parity_label = QtWidgets.QLabel(parity_indicator)
                    parity_label.setAlignment(QtCore.Qt.AlignLeft)
                    
                    # Set object name based on parity type
                    if parity_indicator == 'ز':
                        parity_label.setObjectName("parity_label_even")
                    elif parity_indicator == 'ف':
                        parity_label.setObjectName("parity_label_odd")
                    else:
                        parity_label.setObjectName("parity_label_all")
                    bottom_layout.addWidget(parity_label)
                    bottom_layout.addStretch()
                    preview_layout.addLayout(bottom_layout)
                
                preview_widget.setAutoFillBackground(True)
                preview_widget.setObjectName("preview_widget")
                
                self.table.setCellWidget(srow, col, preview_widget)
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
        """Handle course selection from the list with enhanced debugging"""
        if item is None:
            logger.warning("on_course_clicked called with None item")
            return
            
        key = item.data(QtCore.Qt.UserRole)
        logger.debug(f"Course clicked - item: {item}, key: {key}")
        
        if key:
            logger.info(f"User clicked on course with key: {key}")
            self.clear_preview()
            self.add_course_to_table(key, ask_on_conflict=True)
        else:
            logger.warning(f"Course item clicked but no key found in UserRole data")
            QtWidgets.QMessageBox.warning(
                self, 'خطا', 
                'خطا در تشخیص درس انتخابی. لطفا دوباره تلاش کنید.'
            )

    # Double-click functionality removed as per user request - only single click and X button deletion

    def add_course_to_table(self, course_key, ask_on_conflict=True):
        """Add a course to the schedule table"""
        course = COURSES.get(course_key)
        if not course:
            QtWidgets.QMessageBox.warning(self, 'خطا', f'درس با کلید {course_key} یافت نشد.')
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
                # Skip conflict check with the same course
                if info['course'] == course_key:
                    continue
                prow_start = prow
                prow_span = info['rows']
                if not (srow + span <= prow_start or prow_start + prow_span <= srow):
                    conflict_course = COURSES.get(info['course'], {})
                    conflicts.append(((srow, col), (prow_start, pcol), info['course'], conflict_course.get('name', 'نامشخص')))
        
        # Add conflict indicator to course info if there are conflicts
        has_conflicts = len(conflicts) > 0

        # Handle conflicts with better warning messages and visual indicators
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
            conflicting_courses = set()
            for conf in conflicts:
                (_, _), (rstart, rcol), rcourse, _ = conf
                conflicting_courses.add(rcourse)
            
            # Remove entire conflicting courses
            for conflicting_course_key in conflicting_courses:
                self.remove_course_from_schedule(conflicting_course_key)
        elif conflicts and not ask_on_conflict:
            # If we're not asking about conflicts (e.g., applying presets), still mark as conflicting
            has_conflicts = True

        # Clear preview
        self.clear_preview()

        COLOR_MAP = [
            QtGui.QColor(174, 214, 241),  # Light Blue
            QtGui.QColor(175, 215, 196),  # Light Green
            QtGui.QColor(248, 220, 188),  # Light Orange
            QtGui.QColor(216, 191, 216),  # Light Purple
            QtGui.QColor(240, 202, 202),  # Light Red
            QtGui.QColor(250, 235, 215)   # Light Beige
        ]
        color_idx = len(self.placed) % len(COLOR_MAP)
        # رنگ‌ها - Updated with harmonious color palette
        bg = COLOR_MAP[color_idx % len(COLOR_MAP)]
        for (srow, col, span, sess) in placements:
            # Determine parity information and styling
            parity_indicator = ''
            if sess.get('parity') == 'ز':
                parity_indicator = 'ز'
            elif sess.get('parity') == 'ف':
                parity_indicator = 'ف'

            # Create course cell widget with improved styling
            cell_widget = AnimatedCourseWidget(course_key, bg, has_conflicts, self)
            # Set object name for QSS styling
            cell_widget.setObjectName('course-cell')
            
            # Set properties for styling based on course type and conflicts
            if has_conflicts:
                cell_widget.setProperty('conflict', True)
            elif course.get('code', '').startswith('elective'):
                cell_widget.setProperty('elective', True)
            else:
                cell_widget.setProperty('conflict', False)
                cell_widget.setProperty('elective', False)
            
            # Store background color for animation
            cell_widget.bg_color = bg
            cell_widget.border_color = QtGui.QColor(bg.red()//2, bg.green()//2, bg.blue()//2)
            cell_layout = QtWidgets.QVBoxLayout(cell_widget)
            cell_layout.setContentsMargins(3, 2, 3, 2)
            cell_layout.setSpacing(1)
            
            # Top row with X button
            top_row = QtWidgets.QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            
            # X button for course removal - properly styled in red
            x_button = QtWidgets.QPushButton('✕')
            x_button.setFixedSize(18, 18)
            x_button.setObjectName('close-btn')
            x_button.clicked.connect(lambda checked, ck=course_key: self.remove_course_with_confirmation(ck))
            
            top_row.addStretch()
            top_row.addWidget(x_button)
            cell_layout.addLayout(top_row)
            
            # Course information with improved layout
            # Course Name (Bold)
            course_name_label = QtWidgets.QLabel(course['name'])
            course_name_label.setAlignment(QtCore.Qt.AlignCenter)
            course_name_label.setWordWrap(True)
            course_name_label.setObjectName('course-name-label')
            
            # Professor Name
            professor_label = QtWidgets.QLabel(course.get('instructor', 'نامشخص'))
            professor_label.setAlignment(QtCore.Qt.AlignCenter)
            professor_label.setWordWrap(True)
            professor_label.setObjectName('professor-label')
            
            # Course Code
            code_label = QtWidgets.QLabel(course.get('code', ''))
            code_label.setAlignment(QtCore.Qt.AlignCenter)
            code_label.setWordWrap(True)
            code_label.setObjectName('code-label')
            
            # Conflict indicator (if applicable) with enhanced styling
            conflict_widget = None
            if has_conflicts:
                conflict_layout = QtWidgets.QHBoxLayout()
                conflict_icon = QtWidgets.QLabel("⚠")
                conflict_icon.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 16px;")
                conflict_icon.setToolTip("این درس با دروس دیگر تداخل دارد")
                conflict_text = QtWidgets.QLabel("تداخل!")
                conflict_text.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 12px;")
                conflict_layout.addWidget(conflict_icon)
                conflict_layout.addWidget(conflict_text)
                conflict_layout.addStretch()
                
                conflict_widget = QtWidgets.QWidget()
                conflict_widget.setLayout(conflict_layout)
                conflict_widget.setStyleSheet("background-color: rgba(231, 76, 60, 0.2); border: 2px solid #e74c3c; border-radius: 6px; padding: 4px;")
            
            # Add labels to layout
            cell_layout.addWidget(course_name_label)
            cell_layout.addWidget(professor_label)
            cell_layout.addWidget(code_label)
            
            # Add conflict indicator if there are conflicts
            if conflict_widget:
                cell_layout.addWidget(conflict_widget)
            
            # Bottom row for parity indicator
            bottom_row = QtWidgets.QHBoxLayout()
            bottom_row.setContentsMargins(0, 0, 0, 0)
            
            # Parity indicator (bottom-left corner)
            if parity_indicator:
                parity_label = QtWidgets.QLabel(parity_indicator)
                parity_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom)
                if parity_indicator == 'ز':
                    parity_label.setObjectName('parity-label-even')
                elif parity_indicator == 'ف':
                    parity_label.setObjectName('parity-label-odd')
                else:
                    parity_label.setObjectName('parity-label-all')
                bottom_row.addWidget(parity_label)
            
            bottom_row.addStretch()
            cell_layout.addLayout(bottom_row)
            
            # Store references for hover effects and course operations
            cell_widget.course_key = course_key
            
            # Enable hover effects
            def enter_event(event, widget=cell_widget):
                self.highlight_course_sessions(widget.course_key)
            
            def leave_event(event, widget=cell_widget):
                self.clear_course_highlights()
            
            def mouse_press_event(event, widget=cell_widget):
                if event.button() == QtCore.Qt.LeftButton:
                    self.show_course_details(widget.course_key)
            
            cell_widget.enterEvent = enter_event
            cell_widget.leaveEvent = leave_event
            cell_widget.mousePressEvent = mouse_press_event
            
            self.table.setCellWidget(srow, col, cell_widget)
            if span > 1:
                self.table.setSpan(srow, col, span, 1)
            self.placed[(srow, col)] = {
                'course': course_key, 
                'rows': span, 
                'widget': cell_widget
            }
            
        # Update status after adding course
        self.update_status()
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()
        
        # Auto-save user data
        self.auto_save_user_data()

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

    def remove_course_with_confirmation(self, course_key):
        """Remove course with user confirmation"""
        course = COURSES.get(course_key, {})
        course_name = course.get('name', 'نامشخص')
        instructor = course.get('instructor', 'نامشخص')
        
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Question)
        msg.setWindowTitle('حذف درس')
        msg.setText(f'آیا مایل به حذف کل درس "{course_name}" هستید؟')
        msg.setInformativeText(f'استاد: {instructor}\nتمام جلسات این درس از جدول حذف خواهد شد.')
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg.setDefaultButton(QtWidgets.QMessageBox.No)
        
        if msg.exec_() == QtWidgets.QMessageBox.Yes:
            self.remove_course_from_schedule(course_key)
            self.update_status()
            self.update_detailed_info_if_open()
    
    def show_course_details(self, course_key):
        """Show detailed course information in a dialog"""
        course = COURSES.get(course_key, {})
        if not course:
            return
            
        details_dialog = QtWidgets.QDialog(self)
        details_dialog.setWindowTitle(f'جزییات درس: {course.get("name", "نامشخص")}')
        details_dialog.setModal(True)
        details_dialog.resize(500, 400)
        details_dialog.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        layout = QtWidgets.QVBoxLayout(details_dialog)
        
        # Course information
        info_text = f"""
        <h2 style="color: #2c3e50; font-family: 'Nazanin', 'Tahoma', sans-serif;">{course.get('name', 'نامشخص')}</h2>
        <p style="font-family: 'Nazanin', 'Tahoma', sans-serif;"><b>کد درس:</b> {course.get('code', 'نامشخص')}</p>
        <p style="font-family: 'Nazanin', 'Tahoma', sans-serif;"><b>استاد:</b> {course.get('instructor', 'نامشخص')}</p>
        <p style="font-family: 'Nazanin', 'Tahoma', sans-serif;"><b>تعداد واحد:</b> {course.get('credits', 0)}</p>
        <p style="font-family: 'Nazanin', 'Tahoma', sans-serif;"><b>مکان برگزاری:</b> {course.get('location', 'نامشخص')}</p>
        <p style="font-family: 'Nazanin', 'Tahoma', sans-serif;"><b>زمان امتحان:</b> {course.get('exam_time', 'اعلام نشده')}</p>
        
        <h3 style="font-family: 'Nazanin', 'Tahoma', sans-serif;">جلسات درس:</h3>
        """
        
        for sess in course.get('schedule', []):
            parity = ''
            if sess.get('parity') == 'ز':
                parity = ' (زوج) - <span style="color: #2ed573; font-weight: bold;">ز</span>'
            elif sess.get('parity') == 'ف':
                parity = ' (فرد) - <span style="color: #3742fa; font-weight: bold;">ف</span>'
            info_text += f"<p style='font-family: \"Nazanin\", \"Tahoma\", sans-serif;'>• {sess['day']} {sess['start']}-{sess['end']}{parity}</p>"
        
        info_text += f"""
        <h3 style="font-family: 'Nazanin', 'Tahoma', sans-serif;">توضیحات درس:</h3>
        <p style="background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: 'Nazanin', 'Tahoma', sans-serif;">{course.get('description', 'توضیحی ارائه نشده')}</p>
        """
        
        text_widget = QtWidgets.QTextEdit()
        text_widget.setHtml(info_text)
        text_widget.setReadOnly(True)
        text_widget.setObjectName("course_details")
        layout.addWidget(text_widget)
        
        # Copy course code button
        copy_button = QtWidgets.QPushButton(f'📋 کپی کد درس: {course.get("code", "")}')
        copy_button.clicked.connect(lambda: self.copy_to_clipboard(course.get('code', '')))
        copy_button.setObjectName("copy_code")
        layout.addWidget(copy_button)
        
        # Close button
        close_button = QtWidgets.QPushButton('بستن')
        close_button.clicked.connect(details_dialog.close)
        close_button.setObjectName("dialog_close")
        layout.addWidget(close_button)
        
        details_dialog.exec_()

    def copy_to_clipboard(self, text):
        """Copy text to clipboard with enhanced user feedback"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        
        # Enhanced feedback message with modern styling
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setWindowTitle('کپی شد')
        msg.setText(f'کد درس "{text}" به کلیپبورد کپی شد.')
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        # Styling is now handled by QSS file
        msg.exec_()
    
    def highlight_course_sessions(self, course_key):
        """Highlight all sessions of a course"""
        # Highlight sessions with red border
        # Clear any existing highlights first to prevent overlap
        self.clear_course_highlights()
        for (srow, scol), info in self.placed.items():
            if info['course'] == course_key:
                widget = info.get('widget')
                if widget and hasattr(widget, 'original_style'):
                    # Create hover style with 2px red border and subtle shadow
                    hover_style = widget.original_style.replace(
                        'border: 2px solid rgba(',
                        'border: 2px solid #e74c3c; box-shadow: 0 0 5px rgba(231, 76, 60, 0.3); border-backup: 2px solid rgba('
                    )
                    widget.setStyleSheet(hover_style)

    def clear_course_highlights(self):
        # Restore original styling for all course widgets
        for (srow, scol), info in self.placed.items():
            widget = info.get('widget')
            original_style = info.get('original_style')
            if widget and original_style:
                # Restore the exact original style to prevent any residual effects
                widget.setStyleSheet(original_style)

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
        
        # Auto-save user data
        self.auto_save_user_data()
        
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
        """Update the detailed info window if it's currently open"""
        if self.detailed_info_window and self.detailed_info_window.isVisible():
            self.detailed_info_window.update_content()

    def show_user_guide(self):
        """Show user guide dialog with application instructions"""
        guide_text = """
        <h2 style='color: #2c3e50; text-align: center;'>📚 راهنمای کاربر برنامه‌ریز انتخاب واحد</h2>
        
        <h3 style='color: #3498db;'>📋 نحوه کار با برنامه</h3>
        <ul>
            <li><b>انتخاب دروس:</b> از لیست سمت راست، دروس مورد نظر را انتخاب کنید</li>
            <li><b>اضافه کردن به برنامه:</b> روی درس کلیک کنید یا آن را به جدول بکشید</li>
            <li><b>حذف درس:</b> روی دکمه X قرمز در سلول درس کلیک کنید</li>
            <li><b>مشاهده جزئیات:</b> روی هر درس در جدول کلیک کنید</li>
        </ul>
        
        <h3 style='color: #3498db;'>🤖 قابلیت‌های پیشرفته</h3>
        <ul>
            <li><b>چیدمان خودکار:</b> از قسمت "تولید بهترین برنامه" استفاده کنید</li>
            <li><b>ذخیره برنامه:</b> برنامه‌های مورد پسند خود را ذخیره کنید</li>
            <li><b>برنامه امتحانات:</b> از منوی نمایش گزینه اطلاعات تفصیلی را انتخاب کنید</li>
        </ul>
        
        <h3 style='color: #3498db;'>🔧 نکات کاربردی</h3>
        <ul>
            <li><b>جستجو:</b> از قسمت جستجو برای پیدا کردن سریع دروس استفاده کنید</li>
            <li><b>پاک کردن:</b> برای شروع مجدد از دکمه پاک کردن جدول استفاده کنید</li>
            <li><b>ذخیره تصویر:</b> از منوی فایل برای ذخیره تصویر جدول استفاده کنید</li>
        </ul>
        
        <p style='text-align: center; color: #7f8c8d; font-style: italic;'>
        برنامه‌ریز انتخاب واحد - توسعه یافته با PyQt5 و Python
        </p>
        """
        
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle('راهنمای کاربر')
        msg.setText(guide_text)
        msg.setTextFormat(QtCore.Qt.RichText)
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()

    def show_auto_arrangement_help(self):
        """Show help for auto arrangement feature"""
        help_text = """
        <h2 style='color: #2c3e50; text-align: center;'>🤖 راهنمای چیدمان خودکار</h2>
        
        <h3 style='color: #9b59b6;'> نحوه استفاده</h3>
        <ol>
            <li><b>انتخاب گروه‌ها:</b> از لیست دروس، دروس مورد نظر را انتخاب کنید</li>
            <li><b>افزودن به لیست:</b> دکمه "افزودن به لیست خودکار" را بزنید</li>
            <li><b>تولید برنامه:</b> دکمه "تولید بهترین برنامه" را کلیک کنید</li>
            <li><b>انتخاب برنامه:</b> از بین گزینه‌های پیشنهادی، یکی را انتخاب کنید</li>
        </ol>
        
        <h3 style='color: #9b59b6;'> معیارهای انتخاب</h3>
        <ul>
            <li><b>کمترین روز:</b> برنامه‌ای که در کمترین روز تشکیل شود</li>
            <li><b>کمترین فاصله:</b> برنامه‌ای که کمترین فاصله بین جلسات را داشته باشد</li>
            <li><b>عدم تداخل:</b> برنامه‌ای که هیچ تداخلی نداشته باشد</li>
        </ul>
        
        <p style='text-align: center; color: #7f8c8d; font-style: italic;'>
        الگوریتم بهینه‌سازی سفارشی - برنامه‌ریز انتخاب واحد
        </p>
        """
        
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle('راهنمای چیدمان خودکار')
        msg.setText(help_text)
        msg.setTextFormat(QtCore.Qt.RichText)
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()

    def show_about(self):
        """Show about dialog with application information"""
        about_text = """
        <h2 style='color: #2c3e50; text-align: center;'>ℹ️ درباره برنامه</h2>
        
        <h3 style='color: #e74c3c; text-align: center;'>🎓 برنامه‌ریز انتخاب واحد</h3>
        <p style='text-align: center; font-size: 14px;'>
        <b>نسخه:</b> 2.1<br>
        <b>تکنولوژی:</b> PyQt5 و Python<br>
        <b>توسعه‌دهنده:</b> سیستم برنامه‌ریزی دانشگاهی
        </p>
        
        <h3 style='color: #3498db;'>🎯 ویژگی‌ها</h3>
        <ul>
            <li>چیدمان خودکار دروس با الگوریتم بهینه‌سازی</li>
            <li>تشخیص خودکار تداخل‌های زمانی</li>
            <li>تولید برنامه امتحانات</li>
            <li>ذخیره و بارگذاری برنامه‌های مورد پسند</li>
            <li>پشتیبانی از دروس هفتگی (فرد/زوج)</li>
        </ul>
        
        <p style='text-align: center; color: #7f8c8d; font-style: italic;'>
        این برنامه به صورت رایگان و برای کمک به دانشجویان توسعه یافته است.
        </p>
        """
        
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle('درباره برنامه')
        msg.setText(about_text)
        msg.setTextFormat(QtCore.Qt.RichText)
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()

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
    
    # Load and apply QSS styles from external file
    try:
        qss_styles = load_qss_styles()
        if qss_styles:
            app.setStyleSheet(qss_styles)
            logger.info("Successfully applied QSS styles to application")
        else:
            logger.info("No QSS styles found, using default Qt styling")
    except Exception as e:
        logger.error(f"Failed to apply styles: {e}")
        # Continue without styles rather than crash
    
    win = SchedulerWindow()
    # Load user's last schedule
    win.load_user_schedule()
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



