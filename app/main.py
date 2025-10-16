#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for Golestoon Class Planner
University Course Schedule Planner Application
"""

import sys
import os

# Add the current directory to Python path for direct execution
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Handle both direct execution and module execution
# First, try relative imports (for python -m app.main)
try:
    from .__version__ import __version__
    from .ui.main_window import SchedulerWindow
    from .core.data_manager import load_courses_from_json
    from .core.config import load_qss_styles
    from .core.logger import setup_logging
    USING_RELATIVE_IMPORTS = True
except (ImportError, ValueError):
    # Fall back to absolute imports (for direct script execution)
    try:
        from __version__ import __version__
        from ui.main_window import SchedulerWindow
        from core.data_manager import load_courses_from_json
        from core.config import load_qss_styles
        from core.logger import setup_logging
        USING_RELATIVE_IMPORTS = False
    except ImportError:
        # If that fails, try adjusting the path and importing again
        parent_dir = os.path.dirname(current_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        try:
            from app.__version__ import __version__
            from app.ui.main_window import SchedulerWindow
            from app.core.data_manager import load_courses_from_json
            from app.core.config import load_qss_styles
            from app.core.logger import setup_logging
            USING_RELATIVE_IMPORTS = False
        except ImportError:
            # Final fallback - import directly from the app directory
            app_dir = os.path.join(current_dir, 'app')
            if app_dir not in sys.path:
                sys.path.insert(0, app_dir)
            
            from __version__ import __version__
            from ui.main_window import SchedulerWindow
            from core.data_manager import load_courses_from_json
            from core.config import load_qss_styles
            from core.logger import setup_logging
            USING_RELATIVE_IMPORTS = False

# Import the CourseDatabase
from app.data.courses_db import CourseDatabase
from app.core.data_manager import set_course_database

logger = setup_logging()

from PyQt5 import QtCore

QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)

def main():
    """Main function to run the application"""
    # Import QApplication here to avoid issues with early imports
    from PyQt5.QtWidgets import QApplication
    from PyQt5 import QtCore

    app = QApplication(sys.argv)
    app.setApplicationName('Golestoon Class Planner')
    app.setApplicationVersion(__version__)
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
    
    # Create and show the main window, passing the database instance
    win = SchedulerWindow(db=db)
    win.setWindowTitle('Golestoon Class Planner')
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