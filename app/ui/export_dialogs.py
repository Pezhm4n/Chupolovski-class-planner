#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export dialogs module for Schedule Planner
Contains dialog windows for exporting schedules
"""

import sys
import os
import json

from PyQt5 import QtWidgets, QtCore

# Import from core modules
from ..core.config import COURSES
from ..core.logger import setup_logging

logger = setup_logging()

class ExportMixin:
    """Mixin class for export functionality"""
    
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
                    for info in self.parent_window.placed.values():
                        placed_courses.add(info['course'])
                    
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
                    exam_time = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                    location = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                    
                    # Get additional course information
                    course_credits = 0
                    parity_info = 'همه هفته‌ها'
                    schedule_info = []
                    
                    # Find course by code to get additional info
                    for key, course in COURSES.items():
                        if course.get('code') == code:
                            course_credits = course.get('credits', 0)
                            # Check for parity and schedule from course data
                            for session in course.get('schedule', []):
                                day = session.get('day', '')
                                start = session.get('start', '')
                                end = session.get('end', '')
                                parity = session.get('parity', '')
                                
                                if parity == 'ز':
                                    parity_text = ' (زوج)'
                                    if parity_info == 'همه هفته‌ها':
                                        parity_info = 'زوج'
                                elif parity == 'ف':
                                    parity_text = ' (فرد)'
                                    if parity_info == 'همه هفته‌ها':
                                        parity_info = 'فرد'
                                else:
                                    parity_text = ''
                                
                                schedule_info.append(f'{day} {start}-{end}{parity_text}')
                            break
                    
                    f.write(f'📚 درس {row + 1}:\n')
                    f.write(f'   نام: {name}\n')
                    f.write(f'   کد: {code}\n')
                    f.write(f'   استاد: {instructor}\n')
                    f.write(f'   تعداد واحد: {course_credits}\n')
                    f.write(f'   نوع هفته: {parity_info}\n')
                    f.write(f'   زمان امتحان: {exam_time}\n')
                    f.write(f'   محل برگزاری: {location}\n')
                    
                    if schedule_info:
                        f.write(f'   جلسات درس:\n')
                        for session in schedule_info:
                            f.write(f'     • {session}\n')
                    
                    f.write('-'*50 + '\n\n')
                
                f.write('\n' + '='*60 + '\n')
                f.write('📝 توضیحات علائم:\n')
                f.write('• زوج: دروس هفته‌های زوج (در جدول با علامت ز نشان داده شده)\n')
                f.write('• فرد: دروس هفته‌های فرد (در جدول با علامت ف نشان داده شده)\n')
                f.write('• همه هفته‌ها: دروسی که هر هفته تشکیل می‌شوند\n\n')
                
                f.write(f'💡 این برنامه با استفاده از فناوری PyQt5 و Python توسعه یافته است\n')
                    
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
                for info in self.parent_window.placed.values():
                    placed_courses.add(info['course'])
                
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
                exam_time = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                location = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                
                # Get additional course information
                course_key = None
                course_credits = 0
                parity_info = 'همه هفته‌ها'
                parity_class = 'parity-all'
                
                # Find course by code to get additional info
                for key, course in COURSES.items():
                    if course.get('code') == code:
                        course_key = key
                        course_credits = course.get('credits', 0)
                        # Check for parity from schedule
                        for session in course.get('schedule', []):
                            if session.get('parity') == 'ز':
                                parity_info = 'زوج'
                                parity_class = 'parity-even'
                                break
                            elif session.get('parity') == 'ف':
                                parity_info = 'فرد'
                                parity_class = 'parity-odd'
                                break
                        break
                
                table_rows += f"""
                            <tr>
                                <td class="course-name">{name}</td>
                                <td class="course-code">{code}</td>
                                <td class="instructor">{instructor}</td>
                                <td style="font-weight: bold; color: #e67e22; text-align: center;">{course_credits}</td>
                                <td class="exam-time">{exam_time}</td>
                                <td class="location">{location}</td>
                                <td style="text-align: center;"><span class="parity {parity_class}">{parity_info}</span></td>
                            </tr>
                """
            
            # Create complete HTML document with RTL support
            html_content = f"""<!DOCTYPE html>
            <html dir="rtl" lang="fa">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>برنامه امتحانات</title>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;700&display=swap');
                    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
                    
                    body {{ 
                        font-family: 'Tajawal', 'Nazanin', 'Noto Sans Arabic', 'Tahoma', Arial, sans-serif; 
                        margin: 20px; 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        color: #2c3e50;
                        direction: rtl;
                        text-align: right;
                    }}
                    
                    .container {{ 
                        max-width: 900px; 
                        margin: 0 auto; 
                        background: white; 
                        padding: 40px; 
                        border-radius: 15px; 
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                        direction: rtl;
                        text-align: right;
                    }}
                    
                    h1 {{ 
                        color: #d35400; 
                        text-align: center; 
                        margin-bottom: 30px;
                        font-size: 28px;
                        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
                        font-family: 'Tajawal', 'Nazanin', 'Noto Sans Arabic', 'Tahoma', Arial, sans-serif;
                    }}
                    
                    .stats {{
                        display: flex;
                        justify-content: space-around;
                        margin: 20px 0;
                        flex-wrap: wrap;
                        direction: rtl;
                    }}
                    
                    .stat-item {{
                        text-align: center;
                        margin: 10px;
                        padding: 15px;
                        background: white;
                        border-radius: 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        min-width: 120px;
                        direction: rtl;
                    }}
                    
                    .stat-number {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #e74c3c;
                        margin-bottom: 5px;
                    }}
                    
                    .stat-label {{
                        font-size: 12px;
                        color: #7f8c8d;
                        font-weight: normal;
                    }}
                    
                    table {{ 
                        width: 100%; 
                        border-collapse: collapse; 
                        margin-top: 20px;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                        border-radius: 10px;
                        overflow: hidden;
                        direction: rtl;
                        text-align: right;
                    }}
                    
                    th, td {{ 
                        padding: 15px 10px; 
                        text-align: right; 
                        border-bottom: 1px solid #ecf0f1;
                        font-size: 13px;
                    }}
                    
                    th {{ 
                        background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
                        color: white; 
                        font-weight: bold;
                        font-size: 14px;
                        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
                        text-align: right;
                    }}
                    
                    tr:nth-child(even) {{ 
                        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                    }}
                    
                    .course-name {{
                        font-weight: bold;
                        color: #2c3e50;
                        font-size: 14px;
                        text-align: right;
                    }}
                    
                    .course-code {{
                        font-family: 'Courier New', monospace;
                        background: #e8f4fd;
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-weight: bold;
                        color: #2980b9;
                        text-align: right;
                    }}
                    
                    .exam-time {{ 
                        font-weight: bold; 
                        color: #e74c3c;
                        background: #fff5f5;
                        padding: 6px;
                        border-radius: 4px;
                        text-align: right;
                    }}
                    
                    .instructor {{
                        color: #34495e;
                        font-size: 12px;
                        text-align: right;
                    }}
                    
                    .location {{
                        color: #7f8c8d;
                        font-size: 11px;
                        font-style: italic;
                        text-align: right;
                    }}
                    
                    .parity {{
                        font-weight: bold;
                        padding: 2px 6px;
                        border-radius: 12px;
                        font-size: 10px;
                        color: white;
                        text-align: center;
                    }}
                    
                    .parity-even {{
                        background: #27ae60;
                    }}
                    
                    .parity-odd {{
                        background: #3498db;
                    }}
                    
                    .parity-all {{
                        background: #95a5a6;
                    }}
                    
                    .footer {{ 
                        text-align: center; 
                        margin-top: 40px; 
                        color: #7f8c8d; 
                        font-size: 12px;
                        padding: 20px;
                        background: #ecf0f1;
                        border-radius: 8px;
                        border-right: 3px solid #3498db;
                        direction: rtl;
                    }}
                    
                    @media print {{
                        body {{ 
                            background: white !important; 
                            direction: rtl;
                            text-align: right;
                        }}
                        .container {{ 
                            box-shadow: none !important; 
                            direction: rtl;
                            text-align: right;
                        }}
                        table, th, td {{
                            text-align: right;
                            direction: rtl;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>📅 برنامه امتحانات دانشگاهی</h1>
                    
                    <div class="info-section">
                        <h3 style="color: #27ae60; margin-top: 0;">📊 خلاصه اطلاعات برنامه</h3>
                        <div class="stats">
            """
            
            # Calculate comprehensive statistics
            total_courses = self.exam_table.rowCount()
            total_units = 0
            total_sessions = 0
            days_used = set()
            instructors = set()
            
            # Get placed courses for statistics
            if hasattr(self.parent_window, 'placed'):
                placed_courses = set()
                for info in self.parent_window.placed.values():
                    placed_courses.add(info['course'])
                
                for course_key in placed_courses:
                    course = COURSES.get(course_key, {})
                    total_units += course.get('credits', 0)
                    instructors.add(course.get('instructor', 'نامشخص'))
                    for session in course.get('schedule', []):
                        days_used.add(session.get('day', ''))
                
                total_sessions = len(self.parent_window.placed)
            
            # Add statistics
            html_content += f"""
                            <div class="stat-item">
                                <div class="stat-number">{total_courses}</div>
                                <div class="stat-label">تعداد دروس</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">{total_units}</div>
                                <div class="stat-label">مجموع واحدها</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">{total_sessions}</div>
                                <div class="stat-label">تعداد جلسات</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">{len(days_used)}</div>
                                <div class="stat-label">روزهای حضور</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-number">{len(instructors)}</div>
                                <div class="stat-label">تعداد اساتید</div>
                            </div>
                        </div>
                    </div>
                    
                    <table>
                        <thead>
                            <tr>
                                <th>نام درس</th>
                                <th>کد درس</th>
                                <th>استاد</th>
                                <th>واحد</th>
                                <th>زمان امتحان</th>
                                <th>محل برگزاری</th>
                                <th>نوع هفته</th>
                            </tr>
                        </thead>
                        <tbody>
                    {table_rows}
                        </tbody>
                    </table>
                    
                    <div class="footer">
                        <strong>📚 برنامه‌ریز انتخاب واحد</strong><br>
                        Schedule Planner v2.0 - University Course Selection System<br>
                        🕒 تاریخ و زمان تولید: {current_date}<br>
                        💡 توسعه یافته با PyQt5 و Python
                    </div>
                </div>
            </body>
            </html>
            """
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            QtWidgets.QMessageBox.information(self, 'صدور موفق', f'برنامه امتحانات در فایل زیر ذخیره شد:\n{filename}')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در ذخیره فایل:\n{str(e)}')
    
    def export_as_csv(self):
        """Export exam schedule as CSV with comprehensive course information"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.csv', 'CSV Files (*.csv)'
        )
        if not filename:
            return
            
        try:
            import csv
            with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                
                # Enhanced header with more information
                writer.writerow([
                    'نام درس', 
                    'کد درس', 
                    'استاد', 
                    'تعداد واحد',
                    'زمان امتحان', 
                    'محل برگزاری',
                    'نوع هفته',
                    'جلسات درس',
                    'توضیحات'
                ])
                
                # Write enhanced data
                for row in range(self.exam_table.rowCount()):
                    name = self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else ''
                    code = self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else ''
                    instructor = self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else ''
                    exam_time = self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else ''
                    location = self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else ''
                    
                    # Get additional course information
                    course_credits = 0
                    parity_info = 'همه هفته‌ها'
                    schedule_info = []
                    description = ''
                    
                    # Find course by code to get additional info
                    for key, course in COURSES.items():
                        if course.get('code') == code:
                            course_credits = course.get('credits', 0)
                            description = course.get('description', '')
                            
                            # Check for parity and schedule from course data
                            for session in course.get('schedule', []):
                                day = session.get('day', '')
                                start = session.get('start', '')
                                end = session.get('end', '')
                                parity = session.get('parity', '')
                                
                                if parity == 'ز':
                                    parity_text = ' (زوج)'
                                    if parity_info == 'همه هفته‌ها':
                                        parity_info = 'زوج'
                                elif parity == 'ف':
                                    parity_text = ' (فرد)'
                                    if parity_info == 'همه هفته‌ها':
                                        parity_info = 'فرد'
                                else:
                                    parity_text = ''
                                
                                schedule_info.append(f'{day} {start}-{end}{parity_text}')
                            break
                    
                    # Combine schedule info
                    schedule_text = '; '.join(schedule_info) if schedule_info else 'اطلاعی موجود نیست'
                    
                    writer.writerow([
                        name,
                        code, 
                        instructor,
                        course_credits,
                        exam_time,
                        location,
                        parity_info,
                        schedule_text,
                        description[:100] + '...' if len(description) > 100 else description
                    ])
                    
            QtWidgets.QMessageBox.information(self, 'صدور موفق', f'برنامه امتحانات در فایل زیر ذخیره شد:\n{filename}')
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'خطا', f'خطا در ذخیره فایل:\n{str(e)}')
    
    def export_as_pdf(self):
        """Export exam schedule as PDF with robust error handling"""
        logger.info("Starting PDF export process")
        
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'ذخیره برنامه امتحانات', 'exam_schedule.pdf', 'PDF Files (*.pdf)'
        )
        if not filename:
            logger.info("PDF export cancelled by user")
            return
            
        try:
            exam_count = self.exam_table.rowCount()
            logger.info(f"Exporting {exam_count} exam entries to PDF")
            
            if exam_count == 0:
                QtWidgets.QMessageBox.warning(
                    self, 'هیچ داده‌ای', 
                    'هیچ درسی برای صدور پیدا نشد. لطفاً ابتدا دروس مورد نظر را به جدول اضافه کنید.'
                )
                return
                
            # Try native Qt PDF export first
            if self._export_pdf_native(filename, exam_count):
                return
                
            # Fallback to HTML with detailed instructions
            self._export_pdf_fallback(filename, exam_count)
            
        except Exception as e:
            error_msg = f"Error during PDF export: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, 'خطا در صدور PDF', 
                f'متأسفانه خطایی در صدور PDF رخ داد:\n{str(e)}\n\n'
                f'لطفاً فایل app.log را بررسی کنید.'
            )
    
    def _export_pdf_native(self, filename, exam_count):
        """Try native Qt PDF export using QPrinter"""
        try:
            from PyQt5.QtPrintSupport import QPrinter
            from PyQt5.QtWebEngineWidgets import QWebEngineView
            
            logger.info("Attempting native Qt PDF export")
            
            # Create HTML content with proper Persian fonts
            html_content = self._generate_pdf_html(exam_count)
            
            # Create web view for rendering
            web_view = QWebEngineView()
            web_view.setHtml(html_content)
            
            # Create printer with proper settings for RTL
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(filename)
            printer.setPageSize(QPrinter.A4)
            printer.setPageMargins(20, 20, 20, 20, QPrinter.Millimeter)
            
            # Set up completion handler
            def on_load_finished(success):
                if success:
                    logger.info("Web view loaded successfully, generating PDF")
                    web_view.page().printToPdf(filename)
                else:
                    logger.error("Web view failed to load content")
                    self._export_pdf_fallback(filename, exam_count)
            
            def on_pdf_finished(file_path, success):
                web_view.deleteLater()
                if success and os.path.exists(filename) and os.path.getsize(filename) > 0:
                    logger.info(f"PDF successfully generated: {filename}")
                    QtWidgets.QMessageBox.information(
                        self, 'صدور موفق PDF', 
                        f'برنامه امتحانات با موفقیت در فایل PDF ذخیره شد:\n{filename}\n\n'
                        f'تعداد دروس: {exam_count}'
                    )
                else:
                    logger.error("PDF generation failed, falling back to HTML")
                    self._export_pdf_fallback(filename, exam_count)
            
            web_view.loadFinished.connect(on_load_finished)
            web_view.page().pdfPrintingFinished.connect(on_pdf_finished)
            
            return True
            
        except ImportError as e:
            logger.warning(f"Qt WebEngine not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Native PDF export failed: {e}", exc_info=True)
            return False
    
    def _export_pdf_fallback(self, filename, exam_count):
        """Fallback HTML export with PDF conversion instructions"""
        logger.info("Using HTML fallback for PDF export")
        
        try:
            html_content = self._generate_pdf_html(exam_count)
            html_filename = filename.replace('.pdf', '_exam_schedule.html')
            
            with open(html_filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML file generated successfully: {html_filename}")
            
            QtWidgets.QMessageBox.information(
                self, 'صدور HTML (آماده برای PDF)', 
                f'فایل HTML با قابلیت تبدیل به PDF ذخیره شد.\n\n'
                f'راهنمای تبدیل به PDF:\n'
                f'۱. فایل HTML را در مرورگر باز کنید\n'
                f'۲. Ctrl+P یا کلید ترکیبی پرینت را فشار دهید\n'
                f'۳. در بخش مقصد، "Save as PDF" را انتخاب کنید\n'
                f'۴. فایل PDF را ذخیره کنید\n\n'
                f'فایل HTML: {html_filename}'
            )
            
        except Exception as e:
            logger.error(f"HTML fallback export failed: {e}", exc_info=True)
            raise
    
    def _generate_pdf_html(self, exam_count):
        """Generate HTML content optimized for PDF export with Persian support and comprehensive information"""
        from datetime import datetime
        current_date = datetime.now().strftime('%Y/%m/%d - %H:%M')
        
        # Collect comprehensive exam data
        exam_data = []
        total_units = 0
        total_sessions = 0
        days_used = set()
        instructors = set()
        
        for row in range(exam_count):
            base_data = {
                'name': self.exam_table.item(row, 0).text() if self.exam_table.item(row, 0) else '',
                'code': self.exam_table.item(row, 1).text() if self.exam_table.item(row, 1) else '',
                'instructor': self.exam_table.item(row, 2).text() if self.exam_table.item(row, 2) else '',
                'exam_time': self.exam_table.item(row, 3).text() if self.exam_table.item(row, 3) else '',
                'location': self.exam_table.item(row, 4).text() if self.exam_table.item(row, 4) else '',
                'credits': 0,
                'parity': 'همه هفته‌ها',
                'schedule': []
            }
            
            # Get additional course information
            for key, course in COURSES.items():
                if course.get('code') == base_data['code']:
                    base_data['credits'] = course.get('credits', 0)
                    total_units += base_data['credits']
                    instructors.add(base_data['instructor'])
                    
                    # Check for parity and schedule from course data
                    for session in course.get('schedule', []):
                        days_used.add(session.get('day', ''))
                        day = session.get('day', '')
                        start = session.get('start', '')
                        end = session.get('end', '')
                        parity = session.get('parity', '')
                        
                        if parity == 'ز':
                            parity_text = ' (زوج)'
                            if base_data['parity'] == 'همه هفته‌ها':
                                base_data['parity'] = 'زوج'
                        elif parity == 'ف':
                            parity_text = ' (فرد)'
                            if base_data['parity'] == 'همه هفته‌ها':
                                base_data['parity'] = 'فرد'
                        else:
                            parity_text = ''
                        
                        base_data['schedule'].append(f'{day} {start}-{end}{parity_text}')
                    break
            
            exam_data.append(base_data)
        
        # Get placed courses for additional statistics
        if hasattr(self.parent_window, 'placed'):
            total_sessions = len(self.parent_window.placed)
        
        # Generate table rows with enhanced information
        table_rows = ""
        for i, exam in enumerate(exam_data):
            row_class = "even-row" if i % 2 == 0 else "odd-row"
            
            # Determine parity styling
            parity_class = 'parity-all'
            if exam['parity'] == 'زوج':
                parity_class = 'parity-even'
            elif exam['parity'] == 'فرد':
                parity_class = 'parity-odd'
            
            schedule_text = '<br>'.join(exam['schedule'][:3])  # Show first 3 sessions
            if len(exam['schedule']) > 3:
                schedule_text += f'<br><small>+{len(exam["schedule"])-3} جلسه دیگر</small>'
            
            table_rows += f"""
                <tr class="{row_class}">
                    <td class="course-name" style="text-align: right;">{exam['name']}</td>
                    <td class="course-code" style="text-align: center;">{exam['code']}</td>
                    <td class="instructor" style="text-align: right;">{exam['instructor']}</td>
                    <td class="credits" style="text-align: center;">{exam['credits']}</td>
                    <td class="exam-time" style="text-align: center;">{exam['exam_time']}</td>
                    <td class="location" style="text-align: right;">{exam['location']}</td>
                    <td style="text-align: center;"><span class="parity {parity_class}">{exam['parity']}</span></td>
                    <td class="schedule" style="text-align: right;">{schedule_text}</td>
                </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="fa">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>برنامه امتحانات - Schedule Planner</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;700&display=swap');
                @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
                
                @page {{
                    size: A4 landscape;
                    margin: 15mm;
                    @bottom-center {{
                        content: "صفحه " counter(page) " از " counter(pages);
                        font-size: 10px;
                        color: #666;
                        direction: rtl;
                        text-align: center;
                    }}
                }}
                
                * {{
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Tajawal', 'Nazanin', 'Noto Sans Arabic', 'Tahoma', 'Arial Unicode MS', 'Segoe UI', sans-serif;
                    background: white;
                    color: #2c3e50;
                    line-height: 1.4;
                    margin: 0;
                    padding: 15px;
                    font-size: 12px;
                    direction: rtl;
                    text-align: right;
                }}
                
                .header {{
                    text-align: center;
                    margin-bottom: 25px;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    direction: rtl;
                }}
                
                .header h1 {{
                    margin: 0 0 10px 0;
                    font-size: 22px;
                    font-weight: bold;
                    direction: rtl;
                }}
                
                .header p {{
                    margin: 5px 0;
                    font-size: 14px;
                    opacity: 0.9;
                    direction: rtl;
                }}
                
                .stats {{
                    display: flex;
                    justify-content: space-around;
                    margin: 15px 0;
                    padding: 15px;
                    background: #e8f6f3;
                    border-radius: 8px;
                    border: 2px solid #1abc9c;
                    direction: rtl;
                }}
                
                .stat-item {{
                    text-align: center;
                    direction: rtl;
                }}
                
                .stat-number {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #1abc9c;
                }}
                
                .stat-label {{
                    font-size: 10px;
                    color: #2c3e50;
                    margin-top: 3px;
                }}
                
                .exam-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    border-radius: 8px;
                    overflow: hidden;
                    font-size: 10px;
                    direction: rtl;
                    text-align: right;
                }}
                
                .exam-table th {{
                    background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
                    color: white;
                    padding: 12px 8px;
                    text-align: center;
                    font-weight: bold;
                    font-size: 11px;
                    border: none;
                }}
                
                .exam-table td {{
                    padding: 8px 6px;
                    text-align: center;
                    border-bottom: 1px solid #ecf0f1;
                    vertical-align: middle;
                }}
                
                .even-row {{
                    background-color: #f8f9fa;
                }}
                
                .odd-row {{
                    background-color: white;
                }}
                
                .course-name {{
                    font-weight: bold;
                    color: #2c3e50;
                    text-align: right;
                    font-size: 11px;
                }}
                
                .course-code {{
                    font-family: 'Courier New', monospace;
                    background: #ecf0f1;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-weight: bold;
                    font-size: 9px;
                    text-align: center;
                }}
                
                .exam-time {{
                    font-weight: bold;
                    color: #e74c3c;
                    background: #fff5f5;
                    border-radius: 4px;
                    padding: 4px;
                    font-size: 9px;
                    text-align: center;
                }}
                
                .instructor {{
                    color: #34495e;
                    font-size: 10px;
                    text-align: right;
                }}
                
                .location {{
                    color: #7f8c8d;
                    font-size: 9px;
                    text-align: right;
                }}
                
                .credits {{
                    font-weight: bold;
                    color: #e67e22;
                    font-size: 11px;
                    text-align: center;
                }}
                
                .schedule {{
                    font-size: 8px;
                    color: #34495e;
                    text-align: right;
                    line-height: 1.2;
                }}
                
                .parity {{
                    font-weight: bold;
                    padding: 2px 6px;
                    border-radius: 10px;
                    font-size: 8px;
                    color: white;
                    text-align: center;
                }}
                
                .parity-even {{
                    background: #27ae60;
                }}
                
                .parity-odd {{
                    background: #3498db;
                }}
                
                .parity-all {{
                    background: #95a5a6;
                }}
                
                .footer {{
                    margin-top: 30px;
                    padding: 15px;
                    text-align: center;
                    background: #ecf0f1;
                    border-radius: 8px;
                    color: #7f8c8d;
                    font-size: 10px;
                    border-top: 3px solid #3498db;
                    direction: rtl;
                }}
                
                @media print {{
                    body {{
                        print-color-adjust: exact;
                        -webkit-print-color-adjust: exact;
                        direction: rtl;
                        text-align: right;
                    }}
                    
                    .header, .exam-table th {{
                        background: #667eea !important;
                        color: white !important;
                    }}
                    
                    table, th, td {{
                        text-align: right;
                        direction: rtl;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📅 برنامه امتحانات دانشگاهی</h1>
                <p>برنامه‌ریز انتخاب واحد - Schedule Planner v2.0</p>
            </div>
            
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-number">{exam_count}</div>
                    <div class="stat-label">تعداد دروس</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{total_units}</div>
                    <div class="stat-label">مجموع واحدها</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{total_sessions}</div>
                    <div class="stat-label">تعداد جلسات</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{len(days_used)}</div>
                    <div class="stat-label">روزهای حضور</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{len(instructors)}</div>
                    <div class="stat-label">تعداد اساتید</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{current_date}</div>
                    <div class="stat-label">تاریخ تولید</div>
                </div>
            </div>
            
            <table class="exam-table">
                <thead>
                    <tr>
                        <th style="text-align: center;">نام درس</th>
                        <th style="text-align: center;">کد درس</th>
                        <th style="text-align: center;">استاد</th>
                        <th style="text-align: center;">واحد</th>
                        <th style="text-align: center;">زمان امتحان</th>
                        <th style="text-align: center;">محل</th>
                        <th style="text-align: center;">نوع هفته</th>
                        <th style="text-align: center;">جلسات</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            
            <div class="footer">
                <strong>📚 برنامه‌ریز انتخاب واحد</strong><br>
                Schedule Planner v2.0 - University Course Selection System<br>
                🕒 تاریخ و زمان تولید: {current_date}<br>
                💡 توسعه یافته با PyQt5 و Python
            </div>
        </body>
        </html>
        """
        
        return html_content