#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Student Profile Dialog for Golestoon Class Planner.

This module provides a dialog for displaying student academic information
including photo, basic info, summary stats, and academic records.
"""

import sys
import os
from decimal import Decimal
from PyQt5.QtWidgets import (QDialog, QApplication, QVBoxLayout, QHBoxLayout,
                             QLabel, QTreeWidget, QTreeWidgetItem, QTableWidget,
                             QTableWidgetItem, QSplitter, QFrame, QScrollArea,
                             QDialogButtonBox, QWidget, QFormLayout, QSpinBox,
                             QDoubleSpinBox, QPushButton, QCalendarWidget, QTabWidget,
                             QLineEdit, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSizePolicy)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QDate, QSize
from PyQt5.QtGui import QPixmap, QFont, QColor, QPalette, QIcon, QPainter, QPainterPath
from PyQt5 import uic

from app.scrapers.requests_scraper.models import Student, SemesterRecord, CourseEnrollment
from app.data.student_db import StudentDatabase
from app.core.credentials import load_local_credentials
from app.ui.credentials_dialog import get_golestan_credentials
from app.scrapers.requests_scraper.fetch_data import get_student_record


class CircularImageLabel(QLabel):
    """Custom label for displaying circular images."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap_data = None

    def setPixmapData(self, pixmap):
        """Set the pixmap to display."""
        self.pixmap_data = pixmap
        self.update()

    def paintEvent(self, event):
        """Paint the circular image."""
        if self.pixmap_data is None:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        path = QPainterPath()
        path.addEllipse(0, 0, self.width(), self.height())
        painter.setClipPath(path)

        scaled_pixmap = self.pixmap_data.scaled(
            self.size(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )

        x = (self.width() - scaled_pixmap.width()) // 2
        y = (self.height() - scaled_pixmap.height()) // 2

        painter.drawPixmap(x, y, scaled_pixmap)


class StudentProfileDialog(QDialog):
    """Dialog for displaying student academic profile information."""

    # UI Standards for better readability
    SPACING_SMALL = 6
    SPACING_MEDIUM = 12
    SPACING_LARGE = 18

    PADDING_SMALL = 8
    PADDING_MEDIUM = 12
    PADDING_LARGE = 16

    FONT_SIZE_SMALL = 9
    FONT_SIZE_NORMAL = 11
    FONT_SIZE_MEDIUM = 12
    FONT_SIZE_LARGE = 14
    FONT_SIZE_XLARGE = 16
    FONT_SIZE_XXLARGE = 18

    BUTTON_HEIGHT = 32
    INPUT_HEIGHT = 30
    CARD_MIN_HEIGHT = 120
    CHART_HEIGHT = 500

    PHOTO_SIZE = 120
    ICON_SIZE_SMALL = 14
    ICON_SIZE_MEDIUM = 18
    ICON_SIZE_LARGE = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.student = None
        self.is_dark_mode = False

        # UI Standards for better readability
        self.SPACING_SMALL = 8
        self.SPACING_MEDIUM = 14
        self.SPACING_LARGE = 20

        self.PADDING_SMALL = 10
        self.PADDING_MEDIUM = 14
        self.PADDING_LARGE = 18

        self.FONT_SIZE_SMALL = 9
        self.FONT_SIZE_NORMAL = 11
        self.FONT_SIZE_MEDIUM = 12
        self.FONT_SIZE_LARGE = 14
        self.FONT_SIZE_XLARGE = 16
        self.FONT_SIZE_XXLARGE = 18

        self.BUTTON_HEIGHT = 32
        self.INPUT_HEIGHT = 30
        self.CARD_MIN_HEIGHT = 200
        self.CHART_HEIGHT = 500

        self.PHOTO_SIZE = 120
        self.ICON_SIZE_SMALL = 14
        self.ICON_SIZE_MEDIUM = 18
        self.ICON_SIZE_LARGE = 24

        # Get the directory of this file
        ui_dir = os.path.dirname(os.path.abspath(__file__))
        student_profile_ui_file = os.path.join(ui_dir, 'student_profile.ui')

        # Load UI from external file
        try:
            uic.loadUi(student_profile_ui_file, self)
        except FileNotFoundError:
            print(f"Error: UI file not found: {student_profile_ui_file}")
            sys.exit(1)
        except Exception as e:
            print(f"Error loading UI: {str(e)}")
            sys.exit(1)

        # Initialize UI components
        self.init_ui()

        # Load student data
        self.load_student_data()

    def init_ui(self):
        """Initialize the user interface components."""
        self.setWindowTitle("پروفایل دانشجو - Golestoon Class Planner")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)
        self.setMaximumSize(1600, 1200)
        self.setLayoutDirection(Qt.RightToLeft)
        
        # Set window flags to enable native window controls
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)

        # Apply global dark theme stylesheet
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #ffffff;
            }
        """)

        # Style the header frame
        self.ui_headerFrame.setStyleSheet("""
            QFrame {
                background-color: #2d2d44;
                border: none;
                border-bottom: 1px solid #4a4a6a;
            }
        """)

        # Style the title label
        self.ui_titleLabel.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
        """)

        # Style the header card with distinct color
        self.profile_studentInfoCard.setStyleSheet("""
            QFrame {
                background-color: #2d2d44;
                border: 2px solid #4a4a6a;
                border-radius: 4px;
            }
        """)

        # Style the footer frame
        self.ui_footerFrame.setStyleSheet("""
            QFrame {
                background-color: #2d2d44;
                border: none;
            }
        """)

        # Style the button box
        self.ui_buttonBox.setStyleSheet("""
            QDialogButtonBox {
                color: #ffffff;
            }
            QPushButton {
                background-color: #4a4a6a;
                color: #ffffff;
                border: 1px solid #5a5a7a;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a5a7a;
            }
            QPushButton:pressed {
                background-color: #3a3a5a;
            }
        """)

        # Style the scroll area
        self.ui_contentScrollArea.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2d2d44;
                width: 15px;
                border-radius: 7px;
                margin: 15px 0 15px 0;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a6a;
                border-radius: 7px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5a5a7a;
            }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {
                height: 0px;
            }
            QScrollBar::sub-page:vertical, QScrollBar::add-page:vertical {
                background: none;
            }
        """)

        # Table styling with dark theme and alternating rows
        self.section_coursesTableWidget.setStyleSheet("""
            QTableWidget {
                background-color: #2a2a3e;
                alternate-background-color: #25253a;
                border: 2px solid #4a4a6a;
                border-radius: 6px;
                gridline-color: #4a4a6a;
                font-size: 11px;
                selection-background-color: #5a5a7a;
                selection-color: #ffffff;
                outline: none;
                color: #ffffff;
            }
            QTableWidget::item {
                padding: 8px;
                border: 1px solid #4a4a6a;
            }
            QTableWidget::item:hover {
                background-color: #3a3a5a;
            }
            QHeaderView::section {
                background-color: #3a3a5a;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #5a5a7a;
                border-radius: 4px;
                text-align: center;
                min-height: 40px;
            }
            QHeaderView::section:first {
                border-top-left-radius: 6px;
            }
            QHeaderView::section:last {
                border-top-right-radius: 6px;
            }
        """)

        # Tree widget styling with dark theme
        self.section_semestersTreeWidget.setStyleSheet("""
            QTreeWidget {
                background-color: #2a2a3e;
                alternate-background-color: #25253a;
                border: 2px solid #4a4a6a;
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
                outline: none;
                color: #ffffff;
                selection-background-color: #5a5a7a;
                selection-color: #ffffff;
            }
            QTreeWidget::item {
                padding: 6px;
                border-radius: 3px;
                border: 1px solid transparent;
            }
            QTreeWidget::item:selected {
                background-color: #5a5a7a;
                color: #ffffff;
                border: 1px solid #7a7a9a;
            }
            QTreeWidget::item:hover {
                background-color: #3a3a5a;
            }
            QHeaderView::section {
                background-color: #3a3a5a;  
                color: #ffffff;
                border: 2px solid #5a5a7a;  
                font-weight: bold;
                font-size: 12px;
                border-radius: 4px;
                text-align: center;
                min-height: 40px;
            }
        """)
        
        # Set minimum height for better visibility
        self.section_semestersTreeWidget.setMinimumHeight(350)

        # Style the semesters section frame with dark background
        self.section_semestersFrame.setStyleSheet("""
            QFrame {
                background-color: #2d2d44;
                border: 2px solid #4a4a6a;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        
        # Set minimum and maximum height for the semesters section frame
        self.section_semestersFrame.setMinimumHeight(400)
        self.section_semestersFrame.setMaximumHeight(800)
        
        # Make the frame resizable
        self.section_semestersFrame.setFrameShape(QFrame.StyledPanel)

        # Style the courses section frame with dark background
        self.section_coursesFrame.setStyleSheet("""
            QFrame {
                background-color: #2d2d44;
                border: 2px solid #4a4a6a;
                border-radius: 12px;
                padding: 12px;
            }
        """)

        # Style section headers
        self.section_semestersTitleLabel.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        
        self.section_coursesTitleLabel.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        
        # Set minimum height for courses section
        self.section_coursesFrame.setMinimumHeight(400)
        
        # Make splitter handle more visible
        self.section_contentSplitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #4a4a6a;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #5a5a7a;
            }
        """)

    def toggle_maximize(self):
        """Toggle between maximized and normal window state."""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def display_student_data(self):
        """Display student data in the UI."""
        if not self.student:
            return

        # Display student photo
        self.display_student_photo()

        # Display basic info with proper hierarchy
        self.display_student_info()

        # Add statistics cards
        self.add_statistics_cards()

        # Add GPA trend chart
        self.add_gpa_trend_chart()

        # Add GPA predictor (dark themed)
        self.add_gpa_predictor()

        # Connect semester selection if we have data
        if self.student and self.student.semesters:
            self.section_semestersTreeWidget.currentItemChanged.connect(self.on_semester_selected)

        # Populate semesters tree
        self.populate_semesters_tree()
        
        # Connect semester selection after populating
        self.section_semestersTreeWidget.currentItemChanged.connect(self.on_semester_selected)
        
        # Add minimize capability to semesters section
        self.add_semester_section_minimize()

    def display_student_photo(self):
        """Display student photo with professional circular design."""
        # Create container for photo
        photo_container = QWidget()
        photo_container.setFixedSize(self.PHOTO_SIZE + 16, self.PHOTO_SIZE + 16)

        # Create circular label
        circular_label = CircularImageLabel(photo_container)
        circular_label.setFixedSize(self.PHOTO_SIZE, self.PHOTO_SIZE)
        circular_label.move(8, 8)

        # Style the container with 4px blue border
        photo_container.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border: 2px solid #11111;
                border-radius: {(self.PHOTO_SIZE + 16) // 2}px;
            }}
        """)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))
        photo_container.setGraphicsEffect(shadow)

        if self.student.image_b64:
            try:
                import base64
                image_data = base64.b64decode(self.student.image_b64)
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
                circular_label.setPixmapData(pixmap)
            except Exception as e:
                print(f"Error loading student photo: {e}")
                self.set_placeholder_photo(circular_label)
        else:
            self.set_placeholder_photo(circular_label)

        # Replace the existing photo label
        header_frame = self.findChild(QFrame, "profile_studentInfoCard")
        header_layout = header_frame.layout()

        old_photo_label = self.profile_studentPhotoLabel
        header_layout.replaceWidget(old_photo_label, photo_container)
        old_photo_label.setParent(None)

    def set_placeholder_photo(self, label):
        """Set a placeholder for student photo."""
        label.setStyleSheet("""
            QLabel {
                background-color: #2d2d44;
                color: #b0b0c0;
                font-size: 24px;
            }
        """)
        label.setAlignment(Qt.AlignCenter)
        label.setText("👤")

    def display_student_info(self):
        """Display student information with proper visual hierarchy."""
        # Student name - largest, most prominent
        self.profile_studentNameLabel.setText(self.student.name)
        self.profile_studentNameLabel.setFont(QFont("Arial", 22, QFont.Bold))
        self.profile_studentNameLabel.setStyleSheet("""
            color: #ffffff;
            padding: 6px 0 3px 0;
        """)

        # Student ID - medium size, secondary
        self.profile_studentIdLabel.setText(f"شماره دانشجویی: {self.student.student_id}")
        self.profile_studentIdLabel.setFont(QFont("Arial", 14, QFont.Normal))
        self.profile_studentIdLabel.setStyleSheet("""
            color: #b0b0c0;
            padding: 3px 0;
        """)

        # Faculty and Major - smaller, tertiary
        self.profile_facultyLabel.setText(f"دانشکده: {self.student.faculty}")
        self.profile_facultyLabel.setFont(QFont("Arial", 11, QFont.Normal))
        self.profile_facultyLabel.setStyleSheet("""
            color: #b0b0c0;
            padding: 1px 0;
        """)

        self.profile_majorLabel.setText(f"رشته: {self.student.major}")
        self.profile_majorLabel.setFont(QFont("Arial", 11, QFont.Normal))
        self.profile_majorLabel.setStyleSheet("""
            color: #b0b0c0;
            padding: 1px 0;
        """)

        # Update the GPA, units, and best GPA labels with proper styling
        # GPA label
        gpa_text = f"{self.student.overall_gpa:.2f}" if self.student.overall_gpa is not None else "0.00"
        self.profile_gpaLabel.setText(f"میانگین کل: {gpa_text}")
        self.profile_gpaLabel.setFont(QFont("Arial", 28, QFont.Bold))
        self.profile_gpaLabel.setStyleSheet("""
            color: #ffffff;
            padding: 5px 0;
        """)

        # Units label
        units_text = f"{int(self.student.total_units_passed)}" if self.student.total_units_passed is not None else "0"
        self.profile_unitsLabel.setText(f"واحدهای گذرانده: {units_text}")
        self.profile_unitsLabel.setFont(QFont("Arial", 12))
        self.profile_unitsLabel.setStyleSheet("""
            color: #b0b0c0;
            padding: 3px 0;
        """)

        # Best GPA label
        # Calculate best semester GPA
        best_gpa = Decimal('0.00')
        if self.student.semesters:
            valid_gpas = [semester.semester_gpa for semester in self.student.semesters
                          if semester.semester_gpa is not None and semester.semester_gpa >= Decimal('0.00')]
            if valid_gpas:
                best_gpa = max(valid_gpas)
        
        self.profile_bestGpaLabel.setText(f"بهترین میانگین ترم: {best_gpa:.2f}")
        self.profile_bestGpaLabel.setFont(QFont("Arial", 12))
        self.profile_bestGpaLabel.setStyleSheet("""
            color: #b0b0c0;
            padding: 3px 0;
        """)

    def add_statistics_cards(self):
        """Add enhanced statistics cards."""
        # Create stats container
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.NoFrame)
        stats_frame.setStyleSheet("""
            QFrame {
                background: transparent;
            }
        """)

        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(self.SPACING_MEDIUM)
        stats_layout.setContentsMargins(0, 0, 0, 0)

        # Calculate statistics
        total_courses = sum(len(semester.courses) for semester in self.student.semesters)
        passed_courses = sum(
            1 for semester in self.student.semesters
            for course in semester.courses
            if course.grade is not None and course.grade >= Decimal('10.00')
        )

        # Best semester GPA
        best_gpa = Decimal('0.00')
        if self.student.semesters:
            valid_gpas = [semester.semester_gpa for semester in self.student.semesters
                          if semester.semester_gpa is not None and semester.semester_gpa >= Decimal('0.00')]
            if valid_gpas:
                best_gpa = max(valid_gpas)

        # Card definitions
        cards_data = [
            {
                "icon": "🎓",
                "title": "معدل کل",
                "value": f"{self.student.overall_gpa:.2f}" if self.student.overall_gpa else "0.00",
                "subtitle": "از 20",
                "color": "#667eea",
                "color_dark": "#5568d3"
            },
            {
                "icon": "📚",
                "title": "واحد گذرانده",
                "value": f"{int(self.student.total_units_passed)}" if self.student.total_units_passed else "0",
                "subtitle": f"از 140 واحد",
                "color": "#48bb78",
                "color_dark": "#38a169"
            },
            {
                "icon": "📈",
                "title": "بهترین ترم",
                "value": f"{best_gpa:.2f}",
                "subtitle": "میانگین",
                "color": "#ed8936",
                "color_dark": "#dd6b20"
            }
        ]

        # Create cards
        for card_data in cards_data:
            card = self.create_stat_card(card_data)
            stats_layout.addWidget(card)

        # Add to main layout
        main_layout = self.findChild(QWidget, "ui_scrollAreaWidgetContents").layout()
        main_layout.insertWidget(1, stats_frame)

    def create_stat_card(self, data):
        """Create a single statistics card."""
        card = QFrame()
        card.setMinimumHeight(self.CARD_MIN_HEIGHT)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        
        # Apply colored backgrounds based on card type
        if "معدل کل" in data['title']:
            # GPA card: Purple
            card.setStyleSheet("""
                QFrame {
                    background-color: rgba(139, 92, 246, 0.2);
                    border-radius: 12px;
                    padding: 12px;
                }
            """)
        elif "واحد گذرانده" in data['title']:
            # Units card: Green
            card.setStyleSheet("""
                QFrame {
                    background-color: rgba(34, 197, 94, 0.2);
                    border-radius: 12px;
                    padding: 12px;
                }
            """)
        elif "بهترین ترم" in data['title']:
            # Best GPA card: Blue
            card.setStyleSheet("""
                QFrame {
                    background-color: rgba(59, 130, 246, 0.2);
                    border-radius: 12px;
                    padding: 12px;
                }
            """)
        else:
            # Default card style
            card.setStyleSheet("""
                QFrame {
                    background-color: #2d2d44;
                    border-radius: 12px;
                    padding: 12px;
                }
            """)

        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setSpacing(self.SPACING_SMALL)
        layout.setContentsMargins(0, 0, 0, 0)

        # Top row: icon + title
        top_row = QHBoxLayout()
        top_row.setSpacing(self.SPACING_SMALL)

        icon_label = QLabel(data['icon'])
        icon_label.setFont(QFont("Arial", self.ICON_SIZE_MEDIUM))

        title_label = QLabel(data['title'])
        title_label.setFont(QFont("Arial", self.FONT_SIZE_SMALL, QFont.DemiBold))
        title_label.setStyleSheet("color: #b0b0c0;")

        top_row.addWidget(icon_label)
        top_row.addWidget(title_label)
        top_row.addStretch()

        # Value
        value_label = QLabel(data['value'])
        value_label.setFont(QFont("Arial", 28, QFont.Bold))
        value_label.setStyleSheet("color: #ffffff;")

        # Subtitle
        subtitle_label = QLabel(data['subtitle'])
        subtitle_label.setFont(QFont("Arial", 12))
        subtitle_label.setStyleSheet("color: #b0b0c0;")

        layout.addLayout(top_row)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)
        layout.addStretch()

        return card

    def add_gpa_trend_chart(self):
        """Add GPA trend chart with optimized sizing."""
        try:
            # Set the matplotlib backend before importing pyplot
            import matplotlib
            matplotlib.use('Qt5Agg')
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

            # Filter out semesters with zero GPA (current semester)
            valid_semesters = [s for s in self.student.semesters if s.semester_gpa is not None and s.semester_gpa > 0]
            sorted_semesters = sorted(valid_semesters, key=lambda s: s.semester_id)

            if not sorted_semesters:
                return

            # Create chart frame with dark theme
            chart_frame = QFrame()
            chart_frame.setStyleSheet("""
                QFrame {
                    background: #2d2d44;
                    border: 2px solid #4a4a6a;
                    border-radius: 10px;
                    padding: 14px;
                }
            """)

            chart_layout = QVBoxLayout(chart_frame)
            chart_layout.setSpacing(self.SPACING_MEDIUM)
            chart_layout.setContentsMargins(self.PADDING_MEDIUM, self.PADDING_MEDIUM,
                                            self.PADDING_MEDIUM, self.PADDING_MEDIUM)

            # Title - in Persian to match other titles
            title = QLabel("📊 روند معدل ترمی")
            title.setFont(QFont("Arial", self.FONT_SIZE_LARGE, QFont.Bold))
            title.setStyleSheet("color: #ffffff;")
            chart_layout.addWidget(title)

            # Extract data - use term numbers for x-axis and GPAs for y-axis
            term_numbers = list(range(1, len(sorted_semesters) + 1))
            gpas = [float(s.semester_gpa) for s in sorted_semesters]
            
            # Convert Persian semester descriptions to English for tooltip display
            semester_names = []
            for s in sorted_semesters:
                desc = s.semester_description
                if "بهار" in desc:
                    desc = desc.replace("بهار", "Spring")
                elif "پاییز" in desc:
                    desc = desc.replace("پاییز", "Fall")
                elif "تابستان" in desc:
                    desc = desc.replace("تابستان", "Summer")
                semester_names.append(desc)

            # Create figure with specific DPI for clarity - increased size
            fig, ax = plt.subplots(figsize=(16, 10), dpi=120, facecolor='#2d2d44')
            fig.subplots_adjust(bottom=0.2, top=0.9, left=0.1, right=0.95)

            # Set dark theme for the chart
            ax.set_facecolor('#2d2d44')
            fig.patch.set_facecolor('#2d2d44')
            
            # Change text colors for dark theme
            ax.tick_params(colors='#ffffff', which='both')
            ax.spines['bottom'].set_color('#4a4a6a')
            ax.spines['top'].set_color('#4a4a6a')
            ax.spines['right'].set_color('#4a4a6a')
            ax.spines['left'].set_color('#4a4a6a')
            ax.xaxis.label.set_color('#ffffff')
            ax.yaxis.label.set_color('#ffffff')
            ax.title.set_color('#ffffff')

            # Create bar chart
            bars = ax.bar(term_numbers, gpas, color='#667eea', alpha=0.8, edgecolor='#4a5568', linewidth=1.2)

            # Add value labels on bars
            for i, (bar, gpa) in enumerate(zip(bars, gpas)):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{gpa:.2f}',
                        ha='center', va='bottom', fontsize=self.FONT_SIZE_SMALL, fontweight='bold', color='#ffffff')

            # Calculate average excluding zero GPAs
            avg_gpa = sum(gpas) / len(gpas) if gpas else 0
            
            # Add average line
            ax.axhline(y=avg_gpa, color='#48bb78', linestyle='--',
                       linewidth=2, alpha=0.8, label=f'Average: {avg_gpa:.2f}')

            # Styling - keep English for chart elements
            ax.set_xlabel('Term Number', fontsize=self.FONT_SIZE_NORMAL, fontweight='500', color='#ffffff')
            ax.set_ylabel('GPA', fontsize=self.FONT_SIZE_NORMAL, fontweight='500', color='#ffffff')
            ax.set_ylim(0, 20)
            ax.set_xticks(term_numbers)
            ax.set_xticklabels([f'Term {i}' for i in term_numbers], rotation=0, fontsize=self.FONT_SIZE_NORMAL, color='#ffffff')
            ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, axis='y', color='#4a4a6a')
            ax.legend(loc='upper right', fontsize=self.FONT_SIZE_SMALL, framealpha=0.9, facecolor='#2d2d44', edgecolor='#4a4a6a', labelcolor='#ffffff')

            # Add shadow to frame
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(15)
            shadow.setXOffset(0)
            shadow.setYOffset(2)
            shadow.setColor(QColor(0, 0, 0, 30))
            chart_frame.setGraphicsEffect(shadow)

            # Add to canvas
            canvas = FigureCanvas(fig)
            canvas.setFixedHeight(self.CHART_HEIGHT)
            chart_layout.addWidget(canvas)

            # Add to main layout at the end
            main_layout = self.findChild(QWidget, "ui_scrollAreaWidgetContents").layout()
            main_layout.addWidget(chart_frame)

        except ImportError:
            print("Matplotlib not available")
        except Exception as e:
            print(f"Error creating chart: {e}")

    def create_timeline_card(self, semester):
        """Create a timeline card for a semester."""
        card = QFrame()
        card.setFixedSize(180, 150)

        gpa = float(semester.semester_gpa) if semester.semester_gpa else 0.0
        if gpa >= 17:
            border_color = "#48bb78"
        elif gpa >= 14:
            border_color = "#ffffff"
        else:
            border_color = "#ed8936"

        # Apply 3px colored border as requested
        card.setStyleSheet(f"""
            QFrame {{
                background: #2d2d44;
                border: 3px solid {border_color};
                border-radius: 8px;
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setSpacing(0)
        layout.setContentsMargins(1, 1, 1, 1)

        # Semester name (truncated)
        name = semester.semester_description[:18] + "..." if len(
            semester.semester_description) > 18 else semester.semester_description
        name_label = QLabel(name)
        name_label.setFont(QFont("Arial", 11, QFont.Bold))
        name_label.setStyleSheet("color: #ffffff;")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)

        # GPA
        gpa_label = QLabel(f"{gpa:.2f}")
        gpa_label.setFont(QFont("Arial", 20, QFont.Bold))
        gpa_label.setStyleSheet(f"color: {border_color};")
        gpa_label.setAlignment(Qt.AlignCenter)

        # Units
        units_label = QLabel(f"{int(semester.units_passed)}/{int(semester.units_taken)}")
        units_label.setFont(QFont("Arial", 10))
        units_label.setStyleSheet("color: #b0b0c0;")
        units_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(name_label)
        layout.addWidget(gpa_label)
        layout.addWidget(units_label)

        return card

    def add_gpa_predictor(self):
        """Add GPA predictor widget."""
        try:
            predictor_frame = QFrame()
            predictor_frame.setStyleSheet("""
                QFrame {
                    background: #2d2d44;
                    border: 2px solid #4a4a6a;
                    border-radius: 10px;
                    padding: 16px;
                }
            """)

            predictor_layout = QVBoxLayout(predictor_frame)
            predictor_layout.setSpacing(self.SPACING_MEDIUM)

            # Title
            title = QLabel("🔮 پیش‌بینی معدل ترم بعد")
            title.setFont(QFont("Arial", self.FONT_SIZE_LARGE, QFont.Bold))
            title.setStyleSheet("color: #ffffff;")
            predictor_layout.addWidget(title)

            # Description
            desc = QLabel("با انتخاب تعداد واحد و نمره مورد انتظار، معدل احتمالی خود را محاسبه کنید")
            desc.setFont(QFont("Arial", self.FONT_SIZE_SMALL))
            desc.setStyleSheet("color: #b0b0c0;")
            predictor_layout.addWidget(desc)

            # Form - Modified to have labels and inputs side-by-side
            form_widget = QWidget()
            form_layout = QFormLayout(form_widget)
            form_layout.setSpacing(self.SPACING_MEDIUM)
            form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            # Set field growth policy to ensure proper alignment
            form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

            # Units input - label and input side-by-side
            self.units_input = QSpinBox()
            self.units_input.setRange(12, 24)
            self.units_input.setValue(17)
            self.units_input.setFixedHeight(self.INPUT_HEIGHT)
            self.units_input.setStyleSheet(f"""
                QSpinBox {{
                    padding: 2px 4px;
                    font-size: {self.FONT_SIZE_NORMAL}px;
                    border: 1px solid #4a4a6a;
                    border-radius: 4px;
                    background: #2a2a3e;
                    color: #ffffff;
                    min-width: 100px;
                }}
                QSpinBox:focus {{
                    border: 2px solid #667eea;
                }}
            """)

            # Grade input - label and input side-by-side
            self.grade_input = QDoubleSpinBox()
            self.grade_input.setRange(0, 20)
            self.grade_input.setValue(17.0)
            self.grade_input.setSingleStep(0.5)
            self.grade_input.setFixedHeight(self.INPUT_HEIGHT)
            self.grade_input.setStyleSheet(f"""
                QDoubleSpinBox {{
                    padding: 4px 8px;
                    font-size: {self.FONT_SIZE_NORMAL}px;
                    border: 1px solid #4a4a6a;
                    border-radius: 4px;
                    background: #2a2a3e;
                    color: #ffffff;
                    min-width: 100px;
                }}
                QDoubleSpinBox:focus {{
                    border: 2px solid #667eea;
                }}
            """)

            # Add rows to form layout - labels and inputs side-by-side
            form_layout.addRow(QLabel("تعداد واحد:"), self.units_input)
            form_layout.addRow(QLabel("نمره پیش‌بینی:"), self.grade_input)
            
            # Style the labels in the form
            for i in range(form_layout.rowCount()):
                label_item = form_layout.itemAt(i, QFormLayout.LabelRole)
                if label_item and label_item.widget():
                    label_item.widget().setFont(QFont("Arial", self.FONT_SIZE_NORMAL))
                    label_item.widget().setStyleSheet("color: #ffffff; padding-right: 10px;")

            predictor_layout.addWidget(form_widget)

            # Calculate button
            calc_button = QPushButton("محاسبه معدل جدید")
            calc_button.setFixedHeight(self.BUTTON_HEIGHT)
            calc_button.setCursor(Qt.PointingHandCursor)
            calc_button.setFont(QFont("Arial", self.FONT_SIZE_NORMAL, QFont.DemiBold))
            calc_button.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #667eea, stop:1 #764ba2);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 0 {self.PADDING_LARGE}px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #5568d3, stop:1 #6b3fa0);
                }}
                QPushButton:pressed {{
                    background: #5568d3;
                }}
            """)
            calc_button.clicked.connect(self.calculate_predicted_gpa)
            predictor_layout.addWidget(calc_button)

            # Result widget
            self.result_widget = QFrame()
            self.result_widget.setVisible(False)
            self.result_widget.setStyleSheet("""
                QFrame {
                    background: #2a2a3e;
                    border: 2px solid #4a4a6a;
                    border-radius: 10px;
                    padding: 16px;
                }
            """)

            result_layout = QVBoxLayout(self.result_widget)
            result_layout.setSpacing(self.SPACING_SMALL)

            self.predicted_label = QLabel()
            self.predicted_label.setFont(QFont("Arial", 36, QFont.Bold))
            self.predicted_label.setStyleSheet("color: #ffffff;")
            self.predicted_label.setAlignment(Qt.AlignCenter)

            self.change_label = QLabel()
            self.change_label.setFont(QFont("Arial", self.FONT_SIZE_NORMAL, QFont.DemiBold))
            self.change_label.setStyleSheet("color: #b0b0c0;")
            self.change_label.setAlignment(Qt.AlignCenter)

            result_layout.addWidget(self.predicted_label)
            result_layout.addWidget(self.change_label)

            predictor_layout.addWidget(self.result_widget)

            # Action buttons
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(self.SPACING_MEDIUM)

            print_button = QPushButton("چاپ کارنامه")
            print_button.setFixedHeight(self.BUTTON_HEIGHT)
            print_button.setCursor(Qt.PointingHandCursor)
            print_button.setFont(QFont("Arial", self.FONT_SIZE_NORMAL))
            print_button.setStyleSheet(f"""
                QPushButton {{
                    background: #48bb78;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 0 {self.PADDING_LARGE}px;
                }}
                QPushButton:hover {{
                    background: #38a169;
                }}
            """)
            print_button.clicked.connect(self.save_academic_screenshot)
            print_button.setVisible(False)

            pdf_button = QPushButton("ذخیره کارنامه")
            pdf_button.setFixedHeight(self.BUTTON_HEIGHT)
            pdf_button.setCursor(Qt.PointingHandCursor)
            pdf_button.setFont(QFont("Arial", self.FONT_SIZE_NORMAL))
            pdf_button.setStyleSheet(f"""
                QPushButton {{
                    background: #3498db;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 0 {self.PADDING_LARGE}px;
                }}
                QPushButton:hover {{
                    background: #2980b9;
                }}
            """)
            pdf_button.clicked.connect(self.save_academic_screenshot)
            actions_layout.addWidget(print_button)
            actions_layout.addWidget(pdf_button)
            actions_layout.addStretch()

            predictor_layout.addLayout(actions_layout)

            # Add shadow
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(15)
            shadow.setXOffset(0)
            shadow.setYOffset(2)
            shadow.setColor(QColor(0, 0, 0, 30))
            predictor_frame.setGraphicsEffect(shadow)

            # Add to main layout
            main_layout = self.findChild(QWidget, "ui_scrollAreaWidgetContents").layout()
            main_layout.insertWidget(4, predictor_frame)

        except Exception as e:
            print(f"Error creating GPA predictor: {e}")

    def calculate_predicted_gpa(self):
        """Calculate predicted GPA."""
        try:
            new_units = self.units_input.value()
            new_grade = self.grade_input.value()

            if self.student.overall_gpa and self.student.total_units_passed:
                current_points = float(self.student.overall_gpa) * float(self.student.total_units_passed)
                new_points = new_grade * new_units
                predicted_gpa = (current_points + new_points) / (float(self.student.total_units_passed) + new_units)
                change = predicted_gpa - float(self.student.overall_gpa)

                self.result_widget.setVisible(True)
                self.predicted_label.setText(f"{predicted_gpa:.2f}")

                if change > 0:
                    self.change_label.setText(f"افزایش {change:.2f} نسبت به معدل فعلی 📈")
                    self.change_label.setStyleSheet("color: #15803d;")
                elif change < 0:
                    self.change_label.setText(f"کاهش {abs(change):.2f} نسبت به معدل فعلی 📉")
                    self.change_label.setStyleSheet("color: #dc2626;")
                else:
                    self.change_label.setText("بدون تغییر نسبت به معدل فعلی")
                    self.change_label.setStyleSheet("color: #6c757d;")

        except Exception as e:
            print(f"Error calculating GPA: {e}")

    def save_academic_screenshot(self):
        """Save academic information as screenshot."""
        from PyQt5.QtWidgets import QFileDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTableWidget, QTableWidgetItem
        from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor
        from PyQt5.QtCore import Qt
        
        # Get file path from user
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "ذخیره خلاصه تحصیلی", 
            "academic_summary.png", 
            "PNG Files (*.png)"
        )
        
        if file_path:
            try:
                # Create a widget to hold the academic summary
                summary_widget = QWidget()
                summary_widget.setLayoutDirection(Qt.RightToLeft)
                summary_widget.setStyleSheet("""
                    QWidget {
                        background-color: #1e1e2e;
                        color: white;
                        font-family: Arial;
                    }
                """)
                layout = QVBoxLayout(summary_widget)
                layout.setSpacing(15)
                layout.setContentsMargins(20, 20, 20, 20)
                
                # Header
                header = QLabel("خلاصه وضعیت تحصیلی")
                header.setFont(QFont("Arial", 20, QFont.Bold))
                header.setAlignment(Qt.AlignCenter)
                header.setStyleSheet("color: #ffffff; padding: 10px;")
                layout.addWidget(header)
                
                # Student info section
                info_frame = QFrame()
                info_frame.setStyleSheet("""
                    QFrame {
                        background-color: #2d2d44;
                        border: 2px solid #4a4a6a;
                        border-radius: 12px;
                        padding: 15px;
                    }
                """)
                info_layout = QVBoxLayout(info_frame)
                
                # Student name
                name_label = QLabel(f"نام دانشجو: {self.student.name}")
                name_label.setFont(QFont("Arial", 16, QFont.Bold))
                name_label.setStyleSheet("color: #ffffff;")
                
                # Student ID
                id_label = QLabel(f"شماره دانشجویی: {self.student.student_id}")
                id_label.setFont(QFont("Arial", 12))
                id_label.setStyleSheet("color: #b0b0c0;")
                
                # Faculty and major
                faculty_label = QLabel(f"دانشکده: {self.student.faculty}")
                faculty_label.setFont(QFont("Arial", 12))
                faculty_label.setStyleSheet("color: #b0b0c0;")
                
                major_label = QLabel(f"رشته: {self.student.major}")
                major_label.setFont(QFont("Arial", 12))
                major_label.setStyleSheet("color: #b0b0c0;")
                
                info_layout.addWidget(name_label)
                info_layout.addWidget(id_label)
                info_layout.addWidget(faculty_label)
                info_layout.addWidget(major_label)
                layout.addWidget(info_frame)
                
                # Stats section
                stats_frame = QFrame()
                stats_frame.setStyleSheet("""
                    QFrame {
                        background-color: #2d2d44;
                        border: 1px solid #4a4a6a;
                        border-radius: 12px;
                        padding: 5px;
                    }
                """)
                stats_layout = QHBoxLayout(stats_frame)
                
                # Overall GPA
                gpa_text = f"{self.student.overall_gpa:.2f}" if self.student.overall_gpa is not None else "0.00"
                gpa_box = QFrame()
                gpa_layout = QVBoxLayout(gpa_box)
                gpa_title = QLabel("معدل کل")
                gpa_title.setFont(QFont("Arial", 10))
                gpa_title.setStyleSheet("color: #b0b0c0;")
                gpa_value = QLabel(gpa_text)
                gpa_value.setFont(QFont("Arial", 18, QFont.Bold))
                gpa_value.setStyleSheet("color: #ffffff;")
                gpa_layout.addWidget(gpa_title)
                gpa_layout.addWidget(gpa_value)
                
                # Total units
                units_text = f"{int(self.student.total_units_passed)}" if self.student.total_units_passed is not None else "0"
                units_box = QFrame()
                units_layout = QVBoxLayout(units_box)
                units_title = QLabel("واحدهای گذرانده")
                units_title.setFont(QFont("Arial", 10))
                units_title.setStyleSheet("color: #b0b0c0;")
                units_value = QLabel(units_text)
                units_value.setFont(QFont("Arial", 18, QFont.Bold))
                units_value.setStyleSheet("color: #ffffff;")
                units_layout.addWidget(units_title)
                units_layout.addWidget(units_value)
                
                # Best semester GPA
                best_gpa = Decimal('0.00')
                if self.student.semesters:
                    valid_gpas = [semester.semester_gpa for semester in self.student.semesters
                                if semester.semester_gpa is not None and semester.semester_gpa >= Decimal('0.00')]
                    if valid_gpas:
                        best_gpa = max(valid_gpas)
                best_gpa_box = QFrame()
                best_gpa_layout = QVBoxLayout(best_gpa_box)
                best_gpa_title = QLabel("بهترین ترم")
                best_gpa_title.setFont(QFont("Arial", 10))
                best_gpa_title.setStyleSheet("color: #b0b0c0;")
                best_gpa_value = QLabel(f"{best_gpa:.2f}")
                best_gpa_value.setFont(QFont("Arial", 18, QFont.Bold))
                best_gpa_value.setStyleSheet("color: #ffffff;")
                best_gpa_layout.addWidget(best_gpa_title)
                best_gpa_layout.addWidget(best_gpa_value)
                
                stats_layout.addWidget(gpa_box)
                stats_layout.addWidget(units_box)
                stats_layout.addWidget(best_gpa_box)
                layout.addWidget(stats_frame)
                
                # Semesters section with improved vertical layout
                if self.student.semesters:
                    semesters_frame = QFrame()
                    semesters_layout = QVBoxLayout(semesters_frame)
                    
                    semesters_title = QLabel("ترم‌های تحصیلی")
                    semesters_title.setFont(QFont("Arial", 16, QFont.Bold))
                    semesters_title.setStyleSheet("color: #ffffff;")
                    semesters_layout.addWidget(semesters_title)
                    
                    # Add semester info in a vertical format with full details
                    for semester in sorted(self.student.semesters, key=lambda s: s.semester_id):
                        # Create a frame for each semester
                        semester_frame = QFrame()
                        semester_frame.setStyleSheet("""
                            QFrame {
                                background-color: #2a2a3e;
                                border: 1px solid #4a4a6a;
                                border-radius: 8px;
                            }
                        """)
                        semester_layout_inner = QVBoxLayout(semester_frame)
                        
                        # Term name (full description)
                        term_label = QLabel(semester.semester_description)
                        term_label.setFont(QFont("Arial", 12, QFont.Bold))
                        term_label.setStyleSheet("color: #ffffff;")
                        
                        # GPA
                        gpa = float(semester.semester_gpa) if semester.semester_gpa else 0.0
                        gpa_label = QLabel(f"معدل ترم: {gpa:.2f}")
                        gpa_label.setFont(QFont("Arial", 11))
                        if gpa >= 17:
                            gpa_label.setStyleSheet("color: #48bb78;")
                        elif gpa >= 14:
                            gpa_label.setStyleSheet("color: #667eea;")
                        else:
                            gpa_label.setStyleSheet("color: #ed8936;")
                        
                        # Units
                        units_label = QLabel(f"واحدهای گذرانده: {int(semester.units_passed)}/{int(semester.units_taken)}")
                        units_label.setFont(QFont("Arial", 11))
                        units_label.setStyleSheet("color: #b0b0c0;")
                        
                        # Courses section title
                        courses_title = QLabel("دروس ترم:")
                        courses_title.setFont(QFont("Arial", 11, QFont.Bold))
                        courses_title.setStyleSheet("color: #ffffff;")
                        
                        # Courses list (simplified)
                        courses_text = ""
                        for i, course in enumerate(semester.courses[:5]):
                            grade_text = f" ({course.grade:.2f})" if course.grade is not None else ""
                            courses_text += f"• {course.course_name}{grade_text}\n"
                        
                        # Add "..." if there are more courses
                        if len(semester.courses) > 5:
                            courses_text += "• ...\n"
                        
                        courses_label = QLabel(courses_text.strip())
                        courses_label.setFont(QFont("Arial", 10))
                        courses_label.setStyleSheet("color: #e0e0e0;")
                        
                        semester_layout_inner.addWidget(term_label)
                        semester_layout_inner.addWidget(gpa_label)
                        semester_layout_inner.addWidget(units_label)
                        semester_layout_inner.addWidget(courses_title)
                        semester_layout_inner.addWidget(courses_label)
                        
                        semesters_layout.addWidget(semester_frame)
                    
                    layout.addWidget(semesters_frame)
                
                # Set widget size and render
                summary_widget.adjustSize()
                summary_widget.resize(600, summary_widget.height())
                
                # Create pixmap and render
                pixmap = QPixmap(summary_widget.size())
                pixmap.fill(QColor("#1e1e2e"))
                summary_widget.render(pixmap)
                
                # Save the pixmap
                if pixmap.save(file_path, "PNG"):
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.information(self, "ذخیره خلاصه", "خلاصه وضعیت تحصیلی با موفقیت ذخیره شد.")
                else:
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.critical(self, "خطا", "خطا در ذخیره خلاصه.")
                    
            except Exception as e:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.critical(self, "خطا", f"خطا در ایجاد خلاصه:\n{str(e)}")

    def load_student_data(self):
        """Load student data."""
        try:
            credentials = load_local_credentials()

            if credentials is None:
                result = get_golestan_credentials(self)
                if result[0] is None:
                    self.reject()
                    return
                student_number, password = result
            else:
                student_number = credentials['student_number']
                password = credentials['password']

            db = StudentDatabase(student_number)

            if db.student_exists():
                self.student = db.load_student()
                print(f"✓ Loaded from database: {student_number}")
            else:
                print(f"⟳ Fetching from Golestan: {student_number}")
                self.student = get_student_record(username=student_number, password=password, db=db)
                db.save_student(self.student)
                print(f"✓ Saved to database: {student_number}")

            self.display_student_data()

        except Exception as e:
            print(f"Error loading student data: {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "خطا", f"خطا در بارگذاری اطلاعات:\n{str(e)}")
            self.reject()

    def populate_semesters_tree(self):
        """Populate semesters tree."""
        self.section_semestersTreeWidget.clear()
        
        # Ensure proper RTL layout for the tree
        self.section_semestersTreeWidget.setLayoutDirection(Qt.RightToLeft)
        
        # Set column widths for better visibility
        self.section_semestersTreeWidget.setColumnWidth(0, 250)
        self.section_semestersTreeWidget.setColumnWidth(1, 100)
        self.section_semestersTreeWidget.setColumnWidth(2, 150)

        if not self.student or not self.student.semesters:
            return

        sorted_semesters = sorted(self.student.semesters, key=lambda s: s.semester_id)

        for semester in sorted_semesters:
            item = QTreeWidgetItem(self.section_semestersTreeWidget)
            item.setText(0, semester.semester_description)
            item.setTextAlignment(0, Qt.AlignCenter)

            # Color code GPA according to user requirements
            gpa_text = f"{semester.semester_gpa:.2f}" if semester.semester_gpa else "0.00"
            item.setText(1, gpa_text)
            item.setTextAlignment(1, Qt.AlignCenter)

            if semester.semester_gpa:
                # مشروط (failed) grades: below 10 - red
                if semester.semester_gpa < 10:
                    item.setForeground(1, QColor("#dc2626"))
                # الف (passed with distinction): 17 and above - green
                elif semester.semester_gpa >= 17:
                    item.setForeground(1, QColor("#15803d"))
                # All other grades: white
                else:
                    item.setForeground(1, QColor("#ffffff"))

            units_text = f"{int(semester.units_passed)}/{int(semester.units_taken)}"
            item.setText(2, units_text)
            item.setTextAlignment(2, Qt.AlignCenter)
            item.setData(0, Qt.UserRole, semester)

            # Set font
            font = QFont("Arial", self.FONT_SIZE_NORMAL)
            for col in range(3):
                item.setFont(col, font)

            self.section_semestersTreeWidget.addTopLevelItem(item)

        self.section_semestersTreeWidget.expandAll()

        if self.section_semestersTreeWidget.topLevelItemCount() > 0:
            first_item = self.section_semestersTreeWidget.topLevelItem(0)
            self.section_semestersTreeWidget.setCurrentItem(first_item)

    def on_semester_selected(self):
        """Handle semester selection."""
        selected_items = self.section_semestersTreeWidget.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        semester = item.data(0, Qt.UserRole)

        if semester:
            self.display_semester_courses(semester)

    def display_semester_courses(self, semester):
        """Display courses for selected semester."""
        self.section_coursesTableWidget.setRowCount(0)
        self.section_coursesTableWidget.setColumnCount(5)
        self.section_coursesTableWidget.setHorizontalHeaderLabels([
            'نام درس', 'واحد', 'نمره', 'وضعیت', 'ترم'
        ])
        
        # Ensure proper RTL layout for the table
        self.section_coursesTableWidget.setLayoutDirection(Qt.RightToLeft)
        
        # Set column widths for better visibility
        self.section_coursesTableWidget.setColumnWidth(0, 300)
        self.section_coursesTableWidget.setColumnWidth(1, 80)
        self.section_coursesTableWidget.setColumnWidth(2, 80)
        self.section_coursesTableWidget.setColumnWidth(3, 100)
        self.section_coursesTableWidget.setColumnWidth(4, 150)
        
        # Center align all headers
        for col in range(5):
            self.section_coursesTableWidget.horizontalHeaderItem(col).setTextAlignment(Qt.AlignCenter)

        if not semester or not semester.courses:
            return

        self.section_coursesTableWidget.setRowCount(len(semester.courses))

        for row, course in enumerate(semester.courses):
            # Course name
            name_item = QTableWidgetItem(course.course_name)
            name_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            name_item.setFont(QFont("Arial", self.FONT_SIZE_NORMAL))
            name_item.setForeground(QColor("#ffffff"))
            self.section_coursesTableWidget.setItem(row, 0, name_item)

            # Units
            units_item = QTableWidgetItem(str(course.course_units))
            units_item.setTextAlignment(Qt.AlignCenter)
            units_item.setFont(QFont("Arial", self.FONT_SIZE_NORMAL))
            units_item.setForeground(QColor("#ffffff"))
            self.section_coursesTableWidget.setItem(row, 1, units_item)

            # Grade
            if course.grade is not None:
                grade_text = f"{course.grade:.2f}"
                grade_item = QTableWidgetItem(grade_text)
                grade_item.setFont(QFont("Arial", self.FONT_SIZE_NORMAL, QFont.Bold))

                # Color coding according to user requirements:
                # مشروط (failed) grades: below 10 - red
                if course.grade < 10:
                    grade_item.setForeground(QColor("#dc2626"))
                # الف (passed with distinction): 17 and above - green
                elif course.grade >= 17:
                    grade_item.setForeground(QColor("#15803d"))
                # All other grades: white
                else:
                    grade_item.setForeground(QColor("#ffffff"))
            else:
                grade_item = QTableWidgetItem("—")
                grade_item.setForeground(QColor("#9ca3af"))

            grade_item.setTextAlignment(Qt.AlignCenter)
            self.section_coursesTableWidget.setItem(row, 2, grade_item)

            # Status
            status_item = QTableWidgetItem(course.grade_state)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setFont(QFont("Arial", self.FONT_SIZE_NORMAL))
            status_item.setForeground(QColor("#ffffff"))
            self.section_coursesTableWidget.setItem(row, 3, status_item)

            # Semester
            semester_item = QTableWidgetItem(semester.semester_description[:20])
            semester_item.setTextAlignment(Qt.AlignCenter)
            semester_item.setFont(QFont("Arial", self.FONT_SIZE_SMALL))
            semester_item.setForeground(QColor("#b0b0c0"))
            self.section_coursesTableWidget.setItem(row, 4, semester_item)

    def toggle_semesters_visibility(self):
        """Toggle visibility of semesters tree widget."""
        if self.section_semestersTreeWidget.isVisible():
            self.section_semestersTreeWidget.hide()
            self.semester_minimize_button.setText("+")
            # Reduce the frame height when minimized
            self.section_semestersFrame.setMaximumHeight(100)
        else:
            self.section_semestersTreeWidget.show()
            self.semester_minimize_button.setText("−")
            # Restore the frame height when expanded
            self.section_semestersFrame.setMaximumHeight(800)

    def add_semester_section_minimize(self):
        """Add minimize capability to semesters section."""
        from PyQt5.QtWidgets import QPushButton
        
        # Create a horizontal layout for the title bar
        title_layout = self.section_semestersTitleLabel.parent().layout()
        
        # Add stretch to push the button to the right
        title_layout.addStretch()
        
        # Add a minimize button to the semesters section title
        minimize_button = QPushButton("−")
        minimize_button.setFixedSize(24, 24)
        minimize_button.setStyleSheet("""
            QPushButton {
                background-color: #4a4a6a;
                color: white;
                border: 1px solid #5a5a7a;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a7a;
            }
        """)
        
        title_layout.addWidget(minimize_button)
        
        # Connect the button to toggle the tree widget visibility
        minimize_button.clicked.connect(self.toggle_semesters_visibility)
        
        # Store reference to the button for later use
        self.semester_minimize_button = minimize_button