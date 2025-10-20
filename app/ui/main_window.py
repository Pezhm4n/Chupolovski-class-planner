#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main window module for Schedule Planner
Contains the main application window and core functionality
"""

import sys
import os
import shutil
import datetime
import itertools
from collections import deque
from PyQt5.QtCore import QTimer, QMutex, QMutexLocker
import sip

from PyQt5 import QtWidgets, QtGui, QtCore, uic

# Import from our core modules
from app.core.config import (
    COURSES, DAYS, TIME_SLOTS, EXTENDED_TIME_SLOTS, COLOR_MAP
)
from app.core.data_manager import (
    load_user_data, save_user_data, generate_unique_key
)
from app.core.logger import setup_logging
from app.core.course_utils import (
    to_minutes, overlap, schedules_conflict, 
    calculate_days_needed_for_combo, calculate_empty_time_for_combo,
    generate_best_combinations_for_groups,
    generate_priority_based_schedules, create_greedy_schedule, create_alternative_schedule
)
from .widgets import (
    CourseListWidget, AnimatedCourseWidget
)
from .dialogs import AddCourseDialog, EditCourseDialog, DetailedInfoWindow
from .exam_schedule_window import ExamScheduleWindow

# Import student profile dialog
from .student_profile_dialog import StudentProfileDialog

# Import credential handling modules
from app.core.credentials import load_local_credentials
from .credentials_dialog import get_golestan_credentials

# Set up logger
logger = setup_logging()

# Set up logger
logger = setup_logging()

# ---------------------- Main Application Window ----------------------

class SchedulerWindow(QtWidgets.QMainWindow):
    """Main window for the Schedule Planner application"""
    
    def __init__(self, db=None):
        super().__init__()
        
        # Store the database instance
        self.db = db
        
        # Get the directory of this file
        ui_dir = os.path.dirname(os.path.abspath(__file__))
        main_ui_file = os.path.join(ui_dir, 'main_window.ui')
        
        # Load UI from external file
        try:
            uic.loadUi(main_ui_file, self)
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, "خطا", f"فایل UI یافت نشد: {main_ui_file}")
            sys.exit(1)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در بارگذاری UI: {str(e)}")
            sys.exit(1)
        
        # Debug: Check if comboBox exists - only in debug mode
        if os.environ.get('DEBUG'):
            logger.debug(f"[DEBUG] comboBox exists: {hasattr(self, 'comboBox')}")
            if hasattr(self, 'comboBox'):
                logger.debug(f"[DEBUG] comboBox type: {type(self.comboBox)}")
        # Initialize schedule table FIRST
        self.initialize_schedule_table()
        
        # Setup responsive layout
        self.setup_responsive_layout()
        
        # Set layout direction
        self.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        # Enable responsive design
        self.installEventFilter(self)
        
        # Initialize status bar
        self.status_bar = self.statusBar()

        
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
    
        # Initialize pulse timers for hover animations
        self._pulse_timers = {}
        
        # Store major categories for filtering
        self.major_categories = []
        self.current_major_filter = None
        
        # Initialize course addition queue for debouncing
        from collections import deque
        from PyQt5.QtCore import QTimer, QMutex

        self.course_addition_queue = deque()
        self.course_addition_timer = QTimer(self)
        self.course_addition_timer.setSingleShot(True)
        self.course_addition_timer.timeout.connect(self._process_course_addition_queue)
        self.course_addition_mutex = QMutex()
        
        # Dual course operation lock
        self.dual_operation_mutex = QMutex()
        
        # Overlay tracking for safety
        self.overlays = {}
        
        # Populate UI with data
        # Load courses from database instead of JSON
        self.load_courses_from_database()
        
        # Populate major dropdown AFTER courses are loaded
        self.populate_major_dropdown()
        
        self.populate_course_list()
        self.load_saved_combos_ui()
        
        # Update status
        self.update_status()
        self.update_stats_panel()
        
        # Create timer to update status bar every 10 second
        self.status_timer = QtCore.QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(10000)  # Update every 10 second
        
        # Initialize detailed info window reference
        self.detailed_info_window = None
        
        # Connect signals
        self.connect_signals()
        
        # Create search clear button and add it to the search box
        self.create_search_clear_button()
        
        # Load and apply styles
        self.load_and_apply_styles()
        
        # Load latest backup on startup
        self.load_latest_backup()
        
        # Create menu bar
        self.create_menu_bar()
        
        logger.info("SchedulerWindow initialized successfully")

    def initialize_schedule_table(self):
        """Initialize the schedule table with days and time slots"""
        try:
            from app.core.config import DAYS, EXTENDED_TIME_SLOTS

            
            # Clear the table completely first
            self.schedule_table.clear()
            
            # Set table dimensions - 6 days with time rows (7:00 to 19:00)
            self.schedule_table.setRowCount(len(EXTENDED_TIME_SLOTS) - 1)  # -1 because we show time ranges
            self.schedule_table.setColumnCount(len(DAYS))
            
            # Set headers with correct order: [شنبه][یکشنبه][دوشنبه][سه‌شنبه][چهارشنبه][پنج‌شنبه]
            headers = DAYS
            self.schedule_table.setHorizontalHeaderLabels(headers)
            
            # Configure table appearance
            self.schedule_table.verticalHeader().setVisible(False)
            self.schedule_table.horizontalHeader().setDefaultAlignment(
                QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter
            )
            self.schedule_table.setShowGrid(False)
            self.schedule_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
            self.schedule_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.schedule_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )
            self.schedule_table.setVerticalHeaderItem(
                0, QtWidgets.QTableWidgetItem("7:00–8:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                1, QtWidgets.QTableWidgetItem("8:00–9:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                2, QtWidgets.QTableWidgetItem("9:00–10:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                3, QtWidgets.QTableWidgetItem("10:00–11:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                4, QtWidgets.QTableWidgetItem("11:00–12:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                5, QtWidgets.QTableWidgetItem("12:00–13:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                6, QtWidgets.QTableWidgetItem("13:00–14:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                7, QtWidgets.QTableWidgetItem("14:00–15:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                8, QtWidgets.QTableWidgetItem("15:00–16:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                9, QtWidgets.QTableWidgetItem("16:00–17:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                10, QtWidgets.QTableWidgetItem("17:00–18:00")
            )
            self.schedule_table.setVerticalHeaderItem(
                11, QtWidgets.QTableWidgetItem("18:00–19:00")
            )

            # Add hover effect to cells
            self.schedule_table.cellEntered.connect(self.on_cell_entered)
            self.schedule_table.cellExited.connect(self.on_cell_exited)
        

            # Set cell alignment
            self.schedule_table.horizontalHeader().setDefaultAlignment(
                QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter
            )

            # Set cell alignment
            for i in range(self.schedule_table.rowCount()):
                for j in range(self.schedule_table.columnCount()):
                    item = self.schedule_table.item(i, j)
                    if item is None:
                        item = QtWidgets.QTableWidgetItem()
                        self.schedule_table.setItem(i, j, item)
                    item.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)

        except Exception as e:
            logger.error(f"Failed to initialize schedule table: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان ایجاد جدول زمان‌بندی وجود ندارد: {str(e)}")
            sys.exit(1)
    
    def load_courses_from_database(self):
        """Load courses from database instead of JSON files"""
        try:
            if self.db is None:
                # Fallback to JSON loading if no database provided
                from app.core.data_manager import load_courses_from_json
                load_courses_from_json()
                logger.warning("No database instance provided, falling back to JSON loading")
                return
            
            # Load courses from database using the proper integration method
            from app.core.golestan_integration import load_courses_from_database
            db_courses = load_courses_from_database(self.db)
            
            # Update the global COURSES dictionary
            global COURSES
            COURSES.clear()
            COURSES.update(db_courses)
            
            # Load user-added courses (these are still in JSON)
            from app.core.data_manager import load_user_added_courses
            load_user_added_courses()
            
            logger.info(f"Successfully loaded {len(COURSES)} courses from database")
            
        except Exception as e:
            logger.error(f"Failed to load courses from database: {e}")
            # Fallback to JSON loading
            from app.core.data_manager import load_courses_from_json
            load_courses_from_json()



    def generate_course_key(self, course):
        """Generate a unique key for a course based on its code and other identifiers"""
        from app.core.data_manager import generate_unique_key
        code = course.get('code', '')
        # Create a safe key by replacing problematic characters
        safe_code = code.replace(' ', '_').replace('-', '_').replace('.', '_')
        
        # If the code is empty, generate a unique key
        if not safe_code:
            # Use name and instructor as fallback
            name = course.get('name', 'unknown')
            instructor = course.get('instructor', 'unknown')
            safe_code = f"{name}_{instructor}".replace(' ', '_').replace('-', '_').replace('.', '_')
        
        # Ensure uniqueness using the data manager function
        return generate_unique_key(safe_code, COURSES)

    def populate_major_dropdown(self):
        """Populate the major dropdown with unique categories from courses"""
        try:
            # If no database instance, fallback to JSON loading
            if self.db is None:
                from app.core.data_manager import load_courses_from_json
                load_courses_from_json()
            else:
                # Load courses from database if not already loaded
                if not COURSES:
                    self.load_courses_from_database()

            # Use database method to get faculties with departments
            if self.db is not None:
                # Get faculties with departments from database
                faculties_with_departments = self.db.get_faculties_with_departments()
                
                # Build major categories from database data
                self.major_categories = []
                for faculty, departments in faculties_with_departments.items():
                    for department in departments:
                        major_identifier = f"{faculty} - {department}"
                        if major_identifier not in self.major_categories:
                            self.major_categories.append(major_identifier)
                
                # Sort the categories
                self.major_categories.sort()
            else:
                # Fallback to using COURSES dictionary
                self.major_categories = sorted(
                    set(course.get('major', 'دروس عمومی') for course in COURSES.values())
                )
            
            # Add "دروس اضافه‌شده توسط کاربر" category at the beginning
            user_added_category = "دروس اضافه‌شده توسط کاربر"
            if user_added_category not in self.major_categories:
                self.major_categories.insert(0, user_added_category)
            else:
                # Move it to the beginning if it already exists
                self.major_categories.remove(user_added_category)
                self.major_categories.insert(0, user_added_category)

            # Clear and populate the combobox
            self.comboBox.clear()
            self.comboBox.addItem("انتخاب رشته")  # Default option
            self.comboBox.addItems(self.major_categories)

            # Set default selection
            self.comboBox.setCurrentIndex(0)

            # Connect signal for filtering courses
            self.comboBox.currentIndexChanged.connect(self.on_major_selection_changed)

        except Exception as e:
            logger.error(f"Failed to populate major dropdown: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان پر کردن فیلتر رشته وجود ندارد: {str(e)}")

    def populate_course_list(self):
        """Populate the course list with courses"""
        try:
            # If no database instance, fallback to JSON loading
            if self.db is None:
                from app.core.data_manager import load_courses_from_json
                load_courses_from_json()
            else:
                # Load courses from database if not already loaded
                if not COURSES:
                    self.load_courses_from_database()

            # Ensure we have courses loaded
            if not COURSES:
                self.load_courses_from_database()

            # Create and set the course list widget
            self.course_list_widget = CourseListWidget(self)
            self.course_list_widget.setCourses(COURSES)

            # Connect signal for adding courses
            self.course_list_widget.courseSelected.connect(self.on_course_selected)

            # Set the course list widget as the central widget
            self.setCentralWidget(self.course_list_widget)

        except Exception as e:
            logger.error(f"Failed to populate course list: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان پر کردن فهرست دروس وجود ندارد: {str(e)}")
            sys.exit(1)

    def on_major_changed(self, index):
        """Handle major change"""
        try:
            # Get the selected major
            selected_major = self.comboBox.itemText(index)

            # If selected major is "همه"، show all courses
            if selected_major == "همه":
                self.current_major_filter = None
            else:
                self.current_major_filter = selected_major

            # Update course list based on the selected major
            if hasattr(self, 'course_list_widget') and self.course_list_widget:
                self.course_list_widget.filterCourses(self.current_major_filter)
            else:
                # Fallback to repopulating the course list
                self.populate_course_list()

        except Exception as e:
            logger.error(f"Failed to handle major change: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان مدیریت تغییر رشته وجود ندارد: {str(e)}")
            sys.exit(1)


    def on_course_selected(self, course_key):
        """Handle course selection"""
        try:
            # If no database instance, fallback to JSON loading
            if self.db is None:
                from app.core.data_manager import load_courses_from_json
                load_courses_from_json()
            else:
                # Load courses from database if not already loaded
                if not COURSES:
                    self.load_courses_from_database()

            # Get the course details
            course = COURSES.get(course_key)

            if course:
                # Add course to the list of selected courses
                self.courses.append(course)

                # Update the status bar
                self.update_status()

                # Save user data
                save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to handle course selection: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان مدیریت انتخاب درس وجود ندارد: {str(e)}")
            sys.exit(1)

    def load_saved_combos_ui(self):
        """Load saved combos from user data and display them"""
        try:
            # If no database instance, fallback to JSON loading
            if self.db is None:
                from app.core.data_manager import load_courses_from_json
                load_courses_from_json()
            else:
                # Load courses from database if not already loaded
                if not COURSES:
                    self.load_courses_from_database()

            # Load saved combos from user data
            saved_combos = self.user_data.get('saved_combos', [])

            # Add saved combos to the combo box
            for combo in saved_combos:
                combo_str = ', '.join(combo)
                self.saved_combo_box.addItem(combo_str)

            # Connect signal for loading saved combos
            self.saved_combo_box.currentIndexChanged.connect(self.on_saved_combo_changed)

        except Exception as e:
            logger.error(f"Failed to load saved combos: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان بارگذاری ترکیبات ذخیره شده وجود ندارد: {str(e)}")
            sys.exit(1)

    def on_saved_combo_changed(self, index):
        """Handle saved combo change"""
        try:
            # Get the selected combo
            selected_combo_str = self.saved_combo_box.itemText(index)

            if selected_combo_str:
                # Split the combo string into individual course keys
                selected_combo = selected_combo_str.split(', ')

                # Load and display the selected combo
                self.load_combo(selected_combo)

        except Exception as e:
            logger.error(f"Failed to handle saved combo change: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان مدیریت تغییر ترکیب ذخیره شده وجود ندارد: {str(e)}")
            sys.exit(1)

    def load_combo(self, combo):
        """Load and display a combo"""
        try:
            from app.core.data_manager import load_courses_from_json

            # Load courses first to ensure courses are available
            load_courses_from_json()

            # Clear the current schedule
            self.clear_schedule()

            # Get the course details for each course key in the combo
            courses = [c for c in COURSES if c['key'] in combo]

            # Place each course on the schedule
            for course in courses:
                self.place_course(course)

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to load combo: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان بارگذاری ترکیب وجود ندارد: {str(e)}")
            sys.exit(1)

    def clear_schedule(self):
        """Clear the schedule table"""
        try:
            # Clear all items in the schedule table
            self.schedule_table.clearContents()

            # Clear the list of placed courses
            self.placed = {}

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to clear schedule: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان پاک کردن جدول زمان‌بندی وجود ندارد: {str(e)}")
            sys.exit(1)

    def place_course(self, course):
        """Place a course on the schedule"""
        try:
            # Get the course details
            course_key = course['key']
            course_name = course['name']
            course_days = course['days']
            course_times = course['times']

            # Calculate the cell coordinates for the course
            row_start = to_minutes(course_times[0]) // 60 - 7
            row_span = (to_minutes(course_times[1]) - to_minutes(course_times[0])) // 60
            col_start = DAYS.index(course_days[0])
            col_span = 1

            # Create an item for the course
            item = QtWidgets.QTableWidgetItem(course_name)

            # Set the item background color
            item.setBackground(QtGui.QColor(COLOR_MAP[course_key]))

            # Set the item alignment
            item.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)

            # Set the item user data
            item.setData(QtCore.Qt.UserRole, course_key)

            # Add the item to the schedule table
            self.schedule_table.setSpan(row_start, col_start, row_span, col_span)
            self.schedule_table.setItem(row_start, col_start, item)

            # Store the placed course
            self.placed[course_key] = (row_start, col_start, row_span, col_span)

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to place course: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان قرار دادن درس وجود ندارد: {str(e)}")
            sys.exit(1)

    def on_cell_entered(self, row, col):
        """Handle cell enter event"""
        try:
            # Get the item at the cell
            item = self.schedule_table.item(row, col)

            if item:
                course_key = item.data(QtCore.Qt.UserRole)
                self.last_hover_key = course_key

                # Get the course details
                course = next((c for c in COURSES if c['key'] == course_key), None)

                if course:
                    # Get the course details
                    course_name = course['name']
                    course_days = course['days']
                    course_times = course['times']

                    # Create a tooltip for the course
                    tooltip = f"{course_name}\nروز‌ها: {', '.join(course_days)}\nزمان‌ها: {', '.join(course_times)}"

                    # Set the tooltip for the cell
                    item.setToolTip(tooltip)

                    # Start pulse animation for the cell
                    self.start_pulse_animation(row, col)

        except Exception as e:
            logger.error(f"Failed to handle cell enter event: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان مدیریت ورود به سلول وجود ندارد: {str(e)}")
            sys.exit(1)

    def on_cell_exited(self, row, col):
        """Handle cell exit event"""
        try:
            # Stop pulse animation for the cell
            self.stop_pulse_animation(row, col)

        except Exception as e:
            logger.error(f"Failed to handle cell exit event: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان مدیریت خروج از سلول وجود ندارد: {str(e)}")
            sys.exit(1)

    def start_pulse_animation(self, row, col):
        """Start pulse animation for a cell"""
        try:
            item = self.schedule_table.item(row, col)

            if item:
                course_key = item.data(QtCore.Qt.UserRole)

                if course_key in self._pulse_timers:
                    return

                # Create a pulse animation
                pulse_timer = QtCore.QTimer(self)
                pulse_timer.setInterval(100)  # 100 ms
                pulse_timer.timeout.connect(lambda: self.pulse_cell(item))

                # Store the pulse timer
                self._pulse_timers[course_key] = pulse_timer

                # Start the pulse animation
                pulse_timer.start()

        except Exception as e:
            logger.error(f"Failed to start pulse animation: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان شروع انیمیشن پولس وجود ندارد: {str(e)}")
            sys.exit(1)

    def stop_pulse_animation(self, row, col):
        """Stop pulse animation for a cell"""
        try:
            item = self.schedule_table.item(row, col)

            if item:
                course_key = item.data(QtCore.Qt.UserRole)

                if course_key in self._pulse_timers:
                    pulse_timer = self._pulse_timers[course_key]

                    # Stop the pulse animation
                    pulse_timer.stop()

                    # Remove the pulse timer
                    del self._pulse_timers[course_key]

        except Exception as e:
            logger.error(f"Failed to stop pulse animation: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان متوقف کردن انیمیشن پولس وجود ندارد: {str(e)}")
            sys.exit(1)

    def pulse_cell(self, item):
        """Pulse a cell"""
        try:
            current_color = item.background().color()
            r, g, b, a = current_color.getRgb()

            # Increase or decrease alpha value for pulsing effect
            if a < 255:
                a += 10
            else:
                a -= 10

            # Set the new background color
            item.setBackground(QtGui.QColor(r, g, b, a))

        except Exception as e:
            logger.error(f"Failed to pulse cell: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان انیمیشن پولس وجود ندارد: {str(e)}")
            sys.exit(1)

    def show_detailed_info_window(self, course_key):
        """Show detailed info window for a course"""
        try:
            # Get the course details
            course = next((c for c in COURSES if c['key'] == course_key), None)

            if course:
                # Create and show the detailed info window
                self.detailed_info_window = DetailedInfoWindow(course, self)
                self.detailed_info_window.show()

        except Exception as e:
            logger.error(f"Failed to show detailed info window: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان نمایش پنجره اطلاعات دقیق وجود ندارد: {str(e)}")
            sys.exit(1)

    def show_exam_schedule_window(self):
        """Show exam schedule window"""
        try:
            # Create and show the exam schedule window
            self.exam_schedule_window = ExamScheduleWindow(self)
            self.exam_schedule_window.show()

        except Exception as e:
            logger.error(f"Failed to show exam schedule window: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان نمایش پنجره زمان‌بندی امتحانات وجود ندارد: {str(e)}")
            sys.exit(1)

    def update_status(self):
        """Update the status bar with the number of selected courses"""
        try:
            # Get the number of selected courses
            num_courses = len(self.courses)

            # Update the status bar
            self.status_bar.showMessage(f"تعداد دروس انتخاب شده: {num_courses}")

        except Exception as e:
            logger.error(f"Failed to update status: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان به‌روزرسانی وضعیت وجود ندارد: {str(e)}")
            sys.exit(1)

    def update_stats_panel(self):
        """Update the stats panel with statistics about the selected courses"""
        try:
            # Calculate statistics
            total_hours = sum(
                (to_minutes(course['times'][1]) - to_minutes(course['times'][0])) / 60
                for course in self.courses
            )
            total_days = calculate_days_needed_for_combo(self.courses)
            empty_time = calculate_empty_time_for_combo(self.courses)

            # Update the stats panel
            self.total_hours_label.setText(f"کل ساعات: {total_hours:.1f}")
            self.total_days_label.setText(f"روز‌های نیاز: {total_days}")
            self.empty_time_label.setText(f"زمان خالی: {empty_time} ساعت")

        except Exception as e:
            logger.error(f"Failed to update stats panel: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان به‌روزرسانی پانل آمار وجود ندارد: {str(e)}")
            sys.exit(1)

    def setup_responsive_layout(self):
        """Setup responsive layout"""
        try:
            # Create a stacked widget to hold the central widget
            self.stacked_widget = QtWidgets.QStackedWidget(self)

            # Set the stacked widget as the central widget
            self.setCentralWidget(self.stacked_widget)

            # Create a responsive layout
            self.responsive_layout = QtWidgets.QVBoxLayout()

            # Add the stacked widget to the responsive layout
            self.responsive_layout.addWidget(self.stacked_widget)

            # Set the responsive layout as the main layout
            self.setLayout(self.responsive_layout)

        except Exception as e:
            logger.error(f"Failed to setup responsive layout: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان تنظیم طرح بندی واکنش‌گرا وجود ندارد: {str(e)}")
            sys.exit(1)

    def eventFilter(self, obj, event):
        """Handle events"""
        try:
            if event.type() == QtCore.QEvent.Resize:
                self.on_resize(event)

            return super().eventFilter(obj, event)

        except Exception as e:
            logger.error(f"Failed to handle event: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان مدیریت رویداد وجود ندارد: {str(e)}")
            sys.exit(1)

    def on_resize(self, event):
        """Handle resize event"""
        try:
            # Get the new size
            new_size = event.size()

            # Resize the schedule table
            self.schedule_table.resizeColumnsToContents()

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to handle resize event: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان مدیریت تغییر اندازه وجود ندارد: {str(e)}")
            sys.exit(1)

    def create_search_clear_button(self):
        """Create search clear button and add it to the search box"""
        try:
            # Create a search clear button
            self.search_clear_button = QtWidgets.QToolButton(self.search_box)
            self.search_clear_button.setIcon(QtGui.QIcon(":/icons/clear_icon.png"))
            self.search_clear_button.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
            self.search_clear_button.setStyleSheet("border: none;")
            self.search_clear_button.clicked.connect(self.clear_search_box)

            # Add the search clear button to the search box
            self.search_box.setClearButtonEnabled(True)

        except Exception as e:
            logger.error(f"Failed to create search clear button: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان ایجاد دکمه پاک کردن جستجو وجود ندارد: {str(e)}")
            sys.exit(1)

    def clear_search_box(self):
        """Clear the search box"""
        try:
            self.search_box.clear()

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to clear search box: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان پاک کردن جستجو وجود ندارد: {str(e)}")
            sys.exit(1)

    def load_and_apply_styles(self):
        """Load and apply styles"""
        try:
            # Get the directory of this file
            ui_dir = os.path.dirname(os.path.abspath(__file__))
            style_file = os.path.join(ui_dir, 'styles.qss')

            # Load the style file
            with open(style_file, 'r') as f:
                style = f.read()

            # Apply the style
            self.setStyleSheet(style)

        except Exception as e:
            logger.error(f"Failed to load and apply styles: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان بارگذاری و اعمال استایل‌ها وجود ندارد: {str(e)}")
            sys.exit(1)

    def load_latest_backup(self):
        """Load latest backup on startup"""
        try:
            backup_dir = os.path.join(os.path.expanduser("~"), ".schedule_planner", "backups")

            if os.path.exists(backup_dir):
                # Get the list of backup files
                backup_files = sorted(
                    [f for f in os.listdir(backup_dir) if f.endswith('.bak')],
                    reverse=True
                )

                if backup_files:
                    # Load the latest backup
                    latest_backup = os.path.join(backup_dir, backup_files[0])
                    with open(latest_backup, 'r') as f:
                        backup_data = f.read()

                    # Load the backup data
                    self.user_data = load_user_data(backup_data)

                    # Update the status bar
                    self.update_status()

                    # Save user data
                    save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to load latest backup: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان بارگذاری آخرین پشتیبان وجود ندارد: {str(e)}")
            sys.exit(1)

    def connect_signals(self):
        """Connect signals"""
        try:
            # Connect signal for adding courses
            self.add_course_button.clicked.connect(self.add_course)

            # Connect signal for editing courses
            self.edit_course_button.clicked.connect(self.edit_course)

            # Connect signal for removing courses
            self.remove_course_button.clicked.connect(self.remove_course)

            # Connect signal for generating combinations
            self.generate_combinations_button.clicked.connect(self.generate_combinations)

            # Connect signal for generating greedy schedule
            self.generate_greedy_schedule_button.clicked.connect(self.generate_greedy_schedule)

            # Connect signal for generating alternative schedule
            self.generate_alternative_schedule_button.clicked.connect(self.generate_alternative_schedule)

            # Connect signal for showing detailed info window
            self.show_detailed_info_button.clicked.connect(self.show_detailed_info)

            # Connect signal for showing exam schedule window
            self.show_exam_schedule_button.clicked.connect(self.show_exam_schedule)

        except Exception as e:
            logger.error(f"Failed to connect signals: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان اتصال سیگنال‌ها وجود ندارد: {str(e)}")
            sys.exit(1)

    def add_course(self):
        """Add a new course"""
        try:
            # Create and show the add course dialog
            dialog = AddCourseDialog(self)
            if dialog.exec_():
                course = dialog.get_course_data()
                if course:
                    # Add the course to custom courses in user data
                    if 'custom_courses' not in self.user_data:
                        self.user_data['custom_courses'] = []
                    
                    # Check if course with same code already exists
                    existing_course = next((c for c in self.user_data['custom_courses'] if c['code'] == course['code']), None)
                    if existing_course:
                        # Update existing course
                        index = self.user_data['custom_courses'].index(existing_course)
                        self.user_data['custom_courses'][index] = course
                    else:
                        # Add new course
                        self.user_data['custom_courses'].append(course)
                    
                    # Also add to global COURSES dictionary with proper key
                    from app.core.config import COURSES
                    course_key = course['code']
                    course['key'] = course_key
                    course['major'] = 'دروس اضافه‌شده توسط کاربر'  # Ensure correct category
                    COURSES[course_key] = course
                    
                    # Save user data and user-added courses
                    from app.core.data_manager import save_user_data, save_user_added_courses
                    save_user_data(self.user_data)
                    save_user_added_courses()  # Save to dedicated file
                    
                    # Refresh UI to show the new course immediately
                    self.refresh_ui()
                    
                    # Show confirmation message in Persian with exact required text
                    QtWidgets.QMessageBox.information(
                        self, 
                        'عملیات موفق', 
                        'درس با موفقیت اضافه شد و در دسته «دروس اضافه‌شده توسط کاربر» نمایش داده شد.'
                    )

        except Exception as e:
            logger.error(f"Failed to add course: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان اضافه کردن درس وجود ندارد: {str(e)}")
            sys.exit(1)

    def edit_course(self):
        """Edit a selected course"""
        try:
            # Get the selected course
            selected_courses = self.course_list_widget.getSelectedCourses()

            if selected_courses:
                course_key = selected_courses[0]

                # Get the course details
                course = next((c for c in COURSES if c['key'] == course_key), None)

                if course:
                    # Create and show the edit course dialog
                    dialog = EditCourseDialog(course, self)
                    if dialog.exec_():
                        updated_course = dialog.get_course()

                        # Update the course in the list of selected courses
                        for i, c in enumerate(self.courses):
                            if c['key'] == course_key:
                                self.courses[i] = updated_course

                        # Update the status bar
                        self.update_status()

                        # Save user data
                        save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to edit course: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان ویرایش درس وجود ندارد: {str(e)}")
            sys.exit(1)

    def remove_course(self):
        """Remove a selected course"""
        try:
            # Get the selected course
            selected_courses = self.course_list_widget.getSelectedCourses()

            if selected_courses:
                course_key = selected_courses[0]

                # Remove the course from the list of selected courses
                self.courses = [c for c in self.courses if c['key'] != course_key]

                # Update the status bar
                self.update_status()

                # Save user data
                save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to remove course: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان حذف درس وجود ندارد: {str(e)}")
            sys.exit(1)

    def generate_combinations(self):
        """Generate all possible combinations of selected courses"""
        try:
            # Generate all possible combinations
            self.combinations = list(itertools.combinations(self.courses, len(self.courses)))

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to generate combinations: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان ایجاد تمام ترکیبات وجود ندارد: {str(e)}")
            sys.exit(1)

    def generate_greedy_schedule(self):
        """Generate a greedy schedule for selected courses"""
        try:
            # Generate a greedy schedule
            schedule = create_greedy_schedule(self.courses)

            # Load and display the schedule
            self.load_combo(schedule)

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to generate greedy schedule: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان ایجاد برنامه زمانی متعادل وجود ندارد: {str(e)}")
            sys.exit(1)

    def generate_alternative_schedule(self):
        """Generate an alternative schedule for selected courses"""
        try:
            # Generate an alternative schedule
            schedule = create_alternative_schedule(self.courses)

            # Load and display the schedule
            self.load_combo(schedule)

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to generate alternative schedule: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان ایجاد برنامه زمانی جایگزین وجود ندارد: {str(e)}")
            sys.exit(1)

    def show_detailed_info(self):
        """Show detailed info window for selected course"""
        try:
            # Get the selected course
            selected_courses = self.course_list_widget.getSelectedCourses()

            if selected_courses:
                course_key = selected_courses[0]

                # Show detailed info window
                self.show_detailed_info_window(course_key)

        except Exception as e:
            logger.error(f"Failed to show detailed info: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان نمایش اطلاعات دقیق وجود ندارد: {str(e)}")
            sys.exit(1)

    def show_exam_schedule(self):
        """Show exam schedule window"""
        try:
            # Show exam schedule window
            self.show_exam_schedule_window()

        except Exception as e:
            logger.error(f"Failed to show exam schedule: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان نمایش برنامه زمانی امتحانات وجود ندارد: {str(e)}")
            sys.exit(1)

    def create_menu_bar(self):
        """Create the application menu bar with data and usage history options"""
        try:
            # Use the menu bar from the UI file if available
            if hasattr(self, 'menubar'):
                menubar = self.menubar
            else:
                # Create menu bar if not available in UI
                menubar = self.menuBar()
            
            # Use the data menu from the UI file if available
            if hasattr(self, 'menu_data'):
                data_menu = self.menu_data
                
                # Connect the reset Golestan credentials action if it exists in the UI
                if hasattr(self, 'action_reset_golestan_credentials'):
                    # Disconnect any existing connections first to prevent duplicates
                    try:
                        self.action_reset_golestan_credentials.triggered.disconnect(self.reset_golestan_credentials)
                    except TypeError:
                        # No existing connection, that's fine
                        pass
                    self.action_reset_golestan_credentials.triggered.connect(self.reset_golestan_credentials)
                
                # Connect the fetch Golestan action if it exists in the UI
                if hasattr(self, 'action_fetch_golestan'):
                    # Disconnect any existing connections first to prevent duplicates
                    try:
                        self.action_fetch_golestan.triggered.disconnect(self.fetch_from_golestan)
                    except TypeError:
                        # No existing connection, that's fine
                        pass
                    self.action_fetch_golestan.triggered.connect(self.fetch_from_golestan)
                    
                # Connect the manual fetch action if it exists in the UI
                if hasattr(self, 'action_manual_fetch'):
                    # Disconnect any existing connections first to prevent duplicates
                    try:
                        self.action_manual_fetch.triggered.disconnect(self.manual_fetch_from_golestan)
                    except TypeError:
                        # No existing connection, that's fine
                        pass
                    self.action_manual_fetch.triggered.connect(self.manual_fetch_from_golestan)
            
            # Add Student Profile menu item
            if hasattr(self, 'action_student_profile'):
                print("DEBUG: Connecting action_student_profile")
                # Disconnect any existing connections first to prevent duplicates
                try:
                    self.action_student_profile.triggered.disconnect(self.show_student_profile)
                except TypeError:
                    # No existing connection, that's fine
                    pass
                self.action_student_profile.triggered.connect(self.show_student_profile)
                print("DEBUG: action_student_profile connected successfully")
            else:
                print("DEBUG: Creating new student profile action")
                # Add Student Profile menu item
                student_profile_action = QtWidgets.QAction('پروفایل دانشجو', self)
                student_profile_action.triggered.connect(self.show_student_profile)
                menubar.addAction(student_profile_action)
            
            # Create "Usage History" menu
            history_menu = menubar.addMenu('سوابق استفاده')
            
            # Add date to menu title
            current_date = datetime.datetime.now().strftime('%Y/%m/%d')
            history_menu.setTitle(f'سوابق استفاده ({current_date})')
            
            # Connect menu to populate with backup history when clicked
            history_menu.aboutToShow.connect(self.populate_backup_history_menu)
            
        except Exception as e:
            logger.error(f"Error creating menu bar: {e}")
            import traceback
            traceback.print_exc()

    def show_student_profile(self):
        """Show the student profile dialog."""
        try:
            # Create and show the student profile dialog
            dialog = StudentProfileDialog(self)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Error showing student profile: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                "خطا", 
                f"خطا در نمایش پروفایل دانشجو: {str(e)}"
            )

    def save_user_data(self):
        """Save user data"""
        try:
            # Get the directory of this file
            data_dir = os.path.join(os.path.expanduser("~"), ".schedule_planner")

            if not os.path.exists(data_dir):
                os.makedirs(data_dir)

            # Save the user data to a file
            data_file = os.path.join(data_dir, 'user_data.json')
            # Fix: Don't try to write the return value of save_user_data which is None
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to save user data: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان ذخیره داده‌های کاربر وجود ندارد: {str(e)}")
            sys.exit(1)

    def load_user_data(self):
        """Load user data"""
        try:
            # Get the directory of this file
            data_dir = os.path.join(os.path.expanduser("~"), ".schedule_planner")

            if not os.path.exists(data_dir):
                os.makedirs(data_dir)

            # Load the user data from a file
            data_file = os.path.join(data_dir, 'user_data.json')
            with open(data_file, 'r') as f:
                self.user_data = load_user_data(f.read())

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to load user data: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان بارگذاری داده‌های کاربر وجود ندارد: {str(e)}")
            sys.exit(1)

    def debug_stats_widget(self):
        """Debug stats widget"""
        try:
            # Get the directory of this file
            ui_dir = os.path.dirname(os.path.abspath(__file__))
            stats_widget_ui_file = os.path.join(ui_dir, 'stats_widget.ui')

            # Load UI from external file
            try:
                uic.loadUi(stats_widget_ui_file, self.stats_widget)
            except FileNotFoundError:
                QtWidgets.QMessageBox.critical(self, "خطا", f"فایل UI یافت نشد: {stats_widget_ui_file}")
                sys.exit(1)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در بارگذاری UI: {str(e)}")
                sys.exit(1)

            # Set layout direction
            self.stats_widget.setLayoutDirection(QtCore.Qt.RightToLeft)

            # Add the stats widget to the main window
            self.setCentralWidget(self.stats_widget)

            # Update the stats panel
            self.update_stats_panel()

        except Exception as e:
            logger.error(f"Failed to debug stats widget: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان اجرای تست بر روی ویجت آمار وجود ندارد: {str(e)}")
            sys.exit(1)

    def get_course_priority(self, course_key):
        """
        Get the priority of a course from the auto-select list.
        Lower numbers indicate higher priority.
        Returns 999 (low priority) if course is not in the auto-select list.
        """
        # Check if course exists in auto_select_list and get its priority
        if hasattr(self, 'auto_select_list'):
            for i in range(self.auto_select_list.count()):
                item = self.auto_select_list.item(i)
                if item and item.data(QtCore.Qt.UserRole) == course_key:
                    # Priority is stored in UserRole + 1 (1 = highest priority)
                    priority = item.data(QtCore.Qt.UserRole + 1)
                    if priority is not None:
                        return priority
        
        # Default priority if not found in auto-select list
        return 999

    def initialize_schedule_table(self):
        """Initialize the schedule table with days and time slots"""
        try:
            from app.core.config import DAYS, EXTENDED_TIME_SLOTS

            
            # Clear the table completely first
            self.schedule_table.clear()
            
            # Set table dimensions - 6 days with time rows (7:00 to 19:00)
            self.schedule_table.setRowCount(len(EXTENDED_TIME_SLOTS) - 1)  # -1 because we show time ranges
            self.schedule_table.setColumnCount(len(DAYS))
            
            # Set headers with correct order: [شنبه][یکشنبه][دوشنبه][سه‌شنبه][چهارشنبه][پنج‌شنبه]
            headers = DAYS
            self.schedule_table.setHorizontalHeaderLabels(headers)
            
            # Configure table appearance
            self.schedule_table.setAlternatingRowColors(True)
            self.schedule_table.verticalHeader().setVisible(True)
            
            # Generate Persian time labels for vertical header
            time_labels = []
            for i in range(len(EXTENDED_TIME_SLOTS) - 1):
                start_time = EXTENDED_TIME_SLOTS[i]
                end_time = EXTENDED_TIME_SLOTS[i + 1]
                
                # Convert to Persian numerals
                start_persian = self.convert_to_persian_numerals(start_time)
                end_persian = self.convert_to_persian_numerals(end_time)
                
                # Format as dual-line: start_time - end_time
                time_labels.append(f"{start_persian}\n{end_persian}")
            
            # Set vertical header labels
            self.schedule_table.setVerticalHeaderLabels(time_labels)
            
            # Configure vertical header appearance
            vertical_header = self.schedule_table.verticalHeader()
            vertical_header.setFixedWidth(80)
            vertical_header.setDefaultSectionSize(35)
            
            # Set row heights
            for row in range(len(EXTENDED_TIME_SLOTS) - 1):
                self.schedule_table.setRowHeight(row, 35)
            
            # All styling is now handled by styles.qss file
            pass
            
            logger.info(f"Schedule table initialized with {len(EXTENDED_TIME_SLOTS) - 1} rows and {len(DAYS)} columns")
            logger.info(f"Headers: {headers}")
            
        except Exception as e:
            logger.error(f"Failed to initialize schedule table: {e}")
            import traceback
            traceback.print_exc()

    def convert_to_persian_numerals(self, time_str):
        """Convert English numerals in time string to Persian numerals"""
        english_to_persian = {
            '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
            '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'
        }
        
        result = ""
        for char in time_str:
            result += english_to_persian.get(char, char)
        return result

    def setup_responsive_layout(self):
        """Setup responsive layout and sizing with reduced margins and spacing"""
        try:
            # Set main splitter ratios
            if hasattr(self, 'main_splitter'):
                # Reduce handle width for splitter
                self.main_splitter.setHandleWidth(4)
                
                # Set initial sizes based on window width
                window_width = self.width()
                left_width = int(window_width * 0.25)   # 25%
                center_width = int(window_width * 0.50)  # 50%
                right_width = int(window_width * 0.25)   # 25%
                
                self.main_splitter.setSizes([left_width, center_width, right_width])
                
                # Set stretch factors
                self.main_splitter.setStretchFactor(0, 0)  # Left panel - fixed
                self.main_splitter.setStretchFactor(1, 1)  # Center panel - expandable
                self.main_splitter.setStretchFactor(2, 0)  # Right panel - fixed
            
            # Configure schedule table for responsive behavior
            self.setup_table_responsive()
            
            # Reduce margins and spacing in all layouts
            self.reduce_layout_margins()
            
            # Set minimum height for course list
            if hasattr(self, 'course_list'):
                self.course_list.setMinimumHeight(200)
            
            logger.info("Responsive layout configured")
            
        except Exception as e:
            logger.error(f"Failed to setup responsive layout: {e}")

    def reduce_layout_margins(self):
        """Reduce margins and spacing in all layouts to minimize gaps"""
        try:
            # Reduce margins in main central widget layout
            if hasattr(self, 'centralwidget') and self.centralwidget.layout():
                layout = self.centralwidget.layout()
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(4)  # Set to 4px as required
            
            # Reduce margins in left panel layout
            if hasattr(self, 'left_panel') and self.left_panel.layout():
                layout = self.left_panel.layout()
                layout.setContentsMargins(4, 4, 4, 4)  # Set to 4px margins
                layout.setSpacing(4)  # Set to 4px spacing
                
            # Reduce margins in center panel layout
            if hasattr(self, 'center_panel') and self.center_panel.layout():
                layout = self.center_panel.layout()
                layout.setContentsMargins(0, 0, 0, 0)  # Minimal margins
                layout.setSpacing(4)  # Set to 4px spacing
                
            # Reduce margins in right panel layout
            if hasattr(self, 'right_panel') and self.right_panel.layout():
                layout = self.right_panel.layout()
                layout.setContentsMargins(4, 4, 4, 4)  # Set to 4px margins
                layout.setSpacing(4)  # Set to 4px spacing
                
            # Reduce margins in all group boxes
            for group_box in self.findChildren(QtWidgets.QGroupBox):
                if group_box.layout():
                    layout = group_box.layout()
                    layout.setContentsMargins(4, 6, 4, 4)  # Set to 4px margins
                    layout.setSpacing(4)  # Set to 4px spacing
                    
            # Reduce splitter handle width
            if hasattr(self, 'main_splitter'):
                self.main_splitter.setHandleWidth(4)  # Set to 4px handle width
                    
            logger.info("Layout margins and spacing reduced")
            
        except Exception as e:
            logger.error(f"Failed to reduce layout margins: {e}")

    def setup_table_responsive(self):
        """Configure table for responsive behavior"""
        try:
            if not hasattr(self, 'schedule_table'):
                return
                
            # Set column resize modes - all columns stretch to fill
            header = self.schedule_table.horizontalHeader()
            
            # All day columns - stretch to fill
            for col in range(self.schedule_table.columnCount()):
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.Stretch)
            
            # Set minimum column widths
            for col in range(self.schedule_table.columnCount()):
                self.schedule_table.setColumnWidth(col, 120)  # Minimum width
                
            # Configure vertical header
            vertical_header = self.schedule_table.verticalHeader()
            vertical_header.setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
            vertical_header.setFixedWidth(70)
                
            logger.info("Table responsive mode configured")
            
        except Exception as e:
            logger.error(f"Failed to setup table responsive: {e}")

    def resizeEvent(self, event):
        """Handle window resize events"""
        try:
            super().resizeEvent(event)
            
            # Recalculate splitter sizes on resize
            if hasattr(self, 'main_splitter'):
                window_width = self.width()
                left_width = max(280, int(window_width * 0.25))   # Min 280px
                center_width = max(600, int(window_width * 0.50)) # Min 600px
                right_width = max(250, int(window_width * 0.25))  # Min 250px
                
                self.main_splitter.setSizes([left_width, center_width, right_width])
            
            # Reapply layout adjustments on resize
            self.reduce_layout_margins()
            
        except Exception as e:
            logger.error(f"Error in resizeEvent: {e}")

    def update_status(self):
        """Update status bar with accurate Persian date and time"""
        try:
            import jdatetime
            
            # تنظیم locale برای فارسی
            jdatetime.set_locale(jdatetime.FA_LOCALE)
            
            # گرفتن تاریخ و زمان فعلی شمسی
            now = jdatetime.datetime.now()
            
            # نام‌های روزهای هفته به فارسی
            # Fix: jdatetime weekday uses Saturday=0, but we need to map correctly
            persian_weekdays = {
                0: 'شنبه',    # Saturday
                1: 'یکشنبه',  # Sunday
                2: 'دوشنبه',  # Monday
                3: 'سه‌شنبه', # Tuesday
                4: 'چهارشنبه',# Wednesday
                5: 'پنج‌شنبه',# Thursday
                6: 'جمعه'     # Friday
            }
            
            # نام‌های ماه‌های شمسی
            persian_months = {
                1: 'فروردین', 2: 'اردیبهشت', 3: 'خرداد',
                4: 'تیر', 5: 'مرداد', 6: 'شهریور',
                7: 'مهر', 8: 'آبان', 9: 'آذر',
                10: 'دی', 11: 'بهمن', 12: 'اسفند'
            }
            
            # گرفتن اجزای تاریخ
            persian_year = now.year
            persian_month = now.month
            persian_day = now.day
            weekday = now.weekday()
            
            # فرمت زمان
            time_str = now.strftime('%H:%M')
            
            # نام روز و ماه
            weekday_name = persian_weekdays.get(weekday, '')
            month_name = persian_months.get(persian_month, '')
            
            # ساخت متن تاریخ شمسی کامل
            persian_date_str = f'{persian_day} {month_name} {persian_year}'
            
            # متن کامل status bar
            status_text = f'🗓️ {weekday_name} - {persian_date_str} - ⏰ {time_str}'
            
            # نمایش در status bar
            self.status_bar.showMessage(status_text)
            
            # تنظیم فونت زیبا
            status_font = QtGui.QFont('IRANSans UI', 11, QtGui.QFont.Bold)
            self.status_bar.setFont(status_font)
                
        except ImportError:
            # در صورت عدم وجود jdatetime، fallback به روش قبلی
            self.update_status_fallback()
        except Exception as e:
            print(f"خطا در به‌روزرسانی وضعیت: {e}")
            self.update_status_fallback()

    def debug_stats_widget(self):
        """Debug method to find the correct stats widget name"""
        # Only run in debug mode
        if not os.environ.get('DEBUG'):
            return None
            
        logger.debug("=== Debug Stats Widget ===")
        
        # پیدا کردن تمام label های موجود
        labels = self.findChildren(QtWidgets.QLabel)
        for label in labels:
            if hasattr(label, 'objectName'):
                name = label.objectName()
                text = label.text()[:50] + "..." if len(label.text()) > 50 else label.text()
                logger.debug(f"Label: {name} -> {text}")
        
        # تست مستقیم
        widgets_to_test = [
            'stats_label',
            'statsLabel', 
            'statistics_label',
            'stat_label',
            'program_stats_label'
        ]
        
        for widget_name in widgets_to_test:
            widget = getattr(self, widget_name, None)
            if widget:
                logger.debug(f"✅ Found widget: {widget_name}")
                return widget
            else:
                logger.debug(f"❌ Widget not found: {widget_name}")
        
        return None

    def update_stats_panel(self):
        """Update the stats panel with current schedule information - FORCED VERSION"""
        # Only show debug log if in debug mode
        if os.environ.get('DEBUG'):
            logger.debug("🔄 update_stats_panel called")
        
        try:
            # پیدا کردن widget صحیح
            stats_widget = None
            widget_candidates = [
                getattr(self, 'stats_label', None),
                getattr(self, 'statsLabel', None),
                getattr(self, 'statistics_label', None),
                self.findChild(QtWidgets.QLabel, 'stats_label'),
                self.findChild(QtWidgets.QLabel, 'statsLabel'),
            ]
            
            for widget in widget_candidates:
                if widget:
                    stats_widget = widget
                    if os.environ.get('DEBUG'):
                        logger.debug(f"✅ Found stats widget: {type(widget)}")
                    break
            
            if not stats_widget:
                if os.environ.get('DEBUG'):
                    logger.debug("❌ No stats widget found!")
                # جستجو در کل UI
                all_labels = self.findChildren(QtWidgets.QLabel)
                for label in all_labels:
                    if 'آمار' in label.text() or 'stats' in label.objectName().lower():
                        stats_widget = label
                        if os.environ.get('DEBUG'):
                            logger.debug(f"🔍 Found by search: {label.objectName()}")
                        break
            
            if not stats_widget:
                if os.environ.get('DEBUG'):
                    logger.debug("❌ Still no stats widget found!")
                return
                
            # محاسبه آمار
            if hasattr(self, 'placed') and self.placed:
                # Collect currently placed course keys
                # Handle both single and dual courses correctly
                keys = []
                for info in self.placed.values():
                    if info.get('type') == 'dual':
                        # For dual courses, add both courses
                        keys.extend(info.get('courses', []))
                    else:
                        # For single courses, add the course key
                        keys.append(info.get('course'))

                # Remove duplicates while preserving order
                seen = set()
                unique_keys = []
                for key in keys:
                    if key not in seen:
                        seen.add(key)
                        unique_keys.append(key)
                keys = unique_keys
                
                # Update user data with current schedule
                self.user_data['current_schedule'] = keys
                
                if os.environ.get('DEBUG'):
                    logger.debug(f"📊 Found {len(keys)} courses")
                
                # محاسبه واحدها
                total_units = 0
                total_sessions = len(self.placed)
                days_used = set()
                
                for course_key in keys:
                    course = COURSES.get(course_key, {})
                    units = course.get('credits', 0)
                    total_units += units
                    if os.environ.get('DEBUG'):
                        logger.debug(f"  - {course.get('name', course_key)}: {units} واحد")
                    
                    # گرفتن روزها
                    for session in course.get('schedule', []):
                        days_used.add(session.get('day', ''))
                
                # متن آمار
                stats_text = f"""📊 آمار برنامه فعلی

