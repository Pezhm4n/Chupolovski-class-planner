import sys
import os

from PyQt5 import QtWidgets, QtGui, QtCore

# Import from core modules
from ..core.config import COURSES, DAYS, EXTENDED_TIME_SLOTS
from ..core.logger import setup_logging

logger = setup_logging()


class CourseListWidget(QtWidgets.QWidget):
    """Custom widget for course list items with delete functionality"""
    def __init__(self, course_key, course_info, parent_list, parent=None):
        super().__init__(parent)
        self.course_key = course_key
        self.course_info = course_info
        self.parent_list = parent_list
        self.setup_ui()
        
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)  # Increased margins for better spacing
        layout.setSpacing(4)  # Add spacing between elements
        
        # Enable mouse tracking for hover events
        self.setMouseTracking(True)
        
        # Enable context menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Main course info layout
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.setSpacing(6)
        
        # Course info label with improved styling
        display = f"{self.course_info['name']} — {self.course_info['code']} — {self.course_info.get('instructor', 'نامشخص')}"
        self.course_label = QtWidgets.QLabel(display)
        self.course_label.setWordWrap(True)
        self.course_label.setMinimumHeight(45)  # Increased minimum height for proper display
        self.course_label.setObjectName("course_list_label")  # For QSS styling
        # Enable mouse tracking on the label too
        self.course_label.setMouseTracking(True)
        main_layout.addWidget(self.course_label, 1)
        
        # Conflict indicator label (hidden by default) with enhanced styling
        # Positioned absolutely on hover, not taking up permanent space
        self.conflict_indicator = QtWidgets.QLabel("⚠")
        self.conflict_indicator.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 16px;")
        self.conflict_indicator.hide()
        self.conflict_indicator.setParent(self)
        self.conflict_indicator.setGeometry(self.width() - 25, 2, 16, 16)  # Position at top-right
        self.conflict_indicator.setToolTip("این درس با دروس انتخابی شما تداخل دارد")
        
        # Button container with improved spacing
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(6)  # Increased spacing between buttons
        button_layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        
        # Edit button (pencil icon) - larger and more visible
        self.edit_btn = QtWidgets.QPushButton("✏️")
        self.edit_btn.setObjectName("edit_btn")
        self.edit_btn.setFixedSize(24, 24)  # Increased size from 18x18 to 24x24
        self.edit_btn.setToolTip(f"ویرایش درس {self.course_info['name']}")
        self.edit_btn.clicked.connect(self.edit_course)
        button_layout.addWidget(self.edit_btn)
        
        # Delete button (only for custom courses) - larger and more visible
        if self.is_custom_course():
            self.delete_btn = QtWidgets.QPushButton("✕")
            self.delete_btn.setObjectName("delete_btn")
            self.delete_btn.setFixedSize(24, 24)  # Increased size from 18x18 to 24x24
            self.delete_btn.setToolTip(f"حذف درس {self.course_info['name']}")
            self.delete_btn.clicked.connect(self.delete_course)
            button_layout.addWidget(self.delete_btn)
            
        main_layout.addLayout(button_layout)
        layout.addLayout(main_layout)
        
        # Additional course information from Golestan data
        self.additional_info_widget = self.create_additional_info_widget()
        self.additional_info_widget.hide()
        layout.addWidget(self.additional_info_widget)
            
    def create_additional_info_widget(self):
        """Create widget to display additional Golestan course information"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(2)
        
        # Capacity information
        capacity = self.course_info.get('capacity', '')
        if capacity:
            capacity_label = QtWidgets.QLabel(f"ظرفیت: {capacity}")
            capacity_label.setStyleSheet("font-size: 11px; color: #555;")
            layout.addWidget(capacity_label)
        
        # Gender restriction information
        gender_restriction = self.course_info.get('gender_restriction', '')
        if gender_restriction and gender_restriction != 'مختلط':
            gender_label = QtWidgets.QLabel(f"محدودیت جنسیتی: {gender_restriction}")
            gender_label.setStyleSheet("font-size: 11px; color: #555;")
            layout.addWidget(gender_label)
        
        # Location information
        location = self.course_info.get('location', '')
        if location:
            location_label = QtWidgets.QLabel(f"مکان: {location}")
            location_label.setStyleSheet("font-size: 11px; color: #555;")
            layout.addWidget(location_label)
        
        # Enrollment conditions
        enrollment_conditions = self.course_info.get('enrollment_conditions', '')
        if enrollment_conditions:
            conditions_label = QtWidgets.QLabel(f"شرایط اخذ: {enrollment_conditions}")
            conditions_label.setStyleSheet("font-size: 11px; color: #555;")
            conditions_label.setWordWrap(True)
            layout.addWidget(conditions_label)
        
        # Availability status
        is_available = self.course_info.get('is_available', True)
        if not is_available:
            status_label = QtWidgets.QLabel("وضعیت: پر شده")
            status_label.setStyleSheet("font-size: 11px; color: #e74c3c; font-weight: bold;")
            layout.addWidget(status_label)
        
        return widget
        
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
            from ..core.data_manager import save_courses_to_json
            save_courses_to_json()
            
            # Remove from user_data
            user_data = main_window.user_data
            custom_courses = user_data.get('custom_courses', [])
            user_data['custom_courses'] = [c for c in custom_courses 
                                          if c.get('code') != self.course_info.get('code')]
            
            # Save updated user data
            from ..core.data_manager import save_user_data
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
    
    def show_context_menu(self, position):
        """Show context menu for course list items"""
        main_window = self.get_main_window()
        if not main_window:
            return
            
        menu = QtWidgets.QMenu()
        add_to_auto_action = menu.addAction("اضافه به لیست برنامه‌ریزی خودکار")
        action = menu.exec_(self.mapToGlobal(position))
        
        if action == add_to_auto_action:
            self.add_to_auto_schedule_list(main_window)
    
    def add_to_auto_schedule_list(self, main_window):
        """Add this course to the auto-schedule list"""
        try:
            course = COURSES.get(self.course_key)
            if not course:
                return
                
            # Check if item already exists in auto_select_list
            exists = False
            for j in range(main_window.auto_select_list.count()):
                if main_window.auto_select_list.item(j).data(QtCore.Qt.UserRole) == self.course_key:
                    exists = True
                    break
            
            if not exists:
                # Create display text with position-based priority
                course_name = course.get('name', 'نامشخص')
                position = main_window.auto_select_list.count() + 1
                display = f"({position}) {course_name}"
                
                # Create new item with same data
                new_item = QtWidgets.QListWidgetItem(display)
                new_item.setData(QtCore.Qt.UserRole, self.course_key)
                # Set position as priority (first item = priority 1)
                new_item.setData(QtCore.Qt.UserRole + 1, position)
                main_window.auto_select_list.addItem(new_item)
                
                # Show confirmation
                QtWidgets.QMessageBox.information(
                    main_window, 'اضافه به لیست', 
                    f'درس "{course_name}" به لیست برنامه‌ریزی خودکار اضافه شد.'
                )
            else:
                course = COURSES.get(self.course_key)
                course_name = course.get('name', 'نامشخص') if course else 'نامشخص'
                QtWidgets.QMessageBox.information(
                    main_window, 'اضافه به لیست', 
                    f'درس "{course_name}" قبلاً در لیست برنامه‌ریزی خودکار وجود دارد.'
                )
        except Exception as e:
            logger.error(f"Error adding to auto schedule list: {e}")
            
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
                # Handle both single and dual course entries
                if info.get('type') == 'dual':
                    # For dual courses, check if either course matches
                    if course_key in info.get('courses', []):
                        continue
                else:
                    # For single courses, check directly
                    if info.get('course') == course_key:
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
    
    def enterEvent(self, event):
        """Show additional information when mouse enters the widget with safety wrapper"""
        logger.info("overlay_hover_enter: Course list widget hover enter")
        try:
            # Safety check for parent
            if not hasattr(self, 'parent_list') or not self.parent_list:
                logger.warning("overlay_hover_parent_missing: Parent list not available during hover enter")
                super().enterEvent(event)
                return
                
            self.additional_info_widget.show()
        except Exception as e:
            logger.warning(f"overlay_hover_enter_error: Error in enterEvent for CourseListWidgetItem: {e}")
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide additional information when mouse leaves the widget with safety wrapper"""
        logger.info("overlay_hover_leave: Course list widget hover leave")
        try:
            # Safety check for parent
            if not hasattr(self, 'parent_list') or not self.parent_list:
                logger.warning("overlay_hover_parent_missing: Parent list not available during hover leave")
                super().leaveEvent(event)
                return
                
            self.additional_info_widget.hide()
            main_window = self.get_main_window()
            if main_window:
                main_window.clear_preview()
                main_window.last_hover_key = None
                # Hide conflict indicator when mouse leaves
                self.conflict_indicator.hide()
        except Exception as e:
            logger.warning(f"overlay_hover_leave_error: Error in leaveEvent for CourseListWidgetItem: {e}")
        super().leaveEvent(event)

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
        
        # Enable context menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, position):
        """Show context menu for course cell items"""
        # Get main window reference
        main_window = self.parent().parent()
        while main_window and not isinstance(main_window, QtWidgets.QMainWindow):
            main_window = main_window.parent()
            
        if not main_window:
            return
            
        menu = QtWidgets.QMenu()
        add_to_auto_action = menu.addAction("اضافه به لیست برنامه‌ریزی خودکار")
        action = menu.exec_(self.mapToGlobal(position))
        
        if action == add_to_auto_action:
            self.add_to_auto_schedule_list(main_window)
    
    def add_to_auto_schedule_list(self, main_window):
        """Add this course to the auto-schedule list"""
        try:
            course = COURSES.get(self.course_key)
            if not course:
                return
                
            # Check if item already exists in auto_select_list
            exists = False
            for j in range(main_window.auto_select_list.count()):
                if main_window.auto_select_list.item(j).data(QtCore.Qt.UserRole) == self.course_key:
                    exists = True
                    break
            
            if not exists:
                # Create display text with position-based priority
                course_name = course.get('name', 'نامشخص')
                position = main_window.auto_select_list.count() + 1
                display = f"({position}) {course_name}"
                
                # Create new item with same data
                new_item = QtWidgets.QListWidgetItem(display)
                new_item.setData(QtCore.Qt.UserRole, self.course_key)
                # Set position as priority (first item = priority 1)
                new_item.setData(QtCore.Qt.UserRole + 1, position)
                main_window.auto_select_list.addItem(new_item)
                
                # Show confirmation
                QtWidgets.QMessageBox.information(
                    main_window, 'اضافه به لیست', 
                    f'درس "{course_name}" به لیست برنامه‌ریزی خودکار اضافه شد.'
                )
            else:
                course = COURSES.get(self.course_key)
                course_name = course.get('name', 'نامشخص') if course else 'نامشخص'
                QtWidgets.QMessageBox.information(
                    main_window, 'اضافه به لیست', 
                    f'درس "{course_name}" قبلاً در لیست برنامه‌ریزی خودکار وجود دارد.'
                )
        except Exception as e:
            logger.error(f"Error adding to auto schedule list: {e}")
            
    def enterEvent(self, event):
        """Handle mouse enter event for hover effects with safety wrapper"""
        logger.info("overlay_hover_enter: Animated course widget hover enter")
        try:
            # Safety check for parent
            if not hasattr(self, 'parent') or not self.parent():
                logger.warning("overlay_hover_parent_missing: Parent not available during hover enter")
                super().enterEvent(event)
                return
                
            # Additional safety check for deleted widget
            import sip
            if sip.isdeleted(self):
                logger.warning("overlay_hover_widget_deleted: Widget is deleted during hover enter")
                return
                
            # For conflicting courses, show a subtle highlight without red border
            if self.has_conflicts:
                self.setStyleSheet("QWidget#course-cell { background-color: rgba(231, 76, 60, 0.2) !important; } QWidget#course-cell[conflict=\"true\"] { background-color: rgba(231, 76, 60, 0.3) !important; }")
            else:
                # Apply subtle hover styling for non-conflicting courses
                self.setStyleSheet("QWidget#course-cell { background-color: rgba(25, 118, 210, 0.2) !important; }")
        except Exception as e:
            logger.warning(f"overlay_hover_enter_error: Error in enterEvent for AnimatedCourseWidget: {e}")
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Handle mouse leave event to restore normal styling with safety wrapper"""
        logger.info("overlay_hover_leave: Animated course widget hover leave")
        try:
            # Safety check for parent
            if not hasattr(self, 'parent') or not self.parent():
                logger.warning("overlay_hover_parent_missing: Parent not available during hover leave")
                super().leaveEvent(event)
                return
                
            # Additional safety check for deleted widget
            import sip
            if sip.isdeleted(self):
                logger.warning("overlay_hover_widget_deleted: Widget is deleted during hover leave")
                return
                
            # Restore original styling
            if self.original_style:
                self.setStyleSheet(self.original_style)
            else:
                self.setStyleSheet("")
        except Exception as e:
            logger.warning(f"overlay_hover_leave_error: Error in leaveEvent for AnimatedCourseWidget: {e}")
        super().leaveEvent(event)
