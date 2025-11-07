#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loading Dialog for Golestoon Class Planner
Non-blocking loading dialog with QThread support
"""

from PyQt5 import QtWidgets, QtCore, QtGui
import os
from pathlib import Path


class LoadingDialog(QtWidgets.QDialog):
    """Non-blocking loading dialog with animation support"""
    
    def __init__(self, parent=None, message="در حال بارگذاری..."):
        super().__init__(parent)
        self.setWindowTitle("در حال بارگذاری...")
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setWindowFlags(
            QtCore.Qt.Dialog | 
            QtCore.Qt.WindowTitleHint | 
            QtCore.Qt.CustomizeWindowHint
        )
        
        # Make dialog semi-transparent
        self.setStyleSheet("""
            QDialog {
                background-color: rgba(255, 255, 255, 240);
                border-radius: 10px;
            }
            QLabel {
                color: #2c3e50;
                font-size: 14px;
                font-weight: bold;
                font-family: 'IRANSans UI', 'Shabnam', 'Tahoma', sans-serif;
            }
        """)
        
        # Create layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Try to load GIF animation
        self.movie = None
        gif_path = None
        
        # Check for loading.gif in assets/images
        assets_dir = Path(__file__).parent.parent / 'assets' / 'images'
        if assets_dir.exists():
            gif_path = assets_dir / 'loading.gif'
            if not gif_path.exists():
                gif_path = None
        
        if gif_path and gif_path.exists():
            try:
                self.movie = QtGui.QMovie(str(gif_path))
                self.movie.setScaledSize(QtCore.QSize(64, 64))
                movie_label = QtWidgets.QLabel()
                movie_label.setMovie(self.movie)
                movie_label.setAlignment(QtCore.Qt.AlignCenter)
                layout.addWidget(movie_label)
                self.movie.start()
            except Exception:
                self.movie = None
        
        # If no GIF, use progress bar
        if self.movie is None:
            self.progress = QtWidgets.QProgressBar()
            self.progress.setRange(0, 0)  # Indeterminate progress
            self.progress.setMinimumHeight(8)
            self.progress.setTextVisible(False)
            layout.addWidget(self.progress)
        
        # Message label
        self.message_label = QtWidgets.QLabel(message)
        self.message_label.setAlignment(QtCore.Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)
        
        # Set fixed size
        self.setFixedSize(350, 150)
        
        # Center on parent
        if parent:
            parent_rect = parent.geometry()
            self.move(
                parent_rect.x() + (parent_rect.width() - self.width()) // 2,
                parent_rect.y() + (parent_rect.height() - self.height()) // 2
            )
    
    def set_message(self, message):
        """Update loading message"""
        self.message_label.setText(message)
        QtWidgets.QApplication.processEvents()
    
    def closeEvent(self, event):
        """Stop animation when closing"""
        if self.movie:
            self.movie.stop()
        super().closeEvent(event)


class GolestanWorker(QtCore.QThread):
    """Worker thread for Golestan operations"""
    
    finished = QtCore.pyqtSignal(object)  # Emits result or exception
    progress = QtCore.pyqtSignal(str)  # Emits progress message
    
    def __init__(self, operation_type, **kwargs):
        super().__init__()
        self.operation_type = operation_type
        self.kwargs = kwargs
        self.result = None
        self.error = None
    
    def run(self):
        """Execute the operation in background thread"""
        try:
            if self.operation_type == 'fetch_courses':
                self.progress.emit("در حال اتصال به سامانه گلستان...")
                from app.core.golestan_integration import update_courses_from_golestan
                username = self.kwargs.get('username')
                password = self.kwargs.get('password')
                
                self.progress.emit("در حال دریافت لیست دروس...")
                update_courses_from_golestan(username=username, password=password)
                self.result = True
                
            elif self.operation_type == 'get_student_record':
                self.progress.emit("در حال اتصال به سامانه گلستان...")
                from app.scrapers.requests_scraper.fetch_data import get_student_record
                username = self.kwargs.get('username')
                password = self.kwargs.get('password')
                db = self.kwargs.get('db')
                
                self.progress.emit("در حال دریافت اطلاعات دانشجو...")
                student = get_student_record(username=username, password=password, db=db)
                self.result = student
                
            elif self.operation_type == 'check_database':
                # Quick check if data exists in database
                db = self.kwargs.get('db')
                if db:
                    # Check if courses exist
                    try:
                        count = db.get_course_count()
                        self.result = count > 0
                    except:
                        self.result = False
                else:
                    self.result = False
                    
        except Exception as e:
            self.error = e
            from app.core.logger import setup_logging
            logger = setup_logging()
            logger.error(f"Error in GolestanWorker: {e}")
        finally:
            # Emit finished signal with result or error
            if self.error:
                self.finished.emit(self.error)
            else:
                self.finished.emit(self.result)

