#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exam schedule window module for Schedule Planner
Contains window for viewing exam schedules
"""

import sys
import os

from PyQt5 import QtWidgets, QtCore, uic, QtGui

# Import from core modules
from ..core.config import COURSES, BASE_DIR
from ..core.logger import setup_logging

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
            QtWidgets.QMessageBox.critical(self, "خطا", f"فایل UI یافت نشد: {exam_ui_file}")
            return
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در بارگذاری UI: {str(e)}")
            return
        
        # Connect signals
        self.connect_signals()
        
        # Install event filter for fullscreen functionality
        self.centralwidget.installEventFilter(self)
        
        # Also install event filter on the main window
        self.installEventFilter(self)
        
        # Update content
        self.update_content()
        
    def eventFilter(self, obj, event):
        """Event filter to handle mouse clicks for fullscreen toggle"""
        if event.type() == QtCore.QEvent.MouseButtonPress:
            # Check if the click is on the central widget or its children
            if (obj == self.centralwidget or 
                (isinstance(obj, QtWidgets.QWidget) and 
                 self.centralwidget.isAncestorOf(obj))):
                self.toggle_fullscreen()
                return True
        return super().eventFilter(obj, event)
        
    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode"""
        if self.is_fullscreen:
            # Exit fullscreen
            self.showNormal()
            if self.windowed_geometry:
                self.setGeometry(self.windowed_geometry)
            self.is_fullscreen = False
        else:
            # Enter fullscreen
            self.windowed_geometry = self.geometry()
            self.showFullScreen()
            self.is_fullscreen = True
            
    def connect_signals(self):
        """Connect UI signals to their respective slots"""
        # Connect export action
        self.action_export.triggered.connect(self.export_exam_schedule)
        
    def update_content(self):
        """Update exam schedule content"""
        self.update_exam_schedule()
        
    def format_class_schedule(self, schedule):
        """Format class schedule information for display"""
        if not schedule:
            return "نامشخص"
        
        formatted_sessions = []
        for session in schedule:
            day = session.get('day', '')
            start = session.get('start', '')
            end = session.get('end', '')
            parity = session.get('parity', '')
            
            # Add parity indicator if exists
            parity_indicator = ""
            if parity == 'ز':
                parity_indicator = "(ز)"
            elif parity == 'ف':
                parity_indicator = "(ف)"
            
            formatted_sessions.append(f"{day}{parity_indicator}\n{start} - {end}")
        
        return "\n".join(formatted_sessions)
    
    def format_exam_time(self, exam_time):
        """Format exam time information for display"""
        if not exam_time or exam_time == 'اعلام نشده':
            return "اعلام نشده"
        
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
        
        # Set column widths for better visual balance
        header = self.exam_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)  # Course name
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Code
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # Instructor
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)  # Class time
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)  # Exam time
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)  # Credits
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)  # Location
        
        # Style the table header
        self.exam_table.horizontalHeader().setStyleSheet(
            "QHeaderView::section {"
            "background-color: #9C27B0;"
            "color: black;"
            "font-weight: normal;"
            "padding: 8px;"
            "border: 1px solid #dcdcdc;"
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
        
        # Apply zebra striping and hover effects through styles
        self.exam_table.setStyleSheet(
            "QTableWidget {"
            "background-color: #fff;"
            "border: none;"
            "}"
            "QTableWidget::item {"
            "border: 1px solid #dcdcdc;"
            "padding: 8px;"
            "}"
            "QTableWidget::item:nth-child(even) {"
            "background-color: #fff;"
            "}"
            "QTableWidget::item:nth-child(odd) {"
            "background-color: #f9f9f9;"
            "}"
            "QTableWidget::item:hover {"
            "background-color: #e3f2fd;"
            "}"
        )
        
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
                stats_text = f"📊 آمار برنامه: دروس: {len(placed_courses)} | جلسات: {total_sessions} | واحدها: {total_units} | روزهای حضور: {len(days_used)} روز"
                
                if days_used:
                    days_list = ', '.join(sorted([day for day in days_used if day]))
                    stats_text += f" ({days_list})"
                
                self.stats_label.setText(stats_text)
                # Update stats label styling to match new design
                self.stats_label.setStyleSheet(
                    "background-color: #E1BEE7;"
                    "color: #333;"
                    "padding: 15px;"
                    "border-radius: 8px;"
                    "font-weight: normal;"
                    "text-align: center;"
                )
            else:
                self.stats_label.setText("📊 هیچ درسی انتخاب نشده است")
                # Update stats label styling to match new design
                self.stats_label.setStyleSheet(
                    "background-color: #E1BEE7;"
                    "color: #333;"
                    "padding: 15px;"
                    "border-radius: 8px;"
                    "font-weight: normal;"
                    "text-align: center;"
                )

    def export_exam_schedule(self):
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
            self.export_as_pdf()

    def export_as_text(self):
        """Export exam schedule as plain text with comprehensive information"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.txt', 'Text Files (*.txt)'
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
                f.write('='*60 + '\n\n')
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
                f.write('='*60 + '\n\n')
                
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
                    f.write('-'*50 + '\n\n')
                
                f.write('\n' + '='*60 + '\n')
                f.write('📝 توضیحات علائم:\n')
                f.write('• زوج: دروس هفته‌های زوج (در جدول با علامت ز نشان داده شده)\n')
                f.write('• فرد: دروس هفته‌های فرد (در جدول با علامت ف نشان داده شده)\n')
                f.write('• همه هفته‌ها: دروسی که هر هفته تشکیل می‌شوند\n\n')
                    
            QtWidgets.QMessageBox.information(self, 'صدور موفق', f'برنامه امتحانات در فایل زیر ذخیره شد:\n{filename}\n\nنکته: برای نمایش صحیح متن راست به چپ، فایل را با یک ویرایشگر متن که از UTF-8 و RTL پشتیبانی می‌کند باز کنید.')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در ذخیره فایل:\n{str(e)}')

    def export_as_html(self):
        """Export exam schedule as HTML with improved styling and complete information"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.html', 'HTML Files (*.html)'
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
                
            QtWidgets.QMessageBox.information(self, 'صدور موفق', f'برنامه امتحانات در فایل زیر ذخیره شد:\n{filename}')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در ذخیره فایل:\n{str(e)}')

    def export_as_csv(self):
        """Export exam schedule as CSV"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.csv', 'CSV Files (*.csv)'
        )
        if not filename:
            return
            
        try:
            import csv
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['نام درس', 'کد درس', 'استاد', 'زمان کلاس', 'زمان امتحان', 'واحد', 'محل برگزاری'])
                
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
                    
            QtWidgets.QMessageBox.information(self, 'صدور موفق', f'برنامه امتحانات در فایل زیر ذخیره شد:\n{filename}')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در ذخیره فایل:\n{str(e)}')

    def export_as_pdf(self):
        """Export exam schedule as PDF (placeholder implementation)"""
        QtWidgets.QMessageBox.information(
            self, 'قابلیت آزمایشی', 
            'صدور به فرمت PDF در این نسخه آزمایشی پشتیبانی نمی‌شود.\n'
            'لطفا از فرمت‌های دیگر مانند TXT یا HTML استفاده کنید.'
        )