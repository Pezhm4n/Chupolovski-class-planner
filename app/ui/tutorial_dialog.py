#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tutorial dialog for Schedule Planner
Provides an interactive guide for new users
"""

import sys
import os
from PyQt5 import QtWidgets, QtCore, QtGui, uic
from app.core.translator import translator
from app.core.language_manager import language_manager


class TutorialDialog(QtWidgets.QDialog):
    """Interactive tutorial dialog for the Schedule Planner application"""
    
    # Signal emitted when tutorial is completed or skipped
    tutorial_finished = QtCore.pyqtSignal(bool)  # True if finished normally, False if skipped
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._language_connected = False
        self._connect_language_signal()
        
        # Get the directory of this file
        ui_dir = os.path.dirname(os.path.abspath(__file__))
        tutorial_ui_file = os.path.join(ui_dir, 'tutorial_dialog.ui')
        
        # Load UI from external file
        try:
            uic.loadUi(tutorial_ui_file, self)
            
            # Override layout direction from UI file based on current language
            current_lang = language_manager.get_current_language()
            if current_lang == 'fa':
                self.setLayoutDirection(QtCore.Qt.RightToLeft)
            else:
                self.setLayoutDirection(QtCore.Qt.LeftToRight)
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(
                self, 
                translator.t("tutorial.ui_error_title"), 
                translator.t("tutorial.ui_error_not_found", path=tutorial_ui_file)
            )
            sys.exit(1)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, 
                translator.t("tutorial.ui_error_title"), 
                translator.t("tutorial.ui_error_load", error=str(e))
            )
            sys.exit(1)
        
        # Initialize state BEFORE setup_ui
        self.current_page = 0
        self.total_pages = self.stackedWidget.count()
        
        # Set up the dialog
        self.setup_ui()
        self.setup_connections()
        self._apply_translations()
        
        self.update_ui()
    
    def _connect_language_signal(self):
        """Connect to language change signal."""
        if not self._language_connected:
            language_manager.language_changed.connect(self._on_language_changed)
            self._language_connected = True
    
    def _on_language_changed(self, _lang):
        """Handle language change."""
        self._apply_translations()
    
    def _apply_translations(self):
        """Apply translations to UI elements."""
        language_manager.apply_layout_direction(self)
        
        # Get current language to set text direction
        current_lang = language_manager.get_current_language()
        text_direction = QtCore.Qt.RightToLeft if current_lang == 'fa' else QtCore.Qt.LeftToRight
        
        # Recursively set layout direction for all child widgets
        self._set_widgets_direction(self, text_direction)
        
        # Set window title
        self.setWindowTitle(translator.t("tutorial.window_title"))
        
        # Update sidebar title
        if hasattr(self, 'sidebarTitle'):
            self.sidebarTitle.setText(translator.t("tutorial.sidebar_title"))
            self.sidebarTitle.setLayoutDirection(text_direction)
        
        # Update sidebar buttons
        if hasattr(self, 'welcomeButton'):
            self.welcomeButton.setText(f"🏠 {translator.t('tutorial.welcome')}")
            self.welcomeButton.setLayoutDirection(text_direction)
        if hasattr(self, 'interfaceButton'):
            self.interfaceButton.setText(f"🖥️ {translator.t('tutorial.interface')}")
            self.interfaceButton.setLayoutDirection(text_direction)
        if hasattr(self, 'addCourseButton'):
            self.addCourseButton.setText(f"➕ {translator.t('tutorial.add_course')}")
            self.addCourseButton.setLayoutDirection(text_direction)
        if hasattr(self, 'manageCoursesButton'):
            self.manageCoursesButton.setText(f"🔧 {translator.t('tutorial.manage_courses')}")
            self.manageCoursesButton.setLayoutDirection(text_direction)
        if hasattr(self, 'scheduleButton'):
            self.scheduleButton.setText(f"📅 {translator.t('tutorial.schedule')}")
            self.scheduleButton.setLayoutDirection(text_direction)
        if hasattr(self, 'golestanButton'):
            self.golestanButton.setText(f"🌐 {translator.t('tutorial.golestan')}")
            self.golestanButton.setLayoutDirection(text_direction)
        if hasattr(self, 'databaseButton'):
            self.databaseButton.setText(f"💾 {translator.t('tutorial.database')}")
            self.databaseButton.setLayoutDirection(text_direction)
        if hasattr(self, 'studentProfileButton'):
            self.studentProfileButton.setText(f"👤 {translator.t('tutorial.student_profile')}")
            self.studentProfileButton.setLayoutDirection(text_direction)
        if hasattr(self, 'examScheduleButton'):
            self.examScheduleButton.setText(f"📝 {translator.t('tutorial.exam_schedule')}")
            self.examScheduleButton.setLayoutDirection(text_direction)
        if hasattr(self, 'backupButton'):
            self.backupButton.setText(f"🔒 {translator.t('tutorial.backup')}")
            self.backupButton.setLayoutDirection(text_direction)
        if hasattr(self, 'finishButtonSidebar'):
            self.finishButtonSidebar.setText(f"🏁 {translator.t('tutorial.finish')}")
            self.finishButtonSidebar.setLayoutDirection(text_direction)
        
        # Update main title
        if hasattr(self, 'titleLabel'):
            self.titleLabel.setText(translator.t("tutorial.welcome_title"))
            self.titleLabel.setLayoutDirection(text_direction)
        
        # Update page content
        self._update_page_content()
        
        # Ensure stackedWidget and all its pages have correct direction
        if hasattr(self, 'stackedWidget'):
            self.stackedWidget.setLayoutDirection(text_direction)
            # Apply to all pages in stackedWidget
            for i in range(self.stackedWidget.count()):
                page = self.stackedWidget.widget(i)
                if page:
                    self._set_widgets_direction(page, text_direction)
        
        # Update buttons
        if hasattr(self, 'skipButton'):
            self.skipButton.setText(translator.t("tutorial.skip"))
            self.skipButton.setLayoutDirection(text_direction)
        if hasattr(self, 'backButton'):
            self.backButton.setText(translator.t("tutorial.previous"))
            self.backButton.setLayoutDirection(text_direction)
        if hasattr(self, 'nextButton'):
            self.nextButton.setText(translator.t("tutorial.next"))
            self.nextButton.setLayoutDirection(text_direction)
        if hasattr(self, 'finishButton'):
            self.finishButton.setText(translator.t("tutorial.end"))
            self.finishButton.setLayoutDirection(text_direction)
        if hasattr(self, 'dontShowAgainCheckBox'):
            self.dontShowAgainCheckBox.setText(translator.t("tutorial.dont_show_again"))
            self.dontShowAgainCheckBox.setLayoutDirection(text_direction)
    
    def _update_page_content(self):
        """Update content of all tutorial pages."""
        # Get current language to set text direction
        current_lang = language_manager.get_current_language()
        text_direction = QtCore.Qt.RightToLeft if current_lang == 'fa' else QtCore.Qt.LeftToRight
        
        # Set text alignment based on language
        if current_lang == 'fa':
            text_alignment = QtCore.Qt.AlignRight | QtCore.Qt.AlignTop | QtCore.Qt.AlignAbsolute
        else:
            text_alignment = QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop | QtCore.Qt.AlignAbsolute
        
        # Helper function to set text and alignment for labels
        def set_label_text_and_alignment(label, text_key, is_title=False):
            if hasattr(self, label):
                label_widget = getattr(self, label)
                label_widget.setText(translator.t(text_key))
                label_widget.setLayoutDirection(text_direction)
                # Titles should be centered, other text should be aligned based on language
                if is_title:
                    label_widget.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignTop)
                else:
                    label_widget.setAlignment(text_alignment)
        
        # Welcome page
        set_label_text_and_alignment('welcomeText', "tutorial.welcome_text")
        
        # Interface page
        set_label_text_and_alignment('interfaceTitle', "tutorial.interface_title", is_title=True)
        set_label_text_and_alignment('interfaceText', "tutorial.interface_text")
        
        # Add course page
        set_label_text_and_alignment('addCourseTitle', "tutorial.add_course_title", is_title=True)
        set_label_text_and_alignment('addCourseText', "tutorial.add_course_text")
        
        # Manage courses page
        set_label_text_and_alignment('manageCoursesTitle', "tutorial.manage_courses_title", is_title=True)
        set_label_text_and_alignment('manageCoursesText', "tutorial.manage_courses_text")
        
        # Schedule page
        set_label_text_and_alignment('scheduleTitle', "tutorial.schedule_title", is_title=True)
        set_label_text_and_alignment('scheduleText', "tutorial.schedule_text")
        
        # Golestan page
        set_label_text_and_alignment('golestanTitle', "tutorial.golestan_title", is_title=True)
        set_label_text_and_alignment('golestanText', "tutorial.golestan_text")
        
        # Database page
        set_label_text_and_alignment('databaseTitle', "tutorial.database_title", is_title=True)
        set_label_text_and_alignment('databaseText', "tutorial.database_text")
        
        # Student profile page
        set_label_text_and_alignment('studentProfileTitle', "tutorial.student_profile_title", is_title=True)
        set_label_text_and_alignment('studentProfileText', "tutorial.student_profile_text")
        
        # Exam schedule page
        set_label_text_and_alignment('examScheduleTitle', "tutorial.exam_schedule_title", is_title=True)
        set_label_text_and_alignment('examScheduleText', "tutorial.exam_schedule_text")
        
        # Backup page
        set_label_text_and_alignment('backupTitle', "tutorial.backup_title", is_title=True)
        set_label_text_and_alignment('backupText', "tutorial.backup_text")
        
        # Finish page
        set_label_text_and_alignment('finishTitle', "tutorial.finish_title", is_title=True)
        set_label_text_and_alignment('finishText', "tutorial.finish_text")
    
    def _set_widgets_direction(self, widget, direction):
        """Recursively set layout direction for widget and all its children."""
        try:
            if hasattr(widget, 'setLayoutDirection'):
                widget.setLayoutDirection(direction)
        except:
            pass
        
        # Recursively apply to all children (QWidget, QLabel, QTextEdit, etc.)
        for child in widget.findChildren(QtWidgets.QWidget):
            try:
                if hasattr(child, 'setLayoutDirection'):
                    child.setLayoutDirection(direction)
            except:
                pass
        
        # Also apply to QLabel and QTextEdit specifically (they might not be caught by QWidget)
        # Get current language to set text alignment
        current_lang = language_manager.get_current_language()
        if current_lang == 'fa':
            text_alignment = QtCore.Qt.AlignRight | QtCore.Qt.AlignTop | QtCore.Qt.AlignAbsolute
        else:
            text_alignment = QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop | QtCore.Qt.AlignAbsolute
        
        for label in widget.findChildren(QtWidgets.QLabel):
            try:
                label.setLayoutDirection(direction)
                # Set text alignment for labels (but not for title labels which should be centered)
                if not hasattr(label, 'objectName') or not label.objectName() or not label.objectName().endswith('Title'):
                    label.setAlignment(text_alignment)
            except:
                pass
        
        for text_edit in widget.findChildren(QtWidgets.QTextEdit):
            try:
                text_edit.setLayoutDirection(direction)
            except:
                pass
        
        for plain_text in widget.findChildren(QtWidgets.QPlainTextEdit):
            try:
                plain_text.setLayoutDirection(direction)
            except:
                pass
    
    def _t(self, key, **kwargs):
        """Shortcut for translating tutorial strings."""
        return translator.t(f"tutorial.{key}", **kwargs)
        
    def setup_ui(self):
        """Set up the user interface"""
        # Set window properties (title will be set in _apply_translations)
        # Use standard QDialog modal behavior
        self.setModal(True)
        self.resize(900, 650)
        # RTL layout will be set in _apply_translations
        
        # Set up buttons
        self.backButton.setEnabled(False)
        self.finishButton.setVisible(False)
        
        # Set up progress bar
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.update_progress()
        
        # Hide finish button initially
        self.finishButton.setVisible(False)
        
        # Set up sidebar buttons
        self.setup_sidebar()
        
    def setup_sidebar(self):
        """Set up the sidebar navigation"""
        # Create a group for exclusive sidebar buttons
        self.sidebar_group = QtWidgets.QButtonGroup(self)
        self.sidebar_group.setExclusive(True)
        
        # Add buttons to the group
        self.sidebar_group.addButton(self.welcomeButton, 0)
        self.sidebar_group.addButton(self.interfaceButton, 1)
        self.sidebar_group.addButton(self.addCourseButton, 2)
        self.sidebar_group.addButton(self.manageCoursesButton, 3)
        self.sidebar_group.addButton(self.scheduleButton, 4)
        self.sidebar_group.addButton(self.golestanButton, 5)
        self.sidebar_group.addButton(self.databaseButton, 6)
        self.sidebar_group.addButton(self.studentProfileButton, 7)
        self.sidebar_group.addButton(self.examScheduleButton, 8)
        self.sidebar_group.addButton(self.backupButton, 9)
        self.sidebar_group.addButton(self.finishButtonSidebar, 10)
        
        # Set initial checked button
        self.welcomeButton.setChecked(True)
        
    def setup_connections(self):
        """Set up signal/slot connections"""
        self.nextButton.clicked.connect(self.next_page)
        self.backButton.clicked.connect(self.previous_page)
        self.skipButton.clicked.connect(self.skip_tutorial)
        self.finishButton.clicked.connect(self.finish_tutorial)
        
        # Connect sidebar buttons
        self.welcomeButton.clicked.connect(lambda: self.go_to_page(0))
        self.interfaceButton.clicked.connect(lambda: self.go_to_page(1))
        self.addCourseButton.clicked.connect(lambda: self.go_to_page(2))
        self.manageCoursesButton.clicked.connect(lambda: self.go_to_page(3))
        self.scheduleButton.clicked.connect(lambda: self.go_to_page(4))
        self.golestanButton.clicked.connect(lambda: self.go_to_page(5))
        self.databaseButton.clicked.connect(lambda: self.go_to_page(6))
        self.studentProfileButton.clicked.connect(lambda: self.go_to_page(7))
        self.examScheduleButton.clicked.connect(lambda: self.go_to_page(8))
        self.backupButton.clicked.connect(lambda: self.go_to_page(9))
        self.finishButtonSidebar.clicked.connect(lambda: self.go_to_page(10))
        
        # Connect stacked widget change
        self.stackedWidget.currentChanged.connect(self.on_page_changed)
        
    def update_ui(self):
        """Update UI elements based on current state"""
        # Update button states
        self.backButton.setEnabled(self.current_page > 0)
        self.nextButton.setVisible(self.current_page < self.total_pages - 1)
        self.finishButton.setVisible(self.current_page == self.total_pages - 1)
        
        # Update progress
        self.update_progress()
        
        # Update page content with animation
        self.animate_page_change()
        
        # Update sidebar
        self.update_sidebar()
        
    def update_progress(self):
        """Update progress bar"""
        if self.total_pages > 1:
            progress = int((self.current_page / (self.total_pages - 1)) * 100)
            self.progressBar.setValue(progress)
            
    def update_sidebar(self):
        """Update sidebar button states"""
        # Update the checked button in the sidebar
        buttons = [
            self.welcomeButton,
            self.interfaceButton,
            self.addCourseButton,
            self.manageCoursesButton,
            self.scheduleButton,
            self.golestanButton,
            self.databaseButton,
            self.studentProfileButton,
            self.examScheduleButton,
            self.backupButton,
            self.finishButtonSidebar
        ]
        
        # Uncheck all buttons first
        for button in buttons:
            button.setChecked(False)
            
        # Check the current page button
        if 0 <= self.current_page < len(buttons):
            buttons[self.current_page].setChecked(True)
        
    def animate_page_change(self):
        """Animate page change with fade effect"""
        # Create fade animation
        self.fade_animation = QtCore.QPropertyAnimation(
            self.stackedWidget, b"windowOpacity"
        )
        self.fade_animation.setDuration(300)  # 300ms animation
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        
        # Update the page first
        self.stackedWidget.setCurrentIndex(self.current_page)
        
        # Start the animation
        self.fade_animation.start()
        
    def next_page(self):
        """Navigate to the next page"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_ui()
            
    def previous_page(self):
        """Navigate to the previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_ui()
            
    def go_to_page(self, page_index):
        """Go to a specific page"""
        if 0 <= page_index < self.total_pages:
            self.current_page = page_index
            self.update_ui()
            
    def skip_tutorial(self):
        """Skip the tutorial"""
        reply = QtWidgets.QMessageBox.question(
            self, 
            self._t("skip_confirm_title"), 
            self._t("skip_confirm_text"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.tutorial_finished.emit(False)  # False means skipped
            self.accept()
    
    def closeEvent(self, event):
        """Clean up on close."""
        if self._language_connected:
            try:
                language_manager.language_changed.disconnect(self._on_language_changed)
            except (TypeError, RuntimeError):
                pass
            self._language_connected = False
        super().closeEvent(event)
            
    def finish_tutorial(self):
        """Finish the tutorial"""
        # Check if user wants to hide tutorial in the future
        dont_show_again = self.dontShowAgainCheckBox.isChecked()
        
        # Emit signal with the user's preference
        self.tutorial_finished.emit(True)  # True means finished normally
        
        # Close the dialog
        self.accept()
        
    def on_page_changed(self, index):
        """Handle page change"""
        # This is handled by update_ui now
        pass
        
    def keyPressEvent(self, a0):
        """Handle key press events"""
        # Handle keyboard navigation without using Qt constants to avoid linter issues
        if a0:
            # Check for Escape key (key code 16777216)
            if a0.key() == 16777216:
                self.skip_tutorial()
            # Check for Right arrow or Enter/Return (key codes 16777234 and 16777220/16777221)
            elif a0.key() == 16777234 or a0.key() == 16777220 or a0.key() == 16777221:
                if self.nextButton.isVisible() and self.nextButton.isEnabled():
                    self.next_page()
            # Check for Left arrow (key code 16777235)
            elif a0.key() == 16777235:
                if self.backButton.isEnabled():
                    self.previous_page()
            # Check for F1 key (key code 16777264)
            elif a0.key() == 16777264:
                # F1 should reopen the tutorial from the beginning
                self.current_page = 0
                self.update_ui()
            else:
                super().keyPressEvent(a0)


def show_tutorial(parent=None, show_on_startup=True):
    """
    Show the tutorial dialog
    
    Args:
        parent: Parent window
        show_on_startup: Whether this is the first-time startup tutorial
        
    Returns:
        bool: True if tutorial was shown and completed, False otherwise
    """
    if not show_on_startup:
        # Check if user has opted to not show tutorial again
        # This would typically check a settings file or registry
        pass
        
    dialog = TutorialDialog(parent)
    
    # Connect the finished signal
    def on_tutorial_finished(normally):
        # Handle tutorial completion
        if normally:
            print("Tutorial finished normally")
        else:
            print("Tutorial was skipped")
            
    dialog.tutorial_finished.connect(on_tutorial_finished)
    
    # Show the dialog
    result = dialog.exec_()
    return result == QtWidgets.QDialog.Accepted


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    
    # Set application style for better appearance
    app.setStyle("Fusion")
    
    # Show tutorial
    show_tutorial()
    
    sys.exit(app.exec_())