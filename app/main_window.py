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

# Add the app directory to the Python path to enable imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5 import QtWidgets, QtGui, QtCore, uic

# Import from our modules
from config import (
    COURSES, DAYS, TIME_SLOTS, EXTENDED_TIME_SLOTS, COLOR_MAP, logger
)
from data_manager import (
    load_user_data, save_user_data, save_courses_to_json, generate_unique_key
)
from course_utils import (
    to_minutes, overlap, schedules_conflict, 
    calculate_days_needed_for_combo, calculate_empty_time_for_combo,
    generate_best_combinations_for_groups,
    generate_priority_based_schedules, create_greedy_schedule, create_alternative_schedule
)
from widgets import (
    CourseListWidget, AnimatedCourseWidget
)
from dialogs import AddCourseDialog, EditCourseDialog, DetailedInfoWindow, ExamScheduleWindow

# ---------------------- Main Application Window ----------------------

class SchedulerWindow(QtWidgets.QMainWindow):
    """Main window for the Schedule Planner application"""
    


    def __init__(self):
        super().__init__()
        
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
        
        # Populate UI with data
        # Load courses explicitly to ensure they're available
        from data_manager import load_courses_from_json
        load_courses_from_json()
        
        # Populate major dropdown AFTER courses are loaded
        self.populate_major_dropdown()
        
        self.populate_course_list()
        self.load_saved_combos_ui()
        
        # Debug stats widget
        self.debug_stats_widget()
        
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
        
        # Menu bar is not implemented in this version
        logger.info("SchedulerWindow initialized successfully")

    def initialize_schedule_table(self):
        """Initialize the schedule table with days and time slots"""
        try:
            from config import DAYS, EXTENDED_TIME_SLOTS
            
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
        print("=== Debug Stats Widget ===")
        
        # پیدا کردن تمام label های موجود
        labels = self.findChildren(QtWidgets.QLabel)
        for label in labels:
            if hasattr(label, 'objectName'):
                name = label.objectName()
                text = label.text()[:50] + "..." if len(label.text()) > 50 else label.text()
                print(f"Label: {name} -> {text}")
        
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
                print(f"✅ Found widget: {widget_name}")
                return widget
            else:
                print(f"❌ Widget not found: {widget_name}")
        
        return None

    def update_stats_panel(self):
        """Update the stats panel with current schedule information - FORCED VERSION"""
        print("🔄 update_stats_panel called")  # Debug log
        
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
                    print(f"✅ Found stats widget: {type(widget)}")
                    break
            
            if not stats_widget:
                print("❌ No stats widget found!")
                # جستجو در کل UI
                all_labels = self.findChildren(QtWidgets.QLabel)
                for label in all_labels:
                    if 'آمار' in label.text() or 'stats' in label.objectName().lower():
                        stats_widget = label
                        print(f"🔍 Found by search: {label.objectName()}")
                        break
            
            if not stats_widget:
                print("❌ Still no stats widget found!")
                return
                
            # محاسبه آمار
            if hasattr(self, 'placed') and self.placed:
                placed_courses = list(set(info['course'] for info in self.placed.values()))
                print(f"📊 Found {len(placed_courses)} courses")
                
                # محاسبه واحدها
                total_units = 0
                total_sessions = len(self.placed)
                days_used = set()
                
                for course_key in placed_courses:
                    course = COURSES.get(course_key, {})
                    units = course.get('credits', 0)
                    total_units += units
                    print(f"  - {course.get('name', course_key)}: {units} واحد")
                    
                    # گرفتن روزها
                    for session in course.get('schedule', []):
                        days_used.add(session.get('day', ''))
                
                # متن آمار
                stats_text = f"""📊 آمار برنامه فعلی

📚 تعداد دروس: {len(placed_courses)}
🎯 واحدها: {total_units}
⏰ جلسات: {total_sessions}
📅 روزها: {len(days_used)}
✅ وضعیت: فعال"""

                print(f"📝 Setting stats text: {stats_text[:100]}...")
                stats_widget.setText(stats_text)
                
            else:
                print("📭 No courses placed")
                stats_widget.setText("""📊 آمار برنامه

هنوز هیچ درسی انتخاب نشده است

💡 روی دروس کلیک کنید""")
                
            # فورس refresh
            stats_widget.update()
            stats_widget.repaint()
            
        except Exception as e:
            print(f"❌ Error in update_stats_panel: {e}")
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
        """Add a course to the schedule table with priority-based conflict resolution"""
        # Safety check for schedule_table
        if not hasattr(self, 'schedule_table'):
            logger.error("schedule_table widget not found")
            QtWidgets.QMessageBox.critical(self, 'خطا', 'جدول برنامه یافت نشد.')
            return
            
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
                srow = EXTENDED_TIME_SLOTS.index(sess['start'])
                erow = EXTENDED_TIME_SLOTS.index(sess['end'])
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
        
        # Auto-save user data
        self.auto_save_user_data()
        
        # Update stats panel
        print("🔄 Calling update_stats_panel from add_course_to_table")
        self.update_stats_panel()  # فورس کال
        QtCore.QCoreApplication.processEvents()  # فورس UI update

    def clear_course_highlights(self):
        """Restore original styling for all course widgets"""
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
            if widget and hasattr(widget, 'original_style'):
                # Restore the exact original style to prevent any residual effects
                widget.setStyleSheet(widget.original_style)
            elif widget:
                # If no original style was stored, apply default styling
                widget.setStyleSheet("")
    

    def is_cell_empty(self, row, col):
        """Check if a cell is empty (helper method)"""
        item = self.schedule_table.item(row, col)
        if not item:
            return True
        it = item.data(QtCore.Qt.DisplayRole)
        if it and it.text().strip() != '':
            return False
        return True

    def add_course_to_table_with_priority(self, course_key, course_priorities):
        """Add a course to the schedule table with priority-based conflict resolution"""
        # Safety check for schedule_table
        if not hasattr(self, 'schedule_table'):
            logger.error("schedule_table widget not found")
            QtWidgets.QMessageBox.critical(self, 'خطا', 'جدول برنامه یافت نشد.')
            return False
            
        course = COURSES.get(course_key)
        if not course:
            QtWidgets.QMessageBox.warning(self, 'خطا', f'درس با کلید {course_key} یافت نشد.')
            return False
        
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
        
        # Handle conflicts with priority-based resolution
        if conflicts:
            current_priority = course_priorities.get(course_key, 999)
            
            # Check if any conflicting courses have higher priority (lower number)
            higher_priority_conflicts = []
            conflict_details = []
            for conf in conflicts:
                (_, _), (_, _), conflict_course_key, conflict_name = conf
                conflict_priority = course_priorities.get(conflict_course_key, 999)
                
                # If conflicting course has higher priority (lower number), it should stay
                if conflict_priority < current_priority:
                    higher_priority_conflicts.append((conflict_course_key, conflict_name, conflict_priority))
                conflict_details.append(conflict_name)
            
            # If there are higher priority conflicts, don't add this course
            if higher_priority_conflicts:
                return False

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
        bg = COLOR_MAP[color_idx % len(COLOR_MAP)]
        
        for (srow, col, span, sess) in placements:
            # Determine parity information and styling
            parity_indicator = ''
            if sess.get('parity') == 'ز':
                parity_indicator = 'ز'
            elif sess.get('parity') == 'ف':
                parity_indicator = 'ف'

            # Create course cell widget with improved styling
            cell_widget = AnimatedCourseWidget(course_key, bg, False, self)
            # Set object name for QSS styling
            cell_widget.setObjectName('course-cell')
            
            # Set properties for styling based on course type and conflicts
            cell_widget.setProperty('conflict', False)
            if course.get('code', '').startswith('elective'):
                cell_widget.setProperty('elective', True)
            else:
                cell_widget.setProperty('elective', False)
            
            # Store background color for animation
            cell_widget.bg_color = bg
            cell_widget.border_color = QtGui.QColor(bg.red()//2, bg.green()//2, bg.blue()//2)
            cell_layout = QtWidgets.QVBoxLayout(cell_widget)
            cell_layout.setContentsMargins(2, 1, 2, 1)
            cell_layout.setSpacing(0)
            
            # Top row with X button
            top_row = QtWidgets.QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            
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
        
        # Auto-save user data
        self.auto_save_user_data()
        
        # Update stats panel
        print("🔄 Calling update_stats_panel from add_course_to_table_with_priority")
        self.update_stats_panel()
        QtCore.QCoreApplication.processEvents()
        
        return True

    def add_course_to_table(self, course_key, ask_on_conflict=True):
        """Add a course to the schedule table"""
        # Safety check for schedule_table
        if not hasattr(self, 'schedule_table'):
            logger.error("schedule_table widget not found")
            QtWidgets.QMessageBox.critical(self, 'خطا', 'جدول برنامه یافت نشد.')
            return
            
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
                srow = EXTENDED_TIME_SLOTS.index(sess['start'])
                erow = EXTENDED_TIME_SLOTS.index(sess['end'])
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
        
        # Auto-save user data
        self.auto_save_user_data()
        
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


    def remove_course_from_schedule(self, course_key):
        """Remove all instances of a course from the current schedule"""
        to_remove = []
        for (srow, scol), info in self.placed.items():
            if info['course'] == course_key:
                to_remove.append((srow, scol))
        
        for start_tuple in to_remove:
            self.remove_placed_by_start(start_tuple)
        
        # Update stats panel after removing course
        print("🔄 Calling update_stats_panel from remove_course_from_schedule")
        self.update_stats_panel()
        QtCore.QCoreApplication.processEvents()  # فورس UI update

    def remove_course_silently(self, course_key):
        """Remove course without user confirmation or notification"""
        self.remove_course_from_schedule(course_key)
        self.update_status()
        self.update_detailed_info_if_open()




    def clear_course_highlights(self):
        """Restore original styling for all course widgets"""
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
            if widget and hasattr(widget, 'original_style'):
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
        
        # Update stats panel after removing course
        print("🔄 Calling update_stats_panel from remove_entire_course")
        self.update_stats_panel()
        QtCore.QCoreApplication.processEvents()  # فورس UI update
        
        # Show confirmation
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
        # Clear any existing highlights first to prevent overlap
        self.clear_course_highlights()
        for (srow, scol), info in self.placed.items():
            if info['course'] == course_key:
                widget = info.get('widget')
                if widget:
                    # Store original style if not already stored
                    if not hasattr(widget, 'original_style'):
                        widget.original_style = widget.styleSheet()
                    
                    # Apply hover style with smooth red border effect
                    widget.setStyleSheet("QWidget#course-cell { border: 3px solid #e74c3c !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.2) !important; } QWidget#course-cell[conflict=\"true\"] { border: 3px solid #e74c3c !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.3) !important; } QWidget#course-cell[elective=\"true\"] { border: 3px solid #e74c3c !important; border-radius: 8px !important; background-color: rgba(231, 76, 60, 0.2) !important; }")
                    
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
            from config import COURSES
            
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
            else:
                selected_major = self.comboBox.currentText()
                self.current_major_filter = selected_major
            
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
                self.action_fetch_golestan.triggered.connect(self.fetch_from_golestan)
            
            if hasattr(self, 'action_manual_fetch'):
                self.action_manual_fetch.triggered.connect(self.manual_fetch_from_golestan)
            
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
        """Auto-save user data without user interaction with backup functionality"""
        try:
            # Collect currently placed course keys
            keys = list({info['course'] for info in self.placed.values()})
            
            # Update user data with current schedule
            self.user_data['current_schedule'] = keys
            
            # Create backup before saving
            import shutil
            import datetime
            import os
            # Get USER_DATA_FILE from config
            from config import USER_DATA_FILE
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
            import os
            # Get USER_DATA_FILE from config
            from config import USER_DATA_FILE
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
            from config import COURSES
            
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
            if self.current_major_filter is None:
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
                logger.debug(f"Filtering courses by major: {self.current_major_filter}")
                for key, course in COURSES.items():
                    # Extract major from course key or metadata
                    course_major = self.extract_course_major(key, course)
                    if course_major == self.current_major_filter:
                        courses_to_show[key] = course
                        logger.debug(f"Adding course {key} to filtered list (major: {course_major})")
            else:
                # Show all courses if no filter
                courses_to_show = COURSES
            
            # Filter courses if search text provided (global search across all courses)
            if filter_text.strip():
                filter_text = filter_text.strip().lower()
                # Search across ALL courses, not just filtered ones
                courses_to_show = {
                    key: course for key, course in COURSES.items()
                    if (filter_text in course.get('name', '').lower() or
                        filter_text in course.get('code', '').lower() or
                        filter_text in course.get('instructor', '').lower())
                }
            # If no courses to show after filtering, show a message
            if not courses_to_show:
                no_courses_item = QtWidgets.QListWidgetItem()
                no_courses_widget = QtWidgets.QWidget()
                no_courses_layout = QtWidgets.QVBoxLayout(no_courses_widget)
                no_courses_layout.setContentsMargins(10, 10, 10, 10)
                
                no_courses_label = QtWidgets.QLabel("هیچ درسی برای این رشته یافت نشد.")
                no_courses_label.setAlignment(QtCore.Qt.AlignCenter)
                no_courses_label.setStyleSheet("color: #666; font-size: 14px; font-weight: bold;")
                
                no_courses_layout.addWidget(no_courses_label)
                no_courses_widget.setLayout(no_courses_layout)
                
                no_courses_item.setSizeHint(no_courses_widget.sizeHint())
                self.course_list.addItem(no_courses_item)
                self.course_list.setItemWidget(no_courses_item, no_courses_widget)
                return
                
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
            else:
                selected_major = self.comboBox.currentText()
                self.current_major_filter = selected_major
            
            # Repopulate course list with new filter
            self.populate_course_list()
            
        except Exception as e:
            logger.error(f"Error handling major selection change: {e}")

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
            from dialogs import ExamScheduleWindow
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
        """Handle search text change"""
        try:
            # Filter course list based on search text
            self.filter_course_list(text)
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

    def fetch_from_golestan(self):
        """Fetch courses from Golestan system automatically"""
        try:
            from golestan_integration import update_courses_from_golestan
            
            # Show progress dialog
            progress = QtWidgets.QProgressDialog('در حال دریافت اطلاعات از گلستان...', 'لغو', 0, 0, self)
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.show()
            
            QtWidgets.QApplication.processEvents()  # Update UI
            
            # Fetch courses from Golestan
            update_courses_from_golestan()
            
            # Close progress dialog
            progress.close()
            
            # Refresh course list
            self.populate_course_list()
            
            QtWidgets.QMessageBox.information(
                self, 'موفقیت', 
                'اطلاعات دروس با موفقیت از سامانه گلستان دریافت شد.'
            )
            
        except Exception as e:
            logger.error(f"Error fetching from Golestan: {e}")
            QtWidgets.QMessageBox.critical(
                self, 'خطا', 
                f'خطا در دریافت اطلاعات از گلستان:\n{str(e)}'
            )

    def manual_fetch_from_golestan(self):
        """Fetch courses from Golestan system with manual credentials"""
        try:
            from golestan_integration import update_courses_from_golestan
            
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
            
            # Refresh course list
            self.populate_course_list()
            
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

    def extract_course_major(self, course_key, course):
        """Extract major information from course data"""
        try:
            # Try to get major from golestan integration
            from golestan_integration import get_course_major
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
            
            # Collect all unique majors from courses
            majors = set()
            logger.info(f"Populating major dropdown, total courses: {len(COURSES)}")
            for key, course in COURSES.items():
                major = self.extract_course_major(key, course)
                if major and major != "رشته نامشخص":
                    majors.add(major)
            
            # Add majors to dropdown
            for major in sorted(majors):
                self.comboBox.addItem(major)
                
            logger.info(f"Populated major dropdown with {len(majors)} majors")
            
        except Exception as e:
            logger.error(f"Error populating major dropdown: {e}")

if __name__ == '__main__':
    # Error handling for the main application
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Critical error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


