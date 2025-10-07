#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exam schedule dialog module for Schedule Planner
Contains dialog window for viewing exam schedules
"""

import sys
import os

from PyQt5 import QtWidgets, QtCore

# Import from core modules
from ..core.config import COURSES
from ..core.logger import setup_logging

logger = setup_logging()


class ExamScheduleMixin:
    """Mixin class for exam schedule functionality"""
    
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