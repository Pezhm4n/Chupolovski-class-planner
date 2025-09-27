#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detailed information window for Schedule Planner
Contains the window for displaying detailed information about the schedule
"""

import os
import sys

# Add the app directory to the Python path to enable imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5 import QtWidgets, QtGui, QtCore
from config import logger
from data_manager import save_courses_to_json, save_user_data
from course_utils import to_minutes
from export_dialogs import ExportMixin
from exam_schedule_dialog import ExamScheduleMixin

# ---------------------- Detailed Information Window ----------------------

class DetailedInfoWindow(QtWidgets.QMainWindow, ExportMixin, ExamScheduleMixin):
    """Window for displaying detailed information about the schedule"""
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
        
    def update_content(self):
        """Update exam schedule content only"""
        self.update_exam_schedule()