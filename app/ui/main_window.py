import logging
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
    load_user_data, save_user_data, generate_unique_key, 
    load_courses_from_json
)
from app.core.logger import setup_logging
from app.core.error_humanizer import humanize_error
from app.core.course_utils import (
    to_minutes, overlap, schedules_conflict, 
    calculate_days_needed_for_combo, calculate_empty_time_for_combo,
    generate_best_combinations_for_groups,
    generate_priority_based_schedules, create_greedy_schedule, create_alternative_schedule
)
from .widgets import (
    CourseListWidget, AnimatedCourseWidget
)
from .dialogs import AddCourseDialog, EditCourseDialog, CourseDetailsDialog
from .exam_schedule_window import ExamScheduleWindow

# Import credential handling modules
from app.core.credentials import load_local_credentials
from .credentials_dialog import get_golestan_credentials

# Import Phase 1 - Phase 8 Managers & UI Dialogs
import app.core.auth as auth
import app.core.network as net
from app.core.professor_manager import ProfessorManager
from app.core.cloud_sync_manager import ScheduleSyncManager
from app.core.academic_manager import AcademicManager
from app.core.version_manager import VersionManager
from app.core.settings_manager import SettingsManager
from app.data.offline_storage_service import OfflineStorageService

from app.ui.account_auth_dialog import AccountAuthDialog
from app.ui.professor_review_dialog import ProfessorReviewDialog
from app.ui.sync_dialog import CloudScheduleDialog
from app.ui.settings_dialog import SettingsDialog

# Set up logger
logger = setup_logging()

# ---------------------- Main Application Window ----------------------

