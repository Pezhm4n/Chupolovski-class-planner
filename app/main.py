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
    from app.__version__ import __version__
    from app.ui.main_window import SchedulerWindow
    from app.core.data_manager import load_courses_from_json
    from app.core.config import load_qss_styles
    from app.core.logger import setup_logging
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


def main():
    """Main function to run the application"""
    # Import QApplication here to avoid issues with early imports
    from PyQt5.QtWidgets import QApplication
    from PyQt5 import QtCore
    from PyQt5.QtCore import Qt
    from app.data.courses_db import CourseDatabase
    from app.core.language_manager import language_manager
    from app.core.translator import translator

    logger = setup_logging()
    logger.info("=== Application startup begins ===")
    
    import time
    main_start_time = time.time()
    
    # Set attributes for high DPI scaling and OpenGL contexts
    try:
        # These attributes may not be available in all PyQt versions
        # Using try/except to handle cases where they don't exist
        aa_share_opengl = getattr(Qt, 'AA_ShareOpenGLContexts', None)
        aa_enable_high_dpi = getattr(Qt, 'AA_EnableHighDpiScaling', None)
        
        if aa_share_opengl is not None:
            QApplication.setAttribute(aa_share_opengl)
        if aa_enable_high_dpi is not None:
            QApplication.setAttribute(aa_enable_high_dpi)
    except (AttributeError, TypeError):
        # Fallback for older PyQt versions
        pass

    db_init_start = time.time()
    db = CourseDatabase()
    db_init_time = time.time() - db_init_start
    if db_init_time > 0.1:
        logger.info(f"Database initialized in {db_init_time:.2f}s")
    
    app = QApplication(sys.argv)
    app.setApplicationName('Golestoon Class Planner')
    app.setApplicationVersion(__version__)
    app.setOrganizationName('University Schedule Tools')
    
    try:
        style = app.style()
        if style:
            icon_attr = getattr(style, 'SP_ComputerIcon', None)
            if icon_attr is not None:
                icon = style.standardIcon(icon_attr)
                if icon:
                    app.setWindowIcon(icon)
    except:
        pass
    
    saved_lang = language_manager.get_current_language()
    logger.info(f"Loading language preference: {saved_lang}")
    
    if saved_lang not in ['fa', 'en']:
        logger.warning(f"Invalid language '{saved_lang}', defaulting to 'fa'")
        saved_lang = 'fa'
        language_manager.set_language('fa')
    
    translator.load_translations(saved_lang)
    
    if saved_lang == 'fa':
        direction = getattr(Qt, 'RightToLeft', 1)
        app.setLayoutDirection(direction)
        logger.info(f"Set application layout direction to RTL (language: {saved_lang})")
    else:
        direction = getattr(Qt, 'LeftToRight', 0)
        app.setLayoutDirection(direction)
        logger.info(f"Set application layout direction to LTR (language: {saved_lang})")
    
    actual_direction = app.layoutDirection()
    expected_direction_name = "RTL" if saved_lang == 'fa' else "LTR"
    actual_direction_name = "RTL" if actual_direction == getattr(Qt, 'RightToLeft', 1) else "LTR"
    if actual_direction_name != expected_direction_name:
        logger.error(f"Layout direction mismatch! Expected {expected_direction_name}, but got {actual_direction_name}")
        app.setLayoutDirection(direction)
        logger.info(f"Force-set layout direction to {expected_direction_name}")
    
    language_manager.apply_font(app)
    
    try:
        qss_styles = load_qss_styles()
        if qss_styles:
            app.setStyleSheet(qss_styles)
            logger.info("Successfully applied QSS styles to application")
        else:
            logger.info("No QSS styles found, using default Qt styling")
    except Exception as e:
        logger.error(f"Failed to apply styles: {e}")
    
    window_create_start = time.time()
    win = SchedulerWindow(db=db)
    win.setWindowTitle('Golestoon Class Planner')
    win.show()
    window_create_time = time.time() - window_create_start
    logger.info(f"Main window created and shown in {window_create_time:.2f}s")
    
    total_startup_time = time.time() - main_start_time
    logger.info(f"=== Application startup completed in {total_startup_time:.2f}s ===")
    
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