#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for Chupolovski Class Planner
University Course Schedule Planner Application
"""

import sys
import os

# Add the app directory to the Python path to enable relative imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from main_window import SchedulerWindow
from data_manager import load_courses_from_json
from config import load_qss_styles, logger


def main():
    """Main function to run the application"""
    app = QApplication(sys.argv)
    app.setApplicationName('Schedule Planner')
    app.setApplicationVersion('2.1')
    app.setOrganizationName('University Schedule Tools')
    
    # Set application icon if available
    try:
        app.setWindowIcon(app.style().standardIcon(app.style().SP_ComputerIcon))
    except:
        pass  # Icon file not found, continue without it
    
    # Load and apply QSS styles from external file
    try:
        qss_styles = load_qss_styles()
        if qss_styles:
            app.setStyleSheet(qss_styles)
            logger.info("Successfully applied QSS styles to application")
        else:
            logger.info("No QSS styles found, using default Qt styling")
    except Exception as e:
        logger.error(f"Failed to apply styles: {e}")
        # Continue without styles rather than crash
    
    # Create and show the main window
    win = SchedulerWindow()
    win.show()
    
    return app.exec_()


if __name__ == '__main__':
    # Error handling for the main application
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Critical error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)