class SchedulerWindow(QtWidgets.QMainWindow):
    """Main window for the Schedule Planner application"""
    
    def __init__(self, db=None):
        super().__init__()
        
        # Store the database instance
        self.db = db
        
        # Initialize Services
        from app.core.services.golestan_service import GolestanService
        self.golestan_service = GolestanService(logger)
        from app.core.services.backup_service import BackupService
        self.backup_service = BackupService(logger)
        from app.ui.dialog_coordinator import DialogCoordinator
        self.dialog_coordinator = DialogCoordinator(self, logger)
        from app.ui.builders.menu_builder import MenuBuilder
        from app.ui.controllers.course_search_controller import CourseSearchController
        from app.ui.controllers.schedule_table_controller import ScheduleTableController
        from app.ui.controllers.status_bar_controller import StatusBarController
        from app.ui.controllers.auto_select_controller import AutoSelectListController

        self.course_search_controller = CourseSearchController(logger)
        self.schedule_table_controller = ScheduleTableController(logger)
        self.status_bar_controller = StatusBarController(logger)
        self.auto_select_controller = AutoSelectListController(logger)

        from app.core.services.auto_scheduler_service import AutoSchedulerService
        self.auto_scheduler = AutoSchedulerService(logger)
        
        # Get the directory of this file
        ui_dir = os.path.dirname(os.path.abspath(__file__))
        main_ui_file = os.path.join(ui_dir, 'main_window.ui')
        
        # Load UI from external file
        try:
            uic.loadUi(main_ui_file, self)
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, "خطا", f"فایل UI یافت نشد: {main_ui_file}")
            pass  # Gracefully keep app running
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "خطا در بارگذاری UI: "))
            pass  # Gracefully keep app running
        
        # Debug: Check if comboBox exists - only in debug mode
        if os.environ.get('DEBUG'):
            logger.debug(f"[DEBUG] comboBox exists: {hasattr(self, 'comboBox')}")
            if hasattr(self, 'comboBox'):
                logger.debug(f"[DEBUG] comboBox type: {type(self.comboBox)}")

        # Wire the course search controller to the widgets loaded from the
        # .ui file. Signal wiring stays with connect_signals() (which already
        # routes comboBox/search_box events to the controller), so only the
        # widget references and callbacks are attached here.
        self.course_search_controller.attach(
            search_box=getattr(self, 'search_box', None),
            major_combo=getattr(self, 'comboBox', None),
            course_list_widget=getattr(self, 'course_list', None),
            db_instance=self.db,
            get_current_major_filter=self._current_major_filter,
            on_refresh_course_list=lambda _major: self.populate_course_list(None),
            parent_window=self,
            wire_signals=False,
        )

        # Initialize schedule table FIRST
        self.initialize_schedule_table()
        
        # Setup responsive layout
        self.setup_responsive_layout()
        
        # Set layout direction
        from app.core.language_manager import language_manager
        current_app_lang = language_manager.get_current_language()
        self.setLayoutDirection(QtCore.Qt.LeftToRight if current_app_lang == 'en' else QtCore.Qt.RightToLeft)
        
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
        
        self.populate_course_list(None)  # No filter initially
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

        # Apply the saved language to .ui widgets (English startup support)
        self.retranslate_ui()
        
        # Load latest backup on startup
        self.load_latest_backup()
        
        # Initialize Phase 1 - Phase 8 Core Infrastructure
        self._init_phase_infrastructure()

        # Create menu bar
        self.create_menu_bar()

    def _init_phase_infrastructure(self):
        """Initialize Phase 1-8 Network, Auth, Managers, Settings, and Storage services."""
        try:
            self.token_manager = auth.TokenManager()
            self.network_session = net.SessionFactory.create_session(token_manager=self.token_manager)

            self.settings_manager = SettingsManager()
            self.offline_storage_service = OfflineStorageService()

            self.auth_client = net.AuthClient(session=self.network_session)
            self.schedule_client = net.ScheduleClient(session=self.network_session)
            self.professor_client = net.ProfessorClient(session=self.network_session)
            self.transcript_client = net.TranscriptClient(session=self.network_session)

            self.version_manager = VersionManager(base_client=net.BaseClient(session=self.network_session))
            self.professor_manager = ProfessorManager(client=self.professor_client)
            self.cloud_sync_manager = ScheduleSyncManager(client=self.schedule_client)
            self.academic_manager = AcademicManager(client=self.transcript_client)

            # Startup version check — warn the user when the client is outdated
            self.version_manager.check_api_compatibility(self._on_version_check_result)
        except Exception as e:
            logger.error(f"Failed to initialize Phase 1-8 infrastructure: {e}")

    def _on_version_check_result(self, compatible: bool, server_version: str, error: str = ""):
        """Handle the startup API version compatibility result (user-facing)."""
        try:
            logger.info(f"Version check: compatible={compatible}, ver={server_version}, err={error or 'none'}")
            if compatible:
                return
            # Offline / unknown errors are treated as compatible by the manager;
            # reaching here with compatible=False means a real version mismatch.
            QtWidgets.QMessageBox.warning(
                self,
                "به‌روزرسانی لازم است",
                "نسخه برنامه شما با نسخه فعلی سرورهای گلستون سازگار نیست و برخی قابلیت‌ها "
                "(همگام‌سازی ابری، کارنامه و نظرسنجی اساتید) ممکن است درست کار نکنند.\n\n"
                f"نسخه سرور: {server_version or 'نامشخص'}\n\n"
                "لطفاً آخرین نسخه برنامه را از golestoon-app.ir دریافت و نصب کنید."
            )
        except Exception as e:
            logger.error(f"Error handling version check result: {e}")

    def show_cloud_account_dialog(self):
        """Show Cloud Account Auth dialog."""
        try:
            dialog = AccountAuthDialog(auth_client=self.auth_client, token_manager=self.token_manager, parent=self)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Error showing account auth dialog: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "خطا در نمایش دیالوگ حساب ابری:\n"))

    def show_professor_review_dialog(self):
        """Show Professor Review & Compare dialog."""
        try:
            dialog = ProfessorReviewDialog(
                manager=self.professor_manager,
                parent=self,
                token_manager=getattr(self, 'token_manager', None),
                auth_client=getattr(self, 'auth_client', None),
            )
            dialog.exec_()
        except Exception as e:
            logger.error(f"Error showing professor review dialog: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "خطا در نمایش دیالوگ نظرسنجی اساتید:\n"))

    def show_cloud_schedule_dialog(self):
        """Show Cloud Schedule Sync dialog."""
        try:
            courses_payload = self.courses if hasattr(self, 'courses') and self.courses else []
            dialog = CloudScheduleDialog(sync_manager=self.cloud_sync_manager, current_local_courses=courses_payload, parent=self)
            dialog.load_schedule_requested.connect(self._on_cloud_schedule_loaded)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Error showing cloud schedule dialog: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "خطا در نمایش دیالوگ همگام‌سازی ابری:\n"))

    def _on_cloud_schedule_loaded(self, courses_list):
        """Slot called when user loads a cloud schedule into the main table."""
        try:
            self.clear_schedule()
            for c in courses_list:
                self.place_course(c)
            QtWidgets.QMessageBox.information(self, "موفقیت", "برنامه ابری با موفقیت در جدول کلاسی اعمال شد.")
        except Exception as e:
            logger.error(f"Error loading cloud schedule: {e}")

    def show_settings_dialog(self):
        """Show Settings & Preferences dialog."""
        try:
            dialog = SettingsDialog(settings_manager=self.settings_manager, storage_service=self.offline_storage_service, parent=self)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Error showing settings dialog: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "خطا در نمایش دیالوگ تنظیمات:\n"))
        
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
            self.schedule_table.setAlternatingRowColors(True)
            self.schedule_table.verticalHeader().setVisible(True)
            
            # Clean hourly labels (reference design): a single Persian hour
            # numeral («۷» … «۲۰») on whole-hour rows; half-hour rows stay
            # empty so each hour reads as one visual block.
            time_labels = []
            for i in range(len(EXTENDED_TIME_SLOTS) - 1):
                start_time = EXTENDED_TIME_SLOTS[i]
                if ':30' not in start_time:
                    hour = start_time.split(':')[0].lstrip('0') or '0'
                    time_labels.append(self.convert_to_persian_numerals(hour))
                else:
                    time_labels.append("")

            # Closing boundary mark («۲۰») on the final half-hour row so the
            # column reads ۷ … ۱۹ ۲۰ exactly like the reference design and it
            # is obvious the grid extends to 20:00.
            if time_labels:
                time_labels[-1] = self.convert_to_persian_numerals('20')

            # Set vertical header labels
            self.schedule_table.setVerticalHeaderLabels(time_labels)

            # Configure vertical header appearance (styled dark via QSS)
            vertical_header = self.schedule_table.verticalHeader()
            vertical_header.setFixedWidth(40)
            vertical_header.setDefaultSectionSize(35)
            vertical_header.setDefaultAlignment(QtCore.Qt.AlignCenter)

            # Make sure the table fills its panel completely (no stray gap)
            from PyQt5.QtWidgets import QSizePolicy
            self.schedule_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            
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
            logger.error("Unexpected error occurred", exc_info=True)

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
        self.course_search_controller.populate_major_dropdown()

    def _current_major_filter(self):
        """Current major filter for the course list; None means 'show all'."""
        try:
            combo = getattr(self, 'comboBox', None)
            if combo is None:
                return None
            data = combo.itemData(combo.currentIndex())
            if data is None or data == "ALL":
                return None
            return data
        except Exception:
            return None

    def populate_course_list_deprecated(self):
        """Deprecated method - use populate_course_list() instead"""
        try:
            # Call the new version
            self.populate_course_list()
        except Exception as e:
            logger.error(f"Failed to populate course list: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان پر کردن فهرست دروس وجود ندارد: "))
            pass  # Gracefully keep app running

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
                # Fallback to repopulating the course list with no filter
                self.populate_course_list(None)

        except Exception as e:
            logger.error(f"Failed to handle major change: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان مدیریت تغییر رشته وجود ندارد: "))
            pass  # Gracefully keep app running


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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان مدیریت انتخاب درس وجود ندارد: "))
            pass  # Gracefully keep app running

    def load_saved_combos_ui(self):
        """Load saved combinations into the UI (adds action buttons once)."""
        self._ensure_saved_combo_buttons()
        self.saved_combos_list.clear()
        for sc in self.user_data.get('saved_combos', []):
            name = sc.get('name', 'بدون نام')
            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, sc)
            self.saved_combos_list.addItem(item)

    def _ensure_saved_combo_buttons(self):
        """Arrange saved-combos actions: hide legacy misplaced buttons and add
        the working save/delete row BELOW the list (once)."""
        if getattr(self, '_saved_combo_buttons_added', False):
            return
        try:
            layout = self.saved_combos_layout
        except AttributeError:
            return

        # Hide the legacy «➕ افزودن / ➖ حذف» buttons — they belong to the
        # auto-select list but were placed inside the saved-combos group and
        # looked like broken duplicates.
        for legacy in ('add_to_auto_btn', 'remove_from_auto_btn'):
            btn = getattr(self, legacy, None)
            if btn is not None:
                btn.hide()
                btn.setParent(None)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(6)

        btn_save = QtWidgets.QPushButton("💾 ذخیره برنامه فعلی")
        btn_save.setObjectName("primaryButton")
        btn_save.setToolTip("برنامه‌ی فعلی جدول را با نام دلخواه ذخیره می‌کند")
        btn_save.clicked.connect(self.on_save_current_combo)

        btn_delete = QtWidgets.QPushButton("🗑️ حذف")
        btn_delete.setObjectName("secondaryButton")
        btn_delete.setToolTip("ترکیب انتخاب‌شده را از فهرست حذف می‌کند")
        btn_delete.clicked.connect(self.on_delete_saved_combo)

        btn_row.addWidget(btn_save, stretch=1)
        btn_row.addWidget(btn_delete)

        # Actions live at the BOTTOM of the group, below the list
        layout.addLayout(btn_row)
        # Keep references for live re-translation
        self._saved_combo_save_btn = btn_save
        self._saved_combo_delete_btn = btn_delete
        self._saved_combo_buttons_added = True

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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان مدیریت تغییر ترکیب ذخیره شده وجود ندارد: "))
            pass  # Gracefully keep app running

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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان بارگذاری ترکیب وجود ندارد: "))
            pass  # Gracefully keep app running

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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان پاک کردن جدول زمان‌بندی وجود ندارد: "))
            pass  # Gracefully keep app running

    def _safe_set_span(self, row: int, col: int, span: int) -> None:
        """setSpan without overlap warnings: reset any existing span first."""
        table = self.schedule_table
        try:
            if table.columnSpan(row, col) > 1 or table.rowSpan(row, col) > 1:
                table.setSpan(row, col, 1, 1)
        except Exception:  # noqa: BLE001 — cosmetic guard
            pass
        if span > 1:
            table.setSpan(row, col, span, 1)

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
            self._safe_set_span(row_start, col_start, row_span)
            self.schedule_table.setItem(row_start, col_start, item)

            # Store the placed course
            self.placed[course_key] = (row_start, col_start, row_span, col_span)

            # Update the status bar
            self.update_status()

            # Save user data
            save_user_data(self.user_data)

        except Exception as e:
            logger.error(f"Failed to place course: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان قرار دادن درس وجود ندارد: "))
            pass  # Gracefully keep app running

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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان مدیریت ورود به سلول وجود ندارد: "))
            pass  # Gracefully keep app running

    def on_cell_exited(self, row, col):
        """Handle cell exit event"""
        try:
            # Stop pulse animation for the cell
            self.stop_pulse_animation(row, col)

        except Exception as e:
            logger.error(f"Failed to handle cell exit event: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان مدیریت خروج از سلول وجود ندارد: "))
            pass  # Gracefully keep app running

    def start_pulse_animation(self, row, col):
        self.schedule_table_controller.start_pulse_animation(row, col)

    def stop_pulse_animation(self, row, col):
        self.schedule_table_controller.stop_pulse_animation(row, col)

    def pulse_cell(self, item):
        self.schedule_table_controller.pulse_cell(item)

    def show_detailed_info_window(self, course_key):
        """Show rich course details card for a course (theme-aware modal)."""
        try:
            if course_key in COURSES:
                dialog = CourseDetailsDialog(course_key, parent=self)
                dialog.exec_()
        except Exception as e:
            logger.error(f"Failed to show course details: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان نمایش پنجره اطلاعات دقیق وجود ندارد: "))

    def show_exam_schedule_window(self):
        """Show exam schedule window"""
        try:
            # Create and show the exam schedule window
            self.exam_schedule_window = ExamScheduleWindow(self)
            self.exam_schedule_window.show()

        except Exception as e:
            logger.error(f"Failed to show exam schedule window: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان نمایش پنجره زمان‌بندی امتحانات وجود ندارد: "))
            pass  # Gracefully keep app running

    def update_status(self):
        self.status_bar_controller.update_status()

    def update_stats_panel_deprecated(self):
        """Deprecated method - use update_stats_panel() instead"""
        try:
            # Call the new version
            self.update_stats_panel()
        except Exception as e:
            logger.error(f"Failed to update stats panel: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", 
                f"امکان به‌روزرسانی پانل آمار وجود ندارد: {str(e)}")
            pass  # Gracefully keep app running

        except Exception as e:
            logger.error(f"Failed to update stats panel: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان به‌روزرسانی پانل آمار وجود ندارد: "))
            pass  # Gracefully keep app running

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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان مدیریت تغییر اندازه وجود ندارد: "))
            pass  # Gracefully keep app running

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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان پاک کردن جستجو وجود ندارد: "))
            pass  # Gracefully keep app running

    def load_and_apply_styles(self):
        """Load the themed stylesheet onto this window.

        NOTE: the window-level stylesheet must be the THEMED build — a raw
        light styles.qss here would override the application-level theme for
        the entire main-window subtree (closest-ancestor stylesheet wins in
        Qt), which used to freeze the main window in light mode.
        """
        try:
            from app.core.theme_manager import theme_manager
            themed_qss = theme_manager.build_qss()
            if themed_qss:
                self.setStyleSheet(themed_qss)

            # Keep this window in sync with live theme switches
            try:
                theme_manager.theme_changed.connect(self._on_theme_changed)
            except (RuntimeError, TypeError):
                pass  # already connected
        except Exception as e:
            logger.warning(f"Warning: Could not load styles: {e}")

    def _on_theme_changed(self, effective_theme: str) -> None:
        """Live theme switch: re-apply window QSS and re-tint placed cells."""
        try:
            from app.core.theme_manager import theme_manager
            self.setStyleSheet(theme_manager.build_qss())

            # Re-tint placed course cells with the new theme variant
            from app.core.course_utils import course_color
            is_dark = effective_theme == 'dark'
            text_color = '#f8fafc' if is_dark else '#1e293b'
            for info in self.placed.values():
                if not isinstance(info, dict):
                    continue
                if info.get('type') == 'dual':
                    continue  # dual widget manages its own section colors
                widget = info.get('widget')
                key = info.get('course')
                if widget is None or not key:
                    continue
                color = course_color(key, dark=is_dark)
                try:
                    widget.setStyleSheet(
                        f"background-color: {color.name()};"
                        "border: none; border-radius: 10px;"
                        f"color: {text_color};"
                    )
                except RuntimeError:
                    continue  # widget already deleted
        except Exception as e:
            logger.warning(f"Theme re-apply failed: {e}")
            
    def load_latest_backup(self):
        """Load the latest backup on application startup"""
        try:
            result = self.backup_service.get_latest_backup_data()
            if result.success:
                self.user_data = result.data['backup_data']
                
                current_schedule = self.user_data.get('current_schedule', [])
                for course_key in current_schedule:
                    if course_key in COURSES:
                        self.add_course_to_table(course_key, ask_on_conflict=False)
                
                self.update_status()
                self.update_stats_panel()
                self.update_detailed_info_if_open()
                logger.info(f"Loaded latest backup: {result.data['file_path']}")
            else:
                logger.info(result.message or result.error)
        except Exception as e:
            logger.error(f"Error loading latest backup: {e}")

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
            
            # Auto-select list buttons were removed from the saved-combos group
            # (misplaced duplicates); auto-list management happens via the
            # course context menu and drag & drop.

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

    def add_course(self):
        """Add a new course (delegated to DialogCoordinator)"""
        self.open_add_course_dialog()

    def edit_course(self):
        """Edit a selected course (delegated to DialogCoordinator)"""
        self.open_edit_course_dialog()

    def remove_course(self):
        """Remove a selected course"""
        selected = self.course_list.selectedItems()
        if selected:
            course_key = selected[0].data(QtCore.Qt.UserRole)
            self.remove_course_from_schedule(course_key)

    def generate_combinations(self):
        """Generate course combinations (delegated to AutoScheduler)"""
        self.generate_optimal_schedule()

    def generate_greedy_schedule(self):
        """Generate greedy schedule (delegated to AutoScheduler)"""
        self.generate_optimal_schedule()

    def generate_alternative_schedule(self):
        """Generate alternative schedule (delegated to AutoScheduler)"""
        self.generate_optimal_schedule()

    def show_detailed_info(self):
        """Show detailed info window (delegated to DialogCoordinator)"""
        self.open_detailed_info_window()

    def show_exam_schedule(self):
        """Show exam schedule window (delegated to DialogCoordinator)"""
        self.on_show_exam_schedule()

    def create_menu_bar(self):
        """Create the application menu bar using MenuBuilder"""
        from app.ui.builders.menu_builder import MenuBuilder
        menus, actions = MenuBuilder.build_menu_bar(self, logger)
        
        # Wire actions
        if 'student_dashboard' in actions:
            actions['student_dashboard'].triggered.connect(self.show_student_profile)
        elif 'student_profile' in actions:
            actions['student_profile'].triggered.connect(self.show_student_profile)

        if 'cloud_auth' in actions:
            actions['cloud_auth'].triggered.connect(self.show_cloud_account_dialog)
        if 'cloud_sync' in actions:
            actions['cloud_sync'].triggered.connect(self.show_cloud_schedule_dialog)
        if 'fetch_golestan' in actions:
            actions['fetch_golestan'].triggered.connect(self.manual_fetch_from_golestan)
        if 'reset_creds' in actions:
            actions['reset_creds'].triggered.connect(self.reset_golestan_credentials)
        if 'prof_review' in actions:
            actions['prof_review'].triggered.connect(self.show_professor_review_dialog)
        if 'show_exam_schedule' in actions:
            actions['show_exam_schedule'].triggered.connect(self.on_show_exam_schedule)
        if 'export_exam_schedule' in actions:
            actions['export_exam_schedule'].triggered.connect(self.on_export_exam_schedule)
        if 'settings' in actions:
            actions['settings'].triggered.connect(self.show_settings_dialog)
        if 'tutorial' in actions:
            actions['tutorial'].triggered.connect(self.show_tutorial_dialog)
        if 'about' in actions:
            actions['about'].triggered.connect(self.show_about_dialog)

        # Language selection
        if 'persian_lang' in actions and 'english_lang' in actions:
            from app.core.language_manager import language_manager
            current_lang = language_manager.get_current_language()
            actions['persian_lang'].setChecked(current_lang == 'fa')
            actions['english_lang'].setChecked(current_lang == 'en')
            actions['persian_lang'].triggered.connect(lambda: self.switch_language('fa'))
            actions['english_lang'].triggered.connect(lambda: self.switch_language('en'))

        # Theme selection (light / dark / system) — applies live
        if 'theme_group' in actions:
            self.switch_theme_mode(actions)
            
        if 'history_menu' in menus:
            menus['history_menu'].aboutToShow.connect(self.populate_backup_history_menu)

    def switch_theme_mode(self, actions=None):
        """Wire theme menu actions and apply the persisted theme live."""
        try:
            from app.core.theme_manager import theme_manager

            if actions and 'theme_group' in actions:
                mode_checks = {
                    'light': actions.get('theme_light'),
                    'dark': actions.get('theme_dark'),
                    'system': actions.get('theme_system'),
                }
                current = theme_manager.mode
                for mode, act in mode_checks.items():
                    if act is not None:
                        act.setChecked(mode == current)
                        # Capture mode explicitly to avoid late-binding surprises
                        act.triggered.connect(
                            lambda _=False, m=mode: self.apply_theme_mode(m)
                        )
        except Exception as e:
            logger.error(f"Error wiring theme actions: {e}")

    def apply_theme_mode(self, mode: str):
        """Persist the chosen theme mode and re-apply styles application-wide."""
        try:
            from app.core.theme_manager import theme_manager
            app = QtWidgets.QApplication.instance()
            theme_manager.set_mode(mode)
            if app is not None:
                theme_manager.apply(app)
            logger.info(f"Theme switched to '{mode}' (effective: {theme_manager.effective_theme()})")
        except Exception as e:
            logger.error(f"Error applying theme '{mode}': {e}")

    def show_tutorial_dialog(self):
        """Show the interactive tutorial dialog"""
        try:
            from app.ui.tutorial_dialog import TutorialDialog
            dialog = TutorialDialog(self)
            dialog.exec_()
        except Exception as e:
            logger.error(f"Error showing tutorial dialog: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در نمایش آموزش: {str(e)}")

    def show_about_dialog(self):
        """Show About Golestoon dialog"""
        try:
            QtWidgets.QMessageBox.about(
                self,
                "درباره گلستون (Golestoon)",
                "<h3>🌸 گلستون (Golestoon Desktop)</h3>"
                "<p>نسخه دسکتاپ رسمی سامانه برنامه‌ریزی کلاسی، کارنامه و نظرسنجی اساتید دانشگاه</p>"
                "<p><b>نسخه:</b> 1.0.0</p>"
                "<p><b>وبسایت:</b> <a href='https://golestoon-app.ir'>golestoon-app.ir</a></p>"
                "<p>ساخته شده با افتخار برای دانشجویان دانشگاه‌های ایران 🇮🇷</p>"
            )
        except Exception as e:
            logger.error(f"Error showing about dialog: {e}")

    def retranslate_ui(self):
        """Retranslate the .ui-loaded widgets (groups, buttons, placeholders)
        and the schedule table headers for the current language."""
        try:
            from app.core.translator import translator
            t = translator.t

            # Group boxes
            for attr, key in (
                ('search_group', 'ui.search_group'),
                ('course_list_group', 'ui.course_list_group'),
                ('actions_group', 'ui.actions_group'),
                ('info_group', 'ui.info_group'),
                ('stats_group', 'ui.stats_group'),
                ('notifications_group', 'ui.notifications_group'),
                ('auto_select_group', 'ui.auto_select_group'),
                ('saved_combos_group', 'ui.saved_combos_group'),
            ):
                widget = getattr(self, attr, None)
                if widget is not None:
                    widget.setTitle(t(key))

            # Buttons
            for attr, key in (
                ('detailed_info_btn', 'ui.save_schedule'),
                ('clear_schedule_btn', 'ui.clear_schedule'),
                ('showExamPagebtn', 'ui.show_exams'),
                ('optimal_schedule_btn', 'ui.generate_optimal'),
                ('success_btn', 'ui.add_course'),
            ):
                widget = getattr(self, attr, None)
                if widget is not None:
                    widget.setText(t(key))

            # Search box placeholder
            if hasattr(self, 'search_box') and self.search_box is not None:
                self.search_box.setPlaceholderText(t("ui.search_placeholder"))

            # Saved-combo action buttons (created programmatically)
            if getattr(self, '_saved_combo_save_btn', None) is not None:
                self._saved_combo_save_btn.setText(t("ui.save_current_combo"))
                self._saved_combo_delete_btn.setText(t("ui.delete_combo"))

            # Schedule table day headers (translated labels)
            try:
                from app.core.config import DAYS, get_day_label_map
                label_map = dict(get_day_label_map())
                labels = [label_map.get(day, day) for day in DAYS]
                if labels and hasattr(self, 'schedule_table'):
                    self.schedule_table.setHorizontalHeaderLabels(labels)
            except Exception as err:  # noqa: BLE001
                logger.debug(f"Day header translation skipped: {err}")

            # Course list contents (re-populate so filter texts re-apply)
            try:
                self.populate_course_list(None)
            except Exception:  # noqa: BLE001 — keep UI stable
                pass
        except Exception as e:
            logger.error(f"retranslate_ui failed: {e}")

    def switch_language(self, lang_code: str):
        """Switch application language dynamically with RTL/LTR layout propagation"""
        try:
            from app.core.language_manager import language_manager
            from app.core.translator import translator
            
            language_manager.set_language(lang_code)
            translator.load_translations(lang_code)

            # Apply layout direction
            app = QtWidgets.QApplication.instance()
            if lang_code == 'fa':
                if app: app.setLayoutDirection(QtCore.Qt.RightToLeft)
                self.setLayoutDirection(QtCore.Qt.RightToLeft)
            else:
                if app: app.setLayoutDirection(QtCore.Qt.LeftToRight)
                self.setLayoutDirection(QtCore.Qt.LeftToRight)

            if app:
                language_manager.apply_font(app)

            # Retranslate .ui widgets + table headers, then refresh menus
            self.retranslate_ui()
            self.create_menu_bar()
            self.update_status()
            self.update_stats_panel()
            
            lang_name = "فارسی" if lang_code == 'fa' else "English"
            if os.environ.get('QT_QPA_PLATFORM') != 'offscreen':
                QtWidgets.QMessageBox.information(
                    self,
                    "تغییر زبان" if lang_code == 'fa' else "Language Changed",
                    f"زبان برنامه به {lang_name} تغییر یافت." if lang_code == 'fa' else f"Application language changed to {lang_name}."
                )
        except Exception as e:
            logger.error(f"Error switching language: {e}")

    def show_student_profile(self):
        """Show the unified student academic & transcript dashboard."""
        try:
            from app.ui.unified_student_dashboard import UnifiedStudentDashboard
            dialog = UnifiedStudentDashboard(
                self,
                network_session=getattr(self, 'network_session', None),
                token_manager=getattr(self, 'token_manager', None),
            )
            dialog.exec_()
        except Exception as e:
            logger.error(f"Error showing unified student dashboard: {e}")
            QtWidgets.QMessageBox.critical(
                self, 
                "خطا", 
                f"خطا در نمایش داشبورد تحصیلی دانشجو: {str(e)}"
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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان ذخیره داده‌های کاربر وجود ندارد: "))
            pass  # Gracefully keep app running

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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "امکان بارگذاری داده‌های کاربر وجود ندارد: "))
            pass  # Gracefully keep app running

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

    def update_stats_panel(self):
        self.status_bar_controller.update_stats_panel()

    def updatestatspanel(self):
        self.status_bar_controller.update_stats_panel()

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
                logger.debug("🔄 Calling update_stats_panel from on_course_clicked")
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
        self.schedule_table_controller.clear_table_silent()

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
            self._safe_set_span(srow, scol, 1)
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
                    self._safe_set_span(srow, col, span)
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
        This version processes courses cleanly without re-entrancy deadlocks.
        """
        if getattr(self, '_is_processing_queue', False):
            return
        self._is_processing_queue = True
        logger.info("overlay_processing_start: Starting to process course addition queue")
        try:
            # Process courses one by one to handle dual course creation correctly
            while self.course_addition_queue:
                course_key, ask_on_conflict = self.course_addition_queue.popleft()
                logger.info(f"overlay_processing_item: Processing course {course_key}")
                self._add_course_internal(course_key, ask_on_conflict)
            
            # Save user data once after queue is drained
            save_user_data(self.user_data)
            logger.info("overlay_processing_complete: Course addition queue processing complete")
        finally:
            self._is_processing_queue = False


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
        from .simple_dual_widget import create_dual_course_widget
        from .dual_course_utils import check_odd_even_compatibility
        
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

        # Distinct deterministic color per course (hash-based hue) so courses
        # are visually separable in the grid; pastel on light, deep on dark.
        from app.core.course_utils import course_color
        from app.core.theme_manager import theme_manager
        try:
            is_dark = theme_manager.effective_theme() == 'dark'
        except Exception:  # noqa: BLE001 — styling fallback
            is_dark = False
        bg = course_color(course_key, dark=is_dark)
        
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
                elif str(course.get('code', '') or '').startswith('elective'):
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
                    self._safe_set_span(srow, col, span)
                
                # Update overlay tracking for single course
                if slot_key not in self.overlays:
                    self.overlays[slot_key] = {}
                self.overlays[slot_key]['single'] = cell_widget
                
                # Update placement tracking with type
                self.placed[(srow, col)] = {
                    'type': 'single',
                    'course': course_key, 
                    'rows': span,
                    'widget': cell_widget
                }
            
        # Update status after adding course
        self.update_status()
        
        # Update detailed info window if open
        self.update_detailed_info_if_open()
        
        
        # Update stats panel
        logger.debug("🔄 Calling update_stats_panel from add_course_to_table")
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
        self._safe_set_span(srow, col, 1)
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
        logger.debug("🔄 Calling update_stats_panel from remove_course_from_schedule")
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
        logger.debug("🔄 Calling update_stats_panel from remove_course_silently")
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
        logger.debug("🔄 Calling update_stats_panel from remove_entire_course")
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
            self._safe_set_span(srow, col, 1)
            # Clear any cell widgets
            self.schedule_table.removeCellWidget(srow, col)
        self.preview_cells.clear()

    def open_edit_course_dialog(self):
        """Open dialog to edit an existing course (delegated to DialogCoordinator)"""
        self.dialog_coordinator.open_edit_course_dialog()

    def open_edit_course_dialog_for_course(self, course_key):
        """Open dialog to edit a specific course (delegated to DialogCoordinator)"""
        self.dialog_coordinator.open_edit_course_dialog_for_course(course_key)

    def show_course_details(self, course_key):
        """Show detailed course information in a dialog (delegated to DialogCoordinator)"""
        self.dialog_coordinator.show_course_details(course_key)

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
        """Open the detailed information window (delegated to DialogCoordinator)"""
        self.dialog_coordinator.open_detailed_info_window()

    def update_detailed_info_if_open(self):
        """Update the detailed info window if it's open (delegated to DialogCoordinator)"""
        self.dialog_coordinator.update_detailed_info_if_open()

    def update_item_size_hint(self, item, widget):
        """Update the size hint for a QListWidgetItem based on its widget"""
        if item and widget:
            item.setSizeHint(widget.sizeHint())
            
    def populate_course_list(self, filter_items=None):
        """Populate the course list with courses (delegated to CourseSearchController)"""
        self.course_search_controller.populate_course_list(filter_items)



    def on_major_selection_changed(self, index):
        self.course_search_controller.on_major_selection_changed(index)

    def on_search_text_changed(self, text):
        self.course_search_controller.on_search_text_changed(text)

    def clear_search(self):
        self.course_search_controller.clear_search()

    def auto_save_user_data(self):
        """Auto-save user data without user interaction - DISABLED for backup-on-exit only"""
        pass

    def _cleanup_old_backups(self):
        """Clean up old backup files, keeping only the last 5"""
        self.backup_service.cleanup_old_backups()

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
        """Generate optimal schedule combinations with conflict handling"""
        all_courses = list(COURSES.keys())
        
        progress = QtWidgets.QProgressDialog('در حال تولید بهترین ترکیبات...', 'لغو', 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            result = self.auto_scheduler.generate_optimal_schedule(all_courses)
            progress.setValue(100)
            
            if result.success:
                self.show_optimal_schedule_results(result.data['combinations'])
            else:
                QtWidgets.QMessageBox.information(self, 'پیام', result.message or result.error)
        finally:
            progress.close()

    def show_optimal_schedule_results(self, combos):
        """Show optimal schedule results in a dialog (delegated)"""
        self.dialog_coordinator.show_optimal_schedule_results(combos)

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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "خطا در اعمال ترکیب: "))

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
        self.auto_select_controller.setup_auto_select_list()

    def on_auto_list_reordered(self, parent, start, end, destination, row):
        self.auto_select_controller.on_auto_list_reordered(parent, start, end, destination, row)

    def on_generate_optimal_from_auto_list(self):
        """Handle generate optimal schedule from auto-select list button click"""
        try:
            self.generate_optimal_schedule_from_auto_list()
        except Exception as e:
            logger.error(f"Error generating optimal schedule from auto list: {e}")

    def generate_optimal_schedule_from_auto_list(self):
        """Generate schedules that respect user priority order"""
        ordered_course_keys = []
        for i in range(self.auto_select_list.count()):
            item = self.auto_select_list.item(i)
            if item and item.data(QtCore.Qt.UserRole):
                course_key = item.data(QtCore.Qt.UserRole)
                if course_key in COURSES:
                    ordered_course_keys.append(course_key)
                    
        progress = QtWidgets.QProgressDialog('در حال تولید بهترین ترکیبات...', 'لغو', 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            result = self.auto_scheduler.generate_priority_aware_schedule(ordered_course_keys)
            progress.setValue(100)
            
            if result.success:
                self.show_priority_aware_results(result.data['schedules'], ordered_course_keys)
            else:
                QtWidgets.QMessageBox.information(self, 'پیام', result.message or result.error)
        finally:
            progress.close()

    def show_priority_aware_results(self, schedules, original_priority_order):
        """Show results with clear priority information (delegated)"""
        self.dialog_coordinator.show_priority_aware_results(schedules, original_priority_order)

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
            QtWidgets.QMessageBox.critical(self, "خطا", humanize_error(e, "خطا در اعمال برنامه: "))

    def save_auto_select_list(self):
        """Save the auto-select list to user data"""
        # This method is called to save changes to the auto-select list
        # For now, we'll just log that it was called since the list is managed in memory
        logger.debug("Auto-select list saved")
        pass

    def show_auto_list_context_menu(self, position):
        self.auto_select_controller.show_auto_list_context_menu(position)

    def auto_select_list_key_press_event(self, event):
        self.auto_select_controller.auto_select_list_key_press_event(event)

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
        """Check if a course can be edited (ONLY user-added custom courses)"""
        if not course_key:
            return False
        course = COURSES.get(course_key, {})
        if course.get('is_user_added') is True or course.get('custom') is True:
            return True
        if course.get('major') == 'دروس اضافه‌شده توسط کاربر':
            return True
        
        # Check custom_courses in user_data
        custom_courses = self.user_data.get('custom_courses', [])
        course_code = str(course.get('code', ''))
        for c in custom_courses:
            if str(c.get('code', '')) == course_code and course_code != '':
                return True
                
        return False

    def open_add_course_dialog(self):
        """Open dialog to add a new custom course (delegated to DialogCoordinator)"""
        self.dialog_coordinator.open_add_course_dialog()

    def update_course_info_panel(self, course_key=None):
        """Update the course info panel from a key, the list selection, or schedule summary."""
        try:
            if not hasattr(self, 'course_info_label'):
                return

            if course_key is None and hasattr(self, 'course_list'):
                item = self.course_list.currentItem()
                course_key = item.data(QtCore.Qt.UserRole) if item is not None else None

            if course_key and course_key in COURSES:
                course = COURSES.get(course_key, {})
                exam_time = course.get('exam_time', '') or 'اعلام نشده'
                info_text = (f"نام درس: {course.get('name', 'نامشخص')}\n"
                             f"کد درس: {course.get('code', 'نامشخص')}\n"
                             f"استاد: {course.get('instructor', 'نامشخص')}\n"
                             f"تعداد واحد: {course.get('credits', 'نامشخص')}\n"
                             f"محل برگزاری: {course.get('location', 'نامشخص')}\n"
                             f"امتحان: {exam_time}")
            else:
                placed_count = sum(1 for v in self.placed.values() if isinstance(v, dict))
                info_text = (f"دروس روی برنامه: {placed_count}\n"
                             f"برای دیدن جزئیات، روی یک درس در فهرست یا جدول کلیک کنید.")
            self.course_info_label.setText(info_text)
        except Exception as e:
            logger.debug(f"update_course_info_panel skipped: {e}")

    def on_table_cell_clicked(self, row, column):
        """Show details of the course(s) placed in the clicked schedule cell."""
        try:
            entry = None
            for (start_row, start_col), info in self.placed.items():
                if not isinstance(info, dict) or start_col != column:
                    continue
                span = max(1, int(info.get('rows', 1) or 1))
                if start_row <= row < start_row + span:
                    entry = info
                    break

            if entry is None:
                return

            keys = entry.get('courses') or [entry.get('course')]
            lines = []
            for key in keys:
                if not key:
                    continue
                course = COURSES.get(key, {})
                if not course:
                    continue
                exam_time = course.get('exam_time', '') or 'اعلام نشده'
                lines.append(
                    f"📘 {course.get('name', key)}\n"
                    f"    کد: {course.get('code', '—')} | استاد: {course.get('instructor', '—')}\n"
                    f"    واحد: {course.get('credits', '—')} | محل: {course.get('location', '—')}\n"
                    f"    امتحان: {exam_time}"
                )
            if not lines:
                return

            info_text = "\n\n".join(lines)
            if hasattr(self, 'course_info_label'):
                self.course_info_label.setText(info_text)
            name_first = keys[0] if keys else ''
            self.status_bar.showMessage(f"جزئیات «{COURSES.get(name_first, {}).get('name', name_first)}» در پنل اطلاعات نمایش داده شد", 4000)
        except Exception as e:
            logger.debug(f"on_table_cell_clicked skipped: {e}")

    def filter_course_list(self, text):
        """Filter the course list by search text (delegates to the controller)."""
        self.course_search_controller.populate_course_list(text or None)

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
        """Show exam schedule window (delegated to DialogCoordinator)"""
        self.dialog_coordinator.on_show_exam_schedule()

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
        """Handle add to auto select list button click (delegated)"""
        self.auto_select_controller.on_add_to_auto()

    def _apply_search_filter(self):
        """Apply the search text from the search box"""
        if hasattr(self, 'search_box'):
            self.filter_course_list(self.search_box.text())

    def normalize_persian_text(self, text):
        return self.course_search_controller.normalize_persian_text(text)

    def on_remove_from_auto(self):
        """Handle remove from auto select list button click (delegated)"""
        self.auto_select_controller.on_remove_from_auto()


    def toggle_search_clear_button(self, text):
        self.course_search_controller.toggle_search_clear_button(text)

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
        """Reset Golestan credentials"""
        try:
            result = self.golestan_service.delete_credentials()
            if result.success:
                QtWidgets.QMessageBox.information(self, "موفقیت", result.message)
            else:
                QtWidgets.QMessageBox.critical(self, "خطا", result.error)
        except Exception as e:
            logger.error(f"Error in reset golestan credentials: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در حذف اطلاعات ذخیره‌شده گلستان:\n{str(e)}")

    def fetch_from_golestan(self):
        """Fetch courses from Golestan (delegated to GolestanService)"""
        result = self.golestan_service.fetch_courses()
        if result.success:
            self.refresh_ui()
            QtWidgets.QMessageBox.information(self, "موفقیت", result.message)
        else:
            if result.error:
                QtWidgets.QMessageBox.critical(self, "خطا", result.error)

    def manual_fetch_from_golestan(self):
        """Manual fetch from Golestan (delegated to GolestanService)"""
        result = self.golestan_service.manual_fetch_courses()
        if result.success:
            self.refresh_ui()
            QtWidgets.QMessageBox.information(self, "موفقیت", result.message)
        else:
            if result.error:
                QtWidgets.QMessageBox.critical(self, "خطا", result.error)

    def manage_golestan_credentials(self):
        """Manage Golestan credentials - view (masked) or remove saved credentials"""
        try:
            result = self.golestan_service.get_masked_student_number()
            
            if not result.success:
                QtWidgets.QMessageBox.information(self, "اطلاعات ورود گلستان", "هیچ اطلاعات ورودی ذخیره‌شده‌ای یافت نشد.")
                return
                
            masked_student = result.data['masked_student']
            
            reply = QtWidgets.QMessageBox.question(
                self,
                "مدیریت اطلاعات ورود گلستان",
                f"اطلاعات ورود ذخیره‌شده:\n\nشماره دانشجویی: {masked_student}\n\nآیا می‌خواهید این اطلاعات را حذف کنید؟",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                del_result = self.golestan_service.delete_credentials()
                if del_result.success:
                    QtWidgets.QMessageBox.information(self, "موفقیت", del_result.message)
                else:
                    QtWidgets.QMessageBox.warning(self, "خطا", del_result.error)
        except Exception as e:
            logger.error(f"Error managing credentials: {e}")
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در مدیریت اطلاعات ورود:\n{str(e)}")

    def forget_saved_credentials(self):
        """Delete saved Golestan credentials without asking"""
        self.golestan_service.delete_credentials()

    def fetch_from_golestan_with_new_credentials(self, username, password):
        """Fetch courses using provided credentials without saving them (used when saved credentials fail)"""
        try:
            progress = QtWidgets.QProgressDialog('در حال دریافت اطلاعات از گلستان...', 'لغو', 0, 0, self)
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.show()
            QtWidgets.QApplication.processEvents()
            
            fetch_result = self.golestan_service.fetch_courses(username, password)
            progress.close()
            
            if fetch_result.success:
                self.refresh_ui()
                QtWidgets.QMessageBox.information(self, 'موفقیت', fetch_result.message)
            else:
                QtWidgets.QMessageBox.critical(self, 'خطا', fetch_result.error)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'خطا', f"خطا در دریافت اطلاعات:\n{str(e)}")

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

    def populate_backup_history_menu(self):
        """Populate backup history menu (delegated to BackupService)"""
        if not hasattr(self, 'menu_history') and not hasattr(self, 'menuBar'):
            return
        result = self.backup_service.get_all_backups()
        if result.success and hasattr(self, 'menu_history'):
            menu = self.menu_history
            menu.clear()
            for b_file in result.data.get('backups', []):
                action = menu.addAction(b_file)
                action.triggered.connect(lambda checked, f=b_file: self.load_backup_file(f))

    def load_backup_file(self, backup_file):
        """Load backup file (delegated to BackupService)"""
        result = self.backup_service.load_specific_backup(backup_file)
        if result.success:
            self.user_data = result.data['backup_data']
            self.clear_table_silent()
            current_schedule = self.user_data.get('current_schedule', [])
            for course_key in current_schedule:
                if course_key in COURSES:
                    self.add_course_to_table(course_key, ask_on_conflict=False)
            self.update_status()
            self.update_stats_panel()
            QtWidgets.QMessageBox.information(self, "بازیابی موفق", "برنامه با موفقیت بازیابی شد.")
        else:
            QtWidgets.QMessageBox.critical(self, "خطا", result.error or "خطا در بارگذاری بکاپ")

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
        try:
            if hasattr(self, 'status_timer') and self.status_timer:
                self.status_timer.stop()
            if hasattr(self, 'course_addition_timer') and self.course_addition_timer:
                self.course_addition_timer.stop()
            if hasattr(self, '_pulse_timers'):
                for t in list(self._pulse_timers.values()):
                    if t: t.stop()
                self._pulse_timers.clear()
            if hasattr(self, 'network_session') and self.network_session:
                self.network_session.close()
        except Exception as err:
            logger.error("Error during resource cleanup in closeEvent: %s", err)
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

