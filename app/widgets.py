#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Custom widgets for Schedule Planner
Contains custom UI components for the application
"""

from PyQt5 import QtWidgets, QtGui, QtCore
import sys
import os

# Add the app directory to the Python path to enable imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DAYS, TIME_SLOTS, EXTENDED_TIME_SLOTS, COLOR_MAP, COURSES
from course_utils import schedules_conflict

# ---------------------- Custom Course List Widget ----------------------

class CourseListWidget(QtWidgets.QWidget):
    """Custom widget for course list items with delete functionality"""
    def __init__(self, course_key, course_info, parent_list, parent=None):
        super().__init__(parent)
        self.course_key = course_key
        self.course_info = course_info
        self.parent_list = parent_list
        self.setup_ui()
        
    def setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Enable mouse tracking for hover events
        self.setMouseTracking(True)
        
        # Course info label
        display = f"{self.course_info['name']} — {self.course_info['code']} — {self.course_info.get('instructor', 'نامشخص')}"
        self.course_label = QtWidgets.QLabel(display)
        self.course_label.setWordWrap(True)
        # Enable mouse tracking on the label too
        self.course_label.setMouseTracking(True)
        layout.addWidget(self.course_label, 1)
        
        # Conflict indicator label (hidden by default) with enhanced styling
        # Positioned absolutely on hover, not taking up permanent space
        self.conflict_indicator = QtWidgets.QLabel("⚠")
        self.conflict_indicator.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 16px;")
        self.conflict_indicator.hide()
        self.conflict_indicator.setParent(self)
        self.conflict_indicator.setGeometry(self.width() - 25, 2, 16, 16)  # Position at top-right
        self.conflict_indicator.setToolTip("این درس با دروس انتخابی شما تداخل دارد")
        
        # Button container
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(2)
        
        # Edit button (pencil icon) - smaller and more circular
        self.edit_btn = QtWidgets.QPushButton("✏️")
        self.edit_btn.setObjectName("edit_btn")
        self.edit_btn.setFixedSize(18, 18)
        self.edit_btn.setToolTip(f"ویرایش درس {self.course_info['name']}")
        self.edit_btn.clicked.connect(self.edit_course)
        button_layout.addWidget(self.edit_btn)
        
        # Delete button (only for custom courses) - smaller and more circular
        if self.is_custom_course():
            self.delete_btn = QtWidgets.QPushButton("✕")
            self.delete_btn.setObjectName("delete_btn")
            self.delete_btn.setFixedSize(18, 18)
            self.delete_btn.setToolTip(f"حذف درس {self.course_info['name']}")
            self.delete_btn.clicked.connect(self.delete_course)
            button_layout.addWidget(self.delete_btn)
            
        layout.addLayout(button_layout)
            
    def is_custom_course(self):
        """Check if this course should show delete button (all JSON courses can be deleted)"""
        # With JSON storage, we can allow deletion of all courses
        # Optionally, you might want to protect some system courses
        return True  # Allow deletion for all courses
                                       
    def delete_course(self):
        """Handle course deletion with confirmation"""
        course_name = self.course_info.get('name', 'نامشخص')
        instructor = self.course_info.get('instructor', 'نامشخص')
        
        # Confirmation dialog
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle('حذف درس')
        msg.setText(f'آیا مطمئن هستید که می‌خواهید درس زیر را حذف کنید؟')
        msg.setInformativeText(f'نام درس: {course_name}\nاستاد: {instructor}')
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg.setDefaultButton(QtWidgets.QMessageBox.No)
        
        if msg.exec_() == QtWidgets.QMessageBox.Yes:
            # Get main window reference properly
            main_window = self.get_main_window()
            if not main_window:
                QtWidgets.QMessageBox.warning(self, 'خطا', 'خطا در دسترسی به پنجره اصلی')
                return
            
            # Remove from COURSES dictionary
            if self.course_key in COURSES:
                del COURSES[self.course_key]
            
            # Save courses to JSON
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from data_manager import save_courses_to_json
            save_courses_to_json()
            
            # Remove from user_data
            user_data = main_window.user_data
            custom_courses = user_data.get('custom_courses', [])
            user_data['custom_courses'] = [c for c in custom_courses 
                                          if c.get('code') != self.course_info.get('code')]
            
            # Save updated user data
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from data_manager import save_user_data
            save_user_data(user_data)
            
            # Remove from any placed schedules
            main_window.remove_course_from_schedule(self.course_key)
            
            # Refresh the course list and info panel - FIXED
            main_window.populate_course_list()
            main_window.update_course_info_panel()  # Update info panel
            
            # Update status
            main_window.update_status()
            
            QtWidgets.QMessageBox.information(
                self, 'حذف شد', 
                f'درس "{course_name}" با موفقیت حذف شد.'
            )
            
    def edit_course(self):
        """Handle course editing"""
        main_window = self.get_main_window()
        if not main_window:
            QtWidgets.QMessageBox.warning(self, 'خطا', 'خطا در دسترسی به پنجره اصلی')
            return
            
        # Open edit dialog for this specific course
        main_window.open_edit_course_dialog_for_course(self.course_key)
            
    def get_main_window(self):
        """Get reference to main window"""
        parent = self.parent()
        while parent:
            if isinstance(parent, QtWidgets.QMainWindow):
                return parent
            parent = parent.parent()
        return None
    
    def mousePressEvent(self, event):
        """Handle mouse clicks to select item and emit itemClicked signal"""
        # Only handle left-click, ignore right-click and other buttons
        if event.button() != QtCore.Qt.LeftButton:
            super().mousePressEvent(event)
            return
            
        # Find the corresponding QListWidgetItem
        for i in range(self.parent_list.count()):
            item = self.parent_list.item(i)
            if self.parent_list.itemWidget(item) == self:
                # Set this item as current
                self.parent_list.setCurrentItem(item)
                # Emit itemClicked signal to trigger course addition
                self.parent_list.itemClicked.emit(item)
                break
        
        # Call parent implementation for any buttons (edit/delete)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Forward mouse move events to enable hover preview and conflict checking"""
        # Get the main window
        main_window = self.get_main_window()
        if main_window:
            # Find the corresponding QListWidgetItem
            for i in range(self.parent_list.count()):
                item = self.parent_list.item(i)
                if self.parent_list.itemWidget(item) == self:
                    # Get the course key and trigger preview
                    key = item.data(QtCore.Qt.UserRole)
                    if key and getattr(main_window, 'last_hover_key', None) != key:
                        main_window.clear_preview()
                        main_window.last_hover_key = key
                        main_window.preview_course(key)
                        
                        # Check for conflicts and update indicator
                        self.update_conflict_indicator(main_window, key)
                    break
        
        # Update conflict indicator position on mouse move
        if self.conflict_indicator.isVisible():
            self.conflict_indicator.setGeometry(self.width() - 25, 2, 16, 16)
        
        # Call parent implementation
        super().mouseMoveEvent(event)
    
    def update_conflict_indicator(self, main_window, course_key):
        """Update the conflict indicator based on current schedule"""
        course = COURSES.get(course_key)
        if not course or not main_window.placed:
            self.conflict_indicator.hide()
            return
            
        # Check for conflicts with currently placed courses
        has_conflict = False
        for sess in course['schedule']:
            if sess['day'] not in DAYS:
                continue
            col = DAYS.index(sess['day'])
            try:
                srow = EXTENDED_TIME_SLOTS.index(sess['start'])
                erow = EXTENDED_TIME_SLOTS.index(sess['end'])
            except ValueError:
                continue
            span = max(1, erow - srow)
            
            # Check for conflicts in the same day/time slot
            for (prow, pcol), info in main_window.placed.items():
                if pcol != col:
                    continue
                # Skip conflict check with the same course
                if info['course'] == course_key:
                    continue
                prow_start = prow
                prow_span = info['rows']
                if not (srow + span <= prow_start or prow_start + prow_span <= srow):
                    has_conflict = True
                    break
            
            if has_conflict:
                break
        
        # Update indicator visibility
        if has_conflict:
            self.conflict_indicator.show()
            self.conflict_indicator.setToolTip("این درس با دروس انتخابی شما تداخل دارد")
        else:
            self.conflict_indicator.hide()
    
    def leaveEvent(self, event):
        """Clear preview when mouse leaves the widget"""
        main_window = self.get_main_window()
        if main_window:
            main_window.clear_preview()
            main_window.last_hover_key = None
            # Hide conflict indicator when mouse leaves
            self.conflict_indicator.hide()
        
        super().leaveEvent(event)