📚 تعداد دروس: {len(keys)}
🎯 واحدها: {total_units}
⏰ جلسات: {total_sessions}
📅 روزها: {len(days_used)}
✅ وضعیت: فعال"""

                if os.environ.get('DEBUG'):
                    logger.debug(f"📝 Setting stats text: {stats_text[:100]}...")
                stats_widget.setText(stats_text)
                
            else:
                if os.environ.get('DEBUG'):
                    logger.debug("📭 No courses placed")
                stats_widget.setText("""📊 آمار برنامه

هنوز هیچ درسی انتخاب نشده است

💡 روی دروس کلیک کنید""")
                
            # فورس refresh
            stats_widget.update()
            stats_widget.repaint()
            
        except Exception as e:
            logger.error(f"❌ Error in update_stats_panel: {e}")
            if os.environ.get('DEBUG'):
                import traceback
                traceback.print_exc()

    def updatestatspanel(self):
        """Alias for update_stats_panel"""
        self.update_stats_panel()

    def update_status_fallback(self):
        """Fallback method if jdatetime is not available"""
        from datetime import datetime
        now = datetime.now()
        
        # روش ساده‌تر بدون تبدیل دقیق تقویم
        persian_months = [
            'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
            'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
        ]
        
        # Fix: Convert Python weekday (Monday=0) to Persian (Saturday=0)
        python_weekday = now.weekday()
        persian_weekday_index = (python_weekday + 2) % 7
        
        weekday_names = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه']
        weekday = weekday_names[persian_weekday_index]
        
        # تقریبی - نه دقیق
        month_name = persian_months[now.month - 1] if 1 <= now.month <= 12 else 'نامشخص'
        
        time_str = now.strftime('%H:%M:%S')
        date_str = f'{now.day} {month_name} {now.year}'
        
        status_text = f'📅 {weekday} - {date_str} - ⏰ {time_str} (تقریبی)'
        
        self.status_bar.showMessage(status_text)

    def on_course_clicked(self, item):
        """Handle course selection from the list with enhanced debugging"""
        # Make sure QtWidgets is available in this scope
        
        try:
            if item is None:
                logger.warning("on_course_clicked called with None item")
                return
                
            key = item.data(QtCore.Qt.UserRole)
            logger.debug(f"Course clicked - item: {item}, key: {key}")
            
            # Check if this is a placeholder item (no key data)
            if key is None:
                # This is likely a placeholder message item, ignore the click
                logger.debug("Clicked on placeholder item, ignoring")
                return
            
            if key:
                logger.info(f"User clicked on course with key: {key}")
                self.clear_preview()
                # Enqueue course addition instead of calling directly to prevent race conditions
                self.course_addition_queue.append((key, True))  # True for ask_on_conflict
                if self.course_addition_timer.isActive():
                    self.course_addition_timer.stop()
                self.course_addition_timer.start(50)  # 50ms debounce
                
                # Update course info panel
                if hasattr(self, 'course_info_label'):
                    course = COURSES.get(key, {})
                    info_text = f"""نام درس: {course.get('name', 'نامشخص')}
