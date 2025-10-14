#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dialog windows for Schedule Planner
Contains all dialog classes for the application
"""

# Import all dialog classes from their respective modules
from .course_dialogs import AddCourseDialog, EditCourseDialog
from .info_window import DetailedInfoWindow
from .exam_schedule_window import ExamScheduleWindow
from .credentials_dialog import GolestanCredentialsDialog, get_golestan_credentials

__all__ = ['AddCourseDialog', 'EditCourseDialog', 'DetailedInfoWindow', 'ExamScheduleWindow', 
           'GolestanCredentialsDialog', 'get_golestan_credentials']