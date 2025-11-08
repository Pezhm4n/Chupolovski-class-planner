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
import json
import itertools
import time  # For timing measurements
from collections import deque
from PyQt5.QtCore import QTimer, QMutex, QMutexLocker, Qt

from PyQt5 import QtWidgets, QtGui, QtCore, uic

# Import from our core modules
from app.core.config import (
    COURSES, TIME_SLOTS, EXTENDED_TIME_SLOTS, COLOR_MAP, get_days, get_day_label
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

from .student_profile_dialog import StudentProfileDialog

from .tutorial_dialog import TutorialDialog, show_tutorial

from app.core.credentials import load_local_credentials
from .credentials_dialog import get_golestan_credentials

from ..core.language_manager import language_manager
from ..core.translator import translator
from ..core.i18n import register_widget

logger = setup_logging()

# ---------------------- Main Application Window ----------------------

class SchedulerWindow(QtWidgets.QMainWindow):
    """Main window for the Schedule Planner application"""
    
    def __init__(self, db=None):
        super().__init__()
        
        self.db = db
        
        self.initialize_language()
        
        ui_dir = os.path.dirname(os.path.abspath(__file__))
        main_ui_file = os.path.join(ui_dir, 'main_window.ui')
        
        try:
            uic.loadUi(main_ui_file, self)
            
            # Override layout direction from UI file based on current language
            from app.core.language_manager import language_manager
            current_lang = language_manager.get_current_language()
            if current_lang == 'fa':
                ui_direction = QtCore.Qt.RightToLeft
            else:
                ui_direction = QtCore.Qt.LeftToRight
            
            self.setLayoutDirection(ui_direction)
            
            if hasattr(self, 'schedule_table'):
                self.schedule_table.setLayoutDirection(ui_direction)
                if hasattr(self.schedule_table, 'horizontalHeader'):
                    self.schedule_table.horizontalHeader().setLayoutDirection(ui_direction)
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(
                self, 
                translator.t("common.error"),
                translator.t("messages.ui_file_not_found", path=main_ui_file)
            )
            sys.exit(1)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, 
                translator.t("common.error"),
                translator.t("messages.ui_load_error", error=str(e))
            )
            sys.exit(1)
        
        if os.environ.get('DEBUG'):
            logger.debug(f"[DEBUG] comboBox exists: {hasattr(self, 'comboBox')}")
            if hasattr(self, 'comboBox'):
                logger.debug(f"[DEBUG] comboBox type: {type(self.comboBox)}")
        # Initialize schedule table FIRST
        self.initialize_schedule_table()
        
        self.installEventFilter(self)
        
        if hasattr(self, 'course_list') and self.course_list:
            self.course_list.viewport().installEventFilter(self)
        
        # Initialize status bar
        self.status_bar = self.statusBar()
        
        # Initialize hover debounce timer
        self._hover_timer = QtCore.QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._process_hover_event)
        self._pending_hover_key = None

        
        self.courses = []
        user_data_start = time.time()
        self.user_data = load_user_data()
        user_data_time = time.time() - user_data_start
        if user_data_time > 0.1:
            logger.info(f"User data loaded in {user_data_time:.2f}s")
        if 'saved_combos' not in self.user_data:
            self.user_data['saved_combos'] = []

        self.combinations = []
        self.placed = {}
        self.preview_cells = []
        self.preview_highlighted_widgets = []
        self.last_hover_key = None
    
        self._pulse_timers = {}
        
        self.major_categories = []
        self.current_major_filter = ""
        
        from collections import deque
        from PyQt5.QtCore import QTimer, QMutex

        self.course_addition_queue = deque()
        self.course_addition_timer = QTimer(self)
        self.course_addition_timer.setSingleShot(True)
        self.course_addition_timer.timeout.connect(self._process_course_addition_queue)
        self.course_addition_mutex = QMutex()
        
        self.dual_operation_mutex = QMutex()
        self._init_start_time = time.time()
        self.detailed_info_window = None
        
        self.connect_signals()
        self.create_search_clear_button()
        self.load_and_apply_styles()
        self.create_menu_bar()
        self.update_translations()
        self._register_translatable_widgets()
        self._load_data_async()
        
        self.status_timer = QtCore.QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(10000)  # Update every 10 second
        
        init_time = time.time() - self._init_start_time
        logger.info(f"SchedulerWindow initialized successfully in {init_time:.2f}s")
    
    def _load_data_async(self):
        """Load data asynchronously in background thread"""
        try:
            from .loading_dialog import LoadingDialog
            from .loading_worker import InitialLoadWorker
            
            # Show loading dialog
            self._loading_dialog = LoadingDialog(
                self,
                self._tr_common("loading_data")
            )
            self._loading_dialog.show()
            QtWidgets.QApplication.processEvents()
            
            # Create worker thread
            self._load_worker = InitialLoadWorker(self.db, use_cache=True)
            
            # Connect signals
            def on_progress(message):
                self._loading_dialog.set_message(message)
                QtWidgets.QApplication.processEvents()
            
            def on_courses_loaded(count):
                logger.info(f"Courses loaded signal received: {count} courses")
            
            def on_cache_hit(used_cache):
                if used_cache:
                    logger.info("Using cached course data")
            
            def on_finished(result):
                self._loading_dialog.close()
                
                if isinstance(result, Exception):
                    logger.error(f"Error loading data: {result}")
                    # Fallback to synchronous loading
                    QtWidgets.QMessageBox.warning(
                        self,
                        self._tr_common("warning"),
                        translator.t("messages.error.load_data", error=str(result))
                    )
                    # Try to load minimal data
                    try:
                        from app.core.data_manager import load_courses_from_json
                        load_courses_from_json()
                    except:
                        pass
                else:
                    logger.info("Data loading completed successfully")
                
                # Now populate UI after data is loaded
                self._populate_ui_after_load()
                
                # Log total initialization time
                total_time = time.time() - self._init_start_time
                logger.info(f"=== Total initialization time: {total_time:.2f}s ===")
            
            self._load_worker.progress.connect(on_progress)
            self._load_worker.courses_loaded.connect(on_courses_loaded)
            self._load_worker.cache_hit.connect(on_cache_hit)
            self._load_worker.finished.connect(on_finished)
            
            # Start worker
            self._load_worker.start()
            
        except Exception as e:
            logger.error(f"Error setting up async loading: {e}")
            # Fallback to synchronous loading
            self._load_data_sync()
    
    def _load_data_sync(self):
        """Fallback synchronous data loading"""
        try:
            logger.warning("Falling back to synchronous data loading")
            self.load_courses_from_database()
            self._populate_ui_after_load()
        except Exception as e:
            logger.error(f"Error in synchronous loading: {e}")
    
    def _populate_ui_after_load(self):
        """Populate UI elements after data is loaded"""
        try:
            self.populate_major_dropdown()
            self.populate_course_list()
            self.load_saved_combos_ui()
            self.update_status()
            self.update_stats_panel()
            self.load_latest_backup()
            
        except Exception as e:
            logger.error(f"Error populating UI after load: {e}")
            import traceback
            traceback.print_exc()

    def initialize_language(self):
        """Initialize language and translations before UI creation"""
        try:
            from app.core.language_manager import language_manager, apply_layout_direction
            from app.core.translator import translator
            from PyQt5.QtCore import Qt

            current_lang = language_manager.get_current_language()
            logger.info(f"Main window initializing language: {current_lang}")

            translator.load_translations(current_lang)
            
            app = QtWidgets.QApplication.instance()
            if app is not None:
                if current_lang == 'fa':
                    direction = Qt.RightToLeft
                    app.setLayoutDirection(direction)
                    logger.info(f"Main window: Set application layout direction to RTL (language: {current_lang})")
                else:
                    direction = Qt.LeftToRight
                    app.setLayoutDirection(direction)
                    logger.info(f"Main window: Set application layout direction to LTR (language: {current_lang})")
                
                self.setLayoutDirection(direction)

            logger.info(f"Language initialized to: {current_lang}")

        except Exception as e:
            logger.error(f"Error initializing language: {e}")
            import traceback
            traceback.print_exc()

    def initialize_schedule_table(self):
        """Initialize the schedule table with days and time slots"""
        try:
            from app.core.config import EXTENDED_TIME_SLOTS
            from app.core.translator import translator
            
            headers = [
                translator.t("days.saturday"),
                translator.t("days.sunday"),
                translator.t("days.monday"),
                translator.t("days.tuesday"),
                translator.t("days.wednesday"),
                translator.t("days.thursday"),
                translator.t("days.friday")
            ]

            self.schedule_table.clear()
            
            self.schedule_table.setRowCount(len(EXTENDED_TIME_SLOTS) - 1)
            self.schedule_table.setColumnCount(len(headers))
            
            self.schedule_table.setHorizontalHeaderLabels(headers)
            
            from app.core.language_manager import language_manager
            current_lang = language_manager.get_current_language()
            if current_lang == 'fa':
                table_direction = QtCore.Qt.RightToLeft
            else:
                table_direction = QtCore.Qt.LeftToRight
            self.schedule_table.setLayoutDirection(table_direction)
            self.schedule_table.horizontalHeader().setLayoutDirection(table_direction)
            
            # Configure table appearance
            self.schedule_table.verticalHeader().setVisible(True)
            self.schedule_table.horizontalHeader().setDefaultAlignment(
                QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            self.schedule_table.verticalHeader().setDefaultAlignment(
                QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            self.schedule_table.setShowGrid(False)
            self.schedule_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
            self.schedule_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.schedule_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )
            self.schedule_table.verticalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Fixed
            )
            
            # Set fixed row height for consistent appearance
            row_height = 30
            for i in range(len(EXTENDED_TIME_SLOTS) - 1):
                self.schedule_table.verticalHeader().resizeSection(i, row_height)
                self.schedule_table.setRowHeight(i, row_height)
            
            for i in range(len(EXTENDED_TIME_SLOTS) - 1):
                empty_item = QtWidgets.QTableWidgetItem("")
                self.schedule_table.setVerticalHeaderItem(i, empty_item)
            
            class TimeHeaderView(QtWidgets.QHeaderView):
                def __init__(self, parent_table, time_slots):
                    super().__init__(QtCore.Qt.Vertical, parent_table)
                    self.parent_table = parent_table
                    self.time_slots = time_slots
                    self.hour_positions = {}
                    
                    for hour in range(8, 20):
                        for i in range(len(time_slots) - 1):
                            start_time = time_slots[i]
                            h = int(start_time.split(':')[0])
                            m = int(start_time.split(':')[1])
                            if h == hour and m == 0:
                                self.hour_positions[hour] = i
                                break
                
                def paintEvent(self, event):
                    super().paintEvent(event)
                    painter = QtGui.QPainter(self.viewport())
                    painter.setRenderHint(QtGui.QPainter.Antialiasing)
                    
                    font = QtGui.QFont("IRANSans UI", 14, QtGui.QFont.Bold)
                    painter.setFont(font)
                    painter.setPen(QtGui.QPen(QtGui.QColor("#2c3e50")))
                    
                    viewport_rect = self.viewport().rect()
                    
                    for hour, row_idx in self.hour_positions.items():
                        if row_idx == 0:
                            y_pos_0 = self.sectionViewportPosition(0)
                            row_height_0 = self.sectionSize(0)
                            center_y = y_pos_0 + row_height_0
                        else:
                            prev_row_idx = row_idx - 1
                            y_pos = self.sectionViewportPosition(prev_row_idx)
                            row_height = self.sectionSize(prev_row_idx)
                            center_y = y_pos + row_height
                        
                        text_y = center_y - 9
                        
                        if text_y >= viewport_rect.top() - 15 and text_y <= viewport_rect.bottom() + 15:
                            header_width = self.width()
                            text_rect = QtCore.QRect(0, int(text_y), header_width, 18)
                            painter.drawText(text_rect, QtCore.Qt.AlignCenter, str(hour))
            
            vertical_header = self.schedule_table.verticalHeader()
            time_header = TimeHeaderView(self.schedule_table, EXTENDED_TIME_SLOTS)
            self.schedule_table.setVerticalHeader(time_header)
            time_header.setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
            for i in range(len(EXTENDED_TIME_SLOTS) - 1):
                time_header.resizeSection(i, row_height)
            

            # Add hover effect to cells
            self.schedule_table.cellEntered.connect(self.on_cell_entered)
            # cellExited is not a valid signal, using viewport event filter instead
        

            # Set cell alignment
            self.schedule_table.horizontalHeader().setDefaultAlignment(
                QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
            )

            # Set cell alignment
            for i in range(self.schedule_table.rowCount()):
                for j in range(self.schedule_table.columnCount()):
                    item = self.schedule_table.item(i, j)
                    if item is None:
                        item = QtWidgets.QTableWidgetItem()
                        self.schedule_table.setItem(i, j, item)
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)

            logger.info(f"Schedule table initialized with {len(EXTENDED_TIME_SLOTS) - 1} rows and {len(headers)} columns")
            logger.info(f"Headers: {headers}")
            
        except Exception as e:
            logger.error(f"Failed to initialize schedule table: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_table_init')}: {str(e)}")
            sys.exit(1)
    
    def load_courses_from_database(self):
        """Load courses from database instead of JSON files with enhanced error logging and timing"""
        global COURSES  # Declare global at the beginning of the function
        load_start_time = time.time()
        try:
            if self.db is None:
                # Fallback to JSON loading if no database provided
                from app.core.data_manager import load_courses_from_json
                load_courses_from_json()
                logger.warning("No database instance provided, falling back to JSON loading")
                load_time = time.time() - load_start_time
                logger.info(f"Course loading completed in {load_time:.2f}s")
                return
            
            logger.info("Starting to load courses from database...")
            
            # Check cache first
            from app.core.cache_manager import load_cached_courses, save_cached_courses
            from pathlib import Path
            source_files = [
                Path('app/data/courses_data/available_courses.json'),
                Path('app/data/courses_data/unavailable_courses.json'),
                Path('app/data/courses_data.json')
            ]
            cached_courses = load_cached_courses(source_files)
            
            if cached_courses:
                COURSES.clear()
                COURSES.update(cached_courses)
                load_time = time.time() - load_start_time
                logger.info(f"Loaded {len(COURSES)} courses from cache in {load_time:.2f}s")
                return
            
            # Load courses from database using the proper integration method
            from app.core.golestan_integration import load_courses_from_database
            db_courses = load_courses_from_database(self.db)
            
            if not db_courses:
                logger.warning("Database returned empty course list, falling back to JSON")
                from app.core.data_manager import load_courses_from_json
                load_courses_from_json()
                load_time = time.time() - load_start_time
                logger.info(f"Course loading completed in {load_time:.2f}s")
                return
            
            # Update the global COURSES dictionary
            COURSES.clear()
            COURSES.update(db_courses)
            
            # Load user-added courses (these are still in JSON)
            from app.core.data_manager import load_user_added_courses
            load_user_added_courses()
            
            # Save to cache
            save_cached_courses(COURSES, source_files)
            
            load_time = time.time() - load_start_time
            logger.info(f"Successfully loaded {len(COURSES)} courses from database in {load_time:.2f}s (including {len(db_courses)} from DB and user-added courses)")
            
        except ImportError as e:
            logger.error(f"Import error while loading courses from database: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to JSON loading
            from app.core.data_manager import load_courses_from_json
            load_courses_from_json()
            load_time = time.time() - load_start_time
            logger.info(f"Course loading completed (with errors) in {load_time:.2f}s")
        except Exception as e:
            logger.error(f"Failed to load courses from database: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to JSON loading
            from app.core.data_manager import load_courses_from_json
            load_courses_from_json()
            load_time = time.time() - load_start_time
            logger.info(f"Course loading completed (with errors) in {load_time:.2f}s")



    def generate_unique_key(self, course):
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


    def populate_course_list(self, filter_text=None):
        """Populate course list with optional major filtering"""
        try:
            course_list_widget = None
            if hasattr(self, 'course_list') and self.course_list is not None:
                course_list_widget = self.course_list
            elif hasattr(self, 'course_list_widget') and self.course_list_widget is not None:
                course_list_widget = self.course_list_widget
            elif hasattr(self, 'courselist') and self.courselist is not None:
                course_list_widget = self.courselist
            else:
                course_list_widget = self.findChild(QtWidgets.QListWidget, 'course_list')
                if course_list_widget is None:
                    logger.error("Course list widget not found. Available attributes: " + 
                               ", ".join([attr for attr in dir(self) if 'course' in attr.lower() and not attr.startswith('_')]))
                    return
            
            if self.db is None:
                from app.core.data_manager import load_courses_from_json
                if not COURSES:
                    load_courses_from_json()
            else:
                if not COURSES:
                    self.load_courses_from_database()
            
            search_active = bool(filter_text and filter_text.strip())

            filtered_courses = {}
            major_selected = hasattr(self, 'current_major_filter') and self.current_major_filter and self.current_major_filter.strip() != ""
            if major_selected:
                filtered_courses = {
                    key: course for key, course in COURSES.items()
                    if course.get('major', '').strip() == self.current_major_filter.strip()
                }
                logger.info(f"Filtered to {len(filtered_courses)} courses for major: '{self.current_major_filter}'")
                is_filtered = True
            else:
                if search_active:
                    filtered_courses = dict(COURSES)
                    logger.info("Global search activated without major filter")
                    is_filtered = True
                else:
                    filtered_courses = {}
                    logger.info("No major selected and no search text - showing placeholder")
                    is_filtered = True

            if search_active and filtered_courses:
                filter_text_lower = filter_text.strip().lower()
                filtered_courses = {
                    key: course for key, course in filtered_courses.items()
                    if filter_text_lower in course.get('name', '').lower() or
                       filter_text_lower in course.get('code', '').lower() or
                       filter_text_lower in course.get('instructor', '').lower()
                }
                logger.info(f"Search filtered to {len(filtered_courses)} courses for: '{filter_text}'")
                is_filtered = True
            
            course_list_widget.clear()
            
            if not hasattr(self, 'course_list') or self.course_list is None:
                self.course_list = course_list_widget
            
            if not filtered_courses:
                from app.core.language_manager import language_manager
                current_lang = language_manager.get_current_language()
                placeholder_item = QtWidgets.QListWidgetItem()
                placeholder_item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
                placeholder_item.setForeground(QtGui.QColor(128, 128, 128))

                if search_active:
                    placeholder_text = translator.t("hardcoded_texts.no_search_results")
                elif not major_selected:
                    placeholder_text = translator.t("hardcoded_texts.select_major_placeholder")
                else:
                    placeholder_text = translator.t("hardcoded_texts.no_courses_for_major")

                placeholder_item.setText(placeholder_text)
                course_list_widget.addItem(placeholder_item)
                logger.info("Course list empty after filtering - showing placeholder message")
                
                logger.info(f"Course list populated with {len(filtered_courses)} courses (filtered: {is_filtered})")
                return
            
            # Add courses to list using CourseListWidget for hover preview and conflict indicators
            for course_key, course in filtered_courses.items():
                try:
                    # Create item with course key
                    item = QtWidgets.QListWidgetItem()
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, course_key)
                    item.setSizeHint(QtCore.QSize(200, 60))  # Set size hint for custom widget
                    
                    # Create custom widget for hover preview and conflict indicator
                    item_widget = CourseListWidget(course_key, course, course_list_widget, self)
                    course_list_widget.addItem(item)
                    course_list_widget.setItemWidget(item, item_widget)
                except Exception as e:
                    logger.warning(f"Error creating course list item for {course_key}: {e}")
                    # Fallback to simple text item if custom widget fails
                    course_name = course.get('name', 'Unknown')
                    course_code = course.get('code', '')
                    display_text = f"{course_code}: {course_name}" if course_code else course_name
                    item = QtWidgets.QListWidgetItem(display_text)
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, course_key)
                    course_list_widget.addItem(item)
            
            logger.info(f"Populated course list with {len(filtered_courses)} courses (filtered: {is_filtered})")
            
        except Exception as e:
            logger.error(f"Failed to populate course list: {e}")
            import traceback
            traceback.print_exc()
            major_categories = []
            if self.db is not None:
                # Use database method to get faculties with departments
                faculties_with_departments = self.db.get_faculties_with_departments()
                
                # Build major categories from database data
                for faculty, departments in faculties_with_departments.items():
                    for department in departments:
                        major_identifier = f"{faculty} - {department}"
                        if major_identifier not in major_categories:
                            major_categories.append(major_identifier)
            else:
                for course in COURSES.values():
                    major = course.get('major', '')
                    if major and major.strip() and major != translator.t("messages.unknown_major", fallback="رشته نامشخص"):
                        if major not in major_categories:
                            major_categories.append(major)
        
            # Sort the categories
            major_categories.sort()
        
            user_added_category = "دروس اضافه‌شده توسط کاربر"
            if user_added_category not in major_categories:
                major_categories.insert(0, user_added_category)
            else:
                major_categories.remove(user_added_category)
                major_categories.insert(0, user_added_category)
        
            for major in major_categories:
                self.comboBox.addItem(major)
        
            self.comboBox.setCurrentIndex(0)
            self.major_categories = major_categories
        
            try:
                self.comboBox.currentIndexChanged.disconnect()
            except:
                pass
            self.comboBox.currentIndexChanged.connect(self.on_major_selection_changed)
        
            logger.info(f"Major dropdown populated with {len(major_categories)} majors")
        
        except Exception as e:
            logger.error(f"Failed to populate major dropdown: {e}")
            import traceback
            traceback.print_exc()

    def populate_major_dropdown(self):
        """Populate the major dropdown with unique categories from courses"""
        try:
            from app.core.translator import translator

            if not hasattr(self, 'comboBox'):
                logger.error("comboBox widget not found")
                return

            if self.db is None:
                from app.core.data_manager import load_courses_from_json
                load_courses_from_json()
            else:
                if not COURSES:
                    self.load_courses_from_database()

            self.comboBox.clear()

            default_option = translator.t("combobox.select_major")
            if not isinstance(default_option, str) or default_option.startswith("combobox."):
                from app.core.language_manager import language_manager
                default_option = translator.t("hardcoded_texts.select_major_placeholder")
                if language_manager.get_current_language() == 'fa':
                    default_option = "Select Major"

            self.comboBox.addItem(default_option)

            major_categories = []
            if self.db is not None:
                faculties_with_departments = self.db.get_faculties_with_departments()

                for faculty, departments in faculties_with_departments.items():
                    for department in departments:
                        major_identifier = f"{faculty} - {department}"
                        if major_identifier not in major_categories:
                            major_categories.append(major_identifier)
            else:
                for course in COURSES.values():
                    major = course.get('major', '')
                    if major and major.strip() and major != translator.t("messages.unknown_major", fallback="رشته نامشخص"):
                        if major not in major_categories:
                            major_categories.append(major)

            major_categories.sort()

            user_added_category = "دروس اضافه‌شده توسط کاربر"
            if user_added_category not in major_categories:
                major_categories.insert(0, user_added_category)
            else:
                major_categories.remove(user_added_category)
                major_categories.insert(0, user_added_category)

            for major in major_categories:
                self.comboBox.addItem(major)

            self.comboBox.setCurrentIndex(0)
            self.major_categories = major_categories

            try:
                self.comboBox.currentIndexChanged.disconnect()
            except:
                pass
            self.comboBox.currentIndexChanged.connect(self.on_major_selection_changed)

            logger.info(f"Major dropdown populated with {len(major_categories)} majors")

        except Exception as e:
            logger.error(f"Failed to populate major dropdown: {e}")
            import traceback
            traceback.print_exc()

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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_combo_load')}: {str(e)}")
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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_schedule_clear')}: {str(e)}")
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
            DAYS = get_days()
            row_start = to_minutes(course_times[0]) // 60 - 7
            row_span = (to_minutes(course_times[1]) - to_minutes(course_times[0])) // 60
            col_start = DAYS.index(course_days[0])
            col_span = 1

            # Create an item for the course
            item = QtWidgets.QTableWidgetItem(course_name)

            # Set the item background color
            item.setBackground(QtGui.QColor(COLOR_MAP[course_key]))

            # Set the item alignment
            item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)

            # Set the item user data
            item.setData(QtCore.Qt.ItemDataRole.UserRole, course_key)

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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_course_place')}: {str(e)}")
            sys.exit(1)

    def on_cell_entered(self, row, col):
        """Handle cell enter event"""
        try:
            # Get the item at the cell
            item = self.schedule_table.item(row, col)

            if item:
                course_key = item.data(QtCore.Qt.ItemDataRole.UserRole)
                
                if course_key is None:
                    return
                
                self.last_hover_key = course_key

                if not isinstance(course_key, str):
                    return

                # Get the course details
                course = COURSES.get(course_key)

                if course:
                    if not isinstance(course, dict):
                        logger.error(f"Course data is not a dictionary: {type(course)} - {course}")
                        return
                    
                    course_name = course.get('name', translator.t("messages.unknown"))
                    course_days = []
                    course_times = []
                    schedule = course.get('schedule', [])
                    if isinstance(schedule, list):
                        for session in schedule:
                            if isinstance(session, dict):
                                if session.get('day') and session.get('day') not in course_days:
                                    course_days.append(session['day'])
                                time_range = f"{session.get('start', '')}–{session.get('end', '')}"
                                if time_range not in course_times:
                                    course_times.append(time_range)
                            else:
                                logger.error(f"Session is not a dict: {type(session)} - {session}")

                    # Create a tooltip for the course
                    tooltip = f"{course_name}\nروز‌ها: {', '.join(course_days)}\nزمان‌ها: {', '.join(course_times)}"

                    # Set the tooltip for the cell
                    item.setToolTip(tooltip)

                    # Start pulse animation for the cell
                    self.start_pulse_animation(row, col)
                else:
                    logger.warning(f"Course not found for key: {course_key}")

        except Exception as e:
            logger.error(f"Failed to handle cell enter event: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_cell_enter')}: {str(e)}")

    def on_cell_exited(self, row, col):
        """Handle cell exit event"""
        try:
            # Stop pulse animation for the cell
            self.stop_pulse_animation(row, col)

        except Exception as e:
            logger.error(f"Failed to handle cell exit event: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_cell_exit')}: {str(e)}")
            sys.exit(1)

    def start_pulse_animation(self, row, col):
        """Start pulse animation for a cell"""
        try:
            item = self.schedule_table.item(row, col)

            if item:
                course_key = item.data(QtCore.Qt.ItemDataRole.UserRole)

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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_pulse_start')}: {str(e)}")
            sys.exit(1)

    def stop_pulse_animation(self, row, col):
        """Stop pulse animation for a cell"""
        try:
            item = self.schedule_table.item(row, col)

            if item:
                course_key = item.data(QtCore.Qt.ItemDataRole.UserRole)

                if course_key in self._pulse_timers:
                    pulse_timer = self._pulse_timers[course_key]

                    # Stop the pulse animation
                    pulse_timer.stop()

                    # Remove the pulse timer
                    del self._pulse_timers[course_key]

        except Exception as e:
            logger.error(f"Failed to stop pulse animation: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_pulse_stop')}: {str(e)}")
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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_pulse')}: {str(e)}")
            sys.exit(1)

    def show_detailed_info_window(self, course_key):
        """Show detailed info window for a course"""
        try:
            # Get the course details
            course = next((c for c in COURSES if c['key'] == course_key), None)

            if course:
                # Create and show the detailed info window
                self.detailed_info_window = DetailedInfoWindow(self)
                self.detailed_info_window.show()

        except Exception as e:
            logger.error(f"Failed to show detailed info window: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_info_window')}: {str(e)}")
            sys.exit(1)

    def show_exam_schedule_window(self):
        """Show exam schedule window"""
        try:
            # Create and show the exam schedule window
            self.exam_schedule_window = ExamScheduleWindow(self)
            self.exam_schedule_window.show()

        except Exception as e:
            logger.error(f"Failed to show exam schedule window: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_exam_window')}: {str(e)}")
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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_resize')}: {str(e)}")
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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_search_clear')}: {str(e)}")
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
                    course['major'] = translator.t("hardcoded_texts.user_added_courses")  # Ensure correct category
                    COURSES[course_key] = course
                    
                    # Save user data and user-added courses
                    from app.core.data_manager import save_user_data, save_user_added_courses
                    save_user_data(self.user_data)
                    save_user_added_courses()  # Save to dedicated file
                    
                    # Refresh UI to show the new course immediately
                    self.refresh_ui()
                    
                    # Show confirmation message with translation
                    from app.core.translator import translator
                    title = translator.t("success.operation_successful")
                    message = translator.t("success.course_added")
                    if isinstance(title, dict):
                        title = "Operation Successful"
                    if isinstance(message, dict):
                        message = "Course added successfully"
                    QtWidgets.QMessageBox.information(
                        self, 
                        title, 
                        message
                    )

        except Exception as e:
            logger.error(f"Failed to add course: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_course_add')}: {str(e)}")
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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_course_edit')}: {str(e)}")
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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_course_delete')}: {str(e)}")
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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_combinations')}: {str(e)}")
            sys.exit(1)

    def generate_greedy_schedule(self):
        """Generate a greedy schedule for selected courses"""
        try:
            # Generate a greedy schedule
            schedule = create_greedy_schedule(self.courses)

            self.load_combo(schedule)
            self.update_status()
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to generate greedy schedule: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_greedy_schedule')}: {str(e)}")
            sys.exit(1)

    def generate_alternative_schedule(self):
        """Generate an alternative schedule for selected courses"""
        try:
            schedule = create_alternative_schedule(self.courses, skip_count=0)
            self.load_combo(schedule)

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to generate alternative schedule: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_alternative_schedule')}: {str(e)}")
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
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_info_display')}: {str(e)}")
            sys.exit(1)

    def show_exam_schedule(self):
        """Show exam schedule window"""
        try:
            # Show exam schedule window
            self.show_exam_schedule_window()

        except Exception as e:
            logger.error(f"Failed to show exam schedule: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_exam_display')}: {str(e)}")
            sys.exit(1)

    def show_student_profile(self):
        """Show the student profile dialog."""
        try:
            dialog = StudentProfileDialog(self)
            result = dialog.exec_()
            if result == QtWidgets.QDialog.Rejected:
                logger.debug("Student profile dialog was rejected")
        except Exception as e:
            logger.error(f"Error showing student profile: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                translator.t("hardcoded_texts.error_generic"),
                f"{translator.t('hardcoded_texts.error_profile_display')}: {str(e)}"
            )

    def create_menu_bar(self):
        """Create the application menu bar with data and usage history options"""
        try:
            # Use the menu bar from the UI file if available
            if hasattr(self, 'menubar') and self.menubar is not None:
                menubar = self.menubar
            else:
                # Create menu bar if not available in UI
                menubar = self.menuBar()
            
            # Use the data menu from the UI file if available
            if hasattr(self, 'menu_data') and self.menu_data is not None:
                data_menu = self.menu_data
                
                # Connect the reset Golestan credentials action if it exists in the UI
                if hasattr(self, 'action_reset_golestan_credentials') and self.action_reset_golestan_credentials is not None:
                    # Disconnect any existing connections first to prevent duplicates
                    try:
                        self.action_reset_golestan_credentials.triggered.disconnect(self.reset_golestan_credentials)
                    except TypeError:
                        # No existing connection, that's fine
                        pass
                    self.action_reset_golestan_credentials.triggered.connect(self.reset_golestan_credentials)
                
                # Connect the fetch Golestan action if it exists in the UI
                if hasattr(self, 'action_fetch_golestan') and self.action_fetch_golestan is not None:
                    # Disconnect any existing connections first to prevent duplicates
                    try:
                        self.action_fetch_golestan.triggered.disconnect(self.fetch_from_golestan)
                    except TypeError:
                        # No existing connection, that's fine
                        pass
                    self.action_fetch_golestan.triggered.connect(self.fetch_from_golestan)
                    
                # Connect the manual fetch action if it exists in the UI
                if hasattr(self, 'action_manual_fetch') and self.action_manual_fetch is not None:
                    # Disconnect any existing connections first to prevent duplicates
                    try:
                        self.action_manual_fetch.triggered.disconnect(self.manual_fetch_from_golestan)
                    except TypeError:
                        # No existing connection, that's fine
                        pass
                    self.action_manual_fetch.triggered.connect(self.manual_fetch_from_golestan)
            
            if hasattr(self, 'action_student_profile') and self.action_student_profile is not None:
                try:
                    self.action_student_profile.triggered.disconnect(self.show_student_profile)
                except TypeError:
                    pass
                self.action_student_profile.triggered.connect(self.show_student_profile)
            else:
                student_profile_action = QtWidgets.QAction(self._tr_common("student_profile"), self)
                student_profile_action.triggered.connect(self.show_student_profile)
                if menubar is not None:
                    menubar.addAction(student_profile_action)
                self.student_profile_action = student_profile_action
            
            # Setup language menu
            self.setup_language_menu()
            
            # Create "Usage History" menu
            if menubar is not None:
                history_menu = menubar.addMenu(self._tr_common("usage_history"))
                
                # Add date to menu title
                current_date = datetime.datetime.now().strftime('%Y/%m/%d')
                if history_menu is not None:
                    history_menu.setTitle(self._tr_common("usage_history_with_date", date=current_date))
                self.history_menu = history_menu
                
                # Connect menu to populate with backup history when clicked
                if history_menu is not None:
                    history_menu.aboutToShow.connect(self.populate_backup_history_menu)

                logger.info("Language menu setup completed")

            if hasattr(self, 'action_tutorial') and self.action_tutorial is not None:
                try:
                    self.action_tutorial.triggered.disconnect(self.show_tutorial)
                except (TypeError, RuntimeError):
                    pass
                self.action_tutorial.triggered.connect(self.show_tutorial)
        except Exception as e:
            logger.error(f"Error setting up language menu: {e}")
            import traceback
            traceback.print_exc()

    def _tr_common(self, key, **kwargs):
        """Shortcut for translating common strings."""
        try:
            from app.core.translator import translator
            return translator.t(f"common.{key}", **kwargs)
        except Exception:
            return key

    def _register_translatable_widgets(self):
        """Register static UI widgets with the translation registry."""
        try:
            # Group boxes
            if hasattr(self, 'search_group'):
                register_widget(self.search_group, "dialogs.search.title", method="setTitle")
            if hasattr(self, 'course_list_group'):
                register_widget(self.course_list_group, "dialogs.course_list.title", method="setTitle")
            if hasattr(self, 'actions_group'):
                register_widget(self.actions_group, "dialogs.actions.title", method="setTitle")
            if hasattr(self, 'info_group'):
                register_widget(self.info_group, "dialogs.info.title", method="setTitle")
            if hasattr(self, 'stats_group'):
                register_widget(self.stats_group, "dialogs.stats.title", method="setTitle")
            if hasattr(self, 'notifications_group'):
                register_widget(self.notifications_group, "dialogs.notifications.title", method="setTitle")
            if hasattr(self, 'auto_select_group'):
                register_widget(self.auto_select_group, "dialogs.auto_select.title", method="setTitle")
            if hasattr(self, 'saved_combos_group'):
                register_widget(self.saved_combos_group, "dialogs.saved_combos.title", method="setTitle")

            # Buttons
            if hasattr(self, 'success_btn'):
                register_widget(self.success_btn, "buttons.add_course")
            if hasattr(self, 'detailed_info_btn'):
                register_widget(self.detailed_info_btn, "buttons.save_schedule")
            if hasattr(self, 'clear_schedule_btn'):
                register_widget(self.clear_schedule_btn, "buttons.clear_schedule")
            if hasattr(self, 'showExamPagebtn'):
                register_widget(self.showExamPagebtn, "buttons.show_exam_page")
            if hasattr(self, 'optimal_schedule_btn'):
                register_widget(self.optimal_schedule_btn, "buttons.generate_optimal")
            if hasattr(self, 'add_to_auto_btn'):
                register_widget(self.add_to_auto_btn, "buttons.add")
            if hasattr(self, 'remove_from_auto_btn'):
                register_widget(self.remove_from_auto_btn, "buttons.remove")

            # Labels and placeholders
            if hasattr(self, 'course_info_label'):
                register_widget(self.course_info_label, "labels.course_info")
            if hasattr(self, 'stats_label'):
                register_widget(self.stats_label, "labels.stats")
            if hasattr(self, 'notifications_label'):
                register_widget(self.notifications_label, "labels.notifications")
            if hasattr(self, 'search_box'):
                register_widget(self.search_box, "placeholders.search", method="setPlaceholderText")

            # Menu items
            if hasattr(self, 'menu_data'):
                register_widget(self.menu_data, "menu.data", method="setTitle")
            if hasattr(self, 'menu_tools'):
                register_widget(self.menu_tools, "menu.tools", method="setTitle")
            if hasattr(self, 'menu_help'):
                register_widget(self.menu_help, "menu.help", method="setTitle")
            if hasattr(self, 'menu_language'):
                register_widget(self.menu_language, "menu.language", method="setTitle")
            if hasattr(self, 'action_fetch_golestan'):
                register_widget(self.action_fetch_golestan, "menu.auto_fetch")
            if hasattr(self, 'action_manual_fetch'):
                register_widget(self.action_manual_fetch, "menu.manual_fetch")
            if hasattr(self, 'action_reset_golestan_credentials'):
                register_widget(self.action_reset_golestan_credentials, "menu.reset_golestan")
            if hasattr(self, 'action_show_exam_schedule'):
                register_widget(self.action_show_exam_schedule, "menu.exam_schedule")
            if hasattr(self, 'action_export_exam_schedule'):
                register_widget(self.action_export_exam_schedule, "menu.export_exam_schedule")
            if hasattr(self, 'action_tutorial'):
                register_widget(self.action_tutorial, "menu.tutorial")
            if hasattr(self, 'action_student_profile'):
                register_widget(self.action_student_profile, "common.student_profile")
            if hasattr(self, 'student_profile_action'):
                register_widget(self.student_profile_action, "common.student_profile")
            if hasattr(self, 'history_menu'):
                register_widget(
                    self.history_menu,
                    None,
                    method="setTitle",
                    callback=lambda: self._tr_common(
                        "usage_history_with_date",
                        date=datetime.datetime.now().strftime('%Y/%m/%d')
                    ),
                )

            # Language actions keep native names
            if hasattr(self, 'persian_action'):
                register_widget(self.persian_action, None, fallback="فارسی")
            if hasattr(self, 'english_action'):
                register_widget(self.english_action, None, fallback="English")
        except Exception as exc:
            logger.warning(f"translation_registry_setup_failed: {exc}")

    def setup_language_menu(self):
        """Setup the language menu with Persian and English options"""
        try:
            from app.core.language_manager import language_manager
            
            # Check if language actions exist in the UI
            if hasattr(self, 'action_persian') and hasattr(self, 'action_english'):
                # Store references to language actions
                self.persian_action = self.action_persian
                self.english_action = self.action_english
                
                # Set up exclusive group for language actions
                self.language_group = QtWidgets.QActionGroup(self)
                self.language_group.setExclusive(True)
                self.language_group.addAction(self.persian_action)
                self.language_group.addAction(self.english_action)
                
                # Disconnect any existing connections first to prevent duplicates
                try:
                    self.persian_action.triggered.disconnect()
                except (TypeError, RuntimeError):
                    pass  # No existing connection, that's fine
                
                try:
                    self.english_action.triggered.disconnect()
                except (TypeError, RuntimeError):
                    pass  # No existing connection, that's fine
                
                # Connect language change signals with proper signal management
                self.persian_action.triggered.connect(lambda: self.change_language("fa"))
                self.english_action.triggered.connect(lambda: self.change_language("en"))
                
                # Set initial checked state based on current language
                current_lang = language_manager.get_current_language()
                self.persian_action.setChecked(current_lang == "fa")
                self.english_action.setChecked(current_lang == "en")
                
                # Disconnect any existing language_changed connections to prevent duplicates
                try:
                    language_manager.language_changed.disconnect(self.on_language_changed)
                except (TypeError, RuntimeError):
                    pass  # No existing connection, that's fine
                
                # Connect to language manager's language_changed signal
                language_manager.language_changed.connect(self.on_language_changed)
                
                logger.info("Language menu setup completed successfully")
            else:
                logger.warning("Language actions not found in UI")
                
        except Exception as e:
            logger.error(f"Error setting up language menu: {e}")
            import traceback
            traceback.print_exc()

    def on_major_selection_changed(self, index):
        """Handle major selection changes in the dropdown - FIXED to properly check for empty strings and prevent showing all courses"""
        try:
            # Check if index is valid and comboBox exists
            if not hasattr(self, 'comboBox') or index < 0:
                return
            
            # Get the selected text
            selected_text = self.comboBox.itemText(index)
            
            # Check for empty string or placeholder selection (including "انتخاب رشته" / "Select Major")
            if not selected_text or selected_text.strip() == "":
                self.current_major_filter = ""
            else:
                # Check if it's a placeholder text
                placeholder = translator.t("combobox.select_major")
                
                if selected_text == placeholder:
                    self.current_major_filter = ""
                else:
                    # Valid major selected
                    self.current_major_filter = selected_text.strip()
            
            # Refresh the course list with the new filter
            # This will show empty list if no major is selected (for performance)
            self.populate_course_list()
            
            logger.info(f"Major filter changed to: '{self.current_major_filter}' (empty means no major selected)")
            
        except Exception as e:
            logger.error(f"Error in on_major_selection_changed: {e}")
            import traceback
            traceback.print_exc()

    def change_language(self, lang_code):
        """Change application language dynamically without restart"""
        try:
            from app.core.language_manager import language_manager
            from app.core.translator import translator

            current_lang = language_manager.get_current_language()

            if current_lang == lang_code:
                return

            # Check if there are courses in the schedule
            # Also check the table directly to ensure we catch all cases
            has_courses = False
            if hasattr(self, 'placed') and self.placed:
                has_courses = True
            elif hasattr(self, 'schedule_table'):
                # Check if table has any widgets (courses)
                for row in range(self.schedule_table.rowCount()):
                    for col in range(self.schedule_table.columnCount()):
                        if self.schedule_table.cellWidget(row, col):
                            has_courses = True
                            break
                    if has_courses:
                        break
            
            if has_courses:
                # Ask for confirmation before changing language
                lang_name = translator.t("language.persian") if lang_code == "fa" else translator.t("language.english")
                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setIcon(QtWidgets.QMessageBox.Question)
                msg_box.setWindowTitle(translator.t("messages.change_language_title"))
                msg_box.setText(translator.t("messages.change_language_confirmation", lang=lang_name))
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
                
                # Set layout direction based on current language
                if current_lang == 'fa':
                    msg_box.setLayoutDirection(QtCore.Qt.RightToLeft)
                else:
                    msg_box.setLayoutDirection(QtCore.Qt.LeftToRight)
                
                reply = msg_box.exec_()
                
                if reply != QtWidgets.QMessageBox.Yes:
                    # Restore radio button state to previous language
                    if hasattr(self, 'persian_action') and hasattr(self, 'english_action'):
                        if current_lang == 'fa':
                            self.persian_action.setChecked(True)
                            self.english_action.setChecked(False)
                        else:
                            self.persian_action.setChecked(False)
                            self.english_action.setChecked(True)
                    return
            
            # Save current courses before language change
            saved_courses = []
            if has_courses:
                from app.core.config import COURSES
                for key, info in list(self.placed.items()):
                    # Handle different structures of self.placed
                    if isinstance(info, dict):
                        if info.get('type') == 'dual':
                            # For dual courses, save both course keys
                            courses = info.get('courses', [])
                            for course_key in courses:
                                if course_key and course_key in COURSES:
                                    saved_courses.append(course_key)
                        else:
                            # For single courses, save the course key
                            course_key = info.get('course')
                            if course_key and course_key in COURSES:
                                saved_courses.append(course_key)
                    elif isinstance(key, str):
                        # Old structure: key is course_key directly
                        if key in COURSES:
                            saved_courses.append(key)
                
                # Remove duplicates while preserving order
                saved_courses = list(dict.fromkeys(saved_courses))
            
            # Save language preference
            language_manager.set_language(lang_code)
            
            # Restore courses after language change
            if saved_courses:
                # Use QTimer to restore courses after UI updates
                QtCore.QTimer.singleShot(500, lambda: self._restore_courses_after_language_change(saved_courses))

        except Exception as e:
            logger.error(f"Error changing language: {e}")
            import traceback
            traceback.print_exc()

    def restart_application(self):
        """Restart the application cleanly without causing hanging or crashing"""
        try:
            from PyQt5.QtCore import QProcess
            import sys
            import os

            # Close the current window
            self.close()

            # Restart application using QProcess.startDetached
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                QProcess.startDetached(sys.executable, sys.argv)
            else:
                # Running as script
                QProcess.startDetached(sys.executable, [sys.argv[0]] + sys.argv[1:])

            # Quit current application
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.quit()

        except Exception as e:
            logger.error(f"Error restarting application: {e}")
            import traceback
            traceback.print_exc()

    def on_language_changed(self, lang_code):
        """Handle language change event - Fixed to prevent hanging with QTimer"""
        try:
            # Use QTimer.singleShot to make it non-blocking and prevent hanging
            QtCore.QTimer.singleShot(0, lambda: self._update_language_ui(lang_code))
        except Exception as e:
            logger.error(f"Error handling language change: {e}")
    
    def _update_language_ui(self, lang_code):
        """Update UI after language change - called asynchronously"""
        try:
            from app.core.translator import translator
            from app.core.language_manager import language_manager
            
            # Reload translations for the new language
            translator.load_translations(lang_code)
            
            # Update layout direction first (before UI updates)
            from app.core.language_manager import apply_layout_direction
            apply_layout_direction(self)
            
            # Update font
            font_family = translator.get_meta("font_family")
            if font_family:
                from app.core.language_manager import apply_font
                app = QtWidgets.QApplication.instance()
                if app is not None:
                    apply_font(app)
            
            # Update schedule table layout direction
            if hasattr(self, 'schedule_table'):
                if lang_code == 'fa':
                    table_direction = QtCore.Qt.RightToLeft
                else:
                    table_direction = QtCore.Qt.LeftToRight
                self.schedule_table.setLayoutDirection(table_direction)
                self.schedule_table.horizontalHeader().setLayoutDirection(table_direction)
                # Update only headers without clearing table content
                self.update_schedule_table_headers_only()
            
            # Update all UI elements (non-blocking)
            QtCore.QTimer.singleShot(10, lambda: self.update_translations())
            
            # Update language selection checkboxes
            if hasattr(self, 'persian_action') and hasattr(self, 'english_action'):
                self.persian_action.setChecked(lang_code == "fa")
                self.english_action.setChecked(lang_code == "en")
                
        except Exception as e:
            logger.error(f"Error updating language UI: {e}")
            import traceback
            traceback.print_exc()

    def update_translations(self):
        """Update all UI element translations - Fixed to prevent hanging/crashing"""
        try:
            from app.core.i18n import translation_registry
            from app.core.translator import translator
            
            # Apply registered translations first
            translation_registry.refresh_all()

            # Update window title
            app_title = translator.t("app.title")
            version = translator.t("app.version", **{"0": "2.1"})
            self.setWindowTitle(f"🎓 {app_title} - {version}")
            
            # Update menu items
            # Update combo box
            if hasattr(self, 'comboBox'):
                # Save current index
                current_index = self.comboBox.currentIndex()
                current_data = self.comboBox.currentData()
                placeholder = translator.t("combobox.select_major")
                self.comboBox.blockSignals(True)
                self.comboBox.clear()
                self.comboBox.addItem(placeholder, None)
                for major in getattr(self, 'major_categories', []):
                    self.comboBox.addItem(major)
                if current_index >= 0 and current_index < self.comboBox.count():
                    self.comboBox.setCurrentIndex(current_index)
                elif current_data is not None:
                    index = self.comboBox.findData(current_data)
                    if index >= 0:
                        self.comboBox.setCurrentIndex(index)
                self.comboBox.blockSignals(False)
            
            self.retranslate_schedule_table()
            
            logger.info("UI translations updated successfully")
        except Exception as e:
            logger.error(f"Error updating translations: {e}")
            import traceback
            traceback.print_exc()

    def save_user_data(self):
        """Save user data"""
        try:
            # Get the directory of this file
            data_dir = os.path.join(os.path.expanduser("~"), ".schedule_planner")

            if not os.path.exists(data_dir):
                os.makedirs(data_dir)

            data_file = os.path.join(data_dir, 'user_data.json')
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to save user data: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_user_data_save')}: {str(e)}")
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
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    self.user_data = json.load(f)
            else:
                # Initialize with default structure if file doesn't exist
                self.user_data = {
                    'custom_courses': [],
                    'saved_combos': [],
                    'current_schedule': []
                }

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to load user data: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_user_data_load')}: {str(e)}")
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
                QtWidgets.QMessageBox.critical(
                    self, 
                    translator.t("common.error"),
                    translator.t("messages.ui_file_not_found", path=stats_widget_ui_file)
                )
                sys.exit(1)
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, 
                    translator.t("common.error"),
                    translator.t("messages.ui_load_error", error=str(e))
                )
                sys.exit(1)

            # Set layout direction
            self.stats_widget.setLayoutDirection(QtCore.Qt.LayoutDirection.RightToLeft)

            # Add the stats widget to the main window
            self.setCentralWidget(self.stats_widget)

            # Update the stats panel
            self.update_stats_panel()

        except Exception as e:
            logger.error(f"Failed to debug stats widget: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_stats_test')}: {str(e)}")
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
                if item and item.data(QtCore.Qt.ItemDataRole.UserRole) == course_key:
                    # Priority is stored in UserRole + 1 (1 = highest priority)
                    priority = item.data(QtCore.Qt.ItemDataRole.UserRole + 1)
                    if priority is not None:
                        return priority
        
        # Default priority if not found in auto-select list
        return 999



    def convert_to_persian_numerals(self, time_str):
        """Convert English numerals in time string to Persian numerals"""
        english_to_persian = {
            '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
            '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'
        }
        
        result = ""
        for char in time_str:
            if char is not None:
                result += english_to_persian.get(char, char or "")
            else:
                result += ""
        return result

    def update_schedule_table_headers_only(self):
        """Update schedule table headers only without clearing table content"""
        try:
            from app.core.translator import translator
            
            headers = [
                translator.t("days.saturday"),
                translator.t("days.sunday"),
                translator.t("days.monday"),
                translator.t("days.tuesday"),
                translator.t("days.wednesday"),
                translator.t("days.thursday"),
                translator.t("days.friday")
            ]
            
            self.schedule_table.setHorizontalHeaderLabels(headers)
            logger.info(f"Schedule table headers updated: {headers}")
            
        except Exception as e:
            logger.error(f"Failed to update schedule table headers: {e}")
    
    def retranslate_schedule_table(self):
        """Re-translate schedule table headers (alias for update_schedule_table_headers_only)"""
        self.update_schedule_table_headers_only()
    
    def _restore_courses_after_language_change(self, course_keys):
        """Restore courses to schedule table after language change"""
        try:
            from app.core.config import COURSES
            
            if not course_keys:
                logger.info("No courses to restore after language change")
                return
            
            # Clear current schedule silently
            self.clear_table_silent()
            
            # Wait a bit for UI to update
            QtWidgets.QApplication.processEvents()
            QtCore.QThread.msleep(100)
            
            # Restore courses one by one
            restored_count = 0
            for course_key in course_keys:
                if course_key in COURSES:
                    try:
                        # Add course without asking for conflicts (they were already resolved)
                        self.add_course_to_table(course_key, ask_on_conflict=False)
                        restored_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to restore course {course_key} after language change: {e}")
            
            # Process any queued course additions
            if hasattr(self, 'course_addition_queue') and self.course_addition_queue:
                # Wait for queue to be processed
                max_wait = 50  # Maximum 5 seconds
                wait_count = 0
                while self.course_addition_queue and wait_count < max_wait:
                    QtWidgets.QApplication.processEvents()
                    QtCore.QThread.msleep(100)
                    wait_count += 1
                
                # Process the queue
                self._process_course_addition_queue()
            
            # Final wait to ensure UI updates
            QtWidgets.QApplication.processEvents()
            QtCore.QThread.msleep(200)
            
            logger.info(f"Restored {restored_count} out of {len(course_keys)} courses after language change")
            
        except Exception as e:
            logger.error(f"Error restoring courses after language change: {e}")
            import traceback
            traceback.print_exc()


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
                if layout is not None:
                    layout.setContentsMargins(0, 0, 0, 0)
                    layout.setSpacing(4)  # Set to 4px as required
            
            # Reduce margins in left panel layout
            if hasattr(self, 'left_panel') and self.left_panel.layout():
                layout = self.left_panel.layout()
                if layout is not None:
                    layout.setContentsMargins(4, 4, 4, 4)  # Set to 4px margins
                    layout.setSpacing(4)  # Set to 4px spacing
                
            # Reduce margins in center panel layout
            if hasattr(self, 'center_panel') and self.center_panel.layout():
                layout = self.center_panel.layout()
                if layout is not None:
                    layout.setContentsMargins(0, 0, 0, 0)  # Minimal margins
                    layout.setSpacing(4)  # Set to 4px spacing
                
            # Reduce margins in right panel layout
            if hasattr(self, 'right_panel') and self.right_panel.layout():
                layout = self.right_panel.layout()
                if layout is not None:
                    layout.setContentsMargins(4, 4, 4, 4)  # Set to 4px margins
                    layout.setSpacing(4)  # Set to 4px spacing
                
            # Reduce margins in all group boxes
            for group_box in self.findChildren(QtWidgets.QGroupBox):
                if group_box.layout():
                    layout = group_box.layout()
                    if layout is not None:
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

    def showEvent(self, event):
        super().showEvent(event)

    def resizeEvent(self, a0):
        try:
            super().resizeEvent(a0)
            
            if hasattr(self, 'main_splitter'):
                window_width = self.width()
                left_width = max(280, int(window_width * 0.25))
                center_width = max(600, int(window_width * 0.50))
                right_width = max(250, int(window_width * 0.25))
                self.main_splitter.setSizes([left_width, center_width, right_width])
            
            self.reduce_layout_margins()
            
        except Exception as e:
            logger.error(f"Error in resizeEvent: {e}")

    def update_status(self):
        """Update status bar with accurate Persian date and time"""
        try:
            import jdatetime
            
            # تنظیم locale برای فارسی
            jdatetime.set_locale(jdatetime.FA_LOCALE)
            now = jdatetime.datetime.now()
            
            persian_weekdays = {
                0: 'شنبه',
                1: 'یکشنبه',
                2: 'دوشنبه',
                3: 'سه‌شنبه',
                4: 'چهارشنبه',
                5: 'پنج‌شنبه',
                6: 'جمعه'
            }
            
            persian_months = {
                1: 'فروردین', 2: 'اردیبهشت', 3: 'خرداد',
                4: 'تیر', 5: 'مرداد', 6: 'شهریور',
                7: 'مهر', 8: 'آبان', 9: 'آذر',
                10: 'دی', 11: 'بهمن', 12: 'اسفند'
            }
            
            persian_year = now.year
            persian_month = now.month
            persian_day = now.day
            weekday = now.weekday()
            
            time_str = now.strftime('%H:%M')
            weekday_name = persian_weekdays.get(weekday, '')
            month_name = persian_months.get(persian_month, '')
            persian_date_str = f'{persian_day} {month_name} {persian_year}'
            
            status_text = f'{weekday_name} - {persian_date_str} - {time_str}'
            if self.status_bar is not None:
                self.status_bar.showMessage(status_text)
            
            status_font = QtGui.QFont('IRANSans UI', 11, QtGui.QFont.Bold)
            if self.status_bar is not None:
                self.status_bar.setFont(status_font)
                
        except ImportError:
            self.update_status_fallback()
        except Exception as e:
            print(f"خطا در به‌روزرسانی وضعیت: {e}")
            self.update_status_fallback()

    def debug_stats_widget_v2(self):
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
                logger.debug(f"Found widget: {widget_name}")
                return widget
            else:
                logger.debug(f"Widget not found: {widget_name}")
        
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
                        logger.debug(f"Found stats widget: {type(widget)}")
                    break
            
            if not stats_widget:
                if os.environ.get('DEBUG'):
                    logger.debug("No stats widget found!")
                all_labels = self.findChildren(QtWidgets.QLabel)
                for label in all_labels:
                    if 'آمار' in label.text() or 'stats' in label.objectName().lower():
                        stats_widget = label
                        if os.environ.get('DEBUG'):
                            logger.debug(f"Found by search: {label.objectName()}")
                        break
            
            if not stats_widget:
                if os.environ.get('DEBUG'):
                    logger.debug("Still no stats widget found!")
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
                    logger.debug(f"Found {len(keys)} courses")
                
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
                
                # متن آمار با ترجمه
                from app.core.translator import translator
                stats_text = f"""{translator.t('messages.stats_title')}

{translator.t('messages.stats_courses', count=len(keys))}
{translator.t('messages.stats_units', units=total_units)}
{translator.t('messages.stats_sessions', sessions=total_sessions)}
{translator.t('messages.stats_days', days=len(days_used))}
{translator.t('messages.stats_status')}"""

                if os.environ.get('DEBUG'):
                    logger.debug(f"Setting stats text: {stats_text[:100]}...")
                stats_widget.setText(stats_text)
                
            else:
                if os.environ.get('DEBUG'):
                    logger.debug("No courses placed")
                from app.core.translator import translator
                stats_widget.setText(f"""{translator.t('messages.stats_empty_title')}

{translator.t('messages.stats_empty_message')}

{translator.t('messages.stats_empty_hint')}""")
                
            stats_widget.update()
            stats_widget.repaint()
            
        except Exception as e:
            logger.error(f"Error in update_stats_panel: {e}")
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
        month_name = persian_months[now.month - 1] if 1 <= now.month <= 12 else translator.t("messages.unknown")
        
        time_str = now.strftime('%H:%M:%S')
        date_str = f'{now.day} {month_name} {now.year}'
        
        status_text = f'{weekday} - {date_str} - {time_str} (تقریبی)'
        
        if self.status_bar is not None:
            self.status_bar.showMessage(status_text)

    def on_course_clicked(self, item):
        """Handle course selection from the list with enhanced debugging"""
        # Make sure QtWidgets is available in this scope
        
        try:
            if item is None:
                logger.warning("on_course_clicked called with None item")
                return
                
            key = item.data(QtCore.Qt.ItemDataRole.UserRole)
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
                # Use reasonable debounce - processing will handle synchronization
                self.course_addition_timer.start(100)  # 100ms debounce for responsive UI
                
                # Update course info panel
                if hasattr(self, 'course_info_label'):
                    course = COURSES.get(key, {})
                    unknown_text = translator.t("messages.unknown")
                    info_text = f"""{translator.t('course_details.course_name')}: {course.get('name', unknown_text)}
{translator.t('course_details.course_code')}: {course.get('code', unknown_text)}
{translator.t('course_details.instructor')}: {course.get('instructor', unknown_text)}
{translator.t('course_details.credits')}: {course.get('credits', unknown_text)}
{translator.t('course_details.location')}: {course.get('location', unknown_text)}"""
                    self.course_info_label.setText(info_text)
                
                # Update stats panel
                print("🔄 Calling update_stats_panel from on_course_clicked")
                self.update_stats_panel()
            else:
                logger.warning(f"Course item clicked but no key found in UserRole data")
                QtWidgets.QMessageBox.warning(
                    self, translator.t("hardcoded_texts.error_generic"), 
                    translator.t("hardcoded_texts.error_course_select")
                )
        except Exception as e:
            logger.error(f"Error in on_course_clicked: {e}")
            QtWidgets.QMessageBox.critical(
                self, translator.t("hardcoded_texts.system_error"), 
                f"{translator.t('hardcoded_texts.error_course_select_unexpected')}:\n{str(e)}"
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
        
        title_label = QtWidgets.QLabel(f"{translator.t('hardcoded_texts.combination')} {index + 1}")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        
        # Stats badges
        stats_widget = QtWidgets.QWidget()
        stats_layout = QtWidgets.QHBoxLayout(stats_widget)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        
        days_badge = QtWidgets.QLabel(
            translator.t("stats.days_badge", value=combo["days"])
        )
        days_badge.setStyleSheet("background-color: #3498db; color: white; border-radius: 12px; padding: 4px 12px; font-size: 12px; font-weight: bold;")
        register_widget(
            days_badge,
            None,
            callback=lambda value=combo["days"]: translator.t("stats.days_badge", value=value),
        )
        
        empty_badge_value = f"{combo['empty']:.1f}"
        empty_badge = QtWidgets.QLabel(
            translator.t("stats.empty_badge", value=empty_badge_value)
        )
        empty_badge.setStyleSheet("background-color: #2ecc71; color: white; border-radius: 12px; padding: 4px 12px; font-size: 12px; font-weight: bold;")
        register_widget(
            empty_badge,
            None,
            callback=lambda value=empty_badge_value: translator.t("stats.empty_badge", value=value),
        )
        
        courses_count = len(combo["courses"])
        courses_badge = QtWidgets.QLabel(
            translator.t("stats.courses_badge", value=courses_count)
        )
        courses_badge.setStyleSheet("background-color: #9b59b6; color: white; border-radius: 12px; padding: 4px 12px; font-size: 12px; font-weight: bold;")
        register_widget(
            courses_badge,
            None,
            callback=lambda value=courses_count: translator.t("stats.courses_badge", value=value),
        )
        
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
        
        apply_btn = QtWidgets.QPushButton(translator.t("buttons.apply_combo"))
        apply_btn.setObjectName("success_btn")
        apply_btn.setMinimumHeight(35)
        apply_btn.clicked.connect(lambda checked, idx=index: self.apply_preset(idx))
        register_widget(apply_btn, "buttons.apply_combo")
        
        details_btn = QtWidgets.QPushButton(translator.t("buttons.details"))
        details_btn.setObjectName("detailed_info_btn")
        details_btn.setMinimumHeight(35)
        details_btn.clicked.connect(lambda checked, c=combo: self.show_combination_details(c))
        register_widget(details_btn, "buttons.details")
        
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
                    f"{course['name']} — {course['code']} — {course.get('instructor', translator.t('hardcoded_texts.unknown'))}"
                )
                course_list.addItem(item)
        
        layout.addWidget(course_list)
        
        # Footer with total credits
        footer_widget = QtWidgets.QWidget()
        footer_layout = QtWidgets.QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        
        credits_label = QtWidgets.QLabel(
            translator.t("stats.total_credits", value=total_credits)
        )
        credits_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e74c3c;")
        register_widget(
            credits_label,
            None,
            callback=lambda value=total_credits: translator.t("stats.total_credits", value=value),
        )
        
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
            self,
            translator.t("success.title"),
            translator.t(
                "success.preset_applied",
                index=idx + 1,
                count=success_count,
                days=combo["days"],
                empty=f"{combo['empty']:.1f}"
            ),
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
            QtWidgets.QMessageBox.information(
                self,
                translator.t("common.info"),
                translator.t("messages.schedule_empty")
            )
            return
            
        # Ask for confirmation
        res = QtWidgets.QMessageBox.question(
            self,
            translator.t("menu.clear_schedule"),
            translator.t("dialogs.confirm.clear_schedule"),
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
        
        
        QtWidgets.QMessageBox.information(
            self,
            translator.t("messages.schedule_cleared_title"),
            translator.t("messages.schedule_cleared_text")
        )

    # ---------------------- eventFilter for hover ----------------------
    def eventFilter(self, a0, a1):
        """Handle hover events for course preview with debouncing and improved position mapping"""
        # Check if course_list exists and is not None before accessing it
        if hasattr(self, 'course_list') and self.course_list is not None and (a0 == self.course_list.viewport() or a0 == self.course_list):
            if a1 is not None and a1.type() == QtCore.QEvent.Type.MouseMove:
                try:
                    # Map position correctly whether from viewport or list widget
                    pos = self.course_list.viewport().mapFromGlobal(QtGui.QCursor.pos())
                    
                    if pos is not None:
                        item = self.course_list.itemAt(pos)
                        if item:
                            key = item.data(QtCore.Qt.ItemDataRole.UserRole)
                            if key and getattr(self, 'last_hover_key', None) != key:
                                # Debounce hover events to reduce redundant refreshes
                                self._pending_hover_key = key
                                self._hover_timer.start(50)  # 50ms debounce
                        else:
                            # Clear preview when not hovering over an item
                            if hasattr(self, 'last_hover_key') and self.last_hover_key:
                                self._hover_timer.stop()
                                self._pending_hover_key = None
                                self.last_hover_key = None
                                self.clear_preview()
                except Exception as e:
                    logger.warning(f"Error in eventFilter hover handling: {e}")
            elif a1 is not None and a1.type() == QtCore.QEvent.Type.Leave:
                # Clear preview when mouse leaves the course list entirely
                try:
                    self._hover_timer.stop()
                    self._pending_hover_key = None
                    if hasattr(self, 'last_hover_key') and self.last_hover_key:
                        self.last_hover_key = None
                        self.clear_preview()
                except Exception as e:
                    logger.warning(f"Error clearing hover preview: {e}")
        
        return super().eventFilter(a0, a1)
    
    def _process_hover_event(self):
        """Process debounced hover event"""
        try:
            if self._pending_hover_key:
                key = self._pending_hover_key
                self._pending_hover_key = None
                if key != getattr(self, 'last_hover_key', None):
                    self.last_hover_key = key
                    self.clear_preview()
                    self.preview_course(key)
        except Exception as e:
            logger.warning(f"Error processing hover event: {e}")
    
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
            
        # Get translated day names
        from app.core.config import get_days
        DAYS = get_days()
        
        placements = []
        for sess in course['schedule']:
            if sess['day'] not in DAYS:
                continue
            col = DAYS.index(sess['day'])
            try:
                srow = EXTENDED_TIME_SLOTS.index(sess['start'])
                erow = EXTENDED_TIME_SLOTS.index(sess['end'])
            except ValueError:
                QtWidgets.QMessageBox.warning(
                    self,
                    translator.t("common.warning"),
                    translator.t(
                        "messages.invalid_time",
                        course=course["name"],
                        time_range=f"{sess['start']}-{sess['end']}"
                    )
                )
                continue
            span = max(1, erow - srow)
            placements.append((srow, col, span, sess))
            
        for srow, col, span, sess in placements:
            try:
                existing_widget = self.schedule_table.cellWidget(srow, col)
                existing_info = self.placed.get((srow, col))

                # Handle preview when slot already occupied
                if existing_info:
                    if self._handle_preview_for_existing_slot(existing_info, existing_widget, sess, srow, span):
                        continue
                elif existing_widget is not None:
                    # Unknown widget without placement info - treat as conflict highlight
                    self._highlight_existing_widget_for_preview(existing_widget, mode='conflict')
                    continue

                # Allow preview only on empty cells (no widget present)
                if self.can_place_preview(srow, col, span):
                    # Create preview with improved layout matching main course cells
                    preview_widget = QtWidgets.QWidget()
                    preview_layout = QtWidgets.QVBoxLayout(preview_widget)
                    preview_layout.setContentsMargins(6, 4, 6, 4)
                    preview_layout.setSpacing(2)
                    
                    # Course Name (Bold)
                    course_name_label = QtWidgets.QLabel(course['name'])
                    course_name_label.setObjectName("course_name_label")
                    course_name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    course_name_label.setWordWrap(True)
                    
                    # Professor Name
                    professor_label = QtWidgets.QLabel(course.get('instructor', translator.t('messages.unknown')))
                    professor_label.setObjectName("professor_label")
                    professor_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    professor_label.setWordWrap(True)
                    
                    # Course Code
                    code_label = QtWidgets.QLabel(course.get('code', ''))
                    code_label.setObjectName("code_label")
                    code_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
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
                        parity_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
                        
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
                    
                    # Apply preview styling (light blue with dashed border)
                    preview_widget.setStyleSheet("""
                        QWidget#preview_widget {
                            background-color: rgba(25, 118, 210, 0.15);
                            border: 2px dashed rgba(25, 118, 210, 0.6);
                            border-radius: 6px;
                        }
                    """)
                    
                    # Set cell widget only once with safety check
                    try:
                        self.schedule_table.setCellWidget(srow, col, preview_widget)
                        if span > 1:
                            self.schedule_table.setSpan(srow, col, span, 1)
                        self.preview_cells.append((srow, col, span))
                    except Exception as e:
                        logger.warning(f"Error setting preview widget at ({srow}, {col}): {e}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Error creating preview for session at ({srow}, {col}): {e}")
                import traceback
                traceback.print_exc()
                continue

    def _handle_preview_for_existing_slot(self, info, widget, new_session, start_row, span):
        """Handle preview highlighting for slots that already contain a course"""
        try:
            base_widget = info.get('widget') or widget
            if not base_widget:
                return False

            if info.get('type') == 'dual':
                self._highlight_existing_widget_for_preview(base_widget, mode='conflict')
                return True

            existing_course_key = info.get('course')
            existing_course = COURSES.get(existing_course_key)
            if not existing_course:
                self._highlight_existing_widget_for_preview(base_widget, mode='conflict')
                return True

            for existing_sess in existing_course.get('schedule', []):
                if existing_sess.get('day') != new_session.get('day'):
                    continue
                try:
                    existing_start = EXTENDED_TIME_SLOTS.index(existing_sess['start'])
                    existing_end = EXTENDED_TIME_SLOTS.index(existing_sess['end'])
                except ValueError:
                    continue

                if existing_start == start_row and existing_end == start_row + span:
                    from .dual_course_utils import check_odd_even_compatibility
                    if check_odd_even_compatibility(new_session, existing_sess):
                        self._highlight_existing_widget_for_preview(base_widget, mode='compatible', new_session=new_session)
                    else:
                        self._highlight_existing_widget_for_preview(base_widget, mode='conflict')
                    return True
        except Exception as exc:
            logger.warning(f"preview_existing_slot_error: {exc}")

        return False

    def _highlight_existing_widget_for_preview(self, widget, mode='compatible', new_session=None):
        """Apply a temporary highlight to an occupied cell during preview"""
        if widget is None:
            return

        try:
            # Avoid duplicate entries
            for entry in self.preview_highlighted_widgets:
                if entry['widget'] == widget:
                    if entry.get('mode') != mode and widget.objectName() != 'dual-course-cell':
                        widget.setStyleSheet(self._build_preview_style(widget, mode))
                    entry['mode'] = mode
                    return

            original_style = widget.styleSheet()
            original_tooltip = widget.toolTip() if hasattr(widget, 'toolTip') else ''

            entry = {
                'widget': widget,
                'style': original_style,
                'tooltip': original_tooltip,
                'mode': mode
            }

            object_name = widget.objectName() if hasattr(widget, 'objectName') else ''
            if object_name == 'dual-course-cell' and hasattr(widget, 'set_preview_mode'):
                widget.set_preview_mode(mode)
            else:
                widget.setStyleSheet(self._build_preview_style(widget, mode))

            if hasattr(widget, 'setToolTip'):
                if mode == 'compatible':
                    widget.setToolTip('این بازه با جلسهٔ انتخابی قابل ترکیب است (زوج/فرد).')
                else:
                    widget.setToolTip('این بازه با جلسهٔ انتخابی تداخل زمانی دارد.')

            self.preview_highlighted_widgets.append(entry)
        except RuntimeError as exc:
            logger.debug(f"preview_highlight_runtime: {exc}")
        except Exception as exc:
            logger.warning(f"preview_highlight_error: {exc}")

    def _build_preview_style(self, widget, mode):
        """Construct QSS style string for preview highlighting"""
        object_name = widget.objectName() if hasattr(widget, 'objectName') else ''
        selector = f"QWidget#{object_name}" if object_name else "QWidget"

        if mode == 'compatible':
            border_color = '#3498db'
            background_color = 'rgba(52, 152, 219, 0.18)'
        else:
            border_color = '#e74c3c'
            background_color = 'rgba(231, 76, 60, 0.18)'

        return (
            f"{selector} {{\n"
            f"    border: 2px dashed {border_color};\n"
            f"    border-radius: 8px;\n"
            f"    background-color: {background_color};\n"
            f"}}"
        )

    def can_place_preview(self, srow, col, span):
        """Check if preview can be placed - FIXED to skip dual course cells to prevent crashes"""
        for r in range(srow, srow + span):
            widget = self.schedule_table.cellWidget(r, col)
            if widget is not None:
                # Don't allow preview on any existing widgets (including dual course cells)
                # This prevents crashes when hovering over dual course cells
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
        # Add to queue and debounce - increased debounce time for rapid clicks
        self.course_addition_queue.append((course_key, ask_on_conflict))
        if self.course_addition_timer.isActive():
            self.course_addition_timer.stop()
        self.course_addition_timer.start(50)  # 50ms debounce for responsive UI

    def _process_course_addition_queue(self):
        """
        Process queued course additions with proper synchronization.
        This version processes courses one by one to properly handle dual course creation.
        Removes duplicate entries to improve performance and prevent conflicts.
        """
        logger.info("overlay_processing_start: Starting to process course addition queue")
        locker = QMutexLocker(self.course_addition_mutex)
        try:
            # Remove duplicate entries - keep only the last occurrence of each course
            # This prevents processing the same course multiple times
            seen_courses = {}
            unique_queue = []
            for item in self.course_addition_queue:
                course_key, ask_on_conflict = item
                # Keep the last occurrence (latest ask_on_conflict value)
                seen_courses[course_key] = item
            unique_queue = list(seen_courses.values())
            self.course_addition_queue.clear()
            
            # Process courses one by one to handle dual course creation correctly
            for course_key, ask_on_conflict in unique_queue:
                logger.info(f"overlay_processing_item: Processing course {course_key}")
                
                # Process course addition with dual operation locking
                dual_locker = QMutexLocker(self.dual_operation_mutex)
                try:
                    self._add_course_internal(course_key, ask_on_conflict)
                finally:
                    del dual_locker
            
            self.update_user_data()
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
            QtWidgets.QMessageBox.critical(
                self,
                translator.t("common.error"),
                translator.t("messages.table_missing")
            )
            return
            
        course = COURSES.get(course_key)
        if not course:
            QtWidgets.QMessageBox.warning(
                self,
                translator.t("common.warning"),
                translator.t("messages.course_not_found", key=course_key)
            )
            return
        
        # Import the SIMPLE dual course widget creator and parity compatibility checker
        from .simple_dual_widget import create_simple_dual_widget as create_dual_course_widget
        from .dual_course_utils import check_odd_even_compatibility
        
        # Get translated day names
        from app.core.config import get_days
        DAYS = get_days()
        
        placements = []
        for sess in course['schedule']:
            if sess['day'] not in DAYS:
                continue
            col = DAYS.index(sess['day'])
            try:
                srow = EXTENDED_TIME_SLOTS.index(sess['start'])
                erow = EXTENDED_TIME_SLOTS.index(sess['end'])
            except ValueError:
                QtWidgets.QMessageBox.warning(
                    self,
                    translator.t("common.warning"),
                    translator.t(
                        "messages.invalid_time",
                        course=course["name"],
                        time_range=f"{sess['start']}-{sess['end']}"
                    )
                )
                continue
            span = max(1, erow - srow)
            placements.append((srow, col, span, sess))

        # Check for conflicts with proper weekly_type (parity) handling
        # FIRST: Check the actual table cells directly to catch widgets that aren't in self.placed yet
        conflicts = []
        compatible_slots = {}  # Track odd/even compatible slots
        
        # Check actual table cells first (for race conditions when user clicks fast)
        for (srow, col, span, sess) in placements:
            # Check if there's already a widget in this cell
            existing_widget = self.schedule_table.cellWidget(srow, col)
            
            if existing_widget:
                # Try to extract course information from the widget
                existing_course_key = None
                existing_course = {}
                existing_sess = None
                
                # Check if it's a dual widget
                from .simple_dual_widget import SimpleDualCourseWidget
                if isinstance(existing_widget, SimpleDualCourseWidget):
                    # It's already a dual widget - check if this course is already in it
                    odd_data = existing_widget.odd_data
                    even_data = existing_widget.even_data
                    
                    # If this course is already in the dual widget, skip this placement (already added)
                    if odd_data.get('course_key') == course_key or even_data.get('course_key') == course_key:
                        # This course is already in the dual widget - skip conflict check for this slot
                        continue
                    
                    # Check parity compatibility with new session
                    sess_parity = sess.get('parity', '') or ''
                    odd_parity = odd_data.get('session', {}).get('parity', '') or ''
                    even_parity = even_data.get('session', {}).get('parity', '') or ''
                    
                    # Dual widget is already full (has both odd and even), so this is a conflict
                    # Get both course names from dual widget
                    odd_course_name = odd_data.get('course', {}).get('name', '')
                    even_course_name = even_data.get('course', {}).get('name', '')
                    # Use the first non-empty name, or combine both if available
                    if odd_course_name and even_course_name:
                        conflict_name = f"{odd_course_name} / {even_course_name}"
                    elif odd_course_name:
                        conflict_name = odd_course_name
                    elif even_course_name:
                        conflict_name = even_course_name
                    else:
                        conflict_name = translator.t('messages.unknown')
                    
                    conflicts.append(((srow, col), (srow, col), 'dual_widget', conflict_name))
                    continue
                else:
                    # It's a single course widget - try to get course key from widget
                    # Check if widget has course_key attribute
                    if hasattr(existing_widget, 'course_key'):
                        existing_course_key = existing_widget.course_key
                        
                        # IMPORTANT: If it's the same course, skip conflict check (already added)
                        if existing_course_key == course_key:
                            # This is the same course - it's already added, skip this placement
                            continue
                        
                        existing_course = COURSES.get(existing_course_key, {})
                        
                        # Find matching session
                        for existing_sess_check in existing_course.get('schedule', []):
                            if existing_sess_check['day'] == sess['day']:
                                try:
                                    existing_start = EXTENDED_TIME_SLOTS.index(existing_sess_check['start'])
                                    existing_end = EXTENDED_TIME_SLOTS.index(existing_sess_check['end'])
                                    if existing_start == srow and existing_end == srow + span:
                                        existing_sess = existing_sess_check
                                        break
                                except (ValueError, KeyError):
                                    pass
                        
                        if existing_course:
                            # Make sure we have a valid course name
                            existing_course_name = existing_course.get('name', '').strip()
                            if not existing_course_name:
                                # Try to get name from widget if available
                                if hasattr(existing_widget, 'course_info'):
                                    existing_course_name = existing_widget.course_info.get('name', '')
                                if not existing_course_name:
                                    existing_course_name = translator.t('messages.unknown')
                            
                            if existing_sess:
                                # Check parity compatibility
                                sess_parity = sess.get('parity', '') or ''
                                existing_parity = existing_sess.get('parity', '') or ''
                                
                                is_compatible = (
                                    (sess_parity == 'ز' and existing_parity == 'ف') or
                                    (sess_parity == 'ف' and existing_parity == 'ز')
                                )
                                
                                if is_compatible:
                                    # Store for dual creation - but we'll handle it directly from widget
                                    # Get info from self.placed if available, otherwise create it
                                    existing_info = self.placed.get((srow, col), {
                                        'course': existing_course_key,
                                        'rows': span,
                                        'type': 'single',
                                        'color': getattr(existing_widget, 'bg_color', COLOR_MAP[0])
                                    })
                                    
                                    compatible_slots[(srow, col)] = {
                                        'existing': existing_info,
                                        'existing_session': existing_sess,
                                        'new_session': sess,
                                        'span': span,
                                        'existing_course_key': existing_course_key,
                                        'existing_widget': existing_widget
                                    }
                                    logger.info(f"Found compatible slot from table widget: course {course_key} (parity: {sess_parity}) with course {existing_course_key} (parity: {existing_parity}) at ({srow}, {col})")
                                    continue
                                else:
                                    # Not compatible - it's a conflict
                                    conflicts.append(((srow, col), (srow, col), existing_course_key, existing_course_name))
                                    continue
                            else:
                                # No matching session found but widget exists - it's still a conflict
                                conflicts.append(((srow, col), (srow, col), existing_course_key, existing_course_name))
                                continue
                        elif existing_course_key:
                            # Course key exists but course not found in COURSES - might be a custom course
                            # Try to get name from widget
                            existing_course_name = translator.t('messages.unknown')
                            if hasattr(existing_widget, 'course_info'):
                                existing_course_name = existing_widget.course_info.get('name', existing_course_name)
                            conflicts.append(((srow, col), (srow, col), existing_course_key, existing_course_name))
                            continue
        
        # SECOND: Check self.placed for courses that are already registered
        for (srow, col, span, sess) in placements:
            # Skip if we already found this slot in the table check above
            if (srow, col) in compatible_slots:
                continue
                
            for (prow, pcol), info in list(self.placed.items()):
                if pcol != col:
                    continue
                
                # Skip conflict check with the same course - handle both single and dual courses
                is_same_course = False
                if info.get('type') == 'dual':
                    # For dual courses, check if course_key is in the courses list
                    courses_list = info.get('courses', [])
                    if course_key in courses_list:
                        is_same_course = True
                else:
                    # For single courses, check directly
                    if info.get('course') == course_key:
                        is_same_course = True
                
                if is_same_course:
                    continue
                
                prow_start = prow
                prow_span = info['rows']
                
                # Check for time overlap
                if not (srow + span <= prow_start or prow_start + prow_span <= srow):
                    # Time overlap detected - check if they can coexist based on parity
                    existing_course_key = None
                    existing_course = {}
                    
                    # Get the existing course key and data
                    if info.get('type') == 'dual':
                        # For dual courses, we need to check all courses in the dual widget
                        courses_list = info.get('courses', [])
                        # We'll check the first course for conflict detection
                        # The actual compatibility check will be done per session
                        if courses_list:
                            existing_course_key = courses_list[0]
                            existing_course = COURSES.get(existing_course_key, {})
                    else:
                        existing_course_key = info.get('course')
                        existing_course = COURSES.get(existing_course_key, {})
                    
                    if not existing_course:
                        # If we can't find the course, skip this conflict check
                        # It might be a custom course or a course that was removed
                        logger.warning(f"Course {existing_course_key} not found in COURSES dictionary, skipping conflict check")
                        continue
                    
                    # Find the conflicting session
                    found_matching_session = False
                    for existing_sess in existing_course.get('schedule', []):
                        if existing_sess['day'] != sess['day']:
                            continue
                        
                        # Check start/end time match
                        try:
                            existing_start = EXTENDED_TIME_SLOTS.index(existing_sess['start'])
                            existing_end = EXTENDED_TIME_SLOTS.index(existing_sess['end'])
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Error getting time slot indices: {e}")
                            # If we can't get time indices, skip this conflict check
                            # It might be a data inconsistency issue
                            found_matching_session = True
                            break
                        
                        # Check if times overlap (not just exact match)
                        if not (srow + span <= existing_start or existing_end <= srow):
                            # Times overlap - check if they can coexist based on parity
                            found_matching_session = True
                            
                            # Safety check for parity values with error handling
                            try:
                                sess_parity = sess.get('parity', '') or ''
                                existing_parity = existing_sess.get('parity', '') or ''
                                
                                # Ensure parity values are strings
                                if not isinstance(sess_parity, str):
                                    sess_parity = str(sess_parity)
                                if not isinstance(existing_parity, str):
                                    existing_parity = str(existing_parity)
                                
                                # Check if they are compatible (one even, one odd)
                                is_compatible = (
                                    (sess_parity == 'ز' and existing_parity == 'ف') or  # زوج and فرد
                                    (sess_parity == 'ف' and existing_parity == 'ز')     # فرد and زوج
                                )
                            except Exception as e:
                                # If parity check fails, treat as conflict to be safe
                                logger.warning(f"Error checking parity compatibility: {e}. sess_parity={sess.get('parity')}, existing_parity={existing_sess.get('parity')}")
                                is_compatible = False
                            
                            # If compatible, store for dual placement
                            if is_compatible:
                                # Only store if slot is not already in compatible_slots
                                # Also check if the existing course is the same as the new course
                                # to avoid creating dual with itself
                                if (srow, col) not in compatible_slots:
                                    # Make sure we're not trying to create dual with the same course
                                    if existing_course_key != course_key:
                                        compatible_slots[(srow, col)] = {
                                            'existing': info,
                                            'existing_session': existing_sess,
                                            'new_session': sess,
                                            'span': span,
                                            'existing_course_key': existing_course_key
                                        }
                                        logger.info(f"Found compatible slot for dual widget: course {course_key} (parity: {sess_parity}) with course {existing_course_key} (parity: {existing_parity}) at ({srow}, {col})")
                            else:
                                # If not compatible, it's a real conflict
                                existing_course_name = existing_course.get('name', '').strip()
                                if not existing_course_name:
                                    existing_course_name = translator.t('messages.unknown')
                                conflicts.append(((srow, col), (prow_start, pcol), existing_course_key, existing_course_name))
                            break
                    
                    # If no matching session found but times overlap, check if it's really a conflict
                    # Only add conflict if we actually found a time overlap but no matching session
                    if not found_matching_session:
                        # Make sure we have a valid course name
                        existing_course_name = existing_course.get('name', '').strip()
                        if not existing_course_name:
                            existing_course_name = translator.t('messages.unknown')
                        # Only add conflict if course name is valid (not unknown)
                        if existing_course_name and existing_course_name != translator.t('messages.unknown'):
                            conflicts.append(((srow, col), (prow_start, pcol), existing_course_key, existing_course_name))
                        else:
                            # Skip this conflict if we can't identify the course
                            logger.warning(f"Skipping conflict with unknown course at ({srow}, {col}): {existing_course_key}")
        
        # Add conflict indicator to course info if there are conflicts
        has_conflicts = len(conflicts) > 0

        # Handle conflicts with priority-based resolution
        if conflicts and ask_on_conflict:
            # Get priority of current course (if in auto-select list)
            current_priority = self.get_course_priority(course_key)
            
            # Check if any conflicting courses have higher priority
            # Use a set to avoid duplicate course names
            higher_priority_conflicts = []
            conflict_names_set = set()  # Use set to avoid duplicates
            conflict_course_keys_set = set()  # Track course keys to avoid duplicates
            conflict_details_list = []  # List to maintain order
            
            for conf in conflicts:
                (_, _), (_, _), conflict_course_key, conflict_name = conf
                
                # Skip if we've already processed this course key (avoid duplicates)
                if conflict_course_key in conflict_course_keys_set:
                    continue
                
                # Skip if conflict_name is empty or "unknown" and we can't identify the course
                if not conflict_name or conflict_name == translator.t('messages.unknown'):
                    # Try to get course name from COURSES
                    conflict_course = COURSES.get(conflict_course_key, {})
                    if conflict_course:
                        conflict_name = conflict_course.get('name', translator.t('messages.unknown'))
                    # If still unknown, skip this conflict
                    if not conflict_name or conflict_name == translator.t('messages.unknown'):
                        logger.warning(f"Skipping conflict with unknown course: {conflict_course_key}")
                        continue
                
                conflict_course_keys_set.add(conflict_course_key)
                conflict_priority = self.get_course_priority(conflict_course_key)
                
                # If conflicting course has higher priority (lower number), it should stay
                if conflict_priority < current_priority:
                    higher_priority_conflicts.append((conflict_course_key, conflict_name, conflict_priority))
                
                # Only add to list if not already added (avoid duplicate names)
                if conflict_name not in conflict_names_set:
                    conflict_names_set.add(conflict_name)
                    conflict_details_list.append(conflict_name)
            
            conflict_details = conflict_details_list
            
            # If all conflicts were skipped (all were unknown), allow course addition
            if not conflict_details and len(conflicts) > 0:
                logger.info(f"All conflicts were skipped (unknown courses), allowing course {course_key} to be added")
                # Continue to add the course - no conflicts to show
                has_conflicts = False
            
            # If there are higher priority conflicts, show warning and don't add course
            if higher_priority_conflicts and conflict_details:
                conflict_list = '\n'.join([f"• {name}" for name in conflict_details])
                warning_msg = QtWidgets.QMessageBox()
                warning_msg.setIcon(QtWidgets.QMessageBox.Warning)
                warning_msg.setWindowTitle(translator.t("messages.conflict_priority_title"))
                warning_msg.setText(translator.t("messages.conflict_priority_message", course_name=course["name"]))
                
                # Add details about higher priority conflicts
                priority_details = '\n'.join([f"• {name} ({translator.t('common.priority', fallback='Priority')}: {priority})" for _, name, priority in higher_priority_conflicts])
                warning_msg.setDetailedText(f'{translator.t("messages.conflict_priority_details")}\n{priority_details}')
                
                # Set layout direction
                from app.core.language_manager import language_manager
                current_lang = language_manager.get_current_language()
                if current_lang == 'fa':
                    warning_msg.setLayoutDirection(QtCore.Qt.RightToLeft)
                else:
                    warning_msg.setLayoutDirection(QtCore.Qt.LeftToRight)
                
                warning_msg.exec_()
                return
            
            # If no higher priority conflicts, proceed with normal conflict resolution
            # Only show dialog if we have valid conflict details
            if not conflict_details:
                # No valid conflicts - allow course addition without showing dialog
                logger.info(f"No valid conflicts found (all were skipped), allowing course {course_key} to be added")
                has_conflicts = False
            else:
                # Show conflict resolution dialog only if we have valid conflicts
                conflict_list = '\n'.join([f"• {name}" for name in conflict_details])
                
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle(translator.t("messages.conflict_title"))
                msg.setText(translator.t("messages.conflict_message", course_name=course["name"]))
                msg.setDetailedText(f'{translator.t("messages.conflict_details")}\n{conflict_list}')
                msg.setInformativeText(translator.t("messages.conflict_question"))
                msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
                msg.setDefaultButton(QtWidgets.QMessageBox.No)
                
                # Translate button texts
                msg.button(QtWidgets.QMessageBox.Yes).setText(translator.t("messages.button_yes"))
                msg.button(QtWidgets.QMessageBox.No).setText(translator.t("messages.button_no"))
                msg.button(QtWidgets.QMessageBox.Cancel).setText(translator.t("messages.button_cancel"))
                
                # Set layout direction
                from app.core.language_manager import language_manager
                current_lang = language_manager.get_current_language()
                if current_lang == 'fa':
                    msg.setLayoutDirection(QtCore.Qt.RightToLeft)
                else:
                    msg.setLayoutDirection(QtCore.Qt.LeftToRight)
                
                res = msg.exec_()
                if res == QtWidgets.QMessageBox.Cancel:
                    return
                elif res == QtWidgets.QMessageBox.No:
                    # User chose not to add the course - don't show another message, just return
                    return
                # If Yes, continue to add the course (removing conflicting courses)
                
                # Remove conflicting courses if user confirmed
                # Only remove valid course keys (not 'dual_widget' or 'unknown')
                conflicting_courses = set()
                for conf in conflicts:
                    (_, _), (rstart, rcol), rcourse, _ = conf
                    # Only add valid course keys
                    if rcourse and rcourse != 'dual_widget' and rcourse != 'unknown':
                        conflicting_courses.add(rcourse)
                
                # Remove entire conflicting courses
                for conflicting_course_key in conflicting_courses:
                    self.remove_course_from_schedule(conflicting_course_key)
        elif conflicts and not ask_on_conflict:
            # If we're not asking about conflicts (e.g., applying presets), still mark as conflicting
            has_conflicts = True
            # Don't add the course if there are conflicts and we're not asking
            logger.warning(f"Course {course_key} has conflicts but ask_on_conflict=False, skipping addition")
            return

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
                # ALWAYS check the table directly first (for race conditions when user clicks fast)
                existing_dual_widget = None
                existing_single_info = None
                
                # First, check the actual table widget (most reliable for race conditions)
                existing_widget_from_table = self.schedule_table.cellWidget(srow, col)
                if existing_widget_from_table:
                    from .simple_dual_widget import SimpleDualCourseWidget
                    if isinstance(existing_widget_from_table, SimpleDualCourseWidget):
                        existing_dual_widget = existing_widget_from_table
                        logger.info(f"Found existing dual widget in table at ({srow}, {col})")
                    else:
                        # It's a single widget - we already have info from compatible_slots
                        existing_single_info = existing_info
                        logger.info(f"Found existing single widget in table at ({srow}, {col}) that needs to be converted to dual")
                # Fallback to self.placed if table check didn't find widget
                elif (srow, col) in self.placed:
                    if self.placed[(srow, col)].get('type') == 'dual':
                        existing_dual_widget = self.placed[(srow, col)].get('widget')
                    elif self.placed[(srow, col)].get('type') != 'dual':
                        # There's a single course widget that needs to be converted
                        existing_single_info = self.placed[(srow, col)]
                        logger.info(f"Found existing single course in placed dict at ({srow}, {col}) that needs to be converted to dual")
                # If we have widget from compatible_slots check, use that
                elif compat_info.get('existing_widget'):
                    existing_widget_from_slot = compat_info.get('existing_widget')
                    from .simple_dual_widget import SimpleDualCourseWidget
                    if isinstance(existing_widget_from_slot, SimpleDualCourseWidget):
                        existing_dual_widget = existing_widget_from_slot
                    else:
                        existing_single_info = existing_info
                        logger.info(f"Found existing single widget from slot info at ({srow}, {col}) that needs to be converted to dual")
                
                if existing_dual_widget:
                    # Update existing dual widget instead of creating a new one
                    logger.info(f"overlay_updating_dual: Updating existing dual widget for slot {slot_key}")
                    # This would require modifying the dual widget to update its data
                    # For now, we'll remove the old widget and create a new one
                    self.schedule_table.removeCellWidget(srow, col)
                    
                    existing_start_tuple = None
                    for start_tuple, info in list(self.placed.items()):
                        if start_tuple == (srow, col):
                            existing_start_tuple = start_tuple
                            break
                    
                    if existing_start_tuple:
                        del self.placed[existing_start_tuple]
                    
                    try:
                        dual_widget = create_dual_course_widget(odd_data, even_data, self)
                        self.schedule_table.setCellWidget(srow, col, dual_widget)
                    except Exception as e:
                        logger.error(f"Error creating dual widget: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                    
                    self.placed[(srow, col)] = {
                        'courses': [odd_data['course_key'], even_data['course_key']],
                        'rows': span,
                        'widget': dual_widget,
                        'type': 'dual'
                    }
                else:
                    # Create new dual widget (either from scratch or converting from single)
                    if existing_single_info:
                        logger.info(f"overlay_converting_to_dual: Converting single widget to dual for slot {slot_key}")
                    else:
                        logger.info(f"overlay_creating_dual: Creating new dual widget for slot {slot_key}")
                    
                    # Remove existing widget (single or dual)
                    self.schedule_table.removeCellWidget(srow, col)
                    
                    # Remove from placed dictionary
                    existing_start_tuple = None
                    for start_tuple, info in list(self.placed.items()):
                        if start_tuple == (srow, col):
                            existing_start_tuple = start_tuple
                            break
                    
                    if existing_start_tuple:
                        del self.placed[existing_start_tuple]
                    
                    # Ensure we have the correct course data for the existing course
                    # If we're converting from single, we need to get the session data
                    if existing_single_info and existing_single_info.get('course'):
                        existing_course_key_from_info = existing_single_info.get('course')
                        existing_course_from_info = COURSES.get(existing_course_key_from_info, {})
                        
                        # Find the matching session for the existing course
                        for existing_sess_check in existing_course_from_info.get('schedule', []):
                            if existing_sess_check['day'] == existing_sess['day']:
                                try:
                                    existing_start_check = EXTENDED_TIME_SLOTS.index(existing_sess_check['start'])
                                    existing_end_check = EXTENDED_TIME_SLOTS.index(existing_sess_check['end'])
                                    if existing_start_check == srow and existing_end_check == srow + span:
                                        existing_sess = existing_sess_check
                                        break
                                except (ValueError, KeyError):
                                    pass
                        
                        # Update odd_data and even_data with correct existing course info
                        if existing_sess.get('parity') == 'ف':  # Existing is odd
                            odd_data = {
                                'course': existing_course_from_info,
                                'course_key': existing_course_key_from_info,
                                'session': existing_sess,
                                'color': existing_single_info.get('color', COLOR_MAP[0])
                            }
                            even_data = {
                                'course': course,
                                'course_key': course_key,
                                'session': new_sess,
                                'color': bg
                            }
                        else:  # Existing is even or fixed
                            odd_data = {
                                'course': course,
                                'course_key': course_key,
                                'session': new_sess,
                                'color': bg
                            }
                            even_data = {
                                'course': existing_course_from_info,
                                'course_key': existing_course_key_from_info,
                                'session': existing_sess,
                                'color': existing_single_info.get('color', COLOR_MAP[0])
                            }
                    
                    try:
                        dual_widget = create_dual_course_widget(odd_data, even_data, self)
                        self.schedule_table.setCellWidget(srow, col, dual_widget)
                    except Exception as e:
                        logger.error(f"Error creating dual widget: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                    
                    self.placed[(srow, col)] = {
                        'courses': [odd_data['course_key'], even_data['course_key']],
                        'rows': span,
                        'widget': dual_widget,
                        'type': 'dual'
                    }
            else:
                parity_indicator = ''
                if sess.get('parity') == 'ز':
                    parity_indicator = 'ز'
                elif sess.get('parity') == 'ف':
                    parity_indicator = 'ف'

                cell_widget = AnimatedCourseWidget(course_key, bg, has_conflicts, self)
                cell_widget.setObjectName('course-cell')
                
                if has_conflicts:
                    cell_widget.setProperty('conflict', True)
                elif course.get('code', '').startswith('elective'):
                    cell_widget.setProperty('elective', True)
                else:
                    cell_widget.setProperty('conflict', False)
                    cell_widget.setProperty('elective', False)
                
                cell_widget.bg_color = bg
                cell_widget.border_color = QtGui.QColor(bg.red()//2, bg.green()//2, bg.blue()//2)
                cell_layout = QtWidgets.QVBoxLayout(cell_widget)
                cell_layout.setContentsMargins(2, 1, 2, 1)
                cell_layout.setSpacing(0)
                
                top_row = QtWidgets.QHBoxLayout()
                top_row.setContentsMargins(0, 0, 0, 0)
                top_row.addStretch()
                
                x_button = QtWidgets.QPushButton('✕')
                x_button.setFixedSize(18, 18)
                x_button.setObjectName('close-btn')
                x_button.clicked.connect(lambda checked, ck=course_key: self.remove_course_silently(ck))
                
                top_row.addWidget(x_button)
                cell_layout.addLayout(top_row)
                
                course_name_label = QtWidgets.QLabel(course['name'])
                course_name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                course_name_label.setWordWrap(True)
                course_name_label.setObjectName('course-name-label')
                
                # Professor Name
                professor_label = QtWidgets.QLabel(course.get('instructor', translator.t('hardcoded_texts.unknown')))
                professor_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                professor_label.setWordWrap(True)
                professor_label.setObjectName('professor-label')
                
                # Course Code
                code_label = QtWidgets.QLabel(course.get('code', ''))
                code_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
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
                    parity_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
                    parity_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignBottom)
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
                
                def mouse_press_event(a0, widget=cell_widget):
                    try:
                        if a0.button() == QtCore.Qt.MouseButton.LeftButton:
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

    def remove_course_from_dual_widget(self, course_key, dual_widget):
        """Remove one course from dual widget and convert to single, or remove only this cell"""
        try:
            other_course_data = dual_widget.get_other_course_data(course_key)
            other_course_key = other_course_data['course_key']
            
            widget_position = None
            span = 1
            for (srow, scol), info in list(self.placed.items()):
                if info.get('widget') == dual_widget and info.get('type') == 'dual':
                    widget_position = (srow, scol)
                    span = info.get('rows', 1)
                    break
            
            if widget_position is None:
                logger.error("Could not find dual widget position")
                return
            
            srow, scol = widget_position
            
            self.schedule_table.removeCellWidget(srow, scol)
            del self.placed[widget_position]
            
            from .widgets import AnimatedCourseWidget
            from app.core.config import COURSES
            
            course = COURSES.get(other_course_key, {})
            if not course:
                for r in range(srow, srow + span):
                    self.schedule_table.setItem(r, scol, QtWidgets.QTableWidgetItem(''))
                self.schedule_table.setSpan(srow, scol, 1, 1)
                return
            
            bg_color = other_course_data.get('color')
            if not isinstance(bg_color, QtGui.QColor):
                from app.core.course_utils import get_course_color
                bg_color = get_course_color(course)
            
            cell_widget = AnimatedCourseWidget(other_course_key, bg_color, False, self)
            cell_widget.setObjectName('course-cell')
            cell_widget.setProperty('conflict', False)
            cell_widget.setProperty('elective', False)
            
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
            
            cell_widget.enterEvent = enter_event
            cell_widget.leaveEvent = leave_event
            
            cell_layout = QtWidgets.QVBoxLayout(cell_widget)
            cell_layout.setContentsMargins(2, 1, 2, 1)
            cell_layout.setSpacing(0)
            
            top_row = QtWidgets.QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.addStretch()
            
            x_button = QtWidgets.QPushButton('✕')
            x_button.setFixedSize(18, 18)
            x_button.setObjectName('close-btn')
            x_button.clicked.connect(lambda checked, ck=other_course_key: self.remove_course_silently(ck))
            top_row.addWidget(x_button)
            cell_layout.addLayout(top_row)
            
            course_name_label = QtWidgets.QLabel(course.get('name', 'Unknown'))
            course_name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            course_name_label.setWordWrap(True)
            course_name_label.setObjectName('course-name-label')
            
            professor_label = QtWidgets.QLabel(course.get('instructor', 'نامشخص'))
            professor_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            professor_label.setWordWrap(True)
            professor_label.setObjectName('professor-label')
            
            code_label = QtWidgets.QLabel(course.get('code', ''))
            code_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            code_label.setObjectName('code-label')
            
            cell_layout.addWidget(course_name_label)
            cell_layout.addWidget(professor_label)
            cell_layout.addWidget(code_label)
            
            session = other_course_data.get('session', {})
            parity_indicator = session.get('parity', '')
            if parity_indicator:
                bottom_row = QtWidgets.QHBoxLayout()
                parity_label = QtWidgets.QLabel(parity_indicator)
                parity_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
                if parity_indicator == 'ز':
                    parity_label.setObjectName('parity-label-even')
                elif parity_indicator == 'ف':
                    parity_label.setObjectName('parity-label-odd')
                else:
                    parity_label.setObjectName('parity-label-all')
                bottom_row.addWidget(parity_label)
                bottom_row.addStretch()
                cell_layout.addLayout(bottom_row)
            
            self.schedule_table.setCellWidget(srow, scol, cell_widget)
            if span > 1:
                self.schedule_table.setSpan(srow, scol, span, 1)
            
            self.placed[widget_position] = {
                'course': other_course_key,
                'rows': span,
                'widget': cell_widget,
                'color': other_course_data['color'],
                'type': 'single'
            }
            
            logger.info(f"Converted dual widget to single course: {other_course_key} at ({srow}, {scol})")
            
            self._remove_course_sessions_except_cell(course_key, (srow, scol))
            
            self.update_stats_panel()
            self.update_status()
            
        except Exception as e:
            logger.error(f"Error removing course from dual widget: {e}")
            import traceback
            traceback.print_exc()
    
    def _remove_course_sessions_except_cell(self, course_key, except_cell):
        """Remove all sessions of a course except the specified cell"""
        to_remove = []
        to_convert = []
        except_srow, except_scol = except_cell
        
        for (srow, scol), info in list(self.placed.items()):
            if (srow, scol) == (except_srow, except_scol):
                continue
                
            if info.get('type') == 'dual':
                if course_key in info.get('courses', []):
                    dual_widget = info.get('widget')
                    if dual_widget:
                        other_course_data = dual_widget.get_other_course_data(course_key)
                        other_course_key = other_course_data['course_key']
                        
                        has_other_sessions = False
                        for (orow, ocol), oinfo in list(self.placed.items()):
                            if (orow, ocol) == (except_srow, except_scol):
                                continue
                            if (orow, ocol) != (srow, scol):
                                if oinfo.get('type') == 'dual':
                                    if other_course_key in oinfo.get('courses', []):
                                        has_other_sessions = True
                                        break
                                elif oinfo.get('course') == other_course_key:
                                    has_other_sessions = True
                                    break
                        
                        if has_other_sessions:
                            to_convert.append((srow, scol, dual_widget))
                        else:
                            to_remove.append((srow, scol))
            else:
                if info.get('course') == course_key:
                    to_remove.append((srow, scol))
        
        for srow, scol, dual_widget in to_convert:
            try:
                self.remove_course_from_dual_widget(course_key, dual_widget)
            except Exception as e:
                logger.error(f"Error converting dual to single: {e}")
                to_remove.append((srow, scol))
        
        for start_tuple in to_remove:
            if start_tuple in self.placed:
                self.remove_placed_by_start(start_tuple)
    
    def remove_course_from_schedule(self, course_key):
        """Remove all instances of a course from the current schedule"""
        to_remove = []
        to_convert = []
        
        for (srow, scol), info in list(self.placed.items()):
            if info.get('type') == 'dual':
                if course_key in info.get('courses', []):
                    dual_widget = info.get('widget')
                    if dual_widget:
                        other_course_data = dual_widget.get_other_course_data(course_key)
                        other_course_key = other_course_data['course_key']
                        
                        has_other_sessions = False
                        for (orow, ocol), oinfo in list(self.placed.items()):
                            if (orow, ocol) != (srow, scol):
                                if oinfo.get('type') == 'dual':
                                    if other_course_key in oinfo.get('courses', []):
                                        has_other_sessions = True
                                        break
                                elif oinfo.get('course') == other_course_key:
                                    has_other_sessions = True
                                    break
                        
                        if has_other_sessions:
                            to_convert.append((srow, scol, dual_widget))
                        else:
                            to_remove.append((srow, scol))
            else:
                if info.get('course') == course_key:
                    to_remove.append((srow, scol))
        
        for srow, scol, dual_widget in to_convert:
            try:
                self.remove_course_from_dual_widget(course_key, dual_widget)
                continue
            except Exception as e:
                logger.error(f"Error converting dual to single: {e}")
                to_remove.append((srow, scol))
        
        for start_tuple in to_remove:
            if start_tuple in self.placed:
                self.remove_placed_by_start(start_tuple)
        
        print("🔄 Calling update_stats_panel from remove_course_from_schedule")
        self.update_stats_panel()
        QtCore.QCoreApplication.processEvents()

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
        if clipboard is not None:
            clipboard.setText(text)
        
        # Enhanced feedback message with modern styling
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setWindowTitle(translator.t("hardcoded_texts.copied"))
        msg.setText(translator.t("clipboard.message", code=text))
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        # Styling is now handled by QSS file
        msg.exec_()
    

    def remove_course_silently(self, course_key):
        """Remove all sessions of a course from schedule"""
        from app.core.config import COURSES
        
        # Use remove_course_from_schedule which handles dual widgets correctly
        self.remove_course_from_schedule(course_key)
        
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
        course_name = COURSES.get(course_key, {}).get('name', translator.t('hardcoded_texts.unknown'))
        QtWidgets.QMessageBox.information(
            self, translator.t("hardcoded_texts.deleted"), 
            translator.t("success.sessions_removed", course_name=course_name)
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

        for entry in list(self.preview_highlighted_widgets):
            widget = entry.get('widget')
            if not widget:
                continue
            try:
                if widget.objectName() != 'dual-course-cell':
                    widget.setStyleSheet(entry.get('style', ''))
                if hasattr(widget, 'setToolTip'):
                    widget.setToolTip(entry.get('tooltip', ''))
                if hasattr(widget, 'clear_highlight'):
                    widget.clear_highlight()
            except RuntimeError:
                continue
            except Exception as exc:
                logger.debug(f"preview_restore_error: {exc}")
        self.preview_highlighted_widgets.clear()

    def open_edit_course_dialog(self):
        """Open dialog to edit an existing course (legacy method)"""
        # First, let user select which course to edit
        selected_items = self.course_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(
                self, translator.t("hardcoded_texts.select_course_dialog_title"), 
                translator.t("hardcoded_texts.select_course_first")
            )
            return
            
        selected_item = selected_items[0]
        course_key = selected_item.data(QtCore.Qt.ItemDataRole.UserRole)
        self.open_edit_course_dialog_for_course(course_key)
        
    def open_edit_course_dialog_for_course(self, course_key):
        """Open dialog to edit a specific course by course key"""
        if not course_key or course_key not in COURSES:
            QtWidgets.QMessageBox.warning(
                self, translator.t("hardcoded_texts.error_generic"), 
                translator.t("hardcoded_texts.course_not_found")
            )
            return
            
        course = COURSES[course_key]
        
        # Check if it's a built-in course
        if not self.is_editable_course(course_key):
            QtWidgets.QMessageBox.warning(
                self, translator.t("common.warning"), 
                translator.t("hardcoded_texts.course_not_editable")
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
            self, translator.t("hardcoded_texts.course_edited"), 
            translator.t("success.course_edited", course_name=updated_course["name"])
        )
        
    def show_course_details(self, course_key):
        """Show detailed course information in a dialog"""
        course = COURSES.get(course_key, {})
        if not course:
            return

        details_dialog = QtWidgets.QDialog(self)
        language_manager.apply_layout_direction(details_dialog)
        details_dialog.setModal(True)
        details_dialog.resize(500, 400)

        window_title = translator.t("course_details.title")
        details_dialog.setWindowTitle(f"{window_title}: {course.get('name', translator.t('common.no_description'))}")

        layout = QtWidgets.QVBoxLayout(details_dialog)

        course_name = course.get('name', translator.t('common.no_description'))
        course_code = course.get('code', translator.t('common.no_description'))
        instructor = course.get('instructor', translator.t('common.no_description'))
        credits = course.get('credits', 0)
        location = course.get('location', translator.t('common.no_description'))
        exam_time = course.get('exam_time', translator.t('common.no_exam_time'))

        info_parts = [
            f"<h2 style=\"color: #2c3e50; font-family: 'IRANSans', 'Tahoma', sans-serif;\">{course_name}</h2>",
            f"<p style=\"font-family: 'IRANSans', 'Tahoma', sans-serif;\"><b>{translator.t('course_details.course_code')}</b>: {course_code}</p>",
            f"<p style=\"font-family: 'IRANSans', 'Tahoma', sans-serif;\"><b>{translator.t('course_details.instructor')}</b>: {instructor}</p>",
            f"<p style=\"font-family: 'IRANSans', 'Tahoma', sans-serif;\"><b>{translator.t('course_details.credits')}</b>: {credits}</p>",
            f"<p style=\"font-family: 'IRANSans', 'Tahoma', sans-serif;\"><b>{translator.t('course_details.location')}</b>: {location}</p>",
            f"<p style=\"font-family: 'IRANSans', 'Tahoma', sans-serif;\"><b>{translator.t('course_details.exam_time')}</b>: {exam_time}</p>",
            f"<h3 style=\"font-family: 'IRANSans', 'Tahoma', sans-serif;\">{translator.t('course_details.sessions_title')}</h3>",
        ]

        for sess in course.get('schedule', []):
            day_label = get_day_label(sess.get('day', ''))
            start = sess.get('start', '')
            end = sess.get('end', '')
            parity_value = self._translate_parity(sess.get('parity'))
            parity_display = f" ({parity_value})" if parity_value else ""
            info_parts.append(
                f"<p style=\"font-family: 'IRANSans', 'Tahoma', sans-serif;\">• {day_label} {start}-{end}{parity_display}</p>"
            )

        description = course.get('description', translator.t('common.no_description'))
        info_parts.append(
            f"<h3 style=\"font-family: 'IRANSans', 'Tahoma', sans-serif;\">{translator.t('course_details.description_title')}</h3>"
        )
        info_parts.append(
            f"<p style=\"background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: 'IRANSans', 'Tahoma', sans-serif;\">{description}</p>"
        )

        text_widget = QtWidgets.QTextEdit()
        text_widget.setHtml("\n".join(info_parts))
        text_widget.setReadOnly(True)
        text_widget.setObjectName("course_details")
        layout.addWidget(text_widget)

        copy_button = QtWidgets.QPushButton(
            translator.t("course_details.copy_code", code=course.get('code', ''))
        )
        copy_button.clicked.connect(lambda: self.copy_to_clipboard(course.get('code', '')))
        copy_button.setObjectName("copy_code")
        layout.addWidget(copy_button)

        close_button = QtWidgets.QPushButton(translator.t("course_details.close"))
        close_button.setObjectName("dialog_close")
        close_button.clicked.connect(details_dialog.close)
        layout.addWidget(close_button)

        details_dialog.exec_()

    def _translate_parity(self, parity_value):
        """Translate parity value to localized string"""
        from .dual_course_utils import translate_parity
        return translate_parity(parity_value)
        
    def highlight_course_sessions(self, course_keys):
        """Highlight one or multiple course sessions with smooth border animation"""
        # Normalize input to list of unique course keys
        if isinstance(course_keys, (list, tuple, set)):
            target_keys = [key for key in course_keys if key]
        else:
            target_keys = [course_keys] if course_keys else []

        if not target_keys:
            return

        unique_keys = set(target_keys)

        # Reset previous highlights
        self.clear_course_highlights()

        # Prepare timer containers
        if not hasattr(self, '_pulse_timers'):
            self._pulse_timers = {}
        self._pulse_timer_data = getattr(self, '_pulse_timer_data', {})

        for (srow, scol), info in self.placed.items():
            widget = info.get('widget')
            if not widget:
                continue

            if info.get('type') == 'dual':
                course_pair = info.get('courses', [])
                matched_courses = [ck for ck in course_pair if ck in unique_keys]
                if not matched_courses:
                    continue

                # Store original style once
                if not hasattr(widget, 'original_style'):
                    widget.original_style = widget.styleSheet()

                if len(matched_courses) >= 2 and hasattr(widget, 'highlight_section'):
                    widget.highlight_section('both')
                else:
                    course_key = matched_courses[0]
                    if hasattr(widget, 'highlight_section_for_course'):
                        widget.highlight_section_for_course(course_key)
                    elif hasattr(widget, 'highlight_section'):
                        section = 'odd' if course_key == course_pair[0] else 'even'
                        widget.highlight_section(section)

                # Start pulse timers for each matched course
                for course_key in matched_courses:
                    if course_key not in self._pulse_timers:
                        timer = QtCore.QTimer(widget)
                        self._pulse_timer_data[timer] = {
                            'course_key': course_key,
                            'widget': widget,
                            'step': 0
                        }
                        timer.timeout.connect(self._pulse_highlight)
                        self._pulse_timers[course_key] = timer
                    self._pulse_timers[course_key].start(100)

            else:
                course_key = info.get('course')
                if course_key not in unique_keys:
                    continue

                if not hasattr(widget, 'original_style'):
                    widget.original_style = widget.styleSheet()

                widget.setStyleSheet(
                    "QWidget#course-cell { border: 3px solid #e74c3c !important; border-radius: 8px !important; "
                    "background-color: rgba(231, 76, 60, 0.2) !important; } "
                    "QWidget#course-cell[conflict=\"true\"] { border: 3px solid #e74c3c !important; border-radius: 8px !important; "
                    "background-color: rgba(231, 76, 60, 0.3) !important; } "
                    "QWidget#course-cell[elective=\"true\"] { border: 3px solid #e74c3c !important; border-radius: 8px !important; "
                    "background-color: rgba(231, 76, 60, 0.2) !important; }"
                )

                if course_key not in self._pulse_timers:
                    timer = QtCore.QTimer(widget)
                    self._pulse_timer_data[timer] = {
                        'course_key': course_key,
                        'widget': widget,
                        'step': 0
                    }
                    timer.timeout.connect(self._pulse_highlight)
                    self._pulse_timers[course_key] = timer
                self._pulse_timers[course_key].start(100)
        
    def _pulse_highlight(self):
        """Pulse animation for highlighted course sessions"""
        # Make sure QtWidgets is available in this scope
        
        timer = self.sender()
        if not timer:
            return
            
        # Get the widget and course key from our data structure
        self._pulse_timer_data = getattr(self, '_pulse_timer_data', {})
        timer_data = self._pulse_timer_data.get(timer, {})
        widget = timer_data.get('widget')
        course_key = timer_data.get('course_key')
        
        if not widget or not course_key:
            if hasattr(timer, 'stop'):
                timer.stop()
            return
            
        # Update the pulse step
        step = timer_data.get('step', 0)
        step = (step + 1) % 20
        timer_data['step'] = step
        
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

    def create_course_widget(self, course):
        """Create a widget for a course"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        name_label = QtWidgets.QLabel(course['name'])
        code_label = QtWidgets.QLabel(course['code'])
        description_label = QtWidgets.QLabel(course['description'])
        layout.addWidget(name_label)
        layout.addWidget(code_label)
        layout.addWidget(description_label)
        widget.setLayout(layout)
        return widget


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
            QtWidgets.QMessageBox.information(
                self,
                translator.t("common.info"),
                translator.t("messages.no_courses_to_plan")
            )
            return
            
        # Show progress dialog
        progress = QtWidgets.QProgressDialog(
            translator.t("messages.generating_combinations"), 
            translator.t("messages.cancel"), 
            0, 100, self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        try:
            # Generate best combinations
            combos = generate_best_combinations_for_groups(all_courses)
            progress.setValue(50)
            
            if not combos:
                QtWidgets.QMessageBox.warning(
                    self, 
                    translator.t("messages.result"),
                    translator.t("messages.no_combos_found")
                )
                return
            
            # Display results in a dialog
            self.show_optimal_schedule_results(combos)
            progress.setValue(100)
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, 
                translator.t("common.error"),
                translator.t("messages.generate_combos_error", error=str(e))
            )
            print(f"Error in generate_optimal_schedule: {e}")
        finally:
            progress.close()

    def show_optimal_schedule_results(self, combos):
        """Show optimal schedule results in a dialog"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(translator.t("messages.optimal_combos_title"))
        dialog.resize(600, 400)
        dialog.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Title
        title_label = QtWidgets.QLabel(translator.t("messages.optimal_combos_title"))
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin: 10px;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Info label
        if combos:
            info_label = QtWidgets.QLabel(translator.t("messages.optimal_combos_info"))
        else:
            info_label = QtWidgets.QLabel(translator.t("messages.no_conflict_free_combos"))
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
                
                stats_label = QtWidgets.QLabel(translator.t("hardcoded_texts.days_distance_score", days=combo["days"], empty=combo["empty"], score=combo["score"]))
                stats_label.setStyleSheet("color: #7f8c8d;")
                
                apply_btn = QtWidgets.QPushButton(translator.t("hardcoded_texts.apply"))
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
                            f"{course['name']} - {course['code']} - {course.get('instructor', translator.t('messages.unknown'))}"
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
        close_btn = QtWidgets.QPushButton(translator.t("hardcoded_texts.close"))
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
            
            # Sort courses by priority (lower number = higher priority)
            sorted_courses = sorted(combo['courses'], key=lambda x: course_priorities.get(x, 999))
            
            # Process all course additions first
            for course_key in sorted_courses:
                if course_key in COURSES:
                    try:
                        # Add course with conflict handling (async, goes to queue)
                        self.add_course_to_table(course_key, ask_on_conflict=False)
                    except Exception as e:
                        logger.error(f"Error adding course {course_key}: {e}")
            
            # Wait for all courses to be processed
            while self.course_addition_queue:
                QtWidgets.QApplication.processEvents()
                QtCore.QThread.msleep(50)
            
            # Process the queue to ensure all courses are added
            self._process_course_addition_queue()
            
            # Wait a bit more to ensure UI updates
            QtWidgets.QApplication.processEvents()
            QtCore.QThread.msleep(100)
            
            # Now check which courses were actually added by checking self.placed
            added_courses = set()
            for info in self.placed.values():
                if info.get('type') == 'dual':
                    # For dual courses, add both courses
                    added_courses.update(info.get('courses', []))
                else:
                    # For single courses, add the course key
                    added_courses.add(info.get('course'))
            
            # Determine which courses were added and which had conflicts
            added_count = 0
            conflicts = []
            
            for course_key in sorted_courses:
                if course_key in COURSES:
                    if course_key in added_courses:
                        added_count += 1
                    else:
                        # Course was not added - check if it's actually a conflict
                        course = COURSES[course_key]
                        has_real_conflict = False
                        
                        for sess in course.get('schedule', []):
                            for (prow, pcol), placed_info in list(self.placed.items()):
                                placed_course = COURSES.get(placed_info.get('course'), {})
                                for placed_sess in placed_course.get('schedule', []):
                                    if (sess['day'] == placed_sess['day'] and 
                                        sess['start'] == placed_sess['start'] and
                                        sess['end'] == placed_sess['end']):
                                        # Same time slot - check parity compatibility
                                        sess_parity = sess.get('parity', '') or ''
                                        placed_parity = placed_sess.get('parity', '') or ''
                                        is_compatible = (
                                            (sess_parity == 'ز' and placed_parity == 'ف') or
                                            (sess_parity == 'ف' and placed_parity == 'ز')
                                        )
                                        if not is_compatible:
                                            has_real_conflict = True
                                            break
                                if has_real_conflict:
                                    break
                            if has_real_conflict:
                                break
                        
                        if has_real_conflict:
                            conflicts.append(COURSES[course_key].get('name', course_key))
            
            # Update UI
            self.update_status()
            self.update_stats_panel()
            self.update_detailed_info_if_open()
            
            # Close dialog
            dialog.close()
            
            # Show detailed results with translated messages
            if conflicts:
                # Build detailed message with added courses and conflicts
                added_courses_list = []
                for course_key in sorted_courses:
                    if course_key in added_courses:
                        course = COURSES.get(course_key, {})
                        added_courses_list.append(f"  • {course.get('name', course_key)} ({course.get('code', '')})")
                
                msg = f"{translator.t('messages.courses_added', count=added_count)}\n"
                if added_courses_list:
                    msg += translator.t("messages.added_courses_list") + "\n"
                    msg += "\n".join(added_courses_list[:10])  # Show up to 10 courses
                    if len(added_courses_list) > 10:
                        msg += f"\n  ... {translator.t('messages.courses_conflict_more', count=len(added_courses_list)-10)}"
                
                msg += f"\n\n⚠️ {translator.t('messages.courses_conflict', count=len(conflicts))}\n"
                for conflict_name, conflict_reason in conflicts[:10]:
                    msg += f"  • {conflict_name}\n"
                    if conflict_reason:
                        msg += f"    {conflict_reason}\n"
                if len(conflicts) > 10:
                    msg += f"  ... {translator.t('messages.courses_conflict_more', count=len(conflicts)-10)}"
            else:
                # Build detailed message with all added courses
                added_courses_list = []
                for course_key in sorted_courses:
                    if course_key in added_courses:
                        course = COURSES.get(course_key, {})
                        added_courses_list.append(f"  • {course.get('name', course_key)} ({course.get('code', '')})")
                
                msg = f"{translator.t('messages.courses_added_all', count=added_count)}\n\n"
                if added_courses_list:
                    msg += translator.t("messages.added_courses_list") + "\n"
                    msg += "\n".join(added_courses_list[:15])  # Show up to 15 courses
                    if len(added_courses_list) > 15:
                        msg += f"\n  ... {translator.t('messages.courses_conflict_more', count=len(added_courses_list)-15)}"
            
            # Create message box with correct layout direction
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Information)
            msg_box.setWindowTitle(translator.t("messages.result"))
            msg_box.setText(msg)
            
            # Set layout direction based on current language
            from app.core.language_manager import language_manager
            current_lang = language_manager.get_current_language()
            if current_lang == 'fa':
                msg_box.setLayoutDirection(QtCore.Qt.RightToLeft)
            else:
                msg_box.setLayoutDirection(QtCore.Qt.LeftToRight)
            
            msg_box.exec_()
            
        except Exception as e:
            logger.error(f"Error applying combo: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                translator.t("common.error"), 
                translator.t("messages.apply_combo_error", error=str(e))
            )

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
            self, 
            translator.t("messages.combo_applied"),
            translator.t("messages.combo_applied_message", days=combo["days"], empty=combo["empty"])
        )

    def load_saved_combos_ui(self):
        """Load saved combinations into the UI"""
        self.saved_combos_list.clear()
        for sc in self.user_data.get('saved_combos', []):
            name = sc.get('name', translator.t("common.no_name"))
            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, sc)
            self.saved_combos_list.addItem(item)

    def save_current_combo(self):
        """Save the current combination of courses"""
        from app.core.translator import translator
        
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
            QtWidgets.QMessageBox.information(
                self,
                translator.t("common.info"),
                translator.t("save.no_courses")
            )
            return
            
        # Get existing combo names for duplicate checking
        existing_names = [combo.get('name', '') for combo in self.user_data.get('saved_combos', [])]
        
        while True:
            name, ok = QtWidgets.QInputDialog.getText(
                self, 
                translator.t("messages.combo_name_title"),
                translator.t("messages.combo_name_prompt")
            )
            if not ok:
                return
            
            name = name.strip()
            if not name:
                QtWidgets.QMessageBox.warning(
                    self,
                    translator.t("common.warning"),
                    translator.t("hardcoded_texts.enter_name")
                )
                continue
                
            # Check for duplicate names
            if name in existing_names:
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle(translator.t("messages.duplicate_name_title"))
                msg.setText(translator.t("messages.duplicate_name_text", name=name))
                msg.setInformativeText(translator.t("messages.duplicate_name_info"))
                msg.setStandardButtons(QtWidgets.QMessageBox.Retry | QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
                msg.setDefaultButton(QtWidgets.QMessageBox.Retry)
                msg.button(QtWidgets.QMessageBox.Retry).setText(translator.t("messages.new_name"))
                msg.button(QtWidgets.QMessageBox.Yes).setText(translator.t("messages.replace"))
                msg.button(QtWidgets.QMessageBox.Cancel).setText(translator.t("common.cancel"))
                
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
                
                # Show confirmation with translation
                QtWidgets.QMessageBox.information(
                    self, 
                    translator.t("save.success_title"), 
                    translator.t("save.success_message", name=name, count=len(keys))
                )
            except Exception as e:
                logger.error(f"Error saving combo: {e}")
                QtWidgets.QMessageBox.critical(
                    self, translator.t("hardcoded_texts.error_generic"), 
                    f"{translator.t('save.error')}:\n{str(e)}"
                )
            
            return
        
        


    def update_item_size_hint(self, item, widget):
        """Update the size hint for a QListWidgetItem based on its widget"""
        if item and widget:
            item.setSizeHint(widget.sizeHint())
            



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
            self, 
            translator.t("messages.combo_loaded_title"),
            translator.t("messages.combo_loaded_message", name=sc.get('name', translator.t("common.no_name")), count=loaded_count)
        )
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()

    def on_saved_combo_clicked(self, item):
        """Handle click on saved combination item"""
        if item is not None:
            self.load_saved_combo(item)

    def on_save_current_combo(self):
        """Handle save current combo button click"""
        try:
            logger.info("Save current combo button clicked")
            self.save_current_combo()
        except Exception as e:
            logger.error(f"Error in on_save_current_combo: {e}")
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self, 'خطا', 
                f'خطا در ذخیره ترکیب:\n{str(e)}'
            )

    def on_delete_saved_combo(self):
        """Handle delete saved combo button click"""
        # Get selected item from saved_combos_list
        selected_items = self.saved_combos_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(
                self,
                translator.t("common.info"),
                translator.t("messages.select_combination")
            )
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
                    item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, priority)
                    
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
            QtWidgets.QMessageBox.information(
                self, 
                translator.t("common.info"),
                translator.t("messages.priority_list_empty")
            )
            return
        
        # Show progress dialog
        progress = QtWidgets.QProgressDialog(
            translator.t("messages.generating_combinations"), 
            translator.t("messages.cancel"), 
            0, 100, self
        )
        progress.setWindowModality(Qt.WindowModal)
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
                self, translator.t("hardcoded_texts.error_generic"), 
                f"{translator.t('messages.generate_combos_error')}:\n{str(e)}"
            )
            print(f"Error in generate_optimal_schedule_from_auto_list: {e}")
        finally:
            progress.close()

    def show_optimal_schedule_results(self, combos):
        """Show optimal schedule results in a dialog"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(translator.t("messages.optimal_combos_title"))
        dialog.resize(600, 400)
        dialog.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Title
        title_label = QtWidgets.QLabel(translator.t("messages.optimal_combos_title"))
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin: 10px;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Info label
        if combos:
            info_label = QtWidgets.QLabel('بهترین ترکیب‌ها بر اساس حداقل روزهای حضور و حداقل فاصله بین جلسات')
        else:
            info_label = QtWidgets.QLabel(translator.t("messages.no_conflict_free_combos"))
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
                
                stats_label = QtWidgets.QLabel(translator.t("hardcoded_texts.days_distance_score", days=combo["days"], empty=combo["empty"], score=combo["score"]))
                stats_label.setStyleSheet("color: #7f8c8d;")
                
                apply_btn = QtWidgets.QPushButton(translator.t("hardcoded_texts.apply"))
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
                            f"{course['name']} - {course['code']} - {course.get('instructor', translator.t('messages.unknown'))}"
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
        close_btn = QtWidgets.QPushButton(translator.t("hardcoded_texts.close"))
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec_()



    def show_priority_aware_results(self, schedules, original_priority_order):
        """Show results with clear priority information"""
        if not schedules:
            QtWidgets.QMessageBox.information(
                self, 
                translator.t("messages.result"),
                translator.t("messages.no_schedule_possible")
            )
            return
        
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(translator.t("messages.priority_schedules_title"))
        dialog.setModal(True)
        dialog.resize(700, 500)
        dialog.setLayoutDirection(QtCore.Qt.RightToLeft)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Description label
        info_label = QtWidgets.QLabel(translator.t("messages.priority_schedules_info", count=len(schedules)))
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
            item.setData(QtCore.Qt.ItemDataRole.UserRole, schedule)  # Store complete schedule
            schedule_list.addItem(item)
        
        layout.addWidget(schedule_list)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        apply_btn = QtWidgets.QPushButton(translator.t("messages.apply_schedule"))
        cancel_btn = QtWidgets.QPushButton(translator.t("common.cancel"))
        
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
                QtWidgets.QMessageBox.warning(
                    dialog, 
                    translator.t("common.warning"), 
                    translator.t("messages.select_schedule")
                )
        
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
            
            # Process all course additions first
            for course_key in schedule['courses']:
                if course_key in COURSES:
                    try:
                        # Add course with conflict handling (async, goes to queue)
                        self.add_course_to_table(course_key, ask_on_conflict=False)
                    except Exception as e:
                        logger.error(f"Error adding course {course_key}: {e}")
            
            # Wait for all courses to be processed
            while self.course_addition_queue:
                QtWidgets.QApplication.processEvents()
                QtCore.QThread.msleep(50)
            
            # Process the queue to ensure all courses are added
            self._process_course_addition_queue()
            
            # Wait a bit more to ensure UI updates
            QtWidgets.QApplication.processEvents()
            QtCore.QThread.msleep(100)
            
            # Now check which courses were actually added by checking self.placed
            added_courses = set()
            for info in self.placed.values():
                if info.get('type') == 'dual':
                    # For dual courses, add both courses
                    added_courses.update(info.get('courses', []))
                else:
                    # For single courses, add the course key
                    added_courses.add(info.get('course'))
            
            # Determine which courses were added and which had conflicts
            added_count = 0
            conflicts = []  # List of tuples: (course_name, conflict_reason)
            
            for course_key in schedule['courses']:
                if course_key in COURSES:
                    if course_key in added_courses:
                        added_count += 1
                    else:
                        # Course was not added - check if it's actually a conflict
                        # by verifying if it conflicts with already placed courses
                        course = COURSES[course_key]
                        has_real_conflict = False
                        conflict_reason = ""
                        conflicting_courses = []
                        
                        for sess in course.get('schedule', []):
                            for (prow, pcol), placed_info in list(self.placed.items()):
                                placed_course_key = placed_info.get('course')
                                if placed_course_key and placed_course_key in COURSES:
                                    placed_course = COURSES[placed_course_key]
                                    for placed_sess in placed_course.get('schedule', []):
                                        if (sess['day'] == placed_sess['day'] and 
                                            sess['start'] == placed_sess['start'] and
                                            sess['end'] == placed_sess['end']):
                                            # Same time slot - check parity compatibility
                                            sess_parity = sess.get('parity', '') or ''
                                            placed_parity = placed_sess.get('parity', '') or ''
                                            is_compatible = (
                                                (sess_parity == 'ز' and placed_parity == 'ف') or
                                                (sess_parity == 'ف' and placed_parity == 'ز')
                                            )
                                            if not is_compatible:
                                                has_real_conflict = True
                                                if placed_course.get('name') not in conflicting_courses:
                                                    conflicting_courses.append(placed_course.get('name', placed_course_key))
                                                break
                                    if has_real_conflict:
                                        break
                            if has_real_conflict:
                                break
                        
                        if has_real_conflict:
                            conflict_reason = translator.t("messages.conflict_reason")
                            if conflicting_courses:
                                conflict_reason += " " + ", ".join(conflicting_courses[:3])
                                if len(conflicting_courses) > 3:
                                    conflict_reason += f" (+{len(conflicting_courses)-3} more)"
                            conflicts.append((COURSES[course_key].get('name', course_key), conflict_reason))
            
            # Update UI
            self.update_status()
            self.update_stats_panel()
            self.update_detailed_info_if_open()
            
            # Close dialog
            dialog.close()
            
            # Show detailed results with translated messages
            if conflicts:
                # Build detailed message with added courses and conflicts
                added_courses_list = []
                for course_key in schedule['courses']:
                    if course_key in added_courses:
                        course = COURSES.get(course_key, {})
                        added_courses_list.append(f"  • {course.get('name', course_key)} ({course.get('code', '')})")
                
                msg = f"{translator.t('messages.courses_added', count=added_count)}\n"
                if added_courses_list:
                    msg += translator.t("messages.added_courses_list") + "\n"
                    msg += "\n".join(added_courses_list[:10])  # Show up to 10 courses
                    if len(added_courses_list) > 10:
                        msg += f"\n  ... {translator.t('messages.courses_conflict_more', count=len(added_courses_list)-10)}"
                
                msg += f"\n\n⚠️ {translator.t('messages.courses_conflict', count=len(conflicts))}\n"
                for conflict_name, conflict_reason in conflicts[:10]:
                    msg += f"  • {conflict_name}\n"
                    if conflict_reason:
                        msg += f"    {conflict_reason}\n"
                if len(conflicts) > 10:
                    msg += f"  ... {translator.t('messages.courses_conflict_more', count=len(conflicts)-10)}"
            else:
                # Build detailed message with all added courses
                added_courses_list = []
                for course_key in schedule['courses']:
                    if course_key in added_courses:
                        course = COURSES.get(course_key, {})
                        added_courses_list.append(f"  • {course.get('name', course_key)} ({course.get('code', '')})")
                
                msg = f"{translator.t('messages.courses_added_all', count=added_count)}\n\n"
                if added_courses_list:
                    msg += translator.t("messages.added_courses_list") + "\n"
                    msg += "\n".join(added_courses_list[:15])  # Show up to 15 courses
                    if len(added_courses_list) > 15:
                        msg += f"\n  ... {translator.t('messages.courses_conflict_more', count=len(added_courses_list)-15)}"
            
            # Create message box with correct layout direction
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Information)
            msg_box.setWindowTitle(translator.t("messages.result"))
            msg_box.setText(msg)
            
            # Set layout direction based on current language
            from app.core.language_manager import language_manager
            current_lang = language_manager.get_current_language()
            if current_lang == 'fa':
                msg_box.setLayoutDirection(QtCore.Qt.RightToLeft)
            else:
                msg_box.setLayoutDirection(QtCore.Qt.LeftToRight)
            
            msg_box.exec_()
            
        except Exception as e:
            logger.error(f"Error applying schedule: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                translator.t("common.error"), 
                translator.t("messages.apply_schedule_error", error=str(e))
            )

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
            delete_action = menu.addAction(translator.t("hardcoded_texts.remove_from_list"))
        
        # Always show clear all option if there are items in the list
        if self.auto_select_list.count() > 0:
            clear_all_action = menu.addAction(translator.t("hardcoded_texts.clear_all_title"))
        
        action = menu.exec_(self.auto_select_list.mapToGlobal(position))
        
        if 'delete_action' in locals() and action == delete_action:
            row = self.auto_select_list.row(item)
            self.auto_select_list.takeItem(row)
        elif 'clear_all_action' in locals() and action == clear_all_action:
            # Confirm clear all
            reply = QtWidgets.QMessageBox.question(
                self, translator.t("hardcoded_texts.clear_all_title"), 
                translator.t("hardcoded_texts.clear_all_confirm", count=self.auto_select_list.count()),
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
            self, translator.t("hardcoded_texts.delete_combo_title"), 
            translator.t("hardcoded_texts.delete_combo_confirm", combo_name=combo_name),
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
                self, translator.t("hardcoded_texts.deleted"), 
                translator.t("success.combination_deleted", combo_name=combo_name)
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
        
        # save to user data
        self.user_data.setdefault('custom_courses', []).append(course)
        save_user_data(self.user_data)
        
        # refresh list and info panel
        self.populate_course_list()
        self.update_course_info_panel()  # Update info panel
        QtWidgets.QMessageBox.information(
            self,
            translator.t("success.title"),
            translator.t("success.course_added_saved", course_name=course["name"])
        )

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
            from app.ui.dialogs import ExamScheduleWindow
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
                QtWidgets.QMessageBox.information(
                    self,
                    translator.t("common.info"),
                    translator.t("messages.select_course")
                )
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
                        new_item = QtWidgets.QListWidgetItem(f"({position}) {course['name']} - {course.get('instructor', translator.t('hardcoded_texts.unknown'))}")
                        new_item.setData(QtCore.Qt.ItemDataRole.UserRole, course_key)
                        # Set position as priority (first item = priority 1)
                        new_item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, position)
                        self.auto_select_list.addItem(new_item)
            
            # Save user data
            self.save_auto_select_list()
            
        except Exception as e:
            logger.error(f"Error adding to auto list: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                translator.t("common.error"),
                translator.t("messages.auto_add_error", error=str(e))
            )

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
            logger.error(f"Error : {e}")
            QtWidgets.QMessageBox.critical(
                self,
                translator.t("common.error"),
                translator.t("messages.generic_error", error=str(e))
            )

    def update_item_size_hint(self, item, widget):
        """Update the size hint for a QListWidgetItem based on its widget - FIXED to prevent RuntimeError with deleted objects"""
        try:
            if item and widget:
                # Check if the item and widget still exist (not deleted)
                if hasattr(item, 'setSizeHint') and hasattr(widget, 'sizeHint'):
                    item.setSizeHint(widget.sizeHint())
        except RuntimeError as e:
            # Handle the case where the C/C++ object has been deleted
            if "wrapped C/C++ object" in str(e):
                logger.warning("Attempted to update size hint for deleted C/C++ object - ignoring")
            else:
                logger.error(f"RuntimeError in update_item_size_hint: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in update_item_size_hint: {e}")

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
                QtWidgets.QMessageBox.information(
                    self,
                    translator.t("common.info"),
                    translator.t("messages.select_course")
                )
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
                QtWidgets.QMessageBox.information(
                    self, 
                    translator.t("messages.save_image_title"),
                    translator.t("messages.save_image_success")
                )
            else:
                QtWidgets.QMessageBox.warning(
                    self, 
                    translator.t("common.error"),
                    translator.t("messages.save_image_error")
                )

    def on_show_exam_schedule(self):
        """Show the exam schedule window"""
        try:
            # Create and show exam schedule window
            self.exam_schedule_window = ExamScheduleWindow(self)
            self.exam_schedule_window.show()
        except Exception as e:
            logger.error(f"Error showing exam schedule: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                translator.t("common.error"),
                translator.t("messages.show_exam_schedule_error", error=str(e))
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
                self, 
                translator.t("common.error"),
                translator.t("messages.export_exam_schedule_error", error=str(e))
            )

    def reset_golestan_credentials(self):
        """Reset Golestan credentials - delete saved credentials file and show confirmation"""
        try:
            from app.core.credentials import LOCAL_CREDENTIALS_FILE, delete_local_credentials
            
            # Delete the local credentials file
            if delete_local_credentials():
                # Show confirmation message
                QtWidgets.QMessageBox.information(
                    self, 
                    translator.t("messages.credentials_deleted_title"),
                    translator.t("messages.credentials_deleted_message")
                )
                logger.info("Golestan credentials file deleted successfully")
            else:
                logger.error("Failed to delete Golestan credentials file")
                QtWidgets.QMessageBox.critical(
                    self, 
                    translator.t("common.error"),
                    translator.t("messages.credentials_delete_error")
                )
        except Exception as e:
            logger.error(f"Error in reset golestan credentials: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                translator.t("common.error"),
                translator.t("messages.credentials_delete_error")
            )

    def _handle_golestan_error(self, error):
        """
        Handle Golestan errors and display appropriate user-friendly messages.
        
        Args:
            error: Exception object or error message string
            
        Returns:
            tuple: (title, message) for error dialog
        """
        error_msg = str(error) if isinstance(error, Exception) else error
        
        # Check for specific error types
        if "SSL_ERROR:" in error_msg:
            return (
                translator.t("common.error"),
                translator.t("messages.ssl_error")
            )
        elif "CONNECTION_ERROR:" in error_msg:
            return (
                translator.t("common.error"),
                translator.t("messages.connection_error")
            )
        elif "TIMEOUT_ERROR:" in error_msg:
            return (
                translator.t("common.error"),
                translator.t("messages.timeout_error")
            )
        elif "CAPTCHA_FAILED:" in error_msg or "Authentication failed" in error_msg:
            # Remove any technical details about CAPTCHA
            return (
                translator.t("common.warning"),
                translator.t("messages.captcha_failed")
            )
        elif "No courses were fetched" in error_msg or "No courses" in error_msg:
            return (
                translator.t("common.warning"),
                translator.t("messages.no_courses_error")
            )
        elif "check your username and password" in error_msg.lower() or "invalid" in error_msg.lower() and "credentials" in error_msg.lower():
            return (
                translator.t("common.warning"),
                translator.t("messages.invalid_credentials")
            )
        else:
            # Unknown error - show generic user-friendly message without technical details
            return (
                translator.t("common.error"),
                translator.t("messages.unknown_error")
            )

    def fetch_from_golestan(self):
        """Fetch courses from Golestan system automatically with non-blocking loading"""
        try:
            from app.core.credentials import load_local_credentials
            from .credentials_dialog import GolestanCredentialsDialog
            from .loading_dialog import LoadingDialog, GolestanWorker
            
            # Check if credentials dialog is already open
            if hasattr(self, 'credentials_dialog_open') and self.credentials_dialog_open:
                return
            self.credentials_dialog_open = True
            
            try:
                # Check if local credentials exist
                credentials = load_local_credentials()
                
                # If credentials don't exist, prompt user
                if credentials is None:
                    # Check if a dialog is already open
                    if hasattr(self, '_golestan_dialog') and self._golestan_dialog is not None and self._golestan_dialog.isVisible():
                        self._golestan_dialog.raise_()
                        self._golestan_dialog.activateWindow()
                        return
                    
                    # Create and show dialog to get credentials
                    self._golestan_dialog = GolestanCredentialsDialog(self)
                    result = self._golestan_dialog.get_credentials()
                    self._golestan_dialog = None
                    
                    if result[0] is None or result[1] is None:
                        return
                    
                    student_number, password, remember = result
                    
                    if remember:
                        from app.core.credentials import save_local_credentials
                        save_local_credentials(student_number, password, remember)
                    
                    credentials = {
                        'student_number': student_number,
                        'password': password
                    }
                else:
                    student_number = credentials['student_number']
                    password = credentials['password']
                
                from app.core.credential_validator import validate_credentials
                is_valid, error_message = validate_credentials(student_number.strip() if student_number else "", password.strip() if password else "")
                if not is_valid:
                    QtWidgets.QMessageBox.warning(
                        self,
                        translator.t("common.warning"),
                        error_message or translator.t("messages.credentials_required")
                    )
                    return
                
                loading_dialog = LoadingDialog(
                    self, 
                    translator.t("messages.fetching_golestan_data")
                )
                loading_dialog.show()
                QtWidgets.QApplication.processEvents()
                
                # Create worker thread
                worker = GolestanWorker(
                    'fetch_courses',
                    username=student_number,
                    password=password
                )
                
                # Connect signals
                def on_progress(message):
                    loading_dialog.set_message(message)
                
                def on_finished(result):
                    loading_dialog.close()
                    if isinstance(result, Exception):
                        # Error occurred
                        logger.error(f"Error fetching from Golestan: {result}")
                        error_title, error_message = self._handle_golestan_error(result)
                        
                        # Determine message box type based on title
                        if error_title == translator.t("common.warning"):
                            QtWidgets.QMessageBox.warning(self, error_title, error_message)
                        else:
                            QtWidgets.QMessageBox.critical(self, error_title, error_message)
                    else:
                        # Success - load from database (which now contains fresh data from Golestan)
                        course_count = 0
                        if self.db is not None:
                            try:
                                course_count = self.db.get_course_count()
                            except:
                                pass
                        self.load_courses_from_database()
                        self.refresh_ui()
                        QtWidgets.QMessageBox.information(
                            self, 
                            translator.t("success.title"),
                            translator.t("messages.golestan_fetch_success", count=course_count)
                        )
                
                worker.progress.connect(on_progress)
                worker.finished.connect(on_finished)
                
                # Start worker
                worker.start()
                
                while worker.isRunning():
                    QtWidgets.QApplication.processEvents()
                    QtCore.QThread.msleep(50)
                
            finally:
                self.credentials_dialog_open = False
                
        except Exception as e:
            if hasattr(self, 'credentials_dialog_open'):
                self.credentials_dialog_open = False
            logger.error(f"Error fetching from Golestan: {e}")
            error_title, error_message = self._handle_golestan_error(e)
            if error_title == translator.t("common.warning"):
                QtWidgets.QMessageBox.warning(self, error_title, error_message)
            else:
                QtWidgets.QMessageBox.critical(self, error_title, error_message)

    def manual_fetch_from_golestan(self):
        """Fetch courses from Golestan system with manual credentials and non-blocking loading"""
        try:
            from .loading_dialog import LoadingDialog, GolestanWorker
            
            # Get credentials from user
            username, ok1 = QtWidgets.QInputDialog.getText(
                self, 
                translator.t("credentials_dialog.title"),
                translator.t("credentials_dialog.student_number_label") + ":"
            )
            if not ok1 or not username:
                return
                
            password, ok2 = QtWidgets.QInputDialog.getText(
                self, 
                translator.t("credentials_dialog.title"),
                translator.t("credentials_dialog.password_label") + ":", 
                QtWidgets.QLineEdit.Password
            )
            if not ok2 or not password:
                return
            
            from app.core.credential_validator import validate_credentials
            is_valid, error_message = validate_credentials(username.strip(), password.strip())
            if not is_valid:
                QtWidgets.QMessageBox.warning(
                    self,
                    translator.t("common.warning"),
                    error_message or translator.t("messages.credentials_required")
                )
                return
            
            loading_dialog = LoadingDialog(
                self, 
                "در حال دریافت اطلاعات از سامانه گلستان، لطفاً صبر کنید..."
            )
            loading_dialog.show()
            QtWidgets.QApplication.processEvents()
            
            # Create worker thread
            worker = GolestanWorker(
                'fetch_courses',
                username=username,
                password=password
            )
            
            # Connect signals
            def on_progress(message):
                loading_dialog.set_message(message)
            
            def on_finished(result):
                loading_dialog.close()
                if isinstance(result, Exception):
                    logger.error(f"Error fetching from Golestan: {result}")
                    error_title, error_message = self._handle_golestan_error(result)
                    
                    # Determine message box type based on title
                    if error_title == translator.t("common.warning"):
                        QtWidgets.QMessageBox.warning(self, error_title, error_message)
                    else:
                        QtWidgets.QMessageBox.critical(self, error_title, error_message)
                else:
                    # Success - load from database (which now contains fresh data from Golestan)
                    course_count = 0
                    if self.db is not None:
                        try:
                            course_count = self.db.get_course_count()
                        except:
                            pass
                    self.load_courses_from_database()
                    self.refresh_ui()
                    QtWidgets.QMessageBox.information(
                        self, 
                        translator.t("success.title"),
                        translator.t("messages.golestan_fetch_success", count=course_count) if course_count > 0 else translator.t("messages.golestan_fetch_success")
                    )
            
            worker.progress.connect(on_progress)
            worker.finished.connect(on_finished)
            
            # Start worker
            worker.start()
            
            # Keep dialog visible until worker finishes
            while worker.isRunning():
                QtWidgets.QApplication.processEvents()
                QtCore.QThread.msleep(50)
            
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
        try:
            if hasattr(self, 'credentials_dialog_open') and self.credentials_dialog_open:
                return
            self.credentials_dialog_open = True
            
            try:
                from app.core.credentials import delete_local_credentials
                from .credentials_dialog import GolestanCredentialsDialog
                
                if delete_local_credentials():
                    logger.info("Existing Golestan credentials cleared successfully")
                else:
                    logger.warning("Failed to clear Golestan credentials")
                
                if hasattr(self, '_golestan_dialog') and self._golestan_dialog is not None and self._golestan_dialog.isVisible():
                    self._golestan_dialog.raise_()
                    self._golestan_dialog.activateWindow()
                    return
                
                self._golestan_dialog = GolestanCredentialsDialog(self)
                result = self._golestan_dialog.get_credentials()
                self._golestan_dialog = None
                
                if result[0] is not None and result[1] is not None:
                    student_number, password, remember = result
                    
                    from app.core.credentials import save_local_credentials
                    if save_local_credentials(student_number, password, remember):
                        logger.info("New Golestan credentials saved successfully")
                        QtWidgets.QMessageBox.information(
                            self, 
                            "موفقیت", 
                            "اطلاعات ورود گلستان با موفقیت ذخیره شد. این اطلاعات فقط روی این دستگاه نگهداری می‌شود."
                        )
                        self.fetch_from_golestan_with_new_credentials(student_number, password)
                    else:
                        logger.error("Failed to save new Golestan credentials")
                        QtWidgets.QMessageBox.critical(
                            self, 
                            "خطا", 
                            "خطا در ذخیره اطلاعات ورود جدید."
                        )
                else:
                    logger.info("User cancelled credential entry")
                    
            finally:
                self.credentials_dialog_open = False
                
        except Exception as e:
            if hasattr(self, 'credentials_dialog_open'):
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
            progress = QtWidgets.QProgressDialog(
                translator.t("messages.fetching_golestan_data"), 
                translator.t("messages.cancel"), 
                0, 0, self
            )
            progress.setWindowModality(Qt.WindowModal)
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
        except Exception as e:
            logger.error(f"Failed to load latest backup: {e}")
            QtWidgets.QMessageBox.critical(self, translator.t("hardcoded_texts.error_generic"), f"{translator.t('hardcoded_texts.error_backup_load')}: {str(e)}")
            sys.exit(1)
                    
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
                no_backups_action = menu.addAction(translator.t("backup.no_history"))
                no_backups_action.setEnabled(False)
                return
            
            # Add backup files to menu
            for i, backup_file in enumerate(backup_files):
                # Extract timestamp from filename
                filename = os.path.basename(backup_file)
                timestamp_part = filename.replace('user_data_', '').replace('user_data_auto_', '').replace('.json', '')
                
                try:
                    if '_' in timestamp_part:
                        parts = timestamp_part.split('_', 1)
                        if len(parts) == 2 and parts[0] == 'auto':
                            date_time_part = parts[1]
                        else:
                            date_time_part = timestamp_part
                        
                        date_part, time_part = date_time_part.split('_')
                        
                        year = int(date_part[:4])
                        month = int(date_part[4:6])
                        day = int(date_part[6:8])
                        
                        import jdatetime
                        jalali_date = jdatetime.date.fromgregorian(year=year, month=month, day=day)
                        
                        formatted_time = f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                        
                        display_text = f"{jalali_date.year}/{jalali_date.month:02d}/{jalali_date.day:02d} - {formatted_time}"
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
            from app.core.translator import translator
            QtWidgets.QMessageBox.information(self, translator.t("success.title"), translator.t("success.backup_loaded"))
            
        except Exception as e:
            logger.error(f"Error loading backup file {backup_file}: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                translator.t("common.error"),
                translator.t("messages.backup_load_error", error=str(e))
            )

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

    def show_tutorial(self):
        """Show the tutorial dialog"""
        try:
            # Create and show the tutorial dialog
            dialog = TutorialDialog(self)
            
            # Connect the finished signal
            def on_tutorial_finished(normally):
                # Handle tutorial completion
                if normally:
                    logger.info("Tutorial finished normally")
                else:
                    logger.info("Tutorial was skipped")
                    
            dialog.tutorial_finished.connect(on_tutorial_finished)
            
            # Show the dialog
            dialog.exec_()
        except Exception as e:
            logger.error(f"Error showing tutorial: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                translator.t("common.error"),
                translator.t("errors.tutorial_show", error=str(e))
            )

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
        """Check if new course is compatible with existing dual courses"""
        from .dual_course_utils import courses_are_compatible
        return courses_are_compatible(odd_course, even_course, new_course)

    def _schedules_overlap(self, schedule1, schedule2):
        """Check if two schedules have overlapping time slots"""
        from .dual_course_utils import schedules_overlap
        return schedules_overlap(schedule1, schedule2)

    def keyPressEvent(self, event):
        """Handle key press events for the main window"""
        # Handle F1 key to show tutorial (F1 key code is 16777264)
        if event.key() == 16777264:
            self.show_tutorial()
        else:
            super().keyPressEvent(event)