کد درس: {course.get('code', 'نامشخص')}
استاد: {course.get('instructor', 'نامشخص')}
تعداد واحد: {course.get('credits', 'نامشخص')}
محل برگزاری: {course.get('location', 'نامشخص')}"""
                    self.course_info_label.setText(info_text)
                
                # Update stats panel
                print("🔄 Calling update_stats_panel from on_course_clicked")
                self.update_stats_panel()
            else:
                logger.warning(f"Course item clicked but no key found in UserRole data")
                QtWidgets.QMessageBox.warning(
                    self, 'خطا', 
                    'خطا در تشخیص درس انتخابی. لطفا دوباره تلاش کنید.'
                )
        except Exception as e:
            logger.error(f"Error in on_course_clicked: {e}")
            QtWidgets.QMessageBox.critical(
                self, 'خطای سیستمی', 
                f'خطای غیرمنتظره در هنگام انتخاب درس:\n{str(e)}'
            )
    
    def create_combination_card(self, index, combo):
        """Create a card widget for a schedule combination"""
        card = QtWidgets.QFrame()
        card.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        card.setLineWidth(2)
        card.setObjectName("combination_card")
        card.setStyleSheet("QFrame#combination_card { background-color: #ffffff; border: 2px solid #3498db; border-radius: 15px; margin: 12px; padding: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); } QFrame#combination_card:hover { border: 2px solid #2980b9; background-color: #f8f9fa; }")
        
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
        days_badge.setStyleSheet("background-color: #3498db; color: white; border-radius: 12px; padding: 4px 12px; font-size: 12px; font-weight: bold;")
        
        empty_badge = QtWidgets.QLabel(f'خالی: {combo["empty"]:.1f}h')
        empty_badge.setStyleSheet("background-color: #2ecc71; color: white; border-radius: 12px; padding: 4px 12px; font-size: 12px; font-weight: bold;")
        
        courses_badge = QtWidgets.QLabel(f'دروس: {len(combo["courses"])}')
        courses_badge.setStyleSheet("background-color: #9b59b6; color: white; border-radius: 12px; padding: 4px 12px; font-size: 12px; font-weight: bold;")
        
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
        course_list.setObjectName("combination_course_list")

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
        self.update_stats_panel()
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
            self.schedule_table.removeCellWidget(srow, scol)
            for r in range(srow, srow + span):
                self.schedule_table.setItem(r, scol, QtWidgets.QTableWidgetItem(''))
            self.schedule_table.setSpan(srow, scol, 1, 1)
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
            self.schedule_table.removeCellWidget(srow, scol)
            for r in range(srow, srow + span):
                self.schedule_table.setItem(r, scol, QtWidgets.QTableWidgetItem(''))
            self.schedule_table.setSpan(srow, scol, 1, 1)
        self.placed.clear()
        
        # Clear any preview cells
        self.clear_preview()
        
        # Update status
        self.update_status()
        self.update_stats_panel()
        
        # Course info panel is updated in on_course_clicked
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()
        
        
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
                        self.last_hover_key = key
                        self.clear_preview()
                        self.preview_course(key)
                else:
                    # Clear preview when not hovering over an item
                    if hasattr(self, 'last_hover_key') and self.last_hover_key:
                        self.last_hover_key = None
                        self.clear_preview()
            elif event.type() == QtCore.QEvent.Leave:
                # Clear preview when mouse leaves the course list entirely
                if hasattr(self, 'last_hover_key') and self.last_hover_key:
                    self.last_hover_key = None
                    self.clear_preview()
        
        return super().eventFilter(obj, event)
    
    def calculate_empty_time(self, course_keys):
        """Calculate the empty time (gaps) for a combination of courses"""
        return calculate_empty_time_for_combo(course_keys)

    # ---------------------- Missing Methods ----------------------
    
    def preview_course(self, course_key):
        """Show enhanced preview of course schedule with improved styling"""
        # Safety check for schedule_table
        if not hasattr(self, 'schedule_table'):
            logger.error("schedule_table widget not found")
            return
            
        course = COURSES.get(course_key)
        if not course:
            return
            
        placements = []
        for sess in course['schedule']:
            if sess['day'] not in DAYS:
                continue
            col = DAYS.index(sess['day'])
            try:
                srow = EXTENDED_TIME_SLOTS.index(sess['start'])
                erow = EXTENDED_TIME_SLOTS.index(sess['end'])
            except ValueError:
                QtWidgets.QMessageBox.warning(self, 'خطا', f'زمان نامعتبر برای درس {course["name"]}: {sess["start"]}-{sess["end"]}')
                continue
            span = max(1, erow - srow)
            placements.append((srow, col, span, sess))
            
        for srow, col, span, sess in placements:
            if self.can_place_preview(srow, col, span):
                # Create preview with improved layout matching main course cells
                preview_widget = QtWidgets.QWidget()
                preview_layout = QtWidgets.QVBoxLayout(preview_widget)
                preview_layout.setContentsMargins(6, 4, 6, 4)
                preview_layout.setSpacing(2)
                
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
                
                # Apply additional styling to make preview more visible
                preview_widget.setObjectName("preview_widget")
                self.schedule_table.setCellWidget(srow, col, preview_widget)

                
                self.schedule_table.setCellWidget(srow, col, preview_widget)
                if span > 1:
                    self.schedule_table.setSpan(srow, col, span, 1)
                self.preview_cells.append((srow, col, span))

    def can_place_preview(self, srow, col, span):
        for r in range(srow, srow + span):
            if self.schedule_table.cellWidget(r, col) is not None:
                return False
            it = self.schedule_table.item(r, col)
            if it and it.text().strip() != '':
                return False
        return True

    def add_course_to_table(self, course_key, ask_on_conflict=True):
        """
        Add course to table with debouncing to prevent race conditions.
        This fixes the rapid click Morbi failure issue.
        """
        # Add to queue and debounce
        self.course_addition_queue.append((course_key, ask_on_conflict))
        if self.course_addition_timer.isActive():
            self.course_addition_timer.stop()
        self.course_addition_timer.start(50)  # 50ms debounce

    def _process_course_addition_queue(self):
        """
        Process queued course additions with proper synchronization.
        This version processes courses one by one to properly handle dual course creation.
        """
        logger.info("overlay_processing_start: Starting to process course addition queue")
        locker = QMutexLocker(self.course_addition_mutex)
        try:
            # Process courses one by one to handle dual course creation correctly
            while self.course_addition_queue:
                course_key, ask_on_conflict = self.course_addition_queue.popleft()
                logger.info(f"overlay_processing_item: Processing course {course_key}")
                # Process course addition with dual operation locking
                dual_locker = QMutexLocker(self.dual_operation_mutex)
                try:
                    self._add_course_internal(course_key, ask_on_conflict)
                finally:
                    del dual_locker
                
                # Process events to ensure UI updates
                QtWidgets.QApplication.processEvents()
            
            self.save_user_data()
            logger.info("overlay_processing_complete: Course addition queue processing complete")
        finally:
            del locker

    def _add_course_internal(self, course_key, ask_on_conflict=True):
        """
        Internal method for adding course with proper dual course handling.
        This method should only be called from _process_course_addition_queue.
        """
        logger.info(f"overlay_add_internal: Adding course {course_key} internally")
        # Safety check for schedule_table
        if not hasattr(self, 'schedule_table'):
            logger.error("schedule_table widget not found")
            QtWidgets.QMessageBox.critical(self, 'خطا', 'جدول برنامه یافت نشد.')
            return
            
        course = COURSES.get(course_key)
        if not course:
            QtWidgets.QMessageBox.warning(self, 'خطا', f'درس با کلید {course_key} یافت نشد.')
            return
        
        # Import the dual course widget creator and parity compatibility checker
        from .enhanced_main_window import create_dual_course_widget, check_odd_even_compatibility
        
        placements = []
        for sess in course['schedule']:
            if sess['day'] not in DAYS:
                continue
            col = DAYS.index(sess['day'])
            try:
                srow = EXTENDED_TIME_SLOTS.index(sess['start'])
                erow = EXTENDED_TIME_SLOTS.index(sess['end'])
            except ValueError:
                QtWidgets.QMessageBox.warning(self, 'خطا', f'زمان نامعتبر برای درس {course["name"]}: {sess["start"]}-{sess["end"]}')
                continue
            span = max(1, erow - srow)
            placements.append((srow, col, span, sess))

        # Check for conflicts with proper weekly_type (parity) handling
        conflicts = []
        compatible_slots = {}  # Track odd/even compatible slots
        
        for (srow, col, span, sess) in placements:
            for (prow, pcol), info in list(self.placed.items()):
                if pcol != col:
                    continue
                # Skip conflict check with the same course
                if info.get('course') == course_key:
                    continue
                prow_start = prow
                prow_span = info['rows']
                if not (srow + span <= prow_start or prow_start + prow_span <= srow):
                    # Time overlap detected - check if they can coexist based on parity
                    existing_course = COURSES.get(info.get('course'), {})
                    
                    # Find the conflicting session
                    for existing_sess in existing_course.get('schedule', []):
                        if existing_sess['day'] == sess['day']:
                            # Check start/end time match
                            existing_start = EXTENDED_TIME_SLOTS.index(existing_sess['start'])
                            existing_end = EXTENDED_TIME_SLOTS.index(existing_sess['end'])
                            
                            if existing_start == srow and existing_end == srow + span:
                                # Same time slot - check if they can coexist based on weekly_type (parity)
                                # Courses can coexist ONLY if one is "even" and the other is "odd"
                                # All other combinations result in conflict:
                                # - fixed vs fixed → conflict
                                # - even vs even → conflict
                                # - odd vs odd → conflict
                                # - fixed vs even → conflict
                                # - fixed vs odd → conflict
                                # - even vs odd → allowed
                                # - odd vs even → allowed
                                
                                sess_parity = sess.get('parity', '')
                                existing_parity = existing_sess.get('parity', '')
                                
                                # Check if they are compatible (one even, one odd)
                                is_compatible = (
                                    (sess_parity == 'ز' and existing_parity == 'ف') or  # زوج and فرد
                                    (sess_parity == 'ف' and existing_parity == 'ز')     # فرد and زوج
                                )
                                
                                # If compatible, store for dual placement
                                if is_compatible:
                                    compatible_slots[(srow, col)] = {
                                        'existing': info,
                                        'existing_session': existing_sess,
                                        'new_session': sess,
                                        'span': span
                                    }
                                else:
                                    # If not compatible, it's a real conflict
                                    conflicts.append(((srow, col), (prow_start, pcol), info.get('course'), 
                                                    existing_course.get('name', 'نامشخص')))
                                break
        
        # Add conflict indicator to course info if there are conflicts
        has_conflicts = len(conflicts) > 0

        # Handle conflicts with priority-based resolution
        if conflicts and ask_on_conflict:
            # Get priority of current course (if in auto-select list)
            current_priority = self.get_course_priority(course_key)
            
            # Check if any conflicting courses have higher priority
            higher_priority_conflicts = []
            conflict_details = []
            for conf in conflicts:
                (_, _), (_, _), conflict_course_key, conflict_name = conf
                conflict_priority = self.get_course_priority(conflict_course_key)
                
                # If conflicting course has higher priority (lower number), it should stay
                if conflict_priority < current_priority:
                    higher_priority_conflicts.append((conflict_course_key, conflict_name, conflict_priority))
                conflict_details.append(conflict_name)
            
            # If there are higher priority conflicts, show warning and don't add course
            if higher_priority_conflicts:
                conflict_list = '\n'.join([f"• {name}" for name in conflict_details])
                warning_msg = QtWidgets.QMessageBox()
                warning_msg.setIcon(QtWidgets.QMessageBox.Warning)
                warning_msg.setWindowTitle('تداخل دروس')
                warning_msg.setText(f'درس "{course["name"]}" به دلیل تداخل با دروس با اولویت بالاتر اضافه نشد:')
                
                # Add details about higher priority conflicts
                priority_details = '\n'.join([f"• {name} (اولویت: {priority})" for _, name, priority in higher_priority_conflicts])
                warning_msg.setDetailedText(f'دروس با اولویت بالاتر:\n{priority_details}')
                warning_msg.exec_()
                return
            
            # If no higher priority conflicts, proceed with normal conflict resolution
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

        # Use the imported COLOR_MAP instead of defining locally
        color_idx = len(self.placed) % len(COLOR_MAP)
        # رنگ‌ها - Updated with harmonious color palette
        bg = COLOR_MAP[color_idx % len(COLOR_MAP)]
        
        # Place the course sessions
        # Create a unique slot key for overlay tracking
        slot_keys = []
        for (srow, col, span, sess) in placements:
            slot_key = f"{sess['day']}_{sess['start']}_{sess['end']}"
            slot_keys.append((slot_key, srow, col, span, sess))
        
        # Process all placements with proper dual course handling
        for (slot_key, srow, col, span, sess) in slot_keys:
            # Check if this slot has a compatible odd/even pairing
            if (srow, col) in compatible_slots:
                # Create dual course widget
                compat_info = compatible_slots[(srow, col)]
                existing_info = compat_info['existing']
                existing_sess = compat_info['existing_session']
                new_sess = sess
                
                # Prepare data for both courses
                if new_sess.get('parity') == 'ف':  # If new course is odd
                    odd_data = {
                        'course': course,
                        'course_key': course_key,
                        'session': new_sess,
                        'color': bg
                    }
                    even_data = {
                        'course': COURSES[existing_info.get('course')],
                        'course_key': existing_info.get('course'),
                        'session': existing_sess,
                        'color': existing_info.get('color', COLOR_MAP[0])
                    }
                else:  # If new course is even or fixed
                    odd_data = {
                        'course': COURSES[existing_info.get('course')],
                        'course_key': existing_info.get('course'),
                        'session': existing_sess,
                        'color': existing_info.get('color', COLOR_MAP[0])
                    }
                    even_data = {
                        'course': course,
                        'course_key': course_key,
                        'session': new_sess,
                        'color': bg
                    }
                
                # Check if we already have a dual widget for this slot
                existing_dual_widget = None
                if (srow, col) in self.placed and self.placed[(srow, col)].get('type') == 'dual':
                    existing_dual_widget = self.placed[(srow, col)].get('widget')
                
                if existing_dual_widget:
                    # Update existing dual widget instead of creating a new one
                    logger.info(f"overlay_updating_dual: Updating existing dual widget for slot {slot_key}")
                    # This would require modifying the dual widget to update its data
                    # For now, we'll remove the old widget and create a new one
                    self.schedule_table.removeCellWidget(srow, col)
                    
                    # Remove the existing single widget entry from placed
                    # Find and remove the existing entry for this slot
                    logger.info(f"DEBUG: Looking for existing entry at ({srow}, {col}) for update")
                    logger.info(f"DEBUG: Current placed items: {list(self.placed.keys())}")
                    existing_start_tuple = None
                    for start_tuple, info in list(self.placed.items()):
                        logger.info(f"DEBUG: Checking placed item {start_tuple} for update")
                        if start_tuple == (srow, col):
                            existing_start_tuple = start_tuple
                            logger.info(f"DEBUG: Found existing entry to remove for update: {start_tuple}")
                            break
                    
                    if existing_start_tuple:
                        del self.placed[existing_start_tuple]
                        logger.info(f"DEBUG: Removed existing entry for update: {existing_start_tuple}")
                    else:
                        logger.info(f"DEBUG: No existing entry found to remove at ({srow}, {col}) for update")
                    
                    dual_widget = create_dual_course_widget(odd_data, even_data, self)
                    self.schedule_table.setCellWidget(srow, col, dual_widget)
                    
                    # Update overlay tracking
                    if slot_key not in self.overlays:
                        self.overlays[slot_key] = {}
                    self.overlays[slot_key]['dual'] = dual_widget
                    
                    # Update placed info to track both courses
                    self.placed[(srow, col)] = {
                        'courses': [odd_data['course_key'], even_data['course_key']],
                        'rows': span,
                        'widget': dual_widget,
                        'type': 'dual'
                    }
                else:
                    # Create new dual widget
                    logger.info(f"overlay_creating_dual: Creating new dual widget for slot {slot_key}")
                    # Remove old widget
                    self.schedule_table.removeCellWidget(srow, col)
                    
                    # Remove the existing single widget entry from placed
                    # Find and remove the existing entry for this slot
                    logger.info(f"DEBUG: Looking for existing entry at ({srow}, {col})")
                    logger.info(f"DEBUG: Current placed items: {list(self.placed.keys())}")
                    existing_start_tuple = None
                    for start_tuple, info in list(self.placed.items()):
                        logger.info(f"DEBUG: Checking placed item {start_tuple}")
                        if start_tuple == (srow, col):
                            existing_start_tuple = start_tuple
                            logger.info(f"DEBUG: Found existing entry to remove: {start_tuple}")
                            break
                    
                    if existing_start_tuple:
                        del self.placed[existing_start_tuple]
                        logger.info(f"DEBUG: Removed existing entry: {existing_start_tuple}")
                    else:
                        logger.info(f"DEBUG: No existing entry found to remove at ({srow}, {col})")
                    
                    # Create and place dual widget
                    dual_widget = create_dual_course_widget(odd_data, even_data, self)
                    self.schedule_table.setCellWidget(srow, col, dual_widget)
                    
                    # Update overlay tracking
                    if slot_key not in self.overlays:
                        self.overlays[slot_key] = {}
                    self.overlays[slot_key]['dual'] = dual_widget
                    
                    # Update placed info to track both courses
                    self.placed[(srow, col)] = {
                        'courses': [odd_data['course_key'], even_data['course_key']],
                        'rows': span,
                        'widget': dual_widget,
                        'type': 'dual'
                    }
            else:
                # Normal single course placement
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
                cell_layout.setContentsMargins(2, 1, 2, 1)
                cell_layout.setSpacing(0)
                
                # Top row with X button and conflict indicator
                top_row = QtWidgets.QHBoxLayout()
                top_row.setContentsMargins(0, 0, 0, 0)
                
                # No conflict indicator in schedule table (only in course list)
                # Add a spacer to maintain consistent layout
                top_row.addStretch()
                
                # X button for course removal - properly styled in red
                x_button = QtWidgets.QPushButton('✕')
                x_button.setFixedSize(18, 18)
                x_button.setObjectName('close-btn')
                x_button.clicked.connect(lambda checked, ck=course_key: self.remove_course_silently(ck))
                
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
                
                # Add labels to layout
                cell_layout.addWidget(course_name_label)
                cell_layout.addWidget(professor_label)
                cell_layout.addWidget(code_label)
                
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
                
                # Enable hover effects with access violation protection
                def enter_event(event, widget=cell_widget):
                    try:
                        if hasattr(widget, 'course_key') and widget.course_key:
                            self.highlight_course_sessions(widget.course_key)
                    except Exception as e:
                        logger.warning(f"Hover enter event error: {e}")
                
                def leave_event(event, widget=cell_widget):
                    try:
                        self.clear_course_highlights()
                    except Exception as e:
                        logger.warning(f"Hover leave event error: {e}")
                
                def mouse_press_event(event, widget=cell_widget):
                    try:
                        if event.button() == QtCore.Qt.LeftButton:
                            if hasattr(widget, 'course_key') and widget.course_key:
                                self.show_course_details(widget.course_key)
                    except Exception as e:
                        logger.warning(f"Mouse press event error: {e}")
                
                cell_widget.enterEvent = enter_event
                cell_widget.leaveEvent = leave_event
                cell_widget.mousePressEvent = mouse_press_event
                
                self.schedule_table.setCellWidget(srow, col, cell_widget)
                if span > 1:
                    self.schedule_table.setSpan(srow, col, span, 1)
                
                # Update overlay tracking for single course
                if slot_key not in self.overlays:
                    self.overlays[slot_key] = {}
                self.overlays[slot_key]['single'] = cell_widget
                
                self.placed[(srow, col)] = {
                    'course': course_key, 
                    'rows': span, 
                    'widget': cell_widget
                }
            
        # Update status after adding course
        self.update_status()
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()
        
        
        # Update stats panel
        print("🔄 Calling update_stats_panel from add_course_to_table")
        self.update_stats_panel()  # فورس کال
        QtCore.QCoreApplication.processEvents()  # فورس UI update

    def remove_placed_by_start(self, start_tuple):
         top_row.addStretch()

         # X button for course removal - properly styled in red
         x_button = QtWidgets.QPushButton('✕')
         x_button.setFixedSize(18, 18)
         x_button.setObjectName('close-btn')
         x_button.clicked.connect(lambda checked, ck=course_key: self.remove_course_silently(ck))

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

         # Add labels to layout
         cell_layout.addWidget(course_name_label)
         cell_layout.addWidget(professor_label)
         cell_layout.addWidget(code_label)

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

         # Enable hover effects with access violation protection
         def enter_event(event, widget=cell_widget):
             try:
                 if hasattr(widget, 'course_key') and widget.course_key:
                     self.highlight_course_sessions(widget.course_key)
             except Exception as e:
                 logger.warning(f"Hover enter event error: {e}")

         def leave_event(event, widget=cell_widget):
             try:
                 self.clear_course_highlights()
             except Exception as e:
                 logger.warning(f"Hover leave event error: {e}")

         def mouse_press_event(event, widget=cell_widget):
             try:
                 if event.button() == QtCore.Qt.LeftButton:
                     if hasattr(widget, 'course_key') and widget.course_key:
                         self.show_course_details(widget.course_key)
             except Exception as e:
                 logger.warning(f"Mouse press event error: {e}")

         cell_widget.enterEvent = enter_event
         cell_widget.leaveEvent = leave_event
         cell_widget.mousePressEvent = mouse_press_event

         self.schedule_table.setCellWidget(srow, col, cell_widget)
         if span > 1:
             self.schedule_table.setSpan(srow, col, span, 1)

         # Update overlay tracking for single course
         if slot_key not in self.overlays:
             self.overlays[slot_key] = {}
         self.overlays[slot_key]['single'] = cell_widget

         self.placed[(srow, col)] = {
             'course': course_key,
             'rows': span,
             'widget': cell_widget
         }

    def remove_placed_by_start(self, start_tuple):
        """Remove a placed course session by its starting position"""
        info = self.placed.get(start_tuple)
        if not info:
            return
        srow, col = start_tuple
        span = info['rows']
        self.schedule_table.removeCellWidget(srow, col)
        for r in range(srow, srow + span):
            self.schedule_table.setItem(r, col, QtWidgets.QTableWidgetItem(''))
        self.schedule_table.setSpan(srow, col, 1, 1)
        del self.placed[start_tuple]

    def remove_course_from_schedule(self, course_key):
        """Remove all instances of a course from the current schedule"""
        to_remove = []
        to_convert = []  # Track dual cells that need to be converted to single cells
        
        # Handle both single and dual courses
        for (srow, scol), info in list(self.placed.items()):
            if info.get('type') == 'dual':
                # For dual courses, check if the course is one of the two
                if course_key in info.get('courses', []):
                    # If removing one course from a dual cell, we need to convert it to single
                    dual_widget = info.get('widget')
                    if dual_widget and hasattr(dual_widget, 'remove_single_course'):
                        # Try to convert the dual widget to single course widget
                        try:
                            dual_widget.remove_single_course(course_key)
                            # The conversion was successful, so we don't need to remove this cell
                            continue
                        except Exception as e:
                            # If conversion fails, fall back to removing the entire cell
                            pass
                    # If conversion failed or not possible, mark for removal
                    to_remove.append((srow, scol))
            else:
                # For single courses, check directly
                if info.get('course') == course_key:
                    to_remove.append((srow, scol))
        
        for start_tuple in to_remove:
            self.remove_placed_by_start(start_tuple)
        
        # Update stats panel after removing course
        print("🔄 Calling update_stats_panel from remove_course_from_schedule")
        self.update_stats_panel()
        QtCore.QCoreApplication.processEvents()  # فورس UI update

    def clear_course_highlights(self):
        """Restore original styling for all course widgets"""
        # Make sure QtWidgets is available in this scope
        
        # Stop any pulsing animations
        if hasattr(self, '_pulse_timers'):
            for timer in list(self._pulse_timers.values()):
                try:
                    if timer and timer.isActive():
                        timer.stop()
                except RuntimeError:
                    # Timer has been deleted, skip it
                    pass
            self._pulse_timers.clear()
        
        for (srow, scol), info in self.placed.items():
            widget = info.get('widget')
            if info.get('type') == 'dual':
                # For dual courses, clear section highlighting
                if widget and hasattr(widget, 'clear_highlight'):
                    widget.clear_highlight()
                # Restore original style if stored
                if widget and hasattr(widget, 'original_style'):
                    widget.setStyleSheet(widget.original_style)
            elif widget and hasattr(widget, 'original_style'):
                # Restore the exact original style to prevent any residual effects
                widget.setStyleSheet(widget.original_style)
            elif widget:
                # If no original style was stored, apply default styling
                widget.setStyleSheet("")
    


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
    

    def remove_course_silently(self, course_key):
        """Remove course without user confirmation or notification"""
        # Find all placements for this course
        to_remove = []
        
        # Handle both single and dual courses
        for (srow, scol), info in list(self.placed.items()):
            if info.get('type') == 'dual':
                # For dual courses, check if the course is one of the two
                if course_key in info.get('courses', []):
                    # If removing one course from a dual cell, we need to convert it to single
                    dual_widget = info.get('widget')
                    if dual_widget and hasattr(dual_widget, 'remove_single_course'):
                        # Try to convert the dual widget to single course widget
                        try:
                            dual_widget.remove_single_course(course_key)
                            # The conversion was successful, so we don't need to remove this cell
                            continue
                        except Exception as e:

                            # If conversion fails, fall back to removing the entire cell
                            pass
                    # If conversion failed or not possible, mark for removal
                    to_remove.append((srow, scol))
            else:
                # For single courses, check directly
                if info.get('course') == course_key:
                    to_remove.append((srow, scol))
        
        # Remove all sessions of this course
        for start_tuple in to_remove:
            self.remove_placed_by_start(start_tuple)
            
        # Update stats panel after removing course
        print("🔄 Calling update_stats_panel from remove_course_silently")
        self.update_stats_panel()
        QtCore.QCoreApplication.processEvents()  # فورس UI update
        
        self.update_status()
        self.update_detailed_info_if_open()

    def remove_entire_course(self, course_key):
        """
        Remove all sessions of a course from the schedule.
        """
        to_remove = []
        to_convert = []  # Track dual cells that need to be converted to single cells
        
        # Handle both single and dual courses
        for (srow, scol), info in list(self.placed.items()):
            if info.get('type') == 'dual':
                # For dual courses, check if the course is one of the two
                if course_key in info.get('courses', []):
                    # If removing one course from a dual cell, we need to convert it to single
                    dual_widget = info.get('widget')
                    if dual_widget and hasattr(dual_widget, 'remove_single_course'):
                        # Try to convert the dual widget to single course widget
                        try:
                            dual_widget.remove_single_course(course_key)
                            # The conversion was successful, so we don't need to remove this cell
                            continue
                        except Exception as e:
                            # If conversion fails, fall back to removing the entire cell
                            pass
                    # If conversion failed or not possible, mark for removal
                    to_remove.append((srow, scol))
            else:
                # For single courses, check directly
                if info.get('course') == course_key:
                    to_remove.append((srow, scol))
        
        # Remove all sessions of this course
        for start_tuple in to_remove:
            self.remove_placed_by_start(start_tuple)
        
        # Update status bar
        self.update_status()
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()
        
        # Update stats panel after removing course
        print("🔄 Calling update_stats_panel from remove_entire_course")
        self.update_stats_panel()
        QtCore.QCoreApplication.processEvents()  # فورس UI update
        
        # Show confirmation
        from app.core.config import COURSES
        course_name = COURSES.get(course_key, {}).get('name', 'نامشخص')
        QtWidgets.QMessageBox.information(
            self, 'حذف شد', 
            f'تمام جلسات درس "{course_name}" با موفقیت حذف شدند.'
        )

    def clear_preview(self):
        """Clear preview cells from the schedule table"""
        for (srow, col, span) in self.preview_cells:
            for r in range(srow, srow + span):
                item = self.schedule_table.item(r, col)
                if item:
                    item.setText('')
            self.schedule_table.setSpan(srow, col, 1, 1)
            # Clear any cell widgets
            self.schedule_table.removeCellWidget(srow, col)
        self.preview_cells.clear()

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
        
    def highlight_course_sessions(self, course_key):
        """Highlight all sessions of a course with a smooth red border animation"""
        # Make sure QtWidgets is available in this scope
        
        # Clear any existing highlights first to prevent overlap
        self.clear_course_highlights()
        for (srow, scol), info in self.placed.items():
            # Handle both single and dual courses
            if info.get('type') == 'dual':
                # For dual courses, check if the course is one of the two
                if course_key in info.get('courses', []):
                    widget = info.get('widget')
                    if widget:
                        # Determine which section to highlight (odd or even)
                        odd_course_key = info.get('courses', [None, None])[0]
                        even_course_key = info.get('courses', [None, None])[1]
                        
                        if course_key == odd_course_key:
                            # Highlight the odd section
                            widget.highlight_section('odd')
                        elif course_key == even_course_key:
                            # Highlight the even section
                            widget.highlight_section('even')
                        
                        # Store original style if not already stored
                        if not hasattr(widget, 'original_style'):
                            widget.original_style = widget.styleSheet()
                        
                        # Add a subtle pulsing effect using QTimer
                        if not hasattr(self, '_pulse_timers'):
                            self._pulse_timers = {}
                        
                        # Create a timer for pulsing effect
                        if course_key not in self._pulse_timers:
                            timer = QtCore.QTimer(widget)
                            timer.course_key = course_key
                            timer.widget = widget
                            timer.step = 0
                            timer.timeout.connect(self._pulse_highlight)
                            self._pulse_timers[course_key] = timer
                        
                        # Start the pulsing animation
                        self._pulse_timers[course_key].start(100)
            else:
                # For single courses, check directly
                if info.get('course') == course_key:
                    widget = info.get('widget')
                    if widget:
                        # Store original style if not already stored
                        if not hasattr(widget, 'original_style'):
                            widget.original_style = widget.styleSheet()
                        
                        # Apply hover style with smooth red border effect
                        widget.setStyleSheet("QWidget#course-cell { border: 3px solid #e74c3c !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.2) !important; } QWidget#course-cell[conflict=\"true\"] { border: 3px solid #e74c3c !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.3) !important; } QWidget#course-cell[elective=\"true\"] { border: 3px solid #e74c3c !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.2) !important;}")
                        
                        # Add a subtle pulsing effect using QTimer
                        if not hasattr(self, '_pulse_timers'):
                            self._pulse_timers = {}
                        
                        # Create a timer for pulsing effect
                        if course_key not in self._pulse_timers:
                            timer = QtCore.QTimer(widget)
                            timer.course_key = course_key
                            timer.widget = widget
                            timer.step = 0
                            timer.timeout.connect(self._pulse_highlight)
                            self._pulse_timers[course_key] = timer
                        
                        # Start the pulsing animation
                        self._pulse_timers[course_key].start(100)
        
    def _pulse_highlight(self):
        """Pulse animation for highlighted course sessions"""
        # Make sure QtWidgets is available in this scope
        
        timer = self.sender()
        if not timer:
            return
            
        # Get the widget and course key
        widget = getattr(timer, 'widget', None)
        course_key = getattr(timer, 'course_key', None)
        
        if not widget or not course_key:
            timer.stop()
            return
            
        # Update the pulse step
        step = getattr(timer, 'step', 0)
        step = (step + 1) % 20
        timer.step = step
        
        # Calculate pulse intensity (0 to 1 and back to 0)
        intensity = abs(step - 10) / 10.0
        
        # Calculate colors based on intensity
        red_value = 231 + int((255 - 231) * intensity)
        green_value = 76 + int((100 - 76) * intensity)
        blue_value = 60 + int((100 - 60) * intensity)
        
        # Update the border color for pulsing effect
        widget.setStyleSheet("QWidget#course-cell { border: 3px solid rgb(" + str(red_value) + ", " + str(green_value) + ", " + str(blue_value) + ") !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.2) !important; } QWidget#course-cell[conflict=\"true\"] { border: 3px solid rgb(" + str(red_value) + ", " + str(green_value) + ", " + str(blue_value) + ") !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.3) !important; }")
        
    def open_detailed_info_window(self):
        """Open the detailed information window"""
        # Create window if it doesn't exist or was closed
        if not self.detailed_info_window or not self.detailed_info_window.isVisible():
            self.detailed_info_window = ExamScheduleWindow(self)
            
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

    def update_item_size_hint(self, item, widget):
        """Update the size hint for a QListWidgetItem based on its widget"""
        if item and widget:
            item.setSizeHint(widget.sizeHint())
            
    def populate_course_list(self, filter_text=""):
        """Populate the course list with all available courses - fixed widget lifecycle management"""
        try:
            from app.core.config import COURSES

            
            if not hasattr(self, 'course_list'):
                logger.error("course_list widget not found")
                return
                
            self.course_list.clear()
            
            # Clear widget cache to prevent deleted widget issues
            if hasattr(self, '_course_widgets_cache'):
                self._course_widgets_cache.clear()
            else:
                self._course_widgets_cache = {}
            
            # If no major is selected, show placeholder message
            if self.current_major_filter is None and not filter_text.strip():
                placeholder_item = QtWidgets.QListWidgetItem()
                placeholder_widget = QtWidgets.QWidget()
                placeholder_layout = QtWidgets.QVBoxLayout(placeholder_widget)
                placeholder_layout.setContentsMargins(10, 10, 10, 10)
                
                placeholder_label = QtWidgets.QLabel("برای مشاهده دروس، ابتدا رشته را انتخاب کنید.")
                placeholder_label.setAlignment(QtCore.Qt.AlignCenter)
                placeholder_label.setStyleSheet("color: #666; font-size: 14px; font-weight: bold;")
                
                placeholder_layout.addWidget(placeholder_label)
                placeholder_widget.setLayout(placeholder_layout)
                
                placeholder_item.setSizeHint(placeholder_widget.sizeHint())
                self.course_list.addItem(placeholder_item)
                self.course_list.setItemWidget(placeholder_item, placeholder_widget)
                return
            
            # Filter courses by major if a major is selected
            courses_to_show = {}
            if self.current_major_filter:
                # Filter courses by major
                for key, course in COURSES.items():
                    # Extract major from course key or metadata
                    course_major = self.extract_course_major(key, course)
                    if course_major == self.current_major_filter:
                        courses_to_show[key] = course
            else:
                # Show all courses if no filter
                courses_to_show = COURSES
            
            # Filter courses if search text provided (global search across all courses)
            if filter_text.strip():
                filter_text = filter_text.strip().lower()
                # Search across courses that passed major filter
                courses_to_show = {
                    key: course for key, course in courses_to_show.items()
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
                    # Validate course data before creating widget
                    if not isinstance(course, dict):
                        logger.warning(f"Invalid course data for {key}: not a dictionary")
                        continue
                        
                    required_fields = ['code', 'name', 'credits', 'instructor', 'schedule']
                    missing_fields = [field for field in required_fields if field not in course]
                    if missing_fields:
                        logger.warning(f"Course {key} missing required fields: {missing_fields}")
                        continue
                    
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
                    
                    # Set the custom widget for this item with proper sizing
                    item.setSizeHint(course_widget.sizeHint())
                    self.course_list.setItemWidget(item, course_widget)
                    
                    # Force update the size hint after widget is added
                    QtCore.QTimer.singleShot(0, lambda itm=item, widget=course_widget: self.update_item_size_hint(itm, widget))
                    
                    # Cache tooltip only (not the widget)
                    tooltip_key = f"{key}_tooltip"
                    self._course_widgets_cache[tooltip_key] = tooltip
                    
                    used += 1
                    
                except Exception as e:
                    logger.error(f"Error creating widget for course {key}: {e}", exc_info=True)
                    print(f"Warning: Could not create widget for course {key}: {e}")
                    continue
                
            # Update spacing between items
            self.course_list.setSpacing(3)
            
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
                self.update_stats_panel()
                
            logger.info(f"Populated course list with {shown_courses} courses (filtered: {bool(filter_text.strip())})")
            
        except Exception as e:
            logger.error(f"Failed to populate course list: {e}")





    def on_major_selection_changed(self, index):
        """Handle major selection change"""
        try:
            if index == 0:  # Default "انتخاب رشته" option
                self.current_major_filter = None
                # Don't show all courses when selecting default option
                self.course_list.clear()  # Clear the list instead of showing all courses
            else:
                selected_major = self.comboBox.currentText()
                self.current_major_filter = selected_major
                
                # If we have a database instance, filter courses by department
                if self.db is not None and selected_major != "دروس اضافه‌شده توسط کاربر":
                    # Extract department name from major identifier (faculty - department)
                    if " - " in selected_major:
                        department_name = selected_major.split(" - ", 1)[1]  # Get department part
                        logger.debug(f"Filtering courses by department: {department_name}")
                        
                        # Get courses for this department from database
                        department_courses = self.db.get_courses_by_department(
                            department_name, 
                            availability='both',
                            return_hierarchy=False
                        )
                        
                        # Update COURSES dictionary with only courses from this department
                        global COURSES
                        # Keep user-added courses
                        user_courses = {k: v for k, v in COURSES.items() if v.get('major') == 'دروس اضافه‌شده توسط کاربر'}
                        
                        # Clear and repopulate with department courses
                        COURSES.clear()
                        
                        # Convert database courses to the format expected by the UI
                        from app.core.golestan_integration import convert_db_course_format, generate_course_key_from_db
                        for course in department_courses:
                            course_key = generate_course_key_from_db(course)
                            converted_course = convert_db_course_format(course)
                            # Add major information
                            converted_course['major'] = selected_major
                            COURSES[course_key] = converted_course
                        
                        # Add back user-added courses
                        COURSES.update(user_courses)
                
                # Repopulate course list with new filter
                self.populate_course_list()
            
        except Exception as e:
            logger.error(f"Error handling major selection change: {e}")

    def connect_signals(self):
        """Connect UI signals to their respective slots"""
        try:
            # Search functionality
            if hasattr(self, 'search_box'):
                self.search_box.textChanged.connect(self.on_search_text_changed)
            
            # Search clear button
            if hasattr(self, 'pushButton'):
                self.pushButton.clicked.connect(self.clear_search)
            
            # Add Golestan fetch actions
            if hasattr(self, 'action_fetch_golestan'):
                # Disconnect any existing connections first to prevent duplicates
                try:
                    self.action_fetch_golestan.triggered.disconnect(self.fetch_from_golestan)
                except TypeError:
                    # No existing connection, that's fine
                    pass
                self.action_fetch_golestan.triggered.connect(self.fetch_from_golestan)
            
            if hasattr(self, 'action_manual_fetch'):
                # Disconnect any existing connections first to prevent duplicates
                try:
                    self.action_manual_fetch.triggered.disconnect(self.manual_fetch_from_golestan)
                except TypeError:
                    # No existing connection, that's fine
                    pass
                self.action_manual_fetch.triggered.connect(self.manual_fetch_from_golestan)
            
            # Add exam schedule actions
            if hasattr(self, 'action_show_exam_schedule'):
                self.action_show_exam_schedule.triggered.connect(self.on_show_exam_schedule)
            
            if hasattr(self, 'action_export_exam_schedule'):
                self.action_export_exam_schedule.triggered.connect(self.on_export_exam_schedule)
            
            # Major selection dropdown
            if hasattr(self, 'comboBox'):
                self.comboBox.currentIndexChanged.connect(self.on_major_selection_changed)
            
            # Course list
            if hasattr(self, 'course_list'):
                self.course_list.itemClicked.connect(self.on_course_clicked)
            
            # Buttons
            if hasattr(self, 'success_btn'):
                self.success_btn.clicked.connect(self.on_add_course)
                
            if hasattr(self, 'detailed_info_btn'):
                # Connect save button to save table image method
                self.detailed_info_btn.clicked.connect(self.save_table_image)
                
            if hasattr(self, 'clear_schedule_btn'):
                self.clear_schedule_btn.clicked.connect(self.on_clear_schedule)
                
            if hasattr(self, 'optimal_schedule_btn'):
                self.optimal_schedule_btn.clicked.connect(self.on_generate_optimal_from_auto_list)
                
            if hasattr(self, 'showExamPagebtn'):
                # Connect exam button to show exam schedule method
                self.showExamPagebtn.clicked.connect(self.on_show_exam_schedule)
            
            # Saved combinations buttons - Fix: Connect to proper saved combination handlers
            if hasattr(self, 'add_to_auto_btn'):
                self.add_to_auto_btn.clicked.connect(self.on_save_current_combo)
                
            if hasattr(self, 'remove_from_auto_btn'):
                self.remove_from_auto_btn.clicked.connect(self.on_delete_saved_combo)
            
            # Table interactions
            if hasattr(self, 'schedule_table'):
                self.schedule_table.cellClicked.connect(self.on_table_cell_clicked)
            
            # Saved combinations list
            if hasattr(self, 'saved_combos_list'):
                self.saved_combos_list.itemClicked.connect(self.on_saved_combo_clicked)
            
            # Auto-select list drag & drop
            if hasattr(self, 'auto_select_list'):
                self.setup_auto_select_list()
                # Enable keyboard shortcuts for auto-select list
                self.auto_select_list.keyPressEvent = self.auto_select_list_key_press_event
            
            logger.info("All UI signals connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect signals: {e}")

    def on_search_text_changed(self, text):
        """Handle search box text changes with debouncing for performance"""
        search_text = text.strip()
        
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
        self.update_stats_panel()
        
        # Hide the clear button after clearing
        if hasattr(self, 'search_clear_button'):
            self.search_clear_button.hide()

    def auto_save_user_data(self):
        """Auto-save user data without user interaction - DISABLED for backup-on-exit only"""
        # DISABLED: Backup system now only creates backups on app exit, not after table edits
        pass
            
    def _cleanup_old_backups(self):
        """Clean up old backup files, keeping only the last 5"""
        try:
            from app.core.data_manager import cleanup_old_backups
            cleanup_old_backups()
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
                self.update_stats_panel()
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
            combos = generate_best_combinations_for_groups(all_courses)
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

    def show_optimal_schedule_results(self, combos):
        """Show optimal schedule results in a dialog"""
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
        if combos:
            info_label = QtWidgets.QLabel('بهترین ترکیب‌ها براساس حداقل روزهای حضور و حداقل فاصله بین جلسات')
        else:
            info_label = QtWidgets.QLabel('هیچ ترکیب بهینه‌ای بدون تداخل پیدا نشد. ترکیب‌هایی با تداخل نشان داده نمی‌شوند.')
        info_label.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # Results list
        results_list = QtWidgets.QListWidget()
        layout.addWidget(results_list)
        
        # Add combinations to list
        if combos:
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
                
                stats_label = QtWidgets.QLabel(f'روزها: {combo["days"]} | فاصله: {combo["empty"]:.1f}h | امتیاز: {combo["score"]:.1f}')
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
        else:
            # Show a message when no combinations are found
            no_results_label = QtWidgets.QLabel('هیچ ترکیبی برای نمایش وجود ندارد.')
            no_results_label.setAlignment(QtCore.Qt.AlignCenter)
            no_results_label.setStyleSheet("color: #95a5a6; font-style: italic; padding: 20px;")
            item_widget = QtWidgets.QWidget()
            item_layout = QtWidgets.QVBoxLayout(item_widget)
            item_layout.addWidget(no_results_label)
            list_item = QtWidgets.QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            results_list.addItem(list_item)
            results_list.setItemWidget(list_item, item_widget)
        
        # Close button
        close_btn = QtWidgets.QPushButton('بستن')
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec_()

    def apply_optimal_combo_from_auto_list(self, combo, dialog):
        """Apply an optimal combination from auto-list to the schedule with priority-based conflict resolution"""
        try:
            # Clear current schedule
            self.clear_table_silent()
            
            # Get course priorities from auto-select list
            course_priorities = {}
            if hasattr(self, 'auto_select_list'):
                for i in range(self.auto_select_list.count()):
                    item = self.auto_select_list.item(i)
                    course_key = item.data(QtCore.Qt.UserRole)
                    priority = item.data(QtCore.Qt.UserRole + 1)
                    if course_key and priority:
                        course_priorities[course_key] = priority
            
            # Add courses from combination with priority-based conflict resolution
            added_count = 0
            conflicts = []
            
            # Sort courses by priority (lower number = higher priority)
            sorted_courses = sorted(combo['courses'], key=lambda x: course_priorities.get(x, 999))
            
            for course_key in sorted_courses:
                if course_key in COURSES:
                    try:
                        # Add course with conflict handling based on priority
                        success = self.add_course_to_table_with_priority(course_key, course_priorities)
                        if success:
                            added_count += 1
                        else:
                            conflicts.append(COURSES[course_key].get('name', course_key))
                    except Exception as e:
                        logger.error(f"Error adding course {course_key}: {e}")
                        conflicts.append(COURSES[course_key].get('name', course_key))
            
            # Update UI
            self.update_status()
            self.update_stats_panel()
            self.update_detailed_info_if_open()
            
            # Close dialog
            dialog.close()
            
            # Show results
            if conflicts:
                msg = f"✅ {added_count} درس اضافه شد\n⚠️ {len(conflicts)} درس به دلیل تداخل اضافه نشد:\n" + "\n".join(conflicts[:5])
                if len(conflicts) > 5:
                    msg += f"\n... و {len(conflicts)-5} درس دیگر"
            else:
                msg = f"✅ تمام {added_count} درس با موفقیت اضافه شد!"
            
            QtWidgets.QMessageBox.information(self, "نتیجه", msg)
            
        except Exception as e:
            logger.error(f"Error applying combo: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در اعمال ترکیب: {str(e)}")

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
        self.update_stats_panel()
        self.update_detailed_info_if_open()
        
        # Close dialog
        dialog.close()
        
        QtWidgets.QMessageBox.information(
            self, 'اعمال شد', 
            f'ترکیب بهینه با {combo["days"]} روز حضور و {combo["empty"]:.1f} ساعت فاصله اعمال شد.'
        )

    def load_saved_combos_ui(self):
        """Load saved combinations into the UI"""
        self.saved_combos_list.clear()
        for sc in self.user_data.get('saved_combos', []):
            name = sc.get('name', 'بدون نام')
            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, sc)
            self.saved_combos_list.addItem(item)

    def save_current_combo(self):
        """Save the current combination of courses"""
        # collect currently placed course keys
        # Handle both single and dual courses correctly
        keys = []
        for info in self.placed.values():
            if info.get('type') == 'dual':
                # For dual courses, add both courses
                keys.extend(info.get('courses', []))
            else:
                # For single courses, add the course key
                keys.append(info.get('course'))
        # Remove duplicates while preserving order
        seen = set()
        unique_keys = []
        for key in keys:
            if key not in seen:
                seen.add(key)
                unique_keys.append(key)
        keys = unique_keys
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
                    # Remove existing combo with same name
                    self.user_data['saved_combos'] = [
                        combo for combo in self.user_data['saved_combos'] 
                        if combo.get('name') != name
                    ]
                elif result == QtWidgets.QMessageBox.Cancel:
                    return
                    
            # Create new combo object
            new_combo = {
                'name': name,
                'courses': keys
            }
            
            # Add to saved combos
            self.user_data['saved_combos'].append(new_combo)
            
            # Save to file using the data manager
            try:
                from app.core.data_manager import save_user_data
                save_user_data(self.user_data)
                
                # Update UI
                self.load_saved_combos_ui()
                
                # Show confirmation
                QtWidgets.QMessageBox.information(
                    self, '✅ ذخیره موفق', 
                    f'ترکیب "{name}" با موفقیت ذخیره شد.\nتعداد دروس: {len(keys)}'
                )
            except Exception as e:
                logger.error(f"Error saving combo: {e}")
                QtWidgets.QMessageBox.critical(
                    self, 'خطا', 
                    f'خطا در ذخیره ترکیب:\n{str(e)}'
                )
            
            return
        
    def _pulse_highlight(self):
        """Pulse animation for highlighted course sessions"""
        timer = self.sender()
        if not timer:
            return
            
        # Get the widget and course key
        widget = getattr(timer, 'widget', None)
        course_key = getattr(timer, 'course_key', None)
        
        if not widget or not course_key:
            timer.stop()
            return
            
        # Update the pulse step
        step = getattr(timer, 'step', 0)
        step = (step + 1) % 20
        timer.step = step
        
        # Calculate pulse intensity (0 to 1 and back to 0)
        intensity = abs(step - 10) / 10.0
        
        # Calculate colors based on intensity
        red_value = 231 + int((255 - 231) * intensity)
        green_value = 76 + int((100 - 76) * intensity)
        blue_value = 60 + int((100 - 60) * intensity)
        
        # Update the border color for pulsing effect based on widget type
        if widget.objectName() == 'dual-course-cell':
            # For dual course widgets
            widget.setStyleSheet("QWidget#dual-course-cell { border: 3px solid rgb(" + str(red_value) + ", " + str(green_value) + ", " + str(blue_value) + ") !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.2) !important; }")
        else:
            # For regular course widgets
            widget.setStyleSheet("QWidget#course-cell { border: 3px solid rgb(" + str(red_value) + ", " + str(green_value) + ", " + str(blue_value) + ") !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.2) !important; } QWidget#course-cell[conflict=\"true\"] { border: 3px solid rgb(" + str(red_value) + ", " + str(green_value) + ", " + str(blue_value) + ") !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.3) !important; }")
        
    def open_detailed_info_window(self):
        """Open the detailed information window"""
        # Create window if it doesn't exist or was closed
        if not self.detailed_info_window or not self.detailed_info_window.isVisible():
            self.detailed_info_window = ExamScheduleWindow(self)
            
        # Show and raise the window
        self.detailed_info_window.show()
        self.detailed_info_window.raise_()
        self.detailed_info_window.activateWindow()
        
        # Update content with latest data
        self.detailed_info_window.update_content()

    def update_detailed_info_if_open(self):
        """Update the detailed info window if it's currently open"""
        # Make sure QtWidgets is available in this scope
        
        if self.detailed_info_window and self.detailed_info_window.isVisible():
            self.detailed_info_window.update_content()

    def update_item_size_hint(self, item, widget):
        """Update the size hint for a QListWidgetItem based on its widget"""
        if item and widget:
            item.setSizeHint(widget.sizeHint())
            
    def populate_course_list(self, filter_text=""):
        """Populate the course list with courses"""
        try:
            # If no database instance, fallback to JSON loading
            if self.db is None:
                from app.core.data_manager import load_courses_from_json
                load_courses_from_json()
            else:
                # Load courses from database if not already loaded
                if not COURSES:
                    self.load_courses_from_database()

            # Clear the course list
            self.course_list.clear()
            
            # Filter courses based on current major filter
            courses_to_show = COURSES
            if self.current_major_filter and self.current_major_filter != "دروس اضافه‌شده توسط کاربر":
                # Filter courses by major
                courses_to_show = {
                    key: course for key, course in COURSES.items()
                    if course.get('major') == self.current_major_filter
                }
            elif self.current_major_filter == "دروس اضافه‌شده توسط کاربر":
                # Show only user-added courses
                courses_to_show = {
                    key: course for key, course in COURSES.items()
                    if course.get('major') == "دروس اضافه‌شده توسط کاربر"
                }
            
            # Apply search filter if provided
            if filter_text.strip():
                filter_text = filter_text.strip().lower()
                # Search across courses that passed major filter
                courses_to_show = {
                    key: course for key, course in courses_to_show.items()
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
                    # Validate course data before creating widget
                    if not isinstance(course, dict):
                        logger.warning(f"Invalid course data for {key}: not a dictionary")
                        continue
                        
                    required_fields = ['code', 'name', 'credits', 'instructor', 'schedule']
                    missing_fields = [field for field in required_fields if field not in course]
                    if missing_fields:
                        logger.warning(f"Course {key} missing required fields: {missing_fields}")
                        continue
                
                    # Create list item
                    item = QtWidgets.QListWidgetItem()
                    item.setData(QtCore.Qt.UserRole, key)
                    
                    # Set background color
                    color = COLOR_MAP[used % len(COLOR_MAP)]
                    item.setBackground(QtGui.QBrush(color))
                    
                    # Create tooltip with course details
                    tooltip = f"کد: {course['code']}\n"
                    tooltip += f"نام: {course['name']}\n"
                    tooltip += f"استاد: {course['instructor']}\n"
                    tooltip += f"واحد: {course['credits']}\n"
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
                    
                    # Set the custom widget for this item with proper sizing
                    item.setSizeHint(course_widget.sizeHint())
                    self.course_list.setItemWidget(item, course_widget)
                    used += 1
                    
                except Exception as e:
                    logger.error(f"Error creating course widget for {key}: {e}")
                    continue
            
            logger.info(f"Populated course list with {used} courses")
            
        except Exception as e:
            logger.error(f"Failed to populate course list: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"امکان پر کردن فهرست دروس وجود ندارد: {str(e)}")


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
        self.update_stats_panel()
        QtWidgets.QMessageBox.information(
            self, 'بارگذاری', 
            f"ترکیب '{sc.get('name')}' بارگذاری شد.\n"
            f"تعداد دروس بارگذاری شده: {loaded_count}"
        )
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()

    def on_saved_combo_clicked(self, item):
        """Handle click on saved combination item"""
        if item is not None:
            self.load_saved_combo(item)

    def on_save_current_combo(self):
        """Handle save current combo button click"""
        self.save_current_combo()

    def on_delete_saved_combo(self):
        """Handle delete saved combo button click"""
        # Get selected item from saved_combos_list
        selected_items = self.saved_combos_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(self, 'حذف ترکیب', 'لطفا ابتدا یک ترکیب را از لیست انتخاب کنید.')
            return
            
        # Get the selected item
        item = selected_items[0]
        sc = item.data(QtCore.Qt.UserRole)
        combo_name = sc.get('name', 'بدون نام')
        
        # Use the existing delete_saved_combo method
        self.delete_saved_combo(combo_name)

    def setup_auto_select_list(self):
        """Setup drag and drop functionality for auto-select list"""
        if hasattr(self, 'auto_select_list'):
            # Enable drag and drop
            self.auto_select_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
            self.auto_select_list.setDefaultDropAction(QtCore.Qt.MoveAction)
            
            # Enable context menu
            self.auto_select_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.auto_select_list.customContextMenuRequested.connect(self.show_auto_list_context_menu)
            
            # Connect signal for handling reordering
            self.auto_select_list.model().rowsMoved.connect(self.on_auto_list_reordered)

    def on_auto_list_reordered(self, parent, start, end, destination, row):
        """Handle reordering of auto-select list items"""
        try:
            # Update priorities based on new positions
            for i in range(self.auto_select_list.count()):
                item = self.auto_select_list.item(i)
                if item:
                    # Priority = position + 1 (first item = priority 1)
                    priority = i + 1
                    item.setData(QtCore.Qt.UserRole + 1, priority)
                    
                    # Update display text to show priority
                    course_key = item.data(QtCore.Qt.UserRole)
                    if course_key in COURSES:
                        course = COURSES[course_key]
                        course_name = course.get('name', course_key)
                        item.setText(f"({priority}) {course_name}")
            
            logger.info("Auto-select list priorities updated")
        except Exception as e:
            logger.error(f"Error reordering auto list: {e}")

    def on_generate_optimal_from_auto_list(self):
        """Handle generate optimal schedule from auto-select list button click"""
        try:
            self.generate_optimal_schedule_from_auto_list()
        except Exception as e:
            logger.error(f"Error generating optimal schedule from auto list: {e}")

    def generate_optimal_schedule_from_auto_list(self):
        """Generate schedules that respect user priority order"""
        # Extract courses IN PRIORITY ORDER from auto-select list
        ordered_course_keys = []
        for i in range(self.auto_select_list.count()):
            item = self.auto_select_list.item(i)
            if item and item.data(QtCore.Qt.UserRole):
                course_key = item.data(QtCore.Qt.UserRole)
                if course_key in COURSES:
                    ordered_course_keys.append(course_key)
        
        if not ordered_course_keys:
            QtWidgets.QMessageBox.information(self, "اطلاع", "لیست اولویت خالی است.")
            return
        
        # Show progress dialog
        progress = QtWidgets.QProgressDialog('در حال تولید بهترین ترکیبات...', 'لغو', 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.show()
        
        try:
            # Use priority-aware algorithm instead of combinations
            schedules = generate_priority_based_schedules(ordered_course_keys)
            progress.setValue(50)
            
            # Always proceed even if no perfect combinations found
            # Display results in a dialog
            self.show_priority_aware_results(schedules, ordered_course_keys)
            progress.setValue(100)
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, 'خطا', 
                f'خطا در تولید ترکیبات:\n{str(e)}'
            )
            print(f"Error in generate_optimal_schedule_from_auto_list: {e}")
        finally:
            progress.close()

    def generate_optimal_schedule(self):
        """Generate optimal schedule combinations with conflict handling"""
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
            combos = generate_best_combinations_for_groups(all_courses)
            progress.setValue(50)
            
            # Always proceed even if no perfect combinations found
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

    def show_optimal_schedule_results(self, combos):
        """Show optimal schedule results in a dialog"""
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
        if combos:
            info_label = QtWidgets.QLabel('بهترین ترکیب‌ها بر اساس حداقل روزهای حضور و حداقل فاصله بین جلسات')
        else:
            info_label = QtWidgets.QLabel('هیچ ترکیب بهینه‌ای بدون تداخل پیدا نشد. ترکیب‌هایی با تداخل نشان داده نمی‌شوند.')
        info_label.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(info_label)
        
        # Results list
        results_list = QtWidgets.QListWidget()
        layout.addWidget(results_list)
        
        # Add combinations to list
        if combos:
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
                
                stats_label = QtWidgets.QLabel(f'روزها: {combo["days"]} | فاصله: {combo["empty"]:.1f}h | امتیاز: {combo["score"]:.1f}')
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
        else:
            # Show a message when no combinations are found
            no_results_label = QtWidgets.QLabel('هیچ ترکیبی برای نمایش وجود ندارد.')
            no_results_label.setAlignment(QtCore.Qt.AlignCenter)
            no_results_label.setStyleSheet("color: #95a5a6; font-style: italic; padding: 20px;")
            item_widget = QtWidgets.QWidget()
            item_layout = QtWidgets.QVBoxLayout(item_widget)
            item_layout.addWidget(no_results_label)
            list_item = QtWidgets.QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            results_list.addItem(list_item)
            results_list.setItemWidget(list_item, item_widget)
        
        # Close button
        close_btn = QtWidgets.QPushButton('بستن')
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec_()



    def show_priority_aware_results(self, schedules, original_priority_order):
        """Show results with clear priority information"""
        if not schedules:
            QtWidgets.QMessageBox.information(
                self, "نتیجه", 
                "با توجه به اولویت‌های تعیین شده و تداخل‌های زمانی، برنامه‌ای قابل ساخت نیست."
            )
            return
        
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("برنامه‌های پیشنهادی با اولویت")
        dialog.setModal(True)
        dialog.resize(700, 500)
        dialog.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Description label
        info_label = QtWidgets.QLabel(f"{len(schedules)} برنامه پیشنهادی یافت شد. روی یکی کلیک کنید:")
        layout.addWidget(info_label)
        
        # Clickable list
        schedule_list = QtWidgets.QListWidget()
        schedule_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        
        # Process schedules to add priority information
        for i, schedule in enumerate(schedules):
            # Calculate priority information
            included_priorities = []
            skipped_priorities = []
            
            for j, course_key in enumerate(original_priority_order):
                priority_num = j + 1
                course_name = COURSES[course_key].get('name', course_key)
                
                if course_key in schedule['courses']:
                    included_priorities.append(f"P{priority_num}: {course_name}")
                else:
                    skipped_priorities.append(f"P{priority_num}: {course_name}")
            
            # Create display information
            schedule['display_info'] = {
                'included': included_priorities,
                'skipped': skipped_priorities,
                'priority_success_rate': len(included_priorities) / len(original_priority_order) if original_priority_order else 0
            }
            
            # Create item text with priority information
            method_text = schedule.get('method', 'Unknown Method')
            course_count = len(schedule['courses'])
            days = schedule.get('days', 0)
            empty_time = schedule.get('empty', 0.0)
            
            schedule_text = f"{method_text}: {course_count} درس - {days} روز - {empty_time:.1f} ساعت خالی"
            
            item = QtWidgets.QListWidgetItem(schedule_text)
            item.setData(QtCore.Qt.UserRole, schedule)  # Store complete schedule
            schedule_list.addItem(item)
        
        layout.addWidget(schedule_list)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        apply_btn = QtWidgets.QPushButton("اعمال برنامه")
        cancel_btn = QtWidgets.QPushButton("انصراف")
        
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        # Connect signals
        def on_apply():
            selected_items = schedule_list.selectedItems()
            if selected_items:
                schedule = selected_items[0].data(QtCore.Qt.UserRole)
                self.apply_priority_aware_schedule(schedule, dialog)
            else:
                QtWidgets.QMessageBox.warning(dialog, "هشدار", "لطفاً یک برنامه انتخاب کنید.")
        
        def on_item_double_click(item):
            schedule = item.data(QtCore.Qt.UserRole)
            self.apply_priority_aware_schedule(schedule, dialog)
        
        def on_item_click(item):
            # Show detailed information about the selected schedule
            schedule = item.data(QtCore.Qt.UserRole)
            self.show_schedule_details(schedule)
        
        apply_btn.clicked.connect(on_apply)
        cancel_btn.clicked.connect(dialog.close)
        schedule_list.itemDoubleClicked.connect(on_item_double_click)
        schedule_list.itemClicked.connect(on_item_click)
        
        dialog.exec_()

    def show_schedule_details(self, schedule):
        """Show detailed information about a schedule"""
        # This method can be expanded to show more details about the schedule
        pass

    def apply_priority_aware_schedule(self, schedule, dialog):
        """Apply a priority-aware schedule to the schedule table"""
        try:
            # Clear current schedule
            self.clear_table_silent()
            
            # Add courses from schedule
            added_count = 0
            conflicts = []
            
            for course_key in schedule['courses']:
                if course_key in COURSES:
                    try:
                        # Add course with conflict handling
                        success = self.add_course_to_table(course_key, ask_on_conflict=False)
                        if success:
                            added_count += 1
                        else:
                            conflicts.append(COURSES[course_key].get('name', course_key))
                    except Exception as e:
                        logger.error(f"Error adding course {course_key}: {e}")
                        conflicts.append(COURSES[course_key].get('name', course_key))
            
            # Update UI
            self.update_status()
            self.update_stats_panel()
            self.update_detailed_info_if_open()
            
            # Close dialog
            dialog.close()
            
            # Show results
            if conflicts:
                msg = f"✅ {added_count} درس اضافه شد\n⚠️ {len(conflicts)} درس به دلیل تداخل اضافه نشد:\n" + "\n".join(conflicts[:5])
                if len(conflicts) > 5:
                    msg += f"\n... و {len(conflicts)-5} درس دیگر"
            else:
                msg = f"✅ تمام {added_count} درس با موفقیت اضافه شد!"
            
            QtWidgets.QMessageBox.information(self, "نتیجه", msg)
            
        except Exception as e:
            logger.error(f"Error applying schedule: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در اعمال برنامه: {str(e)}")

    def save_auto_select_list(self):
        """Save the auto-select list to user data"""
        # This method is called to save changes to the auto-select list
        # For now, we'll just log that it was called since the list is managed in memory
        logger.debug("Auto-select list saved")
        pass

    def show_auto_list_context_menu(self, position):
        """Show context menu for auto-select list items"""
        item = self.auto_select_list.itemAt(position)
        
        menu = QtWidgets.QMenu()
        
        # If an item is right-clicked, show delete option
        if item:
            # Delete action
            delete_action = menu.addAction("حذف از لیست")
        
        # Always show clear all option if there are items in the list
        if self.auto_select_list.count() > 0:
            clear_all_action = menu.addAction("پاک کردن همه")
        
        action = menu.exec_(self.auto_select_list.mapToGlobal(position))
        
        if 'delete_action' in locals() and action == delete_action:
            row = self.auto_select_list.row(item)
            self.auto_select_list.takeItem(row)
        elif 'clear_all_action' in locals() and action == clear_all_action:
            # Confirm clear all
            reply = QtWidgets.QMessageBox.question(
                self, 'پاک کردن همه', 
                f'آیا مطمئن هستید که می‌خواهید همه {self.auto_select_list.count()} درس را از لیست حذف کنید؟',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                self.auto_select_list.clear()

    def auto_select_list_key_press_event(self, event):
        """Handle key press events for auto-select list"""
        # Handle Delete key
        if event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
            selected_items = self.auto_select_list.selectedItems()
            if selected_items:
                # Remove selected items (in reverse order to maintain indices)
                for item in reversed(selected_items):
                    row = self.auto_select_list.row(item)
                    self.auto_select_list.takeItem(row)
                return
        
        # Handle Ctrl+A for select all
        if event.key() == QtCore.Qt.Key_A and event.modifiers() == QtCore.Qt.ControlModifier:
            self.auto_select_list.selectAll()
            return
            
        # Call the original event handler for other keys
        QtWidgets.QListWidget.keyPressEvent(self.auto_select_list, event)
    def delete_saved_combo(self, combo_name):
        """Delete a saved combination by name"""
        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self, 'حذف ترکیب', 
            f'آیا مطمئن هستید که می‌خواهید ترکیب "{combo_name}" را حذف کنید؟',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            # Remove from user_data
            self.user_data['saved_combos'] = [
                combo for combo in self.user_data.get('saved_combos', []) 
                if combo.get('name') != combo_name
            ]
            
            # Save user data
            save_user_data(self.user_data)
            
            # Refresh UI
            self.load_saved_combos_ui()
            
            QtWidgets.QMessageBox.information(
                self, 'حذف شد', 
                f'ترکیب "{combo_name}" با موفقیت حذف شد.'
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

    def update_course_info_panel(self):
        """Update the course information panel"""
        # This method is called to update the course info panel
        # Implementation can be added as needed
        pass

    def on_table_cell_clicked(self, row, column):
        """Handle clicks on schedule table cells"""
        # This is a placeholder - implement as needed
        pass

    def on_search_text_changed(self, text):
        """Handle search text change"""
        try:
            # Filter course list based on search text
            self.filter_course_list(text)
        except Exception as e:
            logger.error(f"Error in search: {e}")

    def on_clear_schedule(self):
        """Clear all courses from schedule table"""
        try:
            # Clear all cells
            for row in range(self.schedule_table.rowCount()):
                for col in range(self.schedule_table.columnCount()):
                    self.schedule_table.setCellWidget(row, col, None)
            
            # Clear placed courses dictionary
            self.placed.clear()
            
            logger.info("Schedule table cleared")
            self.update_status()
            self.update_stats_panel()
            
        except Exception as e:
            logger.error(f"Error clearing schedule: {e}")

    def on_show_exam_schedule(self):
        """Show exam schedule window"""
        try:
            from ui.dialogs import ExamScheduleWindow
            exam_window = ExamScheduleWindow(self)
            exam_window.show()
        except Exception as e:
            logger.error(f"Error showing exam schedule: {e}")

    def on_add_course(self):
        """Handle add course button click"""
        try:
            self.open_add_course_dialog()
        except Exception as e:
            logger.error(f"Error adding course: {e}")

    def on_detailed_info(self):
        """Handle detailed info button click"""
        try:
            self.open_detailed_info_window()
        except Exception as e:
            logger.error(f"Error showing detailed info: {e}")

    def on_generate_optimal(self):
        """Handle generate optimal schedule button click"""
        try:
            self.generate_optimal_schedule()
        except Exception as e:
            logger.error(f"Error generating optimal schedule: {e}")

    def on_add_to_auto(self):
        """Handle add to auto select list button click"""
        try:
            # Get selected items from course_list
            selected_items = self.course_list.selectedItems()
            if not selected_items:
                QtWidgets.QMessageBox.information(self, 'انتخاب درس', 'لطفا ابتدا درسی را از لیست انتخاب کنید.')
                return
            
            # Add selected courses to auto_select_list
            for item in selected_items:
                # Check if item already exists in auto_select_list
                exists = False
                for i in range(self.auto_select_list.count()):
                    if self.auto_select_list.item(i).data(QtCore.Qt.UserRole) == item.data(QtCore.Qt.UserRole):
                        exists = True
                        break
                
                if not exists:
                    # Create new item with course data
                    course_key = item.data(QtCore.Qt.UserRole)
                    course = COURSES.get(course_key)
                    if course:
                        position = self.auto_select_list.count() + 1
                        new_item = QtWidgets.QListWidgetItem(f"({position}) {course['name']} - {course.get('instructor', 'نامشخص')}")
                        new_item.setData(QtCore.Qt.UserRole, course_key)
                        # Set position as priority (first item = priority 1)
                        new_item.setData(QtCore.Qt.UserRole + 1, position)
                        self.auto_select_list.addItem(new_item)
            
            # Save user data
            self.save_auto_select_list()
            
        except Exception as e:
            logger.error(f"Error adding to auto list: {e}")
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در افزودن به لیست انتخاب توسط سیستم: {str(e)}')

    def on_search_text_changed(self, text):
        """Handle search text change with debouncing"""
        try:
            # Use QTimer to debounce the search (delay for 300ms)
            if hasattr(self, '_search_timer'):
                self._search_timer.stop()
            else:
                self._search_timer = QtCore.QTimer(self)
                self._search_timer.setSingleShot(True)
                self._search_timer.timeout.connect(lambda: self.filter_course_list(text))
            
            # Start the timer with 300ms delay
            self._search_timer.start(300)
        except Exception as e:
            logger.error(f"Error in search: {e}")

    def filter_course_list(self, filter_text):
        """Filter course list based on search text"""
        try:
            self.populate_course_list(filter_text)
        except Exception as e:
            logger.error(f"Error filtering course list: {e}")

    def on_remove_from_auto(self):
        """Handle remove from auto select list button click"""
        try:
            # Get selected items from auto_select_list
            selected_items = self.auto_select_list.selectedItems()
            if not selected_items:
                QtWidgets.QMessageBox.information(self, 'حذف درس', 'لطفا ابتدا درسی را از لیست انتخاب کنید.')
                return
            
            # Remove selected items (in reverse order to maintain indices)
            for item in reversed(selected_items):
                row = self.auto_select_list.row(item)
                self.auto_select_list.takeItem(row)
                
            logger.info(f"Removed {len(selected_items)} courses from auto select list")
            
        except Exception as e:
            logger.error(f"Error removing from auto select list: {e}")

    def load_and_apply_styles(self):
        """Load styles from external QSS file"""
        try:
            ui_dir = os.path.dirname(os.path.abspath(__file__))
            qss_file = os.path.join(ui_dir, 'styles.qss')
            with open(qss_file, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Warning: styles.qss file not found")
        except Exception as e:
            print(f"Warning: Could not load styles: {e}")
            
    def create_search_clear_button(self):
        """Create and position the search clear button inside the search box"""
        try:
            if hasattr(self, 'search_box'):
                # Create the clear button
                self.search_clear_button = QtWidgets.QPushButton("✖")
                self.search_clear_button.setObjectName("search_clear_button")
                self.search_clear_button.setFixedSize(20, 20)
                self.search_clear_button.setCursor(QtCore.Qt.ArrowCursor)
                
                # Set button properties
                self.search_clear_button.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: none;
                        color: #95a5a6;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        color: #7f8c8d;
                        background: rgba(0, 0, 0, 0.05);
                        border-radius: 10px;
                    }
                """)
                
                # Position the button inside the search box
                frame_width = self.search_box.style().pixelMetric(QtWidgets.QStyle.PM_DefaultFrameWidth)
                button_size = self.search_clear_button.sizeHint()
                
                # For RTL layout, position on the left side
                self.search_clear_button.move(
                    frame_width + 2,  # Small offset from the left edge
                    (self.search_box.height() - button_size.height()) // 2
                )
                
                # Make the button a child of the search box
                self.search_clear_button.setParent(self.search_box)
                
                # Connect the button to clear the search
                self.search_clear_button.clicked.connect(self.clear_search)
                
                # Show/hide button based on text
                self.search_box.textChanged.connect(self.toggle_search_clear_button)
                
                # Initially hide the button
                self.search_clear_button.hide()
                
                # Update button visibility
                self.toggle_search_clear_button("")
                
        except Exception as e:
            logger.error(f"Failed to create search clear button: {e}")
            
    def toggle_search_clear_button(self, text):
        """Show/hide the search clear button based on search text"""
        if hasattr(self, 'search_clear_button'):
            self.search_clear_button.setVisible(bool(text))
            
    def save_table_image(self):
        """Save table as image (table only, not entire window) with high DPI support and improved quality"""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "ذخیره تصویر", "schedule_table.png", "PNG Files (*.png)")
        if path:
            # Use higher quality rendering with 3x scale factor for better clarity
            scale_factor = 3.0
            device_pixel_ratio = self.schedule_table.devicePixelRatio()
            
            # Create a pixmap with proper size accounting for both scale factor and device pixel ratio
            width = int(self.schedule_table.width() * scale_factor * device_pixel_ratio)
            height = int(self.schedule_table.height() * scale_factor * device_pixel_ratio)
            pixmap = QtGui.QPixmap(width, height)
            pixmap.setDevicePixelRatio(device_pixel_ratio * scale_factor)
            
            # Create a painter for high-quality rendering
            painter = QtGui.QPainter(pixmap)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
            painter.setRenderHint(QtGui.QPainter.HighQualityAntialiasing, True)
            
            # Render the table widget to the pixmap with the painter for better quality
            self.schedule_table.render(painter)
            painter.end()
            
            # Save with maximum quality
            if pixmap.save(path, "PNG", 100):
                QtWidgets.QMessageBox.information(self, "ذخیره تصویر", "تصویر جدول با موفقیت ذخیره شد.")
            else:
                QtWidgets.QMessageBox.warning(self, "خطا", "خطا در ذخیره تصویر.")

    def on_show_exam_schedule(self):
        """Show the exam schedule window"""
        try:
            # Create and show exam schedule window
            self.exam_schedule_window = ExamScheduleWindow(self)
            self.exam_schedule_window.show()
        except Exception as e:
            logger.error(f"Error showing exam schedule: {e}")
            QtWidgets.QMessageBox.critical(
                self, 'خطا', 
                f'خطا در نمایش برنامه امتحانات:\n{str(e)}'
            )

    def on_export_exam_schedule(self):
        """Export the exam schedule"""
        try:
            # Create exam schedule window and export directly
            exam_window = ExamScheduleWindow(self)
            exam_window.export_exam_schedule()
        except Exception as e:
            logger.error(f"Error exporting exam schedule: {e}")
            QtWidgets.QMessageBox.critical(
                self, 'خطا', 
                f'خطا در صدور برنامه امتحانات:\n{str(e)}'
            )

    def reset_golestan_credentials(self):
        """Reset Golestan credentials - delete saved credentials file and show confirmation"""
        try:
            from app.core.credentials import LOCAL_CREDENTIALS_FILE, delete_local_credentials
            
            # Delete the local credentials file
            if delete_local_credentials():
                # Show confirmation message in Persian
                QtWidgets.QMessageBox.information(
                    self, 
                    "موفقیت", 
                    "اطلاعات ذخیره‌شده گلستان حذف شد. دفعه بعد هنگام دریافت خودکار دروس، دوباره اطلاعات ورود درخواست می‌شود."
                )
                logger.info("Golestan credentials file deleted successfully")
            else:
                logger.error("Failed to delete Golestan credentials file")
                QtWidgets.QMessageBox.critical(
                    self, 
                    "خطا", 
                    "خطا در حذف اطلاعات ذخیره‌شده گلستان."
                )
        except Exception as e:
            logger.error(f"Error in reset golestan credentials: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                "خطا", 
                f"خطا در حذف اطلاعات ذخیره‌شده گلستان:\n{str(e)}"
            )

    def fetch_from_golestan(self):
        """Fetch courses from Golestan system automatically"""
        print("DEBUG: fetch_from_golestan called - COUNT TRACKER")
        if not hasattr(self, '_fetch_call_count'):
            self._fetch_call_count = 0
        self._fetch_call_count += 1
        print(f"DEBUG: fetch_from_golestan call count: {self._fetch_call_count}")
        try:
            from app.core.golestan_integration import update_courses_from_golestan
            from app.core.credentials import load_local_credentials
            from .credentials_dialog import GolestanCredentialsDialog
            
            # Check if credentials dialog is already open
            if hasattr(self, 'credentials_dialog_open') and self.credentials_dialog_open:
                print("DEBUG: credentials_dialog_open is True, returning early")
                return
            print("DEBUG: Setting credentials_dialog_open = True")
            self.credentials_dialog_open = True
            
            try:
                print("DEBUG: Checking for local credentials")
                # Check if local credentials exist
                credentials = load_local_credentials()
                
                # If credentials don't exist, prompt user
                if credentials is None:
                    print("DEBUG: No local credentials found, prompting user")
                    # Check if a dialog is already open
                    if hasattr(self, '_golestan_dialog') and self._golestan_dialog is not None and self._golestan_dialog.isVisible():
                        # Bring existing dialog to front
                        print("DEBUG: Dialog already visible, bringing to front")
                        self._golestan_dialog.raise_()
                        self._golestan_dialog.activateWindow()
                        return
                    
                    # Create and show dialog to get credentials
                    print("DEBUG: Creating GolestanCredentialsDialog")
                    self._golestan_dialog = GolestanCredentialsDialog(self)
                    print("DEBUG: Calling get_credentials()")
                    result = self._golestan_dialog.get_credentials()
                    print(f"DEBUG: get_credentials() returned: {result}")
                    
                    # Clean up reference
                    self._golestan_dialog = None
                    
                    # If user cancelled or failed to provide credentials, stop the process
                    if result[0] is None or result[1] is None:
                        print("DEBUG: User cancelled or failed to provide credentials")
                        return  # User cancelled, stop the process
                    
                    student_number, password, remember = result
                    
                    # Save credentials if user requested
                    if remember:
                        print("DEBUG: Saving credentials")
                        from app.core.credentials import save_local_credentials
                        save_local_credentials(student_number, password, remember)
                    
                    # Use provided credentials for this fetch
                    credentials = {
                        'student_number': student_number,
                        'password': password
                    }
                else:
                    print("DEBUG: Using existing local credentials")
                    # Use existing credentials
                    student_number = credentials['student_number']
                    password = credentials['password']
                
                # Show progress dialog
                print("DEBUG: Showing progress dialog")
                progress = QtWidgets.QProgressDialog('در حال دریافت اطلاعات از گلستان...', 'لغو', 0, 0, self)
                progress.setWindowModality(QtCore.Qt.WindowModal)
                progress.show()
                
                QtWidgets.QApplication.processEvents()  # Update UI
                
                # Fetch courses from Golestan with credentials
                print("DEBUG: Fetching courses from Golestan")
                update_courses_from_golestan(username=student_number, password=password)
                
                # Close progress dialog
                progress.close()
                
                # Refresh UI to show the new courses immediately
                self.refresh_ui()
                
                QtWidgets.QMessageBox.information(
                    self, 'موفقیت', 
                    'اطلاعات دروس با موفقیت از سامانه گلستان دریافت شد.'
                )
                
            finally:
                # Always reset the dialog open flag
                print("DEBUG: Setting credentials_dialog_open = False in finally block")
                self.credentials_dialog_open = False
                
        except Exception as e:
            # Reset the dialog open flag in case of error
            if hasattr(self, 'credentials_dialog_open'):
                print(f"DEBUG: Setting credentials_dialog_open = False in exception handler: {e}")
                self.credentials_dialog_open = False
            logger.error(f"Error fetching from Golestan: {e}")
            QtWidgets.QMessageBox.critical(
                self, 'خطا', 
                f'خطا در دریافت اطلاعات از گلستان:\n{str(e)}'
            )

    def manual_fetch_from_golestan(self):
        """Fetch courses from Golestan system with manual credentials"""
        try:
            from app.core.golestan_integration import update_courses_from_golestan
            
            # Get credentials from user
            username, ok1 = QtWidgets.QInputDialog.getText(
                self, 'ورود به گلستان', 'نام کاربری:')
            if not ok1 or not username:
                return
                
            password, ok2 = QtWidgets.QInputDialog.getText(
                self, 'ورود به گلستان', 'رمز عبور:', QtWidgets.QLineEdit.Password)
            if not ok2 or not password:
                return
            
            # Show progress dialog
            progress = QtWidgets.QProgressDialog('در حال دریافت اطلاعات از گلستان...', 'لغو', 0, 0, self)
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.show()
            
            QtWidgets.QApplication.processEvents()  # Update UI
            
            # Fetch courses from Golestan with provided credentials
            update_courses_from_golestan(username=username, password=password)
            
            # Close progress dialog
            progress.close()
            
            # Refresh UI to show the new courses immediately
            self.refresh_ui()
            
            QtWidgets.QMessageBox.information(
                self, 'موفقیت', 
                'اطلاعات دروس با موفقیت از سامانه گلستان دریافت شد.'
            )
            
        except Exception as e:
            logger.error(f"Error manual fetching from Golestan: {e}")
            QtWidgets.QMessageBox.critical(
                self, 'خطا', 
                f'خطا در دریافت اطلاعات از گلستان:\n{str(e)}'
            )

    def manage_golestan_credentials(self):
        """Manage Golestan credentials - view (masked) or remove saved credentials"""
        try:
            from app.core.credentials import LOCAL_CREDENTIALS_FILE, load_local_credentials, delete_local_credentials
            
            # Check if credentials file exists
            if not LOCAL_CREDENTIALS_FILE.exists():
                QtWidgets.QMessageBox.information(
                    self, 
                    "اطلاعات ورود گلستان", 
                    "هیچ اطلاعات ورودی ذخیره‌شده‌ای یافت نشد."
                )
                return
            
            # Load credentials to show masked info
            creds = load_local_credentials()
            if not creds:
                QtWidgets.QMessageBox.warning(
                    self, 
                    "خطا", 
                    "خطا در خواندن اطلاعات ورود ذخیره‌شده."
                )
                return
            
            # Show credential info (masked)
            student_number = creds['student_number']
            masked_student = student_number[:3] + '*' * (len(student_number) - 3) if len(student_number) > 3 else '*' * len(student_number)

            
            reply = QtWidgets.QMessageBox.question(
                self,
                "مدیریت اطلاعات ورود گلستان",
                f"اطلاعات ورود ذخیره‌شده:\n\nشماره دانشجویی: {masked_student}\n\nآیا می‌خواهید این اطلاعات را حذف کنید؟",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                # Delete credentials file
                if delete_local_credentials():
                    QtWidgets.QMessageBox.information(
                        self, 
                        "موفقیت", 
                        "اطلاعات ورود گلستان با موفقیت حذف شد."
                    )
                else:
                    QtWidgets.QMessageBox.warning(
                        self, 
                        "خطا", 
                        "خطا در حذف اطلاعات ورود."
                    )
        except Exception as e:
            logger.error(f"Error managing Golestan credentials: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                "خطا", 
                f"خطا در مدیریت اطلاعات ورود گلستان:\n{str(e)}"
            )

    def forget_saved_credentials(self):
        """Forget saved credentials - clear saved credentials and prompt for new ones"""
        print("DEBUG: forget_saved_credentials called")
        try:
            # Check if credentials dialog is already open
            if hasattr(self, 'credentials_dialog_open') and self.credentials_dialog_open:
                print("DEBUG: credentials_dialog_open is True in forget_saved_credentials, returning early")
                return
            print("DEBUG: Setting credentials_dialog_open = True in forget_saved_credentials")
            self.credentials_dialog_open = True
            
            try:
                from app.core.credentials import delete_local_credentials
                from .credentials_dialog import GolestanCredentialsDialog
                
                # Delete existing credentials
                print("DEBUG: Deleting local credentials")
                if delete_local_credentials():
                    logger.info("Existing Golestan credentials cleared successfully")
                    print("DEBUG: Existing Golestan credentials cleared successfully")
                else:
                    logger.warning("Failed to clear Golestan credentials")
                    print("DEBUG: Failed to clear Golestan credentials")
                
                # Check if a dialog is already open
                if hasattr(self, '_golestan_dialog') and self._golestan_dialog is not None and self._golestan_dialog.isVisible():
                    # Bring existing dialog to front
                    print("DEBUG: Dialog already visible in forget_saved_credentials, bringing to front")
                    self._golestan_dialog.raise_()
                    self._golestan_dialog.activateWindow()
                    return
                
                # Open credential dialog to get new credentials
                print("DEBUG: Creating GolestanCredentialsDialog in forget_saved_credentials")
                self._golestan_dialog = GolestanCredentialsDialog(self)
                print("DEBUG: Calling get_credentials() in forget_saved_credentials")
                result = self._golestan_dialog.get_credentials()
                print(f"DEBUG: get_credentials() returned in forget_saved_credentials: {result}")
                
                # Clean up reference
                self._golestan_dialog = None
                
                # If user provided credentials, save them
                if result[0] is not None and result[1] is not None:
                    student_number, password, remember = result
                    
                    # Save new credentials
                    print("DEBUG: Saving new credentials in forget_saved_credentials")
                    from app.core.credentials import save_local_credentials
                    if save_local_credentials(student_number, password, remember):
                        logger.info("New Golestan credentials saved successfully")
                        print("DEBUG: New Golestan credentials saved successfully")
                        
                        # Show success message
                        QtWidgets.QMessageBox.information(
                            self, 
                            "موفقیت", 
                            "اطلاعات ورود گلستان با موفقیت ذخیره شد. این اطلاعات فقط روی این دستگاه نگهداری می‌شود."
                        )
                        
                        # Simulate automatic course fetch with new credentials
                        self.fetch_from_golestan_with_new_credentials(student_number, password)
                    else:
                        logger.error("Failed to save new Golestan credentials")
                        QtWidgets.QMessageBox.critical(
                            self, 
                            "خطا", 
                            "خطا در ذخیره اطلاعات ورود جدید."
                        )
                else:
                    # User cancelled the dialog
                    logger.info("User cancelled credential entry")
                    print("DEBUG: User cancelled credential entry")
                    
            finally:
                # Always reset the dialog open flag
                print("DEBUG: Setting credentials_dialog_open = False in finally block of forget_saved_credentials")
                self.credentials_dialog_open = False
                
        except Exception as e:
            # Reset the dialog open flag in case of error
            if hasattr(self, 'credentials_dialog_open'):
                print(f"DEBUG: Setting credentials_dialog_open = False in exception handler of forget_saved_credentials: {e}")
                self.credentials_dialog_open = False
            logger.error(f"Error in forget saved credentials: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                "خطا", 
                f"خطا در فراموش کردن اطلاعات ذخیره شده:\n{str(e)}"
            )

    def fetch_from_golestan_with_new_credentials(self, username, password):
        """Fetch courses from Golestan using newly entered credentials"""
        try:
            from app.core.golestan_integration import update_courses_from_golestan
            
            # Show progress dialog
            progress = QtWidgets.QProgressDialog('در حال دریافت اطلاعات از گلستان...', 'لغو', 0, 0, self)
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.show()
            
            QtWidgets.QApplication.processEvents()  # Update UI
            
            # Fetch courses from Golestan with new credentials
            update_courses_from_golestan(username=username, password=password)
            
            # Close progress dialog
            progress.close()
            
            # Refresh UI to show the new courses immediately
            self.refresh_ui()
            
            QtWidgets.QMessageBox.information(
                self, 'موفقیت', 
                'اطلاعات دروس با موفقیت از سامانه گلستان دریافت شد.'
            )
            
        except Exception as e:
            logger.error(f"Error fetching from Golestan with new credentials: {e}")
            QtWidgets.QMessageBox.critical(
                self, 'خطا', 
                f'خطا در دریافت اطلاعات از گلستان:\n{str(e)}'
            )

    def refresh_ui(self):
        """Refresh both the major dropdown and course list in real-time"""
        try:
            # Refresh the major dropdown
            self.populate_major_dropdown()
            
            # Refresh the course list
            self.populate_course_list()
            
            logger.info("UI refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh UI: {e}")

    def refresh_course_list(self, category=None):
        """Refresh the course list for a specific category"""
        try:
            # If a category is specified, select it in the dropdown
            if category:
                index = self.comboBox.findText(category)
                if index >= 0:
                    self.comboBox.setCurrentIndex(index)
            
            # Refresh the course list
            self.populate_course_list()
            
            logger.info(f"Course list refreshed for category: {category}")
        except Exception as e:
            logger.error(f"Failed to refresh course list: {e}")

    def extract_course_major(self, course_key, course):
        """Extract major information from course data"""
        try:
            # First check if this is a user-added course
            if course.get('major') == 'دروس اضافه‌شده توسط کاربر':
                return 'دروس اضافه‌شده توسط کاربر'
            
            # Try to get major from golestan integration
            from app.core.golestan_integration import get_course_major
            major = get_course_major(course_key)
            logger.debug(f"Course {course_key} major: {major}")
            return major if major else "رشته نامشخص"
        except Exception as e:
            logger.error(f"Error extracting major for course {course_key}: {e}")
            return "رشته نامشخص"

    def populate_major_dropdown(self):
        """Populate the major dropdown with available majors"""
        try:
            if not hasattr(self, 'comboBox'):
                logger.warning("Major dropdown (comboBox) not found")
                return
                
            # Clear existing items except the first one ("انتخاب رشته")
            while self.comboBox.count() > 1:
                self.comboBox.removeItem(1)
        
            # If no database instance, fallback to JSON loading
            if self.db is None:
                from app.core.data_manager import load_courses_from_json
                load_courses_from_json()
            else:
                # Load courses from database if not already loaded
                if not COURSES:
                    self.load_courses_from_database()
        
            # Collect all unique majors from courses
            majors = set()
            logger.info(f"Populating major dropdown, total courses: {len(COURSES)}")
            for key, course in COURSES.items():
                # For database-loaded courses, we can directly use the 'major' field
                if 'major' in course and course['major'] != "رشته نامشخص":
                    majors.add(course['major'])
                else:
                    # Fallback to extract_course_major for other courses
                    major = self.extract_course_major(key, course)
                    if major and major != "رشته نامشخص":
                        majors.add(major)
        
            # Convert to sorted list
            sorted_majors = sorted(majors)
        
            # Add "دروس اضافه‌شده توسط کاربر" category at the beginning
            user_added_category = "دروس اضافه‌شده توسط کاربر"
            if user_added_category not in sorted_majors:
                sorted_majors.insert(0, user_added_category)
            else:
                # Move it to the beginning if it already exists
                sorted_majors.remove(user_added_category)
                sorted_majors.insert(0, user_added_category)
        
            # Add majors to dropdown (removed "همه" option)
            for major in sorted_majors:
                self.comboBox.addItem(major)
            
            logger.info(f"Populated major dropdown with {len(sorted_majors)} majors")
        
        except Exception as e:
            logger.error(f"Error populating major dropdown: {e}")

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
                self.update_stats_panel()
                self.update_detailed_info_if_open()
                
                logger.info(f"Loaded {len(current_schedule)} courses from saved schedule")
                
        except Exception as e:
            logger.error(f"Failed to load user schedule: {e}")
            # Don't show error to user to keep startup smooth

    def load_latest_backup(self):
        """Load the latest backup on application startup"""
        try:
            from app.core.data_manager import get_latest_auto_backup, load_auto_backup
            
            # Get the latest auto backup file
            latest_backup = get_latest_auto_backup()
            
            if latest_backup:
                # Load data from the latest backup
                backup_data = load_auto_backup(latest_backup)
                
                if backup_data:
                    # Update user data
                    self.user_data = backup_data
                    
                    # Load courses from backup data
                    current_schedule = self.user_data.get('current_schedule', [])
                    for course_key in current_schedule:
                        if course_key in COURSES:
                            self.add_course_to_table(course_key, ask_on_conflict=False)
                    
                    # Update UI
                    self.update_status()
                    self.update_stats_panel()
                    self.update_detailed_info_if_open()
                    
                    logger.info(f"Loaded latest backup: {latest_backup}")
                else:
                    logger.error(f"Failed to load backup data from: {latest_backup}")
            else:
                logger.info("No backup files found, starting with empty schedule")
                
        except Exception as e:
            logger.error(f"Error loading latest backup: {e}")

    def create_menu_bar(self):
        """Create the application menu bar with data and usage history options"""
        try:
            # Use the menu bar from the UI file if available
            if hasattr(self, 'menubar'):
                menubar = self.menubar
            else:
                # Create menu bar if not available in UI
                menubar = self.menuBar()
            
            # Use the data menu from the UI file if available
            if hasattr(self, 'menu_data'):
                data_menu = self.menu_data
                
                # Connect the reset Golestan credentials action if it exists in the UI
                if hasattr(self, 'action_reset_golestan_credentials'):
                    # Disconnect any existing connections first to prevent duplicates
                    try:
                        self.action_reset_golestan_credentials.triggered.disconnect(self.reset_golestan_credentials)
                    except TypeError:
                        # No existing connection, that's fine
                        pass
                    self.action_reset_golestan_credentials.triggered.connect(self.reset_golestan_credentials)
                
                # Connect the fetch Golestan action if it exists in the UI
                if hasattr(self, 'action_fetch_golestan'):
                    # Disconnect any existing connections first to prevent duplicates
                    try:
                        self.action_fetch_golestan.triggered.disconnect(self.fetch_from_golestan)
                    except TypeError:
                        # No existing connection, that's fine
                        pass
                    self.action_fetch_golestan.triggered.connect(self.fetch_from_golestan)
                    
                # Connect the manual fetch action if it exists in the UI
                if hasattr(self, 'action_manual_fetch'):
                    # Disconnect any existing connections first to prevent duplicates
                    try:
                        self.action_manual_fetch.triggered.disconnect(self.manual_fetch_from_golestan)
                    except TypeError:
                        # No existing connection, that's fine
                        pass
                    self.action_manual_fetch.triggered.connect(self.manual_fetch_from_golestan)
            
            # Connect the student profile action if it exists in the UI
            if hasattr(self, 'action_student_profile'):
                # Disconnect any existing connections first to prevent duplicates
                try:
                    self.action_student_profile.triggered.disconnect(self.show_student_profile)
                except TypeError:
                    # No existing connection, that's fine
                    pass
                self.action_student_profile.triggered.connect(self.show_student_profile)
            
            # Create "Usage History" menu
            history_menu = menubar.addMenu('سوابق استفاده')
            
            # Add date to menu title
            current_date = datetime.datetime.now().strftime('%Y/%m/%d')
            history_menu.setTitle(f'سوابق استفاده ({current_date})')
            
            # Connect menu to populate with backup history when clicked
            history_menu.aboutToShow.connect(self.populate_backup_history_menu)
            
        except Exception as e:
            logger.error(f"Error creating menu bar: {e}")
            import traceback
            traceback.print_exc()
    
    def populate_backup_history_menu(self):
        """Populate the backup history menu with available backups"""
        try:
            # Clear existing menu items
            menu = self.sender()
            menu.clear()
            
            # Get backup history from data manager
            from app.core.data_manager import get_backup_history
            backup_files = get_backup_history(5)
            
            if not backup_files:
                no_backups_action = menu.addAction("هیچ سوابقی موجود نیست")
                no_backups_action.setEnabled(False)
                return
            
            # Add backup files to menu
            for i, backup_file in enumerate(backup_files):
                # Extract timestamp from filename
                filename = os.path.basename(backup_file)
                timestamp_part = filename.replace('user_data_', '').replace('user_data_auto_', '').replace('.json', '')
                
                # Format timestamp for display with Jalali date
                try:
                    if '_' in timestamp_part:
                        # Handle both manual (YYYYMMDD_HHMMSS) and auto (auto_YYYYMMDD_HHMMSS) backup formats
                        parts = timestamp_part.split('_', 1)  # Split only on first underscore
                        if len(parts) == 2 and parts[0] == 'auto':
                            # Auto backup format: auto_YYYYMMDD_HHMMSS
                            date_time_part = parts[1]
                        else:
                            # Manual backup format: YYYYMMDD_HHMMSS
                            date_time_part = timestamp_part
                        
                        # Split date and time parts
                        date_part, time_part = date_time_part.split('_')
                        
                        # Extract year, month, day
                        year = int(date_part[:4])
                        month = int(date_part[4:6])
                        day = int(date_part[6:8])
                        
                        # Convert Gregorian to Jalali
                        import jdatetime
                        jalali_date = jdatetime.date.fromgregorian(year=year, month=month, day=day)
                        
                        # Format time
                        formatted_time = f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                        
                        # Display in Persian format: 📅 1403/07/17 - 🕒 11:40:06
                        display_text = f"📅 {jalali_date.year}/{jalali_date.month:02d}/{jalali_date.day:02d} - 🕒 {formatted_time}"
                    else:
                        display_text = f"برنامه {i+1} — تاریخ خروج: {timestamp_part}"
                except Exception as e:
                    logger.error(f"Error formatting backup timestamp: {e}")
                    display_text = f"برنامه {i+1} — تاریخ خروج: {timestamp_part}"
                
                # Create action for this backup
                action = menu.addAction(display_text)
                action.triggered.connect(lambda checked, f=backup_file: self.load_backup_file(f))
                
        except Exception as e:
            logger.error(f"Error populating backup history menu: {e}")

    def load_backup_file(self, backup_file):
        """Load a specific backup file and populate the schedule table"""
        try:
            from app.core.data_manager import load_auto_backup
            import json
            
            logger.info(f"Loading backup file: {backup_file}")
            
            # Load data from backup file
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Update user data
            self.user_data = backup_data
            
            # Clear current schedule completely
            self.clear_table_silent()
            
            # Load courses from backup data
            current_schedule = self.user_data.get('current_schedule', [])
            for course_key in current_schedule:
                if course_key in COURSES:
                    self.add_course_to_table(course_key, ask_on_conflict=False)
            
            # Update UI
            self.update_status()
            self.update_stats_panel()
            self.update_detailed_info_if_open()
            
            logger.info(f"Backup successfully loaded and replaced current table: {backup_file}")
            QtWidgets.QMessageBox.information(self, 'موفقیت', 'نسخه پشتیبان با موفقیت بارگذاری شد.')
            
        except Exception as e:
            logger.error(f"Error loading backup file {backup_file}: {e}")
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در بارگذاری نسخه پشتیبان:\n{str(e)}')

    def clear_schedule_table(self):
        """Clear all courses from the schedule table"""
        try:
            # Get all course keys first to avoid dictionary change during iteration
            # Handle both single and dual courses correctly
            course_keys = []
            for info in self.placed.values():
                if info.get('type') == 'dual':
                    # For dual courses, add both courses
                    course_keys.extend(info.get('courses', []))
                else:
                    # For single courses, add the course key
                    course_keys.append(info.get('course'))
            
            # Remove all placed courses
            for course_key in set(course_keys):  # Use set to avoid duplicates
                self.remove_course_from_schedule(course_key)
            
            # Clear the placed dictionary (should already be empty after remove_course_from_schedule)
            self.placed.clear()
            
            # Update UI
            self.update_status()
            self.update_stats_panel()
            
        except Exception as e:
            logger.error(f"Error clearing schedule table: {e}")

    def closeEvent(self, event):
        """Handle application close event - create auto backup before exit"""
        try:
            logger.info("Auto-backup triggered on app exit.")
            
            # Collect currently placed course keys
            # Handle both single and dual courses correctly
            keys = []
            for info in self.placed.values():
                if info.get('type') == 'dual':
                    # For dual courses, add both courses
                    keys.extend(info.get('courses', []))
                else:
                    # For single courses, add the course key
                    keys.append(info.get('course'))
            # Remove duplicates while preserving order
            seen = set()
            unique_keys = []
            for key in keys:
                if key not in seen:
                    seen.add(key)
                    unique_keys.append(key)
            keys = unique_keys
            
            # Update user data with current schedule
            self.user_data['current_schedule'] = keys
            
            # Create auto backup
            from app.core.data_manager import create_auto_backup
            backup_file = create_auto_backup(self.user_data)
            
            if backup_file:
                logger.info(f"Auto-backup created: {backup_file}")
            else:
                logger.error("Failed to create auto-backup")
                
        except Exception as e:
            logger.error(f"Error during auto-backup on exit: {e}")
        
        # Accept the close event
        event.accept()
    
    def update_user_data(self):
        """Update user data with current schedule"""
        keys = []
        for pos, info in self.placed.items():
            if info.get('type') == 'dual':
                keys.append(info.get('odd_key') or info.get('courses', [None])[0])
                keys.append(info.get('even_key') or info.get('courses', [None])[-1])
            else:
                keys.append(info.get('course_key'))
        # Update user data with current schedule
        self.user_data['current_schedule'] = keys

    def manage_golestan_credentials(self):
        """Manage Golestan credentials - view (masked) or remove saved credentials"""
        try:
            from app.core.credentials import LOCAL_CREDENTIALS_FILE, load_local_credentials, delete_local_credentials
            
            # Check if credentials file exists
            if not LOCAL_CREDENTIALS_FILE.exists():
                QtWidgets.QMessageBox.information(
                    self, 
                    "اطلاعات ورود گلستان", 
                    "هیچ اطلاعات ورودی ذخیره‌شده‌ای یافت نشد."
                )
                return
            
            # Load credentials to show masked info
            creds = load_local_credentials()
            if not creds:
                QtWidgets.QMessageBox.warning(
                    self, 
                    "خطا", 
                    "خطا در خواندن اطلاعات ورود ذخیره‌شده."
                )
                return
            
            # Show credential info (masked)
            student_number = creds['student_number']
            masked_student = student_number[:3] + '*' * (len(student_number) - 3) if len(student_number) > 3 else '*' * len(student_number)

            
            reply = QtWidgets.QMessageBox.question(
                self,
                "مدیریت اطلاعات ورود گلستان",
                f"اطلاعات ورود ذخیره‌شده:\n\nشماره دانشجویی: {masked_student}\n\nآیا می‌خواهید این اطلاعات را حذف کنید؟",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                # Delete credentials file
                if delete_local_credentials():
                    QtWidgets.QMessageBox.information(
                        self, 
                        "موفقیت", 
                        "اطلاعات ورود گلستان با موفقیت حذف شد."
                    )
                else:
                    QtWidgets.QMessageBox.warning(
                        self, 
                        "خطا", 
                        "خطا در حذف اطلاعات ورود."
                    )
        except Exception as e:
            logger.error(f"Error managing Golestan credentials: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                "خطا", 
                f"خطا در مدیریت اطلاعات ورود گلستان:\n{str(e)}"
            )

    def _find_existing_compatible_dual(self, course):
        """
        Find existing dual widget that is compatible with the given course.
        This prevents race conditions in dual creation.
        """
        for pos, info in self.placed.items():
            if info.get('type') == 'dual':
                # Check if course is compatible with this dual
                odd_key = info.get('odd_key') or info.get('courses', [None])[0]
                even_key = info.get('even_key') or info.get('courses', [None])[-1]

                odd_course = COURSES.get(odd_key)
                even_course = COURSES.get(even_key)
                
                if self._courses_are_compatible(odd_course, even_course, course):
                    return info
        return None

    def _courses_are_compatible(self, odd_course, even_course, new_course):
        """
        Check if new course is compatible with existing dual courses.
        """
        if not all([odd_course, even_course, new_course]):
            return False
            
        # Check if new course shares time slot with existing dual
        new_schedule = new_course.get('schedule', [])
        odd_schedule = odd_course.get('schedule', [])
        # Implementation of compatibility check
        return self._schedules_overlap(odd_schedule, new_schedule)

    def _schedules_overlap(self, schedule1, schedule2):
        """
        Check if two schedules have overlapping time slots.
        """
        for sess1 in schedule1:
            for sess2 in schedule2:
                if (sess1.get('day') == sess2.get('day') and
                    sess1.get('start') == sess2.get('start') and
                    sess1.get('end') == sess2.get('end')):
                    return True
        return False

    def _update_existing_dual(self, existing_dual, course_key, course):
        """
        Update existing dual instead of creating new one.
        """
        # Implementation would go here
        pass

    def _add_course_or_create_dual(self, course_key, course, ask_on_conflict=True):
        """
        Add course as single or create new dual based on compatibility.
        This is called when no existing compatible dual is found.
        """
        # Implementation would go here
        pass

