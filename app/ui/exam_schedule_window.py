#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exam schedule window module for Schedule Planner
Contains window for viewing exam schedules
"""

import sys
import os

from PyQt5 import QtWidgets, QtCore, uic, QtGui

# Import from core modules - handle both relative and absolute imports
try:
    from app.core.config import COURSES, BASE_DIR, get_day_label
    from app.core.logger import setup_logging
    from app.core.language_manager import language_manager
    from app.core.translator import translator
except ImportError:
    # Fallback to relative imports for package execution
    from ..core.config import COURSES, BASE_DIR, get_day_label
    from ..core.logger import setup_logging
    from ..core.language_manager import language_manager
    from ..core.translator import translator

logger = setup_logging()


class ExamScheduleWindow(QtWidgets.QMainWindow):
    """Window for displaying exam schedule information loaded from UI file"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.is_fullscreen = False
        self.windowed_geometry = None

        # Get the directory of this file using BASE_DIR
        ui_dir = BASE_DIR / 'ui'
        exam_ui_file = ui_dir / 'exam_schedule_window.ui'

        # Load UI from external file
        try:
            uic.loadUi(str(exam_ui_file), self)
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(
                self,
                translator.t("common.error"),
                self._t("ui_not_found", path=exam_ui_file)
            )
            return
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                translator.t("common.error"),
                self._t("ui_load_error", error=str(e))
            )
            return

        # Connect signals
        self.connect_signals()

        # Set window flags to prevent fullscreen and always show window controls
        # Remove any existing fullscreen-related flags and ensure window controls are always visible
        flags = (
            QtCore.Qt.Window |
            QtCore.Qt.WindowCloseButtonHint |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowMaximizeButtonHint
        )
        # Explicitly remove fullscreen button hint
        flags &= ~QtCore.Qt.WindowFullscreenButtonHint
        # Ensure it's not a frameless window (which can hide controls)
        flags &= ~QtCore.Qt.FramelessWindowHint
        
        self.setWindowFlags(flags)
        
        # Prevent widgets from being movable
        self._lock_widget_positions()
        
        # Override resizeEvent to prevent fullscreen mode
        self._original_resizeEvent = self.resizeEvent
        self.resizeEvent = self._custom_resize_event

        self._language_connected = False
        self._connect_language_signal()
        self._apply_translations()
        
        # Enable copy functionality for table
        self.exam_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.exam_table.customContextMenuRequested.connect(self._show_table_context_menu)
        
        # Enable keyboard shortcuts for copy (Ctrl+C)
        copy_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence.Copy, self.exam_table)
        copy_shortcut.activated.connect(self._copy_selected_rows)
        
        self.update_content()
    
    def _lock_widget_positions(self):
        """Lock all widget positions to prevent movement"""
        # Lock toolbar
        if hasattr(self, 'toolBar'):
            self.toolBar.setMovable(False)
            self.toolBar.setFloatable(False)
        
        # Lock central widget and its children
        if hasattr(self, 'centralwidget'):
            self._lock_widget(self.centralwidget)
    
    def _lock_widget(self, widget):
        """Recursively lock a widget and its children"""
        if isinstance(widget, QtWidgets.QDockWidget):
            widget.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        elif isinstance(widget, QtWidgets.QToolBar):
            widget.setMovable(False)
            widget.setFloatable(False)
        
        # Lock all child widgets
        for child in widget.findChildren(QtWidgets.QWidget):
            if isinstance(child, QtWidgets.QDockWidget):
                child.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
            elif isinstance(child, QtWidgets.QToolBar):
                child.setMovable(False)
                child.setFloatable(False)
    
    def _custom_resize_event(self, event):
        """Override resize event to prevent entering fullscreen mode"""
        # If window is being resized to fullscreen size, constrain it
        screen = QtWidgets.QApplication.desktop().screenGeometry()
        if event.size().width() >= screen.width() and event.size().height() >= screen.height():
            # Don't allow fullscreen - keep a small margin
            max_width = screen.width() - 50
            max_height = screen.height() - 50
            if event.size().width() > max_width or event.size().height() > max_height:
                self.resize(min(event.size().width(), max_width), 
                           min(event.size().height(), max_height))
                return
        
        # Call original resize event
        if hasattr(self, '_original_resizeEvent'):
            self._original_resizeEvent(event)
    
    def changeEvent(self, event):
        """Override change event to prevent fullscreen state changes"""
        if event.type() == QtCore.QEvent.WindowStateChange:
            # Check if window is trying to enter fullscreen
            if self.windowState() & QtCore.Qt.WindowFullScreen:
                # Force exit from fullscreen
                self.setWindowState(self.windowState() & ~QtCore.Qt.WindowFullScreen)
                # Restore previous geometry if available
                if hasattr(self, 'windowed_geometry') and self.windowed_geometry:
                    self.setGeometry(self.windowed_geometry)
                return
        
        super().changeEvent(event)

    def closeEvent(self, event):
        self._disconnect_language_signal()
        super().closeEvent(event)

    def connect_signals(self):
        """Connect UI signals to their respective slots"""
        # Connect export action
        self.action_export.triggered.connect(self.export_exam_schedule)
    
    def _show_table_context_menu(self, position):
        """Show context menu for table with copy option"""
        from app.core.translator import translator
        from app.core.language_manager import language_manager
        
        menu = QtWidgets.QMenu(self)
        
        copy_action = QtWidgets.QAction(translator.t("common.copy"), self)
        copy_action.triggered.connect(self._copy_selected_rows)
        menu.addAction(copy_action)
        
        current_lang = language_manager.get_current_language()
        if current_lang == 'fa':
            menu.setLayoutDirection(QtCore.Qt.RightToLeft)
        else:
            menu.setLayoutDirection(QtCore.Qt.LeftToRight)
        
        menu.exec_(self.exam_table.viewport().mapToGlobal(position))
    
    def _copy_selected_rows(self):
        """Copy selected items (cells, rows, or columns) to clipboard"""
        selected_items = self.exam_table.selectedItems()
        if not selected_items:
            return
        
        # Group items by row to maintain structure
        rows_data = {}
        for item in selected_items:
            row = item.row()
            col = item.column()
            if row not in rows_data:
                rows_data[row] = {}
            rows_data[row][col] = item.text()
        
        # Build clipboard text maintaining row/column structure
        if not rows_data:
            return
        
        # Get all columns that have selected items
        all_cols = set()
        for row_data in rows_data.values():
            all_cols.update(row_data.keys())
        all_cols = sorted(all_cols)
        
        # Build text with proper spacing
        clipboard_text = []
        for row in sorted(rows_data.keys()):
            row_data = rows_data[row]
            row_text = []
            for col in all_cols:
                row_text.append(row_data.get(col, ''))
            clipboard_text.append('\t'.join(row_text))
        
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText('\n'.join(clipboard_text))

    # ------------------------------------------------------------------
    # Translation helpers
    # ------------------------------------------------------------------

    def _connect_language_signal(self):
        if not getattr(self, "_language_connected", False):
            language_manager.language_changed.connect(self._on_language_changed)
            self._language_connected = True

    def _disconnect_language_signal(self):
        if getattr(self, "_language_connected", False):
            try:
                language_manager.language_changed.disconnect(self._on_language_changed)
            except (TypeError, RuntimeError):
                pass
            self._language_connected = False

    def _on_language_changed(self, _lang):
        self._apply_translations()
        self.update_content()

    def _t(self, key, **kwargs):
        return translator.t(f"exam_window.{key}", **kwargs)

    def _current_language(self):
        return language_manager.get_current_language()

    def _apply_translations(self):
        language_manager.apply_layout_direction(self)
        direction = language_manager.get_layout_direction()
        if hasattr(self, 'centralwidget'):
            self.centralwidget.setLayoutDirection(direction)

        if hasattr(self, 'title_label'):
            self.title_label.setText(self._t("title"))
        if hasattr(self, 'info_label'):
            self.info_label.setText(self._t("subtitle"))
        if hasattr(self, 'stats_label') and not self.exam_table.rowCount():
            self.stats_label.setText(self._t("stats_placeholder"))
        if hasattr(self, 'explanation_label'):
            legend_text = "\n".join([
                self._t("legend_header"),
                self._t("legend_even"),
                self._t("legend_odd"),
                self._t("legend_all"),
            ])
            self.explanation_label.setText(legend_text)
            # Set layout direction based on current language
            if self._current_language() == 'fa':
                self.explanation_label.setLayoutDirection(QtCore.Qt.RightToLeft)
            else:
                self.explanation_label.setLayoutDirection(QtCore.Qt.LeftToRight)

        if hasattr(self, 'action_export'):
            self.action_export.setText(self._t("export_title"))
        if hasattr(self, 'toolBar'):
            self.toolBar.setWindowTitle(self._t("export_title"))

        headers = [
            self._t("table_columns.name"),
            self._t("table_columns.code"),
            self._t("table_columns.instructor"),
            self._t("table_columns.class_time"),
            self._t("table_columns.exam_time"),
            self._t("table_columns.credits"),
            self._t("table_columns.location"),
        ]
        if self.exam_table.columnCount() == len(headers):
            self.exam_table.setHorizontalHeaderLabels(headers)

    def _format_parity(self, parity_value):
        lang = self._current_language()
        if parity_value == 'ز':
            symbol = 'E' if lang != 'fa' else 'ز'
            return symbol, translator.t("parity.even")
        if parity_value == 'ف':
            symbol = 'O' if lang != 'fa' else 'ف'
            return symbol, translator.t("parity.odd")
        symbol = ''
        text = translator.t("parity.none") if parity_value else ''
        return symbol, text

    def update_content(self):
        """Update exam schedule content"""
        self.update_exam_schedule()

    def format_class_schedule(self, schedule):
        """Format class schedule information for display"""
        if not schedule:
            return self._t("stats_placeholder")

        formatted_sessions = []
        for session in schedule:
            day = session.get('day', '')
            start = session.get('start', '')
            end = session.get('end', '')
            parity = session.get('parity', '')

            day_label = get_day_label(day)
            symbol, parity_text = self._format_parity(parity)
            parity_parts = []
            if parity_text and parity_text != translator.t("parity.none"):
                parity_parts.append(parity_text)
            if symbol:
                parity_parts.append(symbol)

            parity_display = f" ({' / '.join(parity_parts)})" if parity_parts else ""
            formatted_sessions.append(f"{day_label}{parity_display}\n{start} - {end}")

        return "\n".join(formatted_sessions)

    def format_exam_time(self, exam_time):
        """Format exam time information for display"""
        if not exam_time or exam_time in ('اعلام نشده', translator.t("common.no_exam_time")):
            return translator.t("common.no_exam_time")

        # For non-Persian locales, return raw value (data uses Jalali format)
        if self._current_language() != 'fa':
            return exam_time

        # Assuming exam_time is in format like "1404/07/08 08:00-10:00"
        # We want to format it as:
        # 1404 بهمن 07
        # 08:00 - 10:00
        parts = exam_time.split()
        if len(parts) == 2:
            date_part = parts[0]
            time_part = parts[1]

            # Split date part (assuming format 1404/07/08)
            date_parts = date_part.split('/')
            if len(date_parts) == 3:
                year = date_parts[0]
                month = date_parts[1]
                day = date_parts[2]

                # Convert month number to Persian month name
                persian_months = {
                    '01': 'فروردین', '02': 'اردیبهشت', '03': 'خرداد',
                    '04': 'تیر', '05': 'مرداد', '06': 'شهریور',
                    '07': 'مهر', '08': 'آبان', '09': 'آذر',
                    '10': 'دی', '11': 'بهمن', '12': 'اسفند'
                }
                month_name = persian_months.get(month, month)

                # Format time part (assuming format 08:00-10:00)
                time_parts = time_part.split('-')
                if len(time_parts) == 2:
                    start_time = time_parts[0]
                    end_time = time_parts[1]
                    return f"{year} {month_name} {day}\n{start_time} - {end_time}"

        return exam_time

    def update_exam_schedule(self):
        """Update the exam schedule table with only selected courses"""
        if not self.parent_window:
            return

        # Get currently placed courses from the main window
        placed_courses = set()
        if hasattr(self.parent_window, 'placed'):
            # Handle both single and dual courses correctly
            for info in self.parent_window.placed.values():
                if info.get('type') == 'dual':
                    # For dual courses, add both courses
                    placed_courses.update(info.get('courses', []))
                else:
                    # For single courses, add the course key
                    placed_courses.add(info.get('course'))

        # Prepare table data
        exam_data = []
        for course_key in placed_courses:
            course = COURSES.get(course_key)
            if course:
                exam_data.append({
                    'name': course.get('name', 'نامشخص'),
                    'code': course.get('code', 'نامشخص'),
                    'instructor': course.get('instructor', 'نامشخص'),
                    'class_schedule': self.format_class_schedule(course.get('schedule', [])),
                    'exam_time': self.format_exam_time(course.get('exam_time', 'اعلام نشده')),
                    'credits': course.get('credits', 0),
                    'location': course.get('location', 'نامشخص')
                })

        # Sort by exam time (basic sorting)
        exam_data.sort(key=lambda x: x['exam_time'])

        # Update table with improved styling
        self.exam_table.setRowCount(len(exam_data))
        
        # Make table non-editable but allow selection and copying
        self.exam_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.exam_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.exam_table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        # Set column widths for better visual balance
        header = self.exam_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)  # Course name
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Code
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # Instructor
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)  # Class time
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)  # Exam time
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)  # Credits
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)  # Location

        # Style the table header to match main schedule table
        self.exam_table.horizontalHeader().setStyleSheet(
            "QHeaderView::section {"
            "background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, "
            "stop: 0 #1976D2, stop: 1 #1565C0);"
            "color: white;"
            "font-weight: bold;"
            "font-size: 14px;"
            "padding: 10px;"
            "border: none;"
            "font-family: 'IRANSans UI', 'Shabnam', 'Tahoma', sans-serif;"
            "}"
        )

        for row, data in enumerate(exam_data):
            # Course name
            name_item = QtWidgets.QTableWidgetItem(data['name'])
            name_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            name_item.setFont(QtGui.QFont('IRANSans UI', 11))
            self.exam_table.setItem(row, 0, name_item)

            # Course code
            code_item = QtWidgets.QTableWidgetItem(str(data['code']))
            code_item.setTextAlignment(QtCore.Qt.AlignCenter)
            code_item.setFont(QtGui.QFont('IRANSans UI', 11))
            self.exam_table.setItem(row, 1, code_item)

            # Instructor
            instructor_item = QtWidgets.QTableWidgetItem(data['instructor'])
            instructor_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            instructor_item.setFont(QtGui.QFont('IRANSans UI', 11))
            self.exam_table.setItem(row, 2, instructor_item)

            # Class schedule
            class_schedule_item = QtWidgets.QTableWidgetItem(data['class_schedule'])
            class_schedule_item.setTextAlignment(QtCore.Qt.AlignCenter)
            class_schedule_item.setFont(QtGui.QFont('IRANSans UI', 11))
            self.exam_table.setItem(row, 3, class_schedule_item)

            # Exam time
            exam_time_item = QtWidgets.QTableWidgetItem(data['exam_time'])
            exam_time_item.setTextAlignment(QtCore.Qt.AlignCenter)
            exam_time_item.setFont(QtGui.QFont('IRANSans UI', 11))
            self.exam_table.setItem(row, 4, exam_time_item)

            # Credits (Units) - right aligned as numeric
            credits_item = QtWidgets.QTableWidgetItem(str(data['credits']))
            credits_item.setTextAlignment(QtCore.Qt.AlignCenter)
            credits_item.setFont(QtGui.QFont('IRANSans UI', 11))
            self.exam_table.setItem(row, 5, credits_item)

            # Location
            location_item = QtWidgets.QTableWidgetItem(data['location'])
            location_item.setTextAlignment(QtCore.Qt.AlignCenter)
            location_item.setFont(QtGui.QFont('IRANSans UI', 11))
            self.exam_table.setItem(row, 6, location_item)

        # Set consistent row height for all rows
        for row in range(self.exam_table.rowCount()):
            self.exam_table.setRowHeight(row, 60)

        # Apply improved styling to match main schedule table
        self.exam_table.setStyleSheet(
            "QTableWidget {"
            "background-color: white;"
            "border: 1px solid #d5dbdb;"
            "border-radius: 8px;"
            "gridline-color: #ecf0f1;"
            "font-size: 12px;"
            "font-family: 'IRANSans UI', 'Shabnam', 'Tahoma', sans-serif;"
            "}"
            "QTableWidget::item {"
            "border: none;"
            "padding: 10px;"
            "border-bottom: 1px solid #ecf0f1;"
            "}"
            "QTableWidget::item:alternate {"
            "background-color: #f8f9fa;"
            "}"
            "QTableWidget::item:selected {"
            "background-color: #d6eaf8;"
            "color: #2980b9;"
            "}"
            "QTableWidget::item:hover {"
            "background-color: #e3f2fd;"
            "}"
        )

        # Calculate and display statistics
        if hasattr(self, 'stats_label'):
            if placed_courses:
                total_units = 0
                days_used = set()
                instructors = set()
                total_sessions = len(self.parent_window.placed) if hasattr(self.parent_window, 'placed') else 0

                for course_key in placed_courses:
                    course = COURSES.get(course_key, {})
                    total_units += course.get('credits', 0)
                    instructors.add(course.get('instructor', ''))
                    for session in course.get('schedule', []):
                        day_name = session.get('day', '')
                        if day_name:
                            days_used.add(get_day_label(day_name))

                day_labels = sorted([d for d in days_used if d])
                stats_text = self._t(
                    "stats_summary",
                    courses=len(placed_courses),
                    sessions=total_sessions,
                    credits=total_units,
                    days=len(day_labels)
                )

                if day_labels:
                    stats_text += f" ({', '.join(day_labels)})"

                self.stats_label.setText(stats_text)
            else:
                self.stats_label.setText(self._t("stats_empty"))

            self.stats_label.setStyleSheet(
                "background-color: #E1BEE7;"
                "color: #333;"
                "padding: 15px;"
                "border-radius: 8px;"
                "font-weight: normal;"
                "text-align: center;"
            )

    '''def export_exam_schedule(self):
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
            self.export_as_pdf_vertical()'''

    def export_exam_schedule(self):
        """Export the exam schedule to various formats"""
        if self.exam_table.rowCount() == 0:
            QtWidgets.QMessageBox.information(
                self,
                self._t("no_courses_dialog_title"),
                self._t("no_courses_dialog_text")
            )
            return

        # Ask user for export format
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle(self._t("export_title"))
        msg.setText(self._t("export_prompt"))

        txt_btn = msg.addButton(self._t("export_text_option"), QtWidgets.QMessageBox.ActionRole)
        html_btn = msg.addButton(self._t("export_html_option"), QtWidgets.QMessageBox.ActionRole)
        csv_btn = msg.addButton(self._t("export_csv_option"), QtWidgets.QMessageBox.ActionRole)

        pdf_v_btn = msg.addButton(self._t("export_pdf_portrait"), QtWidgets.QMessageBox.ActionRole)
        pdf_h_btn = msg.addButton(self._t("export_pdf_landscape"), QtWidgets.QMessageBox.ActionRole)

        cancel_btn = msg.addButton(translator.t("common.cancel"), QtWidgets.QMessageBox.RejectRole)

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
        elif clicked_button == pdf_v_btn:
            self.export_as_pdf_vertical()  # عمودی
        elif clicked_button == pdf_h_btn:
            self.export_as_pdf_horizontal()  # افقی

    def export_as_text(self):
        """Export exam schedule as plain text with comprehensive information"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self._t("export_title"), 'exam_schedule.txt', 'Text Files (*.txt)'
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
                f.write('=' * 60 + '\n\n')
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
                    # Handle both single and dual courses correctly
                    for info in self.parent_window.placed.values():
                        if info.get('type') == 'dual':
                            # For dual courses, add both courses
                            placed_courses.update(info.get('courses', []))
                        else:
                            # For single courses, add the course key
                            placed_courses.add(info.get('course'))

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
                f.write('=' * 60 + '\n\n')

                for row in range(self.exam_table.rowCount()):
                    name = self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else ''
                    code = self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else ''
                    instructor = self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else ''
                    class_schedule = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                    exam_time = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                    credits = self.exam_table.item(row, 5).text() if self.exam_table.item(row, 5) else ''
                    location = self.exam_table.item(row, 6).text() if self.exam_table.item(row, 6) else ''

                    f.write(f'📚 درس {row + 1}:\n')
                    f.write(f'   نام: {name}\n')
                    f.write(f'   کد: {code}\n')
                    f.write(f'   استاد: {instructor}\n')
                    f.write(f'   تعداد واحد: {credits}\n')
                    f.write(f'   زمان کلاس:\n{class_schedule}\n')
                    f.write(f'   زمان امتحان:\n{exam_time}\n')
                    f.write(f'   محل برگزاری: {location}\n')
                    f.write('-' * 50 + '\n\n')

                f.write('\n' + '=' * 60 + '\n')
                f.write('📝 توضیحات علائم:\n')
                f.write('• زوج: دروس هفته‌های زوج (در جدول با علامت ز نشان داده شده)\n')
                f.write('• فرد: دروس هفته‌های فرد (در جدول با علامت ف نشان داده شده)\n')
                f.write('• همه هفته‌ها: دروسی که هر هفته تشکیل می‌شوند\n\n')

            QtWidgets.QMessageBox.information(
                self,
                self._t("export_success_title"),
                self._t("export_success_text_note", path=filename)
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                self._t("export_error_title"),
                self._t("export_error_text", error=str(e))
            )

    def export_as_html(self):
        """Export exam schedule as HTML with improved styling and complete information"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self._t("export_title"), 'exam_schedule.html', 'HTML Files (*.html)'
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
                # Handle both single and dual courses correctly
                for info in self.parent_window.placed.values():
                    if info.get('type') == 'dual':
                        # For dual courses, add both courses
                        placed_courses.update(info.get('courses', []))
                    else:
                        # For single courses, add the course key
                        placed_courses.add(info.get('course'))

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
                class_schedule = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                exam_time = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                credits = self.exam_table.item(row, 5).text() if self.exam_table.item(row, 5) else ''
                location = self.exam_table.item(row, 6).text() if self.exam_table.item(row, 6) else ''

                table_rows += f"""
                <tr>
                    <td>{name}</td>
                    <td>{code}</td>
                    <td>{instructor}</td>
                    <td style="white-space: pre-line;">{class_schedule}</td>
                    <td style="white-space: pre-line;">{exam_time}</td>
                    <td>{credits}</td>
                    <td>{location}</td>
                </tr>
                """

            # Create complete HTML document with all requested styling
            html_content = f"""<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>برنامه امتحانات دانشگاهی</title>
    <style>
        @import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazir-font@v30.1.0/dist/font-face.css');

        body {{
            font-family: 'Vazir', 'Vazir Matn', 'IRANSans', 'Tahoma', 'Arial', sans-serif;
            background-color: #fff;
            margin: 0;
            padding: 20px;
            direction: rtl;
            text-align: right;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            color: #9C27B0;
            text-align: center;
            margin-bottom: 30px;
            font-weight: bold;
        }}
        .summary {{
            background-color: #E1BEE7;
            color: #333;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            margin-bottom: 30px;
        }}
        .table-container {{
            overflow-x: auto;
            margin-bottom: 30px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 4px;
        }}
        .exam-table {{
            width: 100%;
            border-collapse: collapse;
            background-color: #fff;
        }}
        .exam-table thead {{
            background-color: #9C27B0;
            color: black;
        }}
        .exam-table th {{
            padding: 12px 15px;
            text-align: center;
            font-weight: normal;
        }}
        .exam-table td {{
            padding: 12px 15px;
            border: 1px solid #dcdcdc;
            text-align: right;
            vertical-align: middle;
        }}
        .exam-table tr:nth-child(even) {{
            background-color: #fff;
        }}
        .exam-table tr:nth-child(odd) {{
            background-color: #f9f9f9;
        }}
        .exam-table tr:hover {{
            background-color: #e3f2fd;
        }}
        .numeric {{
            text-align: center;
        }}
        .explanation {{
            color: #7f8c8d;
            font-size: 14px;
            text-align: right;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 4px;
        }}
        .footer {{
            display: none;
        }}
        @media (max-width: 768px) {{
            .container {{
                padding: 10px;
            }}
            .exam-table th,
            .exam-table td {{
                padding: 8px 10px;
                font-size: 14px;
            }}
            .summary {{
                padding: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📅 برنامه امتحانات دانشگاهی</h1>

        <div class="summary">
            📊 خلاصه اطلاعات برنامه:<br>
            تعداد دروس: {total_courses} | مجموع واحدها: {total_units} | تعداد جلسات: {total_sessions} | روزهای حضور: {len(days_used)} روز
        </div>

        <div class="table-container">
            <table class="exam-table">
                <thead>
                    <tr>
                        <th>نام درس</th>
                        <th>کد درس</th>
                        <th>استاد</th>
                        <th>زمان کلاس</th>
                        <th>زمان امتحان</th>
                        <th class="numeric">واحد</th>
                        <th>محل برگزاری</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>

        <div class="explanation">
            <strong>توضیحات:</strong><br>
            • زوج: دروس هفته‌های زوج (در جدول با علامت ز نشان داده شده)<br>
            • فرد: دروس هفته‌های فرد (در جدول با علامت ف نشان داده شده)<br>
            • همه هفته‌ها: دروسی که هر هفته تشکیل می‌شوند
        </div>
    </div>
</body>
</html>"""

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)

            QtWidgets.QMessageBox.information(
                self,
                self._t("export_success_title"),
                self._t("export_success_text", path=filename)
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                self._t("export_error_title"),
                self._t("export_error_text", error=str(e))
            )

    def export_as_csv(self):
        """Export exam schedule as CSV"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self._t("export_title"), 'exam_schedule.csv', 'CSV Files (*.csv)'
        )
        if not filename:
            return

        try:
            import csv
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    self._t("table_columns.name"),
                    self._t("table_columns.code"),
                    self._t("table_columns.instructor"),
                    self._t("table_columns.class_time"),
                    self._t("table_columns.exam_time"),
                    self._t("table_columns.credits"),
                    self._t("table_columns.location")
                ])

                # Write data
                for row in range(self.exam_table.rowCount()):
                    name = self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else ''
                    code = self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else ''
                    instructor = self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else ''
                    class_schedule = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                    exam_time = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                    credits = self.exam_table.item(row, 5).text() if self.exam_table.item(row, 5) else ''
                    location = self.exam_table.item(row, 6).text() if self.exam_table.item(row, 6) else ''
                    writer.writerow([name, code, instructor, class_schedule, exam_time, credits, location])

            QtWidgets.QMessageBox.information(
                self,
                self._t("export_success_title"),
                self._t("export_success_text", path=filename)
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                self._t("export_error_title"),
                self._t("export_error_text", error=str(e))
            )

    def export_as_pdf(self):
        """Export exam schedule as PDF (placeholder implementation)"""
        QtWidgets.QMessageBox.information(
            self,
            self._t("export_pdf_placeholder_title"),
            self._t("export_pdf_placeholder_text")
        )

    def export_as_html_to_file(self, path):
        """Generate HTML file for exam schedule without QFileDialog (used for PDF export)"""
        try:
            from datetime import datetime
            current_date = datetime.now().strftime('%Y/%m/%d - %H:%M')

            total_courses = self.exam_table.rowCount()
            total_units = 0
            total_sessions = 0
            days_used = set()
            instructors = set()

            if hasattr(self.parent_window, 'placed'):
                placed_courses = set()
                for info in self.parent_window.placed.values():
                    if info.get('type') == 'dual':
                        placed_courses.update(info.get('courses', []))
                    else:
                        placed_courses.add(info.get('course'))

                for course_key in placed_courses:
                    course = COURSES.get(course_key, {})
                    total_units += course.get('credits', 0)
                    instructors.add(course.get('instructor', 'نامشخص'))
                    for session in course.get('schedule', []):
                        days_used.add(session.get('day', ''))

                total_sessions = len(self.parent_window.placed)

            table_rows = ""
            for row in range(self.exam_table.rowCount()):
                name = self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else ''
                code = self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else ''
                instructor = self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else ''
                class_schedule = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                exam_time = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                credits = self.exam_table.item(row, 5).text() if self.exam_table.item(row, 5) else ''
                location = self.exam_table.item(row, 6).text() if self.exam_table.item(row, 6) else ''

                table_rows += f"""
                <tr>
                    <td>{name}</td>
                    <td class="course-code">{code}</td>
                    <td>{instructor}</td>
                    <td style="white-space: pre-line;">{class_schedule}</td>
                    <td style="white-space: pre-line;">{exam_time}</td>
                    <td>{credits}</td>
                    <td>{location}</td>
                </tr>
                """

            html_content = f"""<!DOCTYPE html>
    <html dir="rtl" lang="fa">
    <head>
    <meta charset="UTF-8">
    <title>برنامه امتحانات دانشگاهی</title>
    <style>
    body {{
        font-family: 'IRANSans', 'Tahoma', sans-serif;
        background-color: #fff;
        margin: 0;
        padding: 20px;
        direction: rtl;
        text-align: right;
    }}
    h1 {{ color: #9C27B0; text-align:center; }}
    .summary {{
        background-color:#E1BEE7;
        padding:15px;
        border-radius:8px;
        margin-bottom:20px;
        text-align:center;
    }}
    table {{
        width:100%;
        border-collapse: collapse;
        table-layout: fixed;
    }}
    th, td {{
        border:1px solid #dcdcdc;
        padding:8px;
        text-align:center;
        word-wrap: break-word;
    }}
    tr:nth-child(even) {{ background-color:#fff; }}
    tr:nth-child(odd) {{ background-color:#f9f9f9; }}
    .course-code {{
        font-size: 0.8em; /* کوچک کردن کد درس */
        white-space: nowrap; /* جلوگیری از شکستن کد در چند خط */
    }}
    </style>
    </head>
    <body>
    <h1>📅 برنامه امتحانات دانشگاهی</h1>
    <div class="summary">
    📊 خلاصه اطلاعات برنامه:<br>
    تعداد دروس: {total_courses} | مجموع واحدها: {total_units} | تعداد جلسات: {total_sessions} | روزهای حضور: {len(days_used)} روز
    </div>
    <table>
    <thead>
    <tr>
    <th>نام درس</th>
    <th>کد درس</th>
    <th>استاد</th>
    <th>زمان کلاس</th>
    <th>زمان امتحان</th>
    <th>واحد</th>
    <th>محل برگزاری</th>
    </tr>
    </thead>
    <tbody>
    {table_rows}
    </tbody>
    </table>
    </body>
    </html>"""

            with open(path, 'w', encoding='utf-8') as f:
                f.write(html_content)

        except Exception as e:
            from PyQt5 import QtWidgets
            QtWidgets.QMessageBox.critical(
                self,
                self._t("export_error_title"),
                self._t("export_error_html_build", error=str(e))
            )

    def export_as_pdf_vertical(self):
        """Export exam schedule as PDF compatible with all PyQt5 versions"""
        from PyQt5 import QtCore, QtWidgets, QtWebEngineWidgets
        import tempfile
        import os

        # مسیر ذخیره PDF
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self._t("export_title"), 'exam_schedule.pdf', 'PDF Files (*.pdf)'
        )
        if not filename:
            return

        try:
            # ساخت فایل HTML موقت
            temp_html = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
            self.export_as_html_to_file(temp_html.name)
            temp_html.close()

            view = QtWebEngineWidgets.QWebEngineView()
            view.setUrl(QtCore.QUrl.fromLocalFile(temp_html.name))

            def pdf_callback(pdf_bytes):
                try:
                    with open(filename, 'wb') as f:
                        f.write(pdf_bytes)
                    QtWidgets.QMessageBox.information(
                        self,
                        self._t("export_success_title"),
                        self._t("export_success_pdf", path=filename)
                    )
                except Exception as e:
                    QtWidgets.QMessageBox.critical(
                        self,
                        self._t("export_error_title"),
                        self._t("export_error_text", error=str(e))
                    )
                finally:
                    if os.path.exists(temp_html.name):
                        os.unlink(temp_html.name)

            # وقتی صفحه بارگذاری شد، PDF تولید شود
            def on_load_finished(ok):
                if ok:
                    view.page().printToPdf(pdf_callback)
                else:
                    QtWidgets.QMessageBox.critical(
                        self,
                        self._t("export_error_title"),
                        self._t("export_error_pdf_load")
                    )
                    if os.path.exists(temp_html.name):
                        os.unlink(temp_html.name)

            view.loadFinished.connect(on_load_finished)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                self._t("export_error_title"),
                self._t("export_error_pdf", error=str(e))
            )

    def export_as_pdf_horizontal(self):
        """Export the exam schedule as PDF in landscape (horizontal) layout"""
        try:
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, self._t("export_title"), 'exam_schedule_horizontal.pdf', 'PDF Files (*.pdf)'
            )
            if not filename:
                return

            from PyQt5.QtWebEngineWidgets import QWebEngineView
            from PyQt5.QtGui import QPageLayout, QPageSize
            from PyQt5.QtCore import QMarginsF, QSizeF

            # ساخت فایل HTML موقت
            html_temp_path = filename.replace('.pdf', '_temp.html')
            self.export_as_html_to_file(html_temp_path)

            # بارگذاری HTML در WebEngine
            web = QWebEngineView()
            web.load(QtCore.QUrl.fromLocalFile(os.path.abspath(html_temp_path)))

            def on_load_finished(ok):
                if not ok:
                    QtWidgets.QMessageBox.critical(
                        self,
                        self._t("export_error_title"),
                        self._t("export_error_pdf_load")
                    )
                    return

                layout = QPageLayout(
                    QPageSize(QPageSize.A4),
                    QPageLayout.Landscape,  # جهت افقی
                    QMarginsF(10, 10, 10, 10)
                )

                web.page().printToPdf(filename, layout)
                QtWidgets.QMessageBox.information(
                    self,
                    self._t("export_success_title"),
                    self._t("export_success_pdf_horizontal", path=filename)
                )

                # حذف فایل HTML موقت
                try:
                    os.remove(html_temp_path)
                except:
                    pass

            web.loadFinished.connect(on_load_finished)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                self._t("export_error_title"),
                self._t("export_error_pdf_horizontal", error=str(e))
            )
