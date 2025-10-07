#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Info window module for Schedule Planner
Contains information window for application details
"""

import sys
import os

from PyQt5 import QtWidgets, QtCore, uic

# Import from core modules
from ..core.logger import setup_logging

logger = setup_logging()

# ---------------------- Detailed Information Window ----------------------

class DetailedInfoWindow(QtWidgets.QMainWindow):
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
        
        # Create splitter for exam section only
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # Bottom section: Exam Schedule (now the only section)
        self.create_exam_schedule_section(splitter)
        
    def update_content(self):
        """Update exam schedule content only"""
        self.update_exam_schedule()