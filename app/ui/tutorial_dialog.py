#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tutorial dialog for Schedule Planner
Provides an interactive guide for new users
"""

import sys
import os
from PyQt5 import QtWidgets, QtCore, QtGui, uic


class TutorialDialog(QtWidgets.QDialog):
    """Interactive tutorial dialog for the Schedule Planner application"""
    
    # Signal emitted when tutorial is completed or skipped
    tutorial_finished = QtCore.pyqtSignal(bool)  # True if finished normally, False if skipped
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Get the directory of this file
        ui_dir = os.path.dirname(os.path.abspath(__file__))
        tutorial_ui_file = os.path.join(ui_dir, 'tutorial_dialog.ui')
        
        # Load UI from external file
        try:
            uic.loadUi(tutorial_ui_file, self)
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, "خطا", f"فایل UI یافت نشد: {tutorial_ui_file}")
            sys.exit(1)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "خطا", f"خطا در بارگذاری UI: {str(e)}")
            sys.exit(1)
        
        # Initialize state BEFORE setup_ui
        self.current_page = 0
        self.total_pages = self.stackedWidget.count()
        
        # Set up the dialog
        self.setup_ui()
        self.setup_connections()
        
        self.update_ui()
        
    def setup_ui(self):
        """Set up the user interface"""
        # Set window properties
        self.setWindowTitle("راهنمای گلستون کلاس پلنر")
        # Use standard QDialog modal behavior
        self.setModal(True)
        self.resize(900, 650)
        # RTL layout is set in the UI file
        
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
            'رد کردن آموزش', 
            'آیا مطمئن هستید که می‌خواهید آموزش را رد کنید؟',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.tutorial_finished.emit(False)  # False means skipped
            self.accept()
            
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