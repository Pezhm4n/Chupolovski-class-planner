#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exam Schedule Window for Schedule Planner
Window for displaying exam schedule information loaded from UI file
"""

import os
import sys

# Add the app directory to the Python path to enable imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5 import QtWidgets, QtGui, QtCore, uic
from config import COURSES
from export_dialogs import ExportMixin

class ExamScheduleWindow(QtWidgets.QMainWindow, ExportMixin):
    """Window for displaying exam schedule information loaded from UI file"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        
        # Get the directory of this file
        ui_dir = os.path.dirname(os.path.abspath(__file__))
        exam_ui_file = os.path.join(ui_dir, 'exam_schedule_window.ui')
        
        # Load UI from external file
        try:
            uic.loadUi(exam_ui_file, self)
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, "خطا", f"فایل UI یافت نشد: {exam_ui_file}")
            return
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در بارگذاری UI: {str(e)}")
            return
        
        # Connect signals
        self.connect_signals()
        
        # Update content
        self.update_content()
        
    def connect_signals(self):
        """Connect UI signals to their respective slots"""
        # Connect export action
        self.action_export.triggered.connect(self.export_exam_schedule)
        
    def update_content(self):
        """Update exam schedule content"""
        self.update_exam_schedule()
        
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
        
        # Update table
        self.exam_table.setRowCount(len(exam_data))
        
        for row, data in enumerate(exam_data):
            # Course name
            name_item = QtWidgets.QTableWidgetItem(data['name'])
            self.exam_table.setItem(row, 0, name_item)
            
            # Course code
            code_item = QtWidgets.QTableWidgetItem(data['code'])
            code_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.exam_table.setItem(row, 1, code_item)
            
            # Instructor
            instructor_item = QtWidgets.QTableWidgetItem(data['instructor'])
            self.exam_table.setItem(row, 2, instructor_item)
            
            # Exam time
            exam_item = QtWidgets.QTableWidgetItem(data['exam_time'])
            exam_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.exam_table.setItem(row, 3, exam_item)
            
            # Location
            location_item = QtWidgets.QTableWidgetItem(data['location'])
            location_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.exam_table.setItem(row, 4, location_item)
        
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
            else:
                self.stats_label.setText("📊 هیچ درسی انتخاب نشده است")