class DraggableCourseList(QtWidgets.QListWidget):
    """Custom list widget that supports drag and drop operations"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

    def startDrag(self, supportedActions):
        """Start drag operation for course items"""
        item = self.currentItem()
        if not item:
            return
        course_key = item.data(QtCore.Qt.UserRole)
        mime = QtCore.QMimeData()
        mime.setText(course_key)
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        pix = QtGui.QPixmap(self.visualItemRect(item).size())
        pix.fill(QtGui.QColor(220, 220, 220))
        drag.setPixmap(pix)
        drag.exec_(QtCore.Qt.MoveAction)


# ---------------------- Schedule Table Widgets ----------------------

class AnimatedCourseWidget(QtWidgets.QFrame):
    """Course cell widget with smooth hover effects"""
    
    def __init__(self, course_key, original_style, has_conflicts=False, parent=None):
        super().__init__(parent)
        self.course_key = course_key
        self.has_conflicts = has_conflicts
        # Handle both string styles and QColor objects
        if isinstance(original_style, QtGui.QColor):
            # Convert QColor to CSS string
            self.original_style = f"background-color: rgba({original_style.red()}, {original_style.green()}, {original_style.blue()}, {original_style.alpha()});"
        else:
            self.original_style = original_style or ""
        
        # Set frame style for visible borders
        self.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Raised)
        self.setLineWidth(2)
        # Only apply inline style if provided (for background color)
        if self.original_style:
            self.setStyleSheet(self.original_style)
        
        # Set object name for QSS styling
        self.setObjectName('course-cell')
        
        # Set properties for styling based on course type and conflicts
        if self.has_conflicts:
            self.setProperty('conflict', True)
        else:
            self.setProperty('conflict', False)
        
    def enterEvent(self, event):
        """Handle mouse enter event for hover effects"""
        # For conflicting courses, show a subtle highlight without red border
        if self.has_conflicts:
            self.setStyleSheet("QWidget#course-cell { background-color: rgba(231, 76, 60, 0.2) !important; } QWidget#course-cell[conflict=\"true\"] { background-color: rgba(231, 76, 60, 0.3) !important; }")
        else:
            # Apply subtle hover styling for non-conflicting courses
            self.setStyleSheet("QWidget#course-cell { background-color: rgba(25, 118, 210, 0.2) !important; }")
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Handle mouse leave event to restore normal styling"""
        # Restore original styling
        if self.original_style:
            self.setStyleSheet(self.original_style)
        else:
            self.setStyleSheet("")
        super().leaveEvent(event)


class ScheduleTable(QtWidgets.QTableWidget):
    """Custom table widget for displaying the weekly schedule"""
    def __init__(self, rows, cols, parent=None):
        super().__init__(rows, cols, parent)
        self.setAcceptDrops(True)
        self.parent_window = parent

    def dragEnterEvent(self, event):
        """Handle drag enter event"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """Handle drag move event"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """Handle drop event"""
        if event.mimeData().hasText():
            course_key = event.mimeData().text()
            self.parent_window.add_course_to_table(course_key, ask_on_conflict=True)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)