#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Dual Course Widget - Clean and stable implementation
No complex overlays or hover effects - just clear display of both courses
"""

from PyQt5 import QtWidgets, QtGui, QtCore
from app.core.logger import setup_logging

logger = setup_logging()


def create_simple_dual_widget(odd_course_data, even_course_data, parent):
    """
    Create a simple widget that displays two courses (odd/even weeks) side by side
    - No diagonal split
    - No complex hover effects
    - Clear and readable
    - Stable and crash-free
    """
    
    class SimpleDualCourseWidget(QtWidgets.QWidget):
        def __init__(self, odd_data, even_data, parent_window):
            super().__init__()
            self.odd_data = odd_data
            self.even_data = even_data
            self.parent_window = parent_window
            self.section_widgets = {}
            self.section_styles = {}
            self.current_highlight = None
            self.preview_mode = None

            self.setObjectName('dual-course-cell')
            self.original_style = self.styleSheet()
            self.setAttribute(QtCore.Qt.WA_Hover, True)
            self.setMouseTracking(True)

            # Set size constraints to prevent overflow
            self.setMinimumHeight(60)
            self.setMinimumWidth(90)
            self.setMaximumHeight(110)
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

            # Create simple vertical layout
            self.init_ui()

        def init_ui(self):
            """Initialize UI with stacked sections"""
            main_layout = QtWidgets.QVBoxLayout(self)
            main_layout.setContentsMargins(2, 2, 2, 2)
            main_layout.setSpacing(1)

            odd_section = self.create_course_section(self.odd_data, 'ف', is_odd=True, key='odd')
            even_section = self.create_course_section(self.even_data, 'ز', is_odd=False, key='even')

            self.section_widgets['odd'] = odd_section
            self.section_widgets['even'] = even_section
            self.section_styles['odd'] = odd_section.styleSheet()
            self.section_styles['even'] = even_section.styleSheet()

            main_layout.addWidget(odd_section)
            main_layout.addWidget(even_section)

        def create_course_section(self, course_data, parity_label, is_odd=True, key='odd'):
            """Create a section for one course"""
            section = QtWidgets.QFrame()
            section.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
            section.setLineWidth(1)
            section.setMouseTracking(True)

            color = course_data['color']
            section.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba({min(255, color.red() + 30)}, {min(255, color.green() + 30)}, {min(255, color.blue() + 30)}, 255),
                        stop:1 rgba({color.red()}, {color.green()}, {color.blue()}, 255)
                    );
                    border: 1px solid rgba(0, 0, 0, 100);
                    border-radius: 4px;
                }}
            """)

            layout = QtWidgets.QHBoxLayout(section)
            layout.setContentsMargins(4, 2, 4, 2)
            layout.setSpacing(2)

            info_layout = QtWidgets.QVBoxLayout()
            info_layout.setSpacing(0)

            course_name = course_data['course'].get('name', 'نامشخص')
            if len(course_name) > 20:
                course_name = course_name[:17] + '...'

            name_label = QtWidgets.QLabel(course_name)
            name_label.setStyleSheet("font-weight: bold; font-size: 8pt; color: black;")
            name_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            name_label.setWordWrap(True)

            instructor = course_data['course'].get('instructor', '')
            if len(instructor) > 18:
                instructor = instructor[:15] + '...'

            instructor_label = QtWidgets.QLabel(instructor)
            instructor_label.setStyleSheet("font-size: 7pt; color: #333;")
            instructor_label.setWordWrap(True)

            info_layout.addWidget(name_label)
            info_layout.addWidget(instructor_label)
            info_layout.addStretch()

            right_layout = QtWidgets.QVBoxLayout()
            right_layout.setSpacing(0)

            parity_widget = QtWidgets.QLabel(parity_label)
            parity_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            parity_widget.setFixedSize(22, 22)

            if is_odd:
                parity_widget.setStyleSheet("""
                    background-color: rgba(58, 66, 250, 200);
                    color: white;
                    border-radius: 11px;
                    font-weight: bold;
                    font-size: 10pt;
                """)
            else:
                parity_widget.setStyleSheet("""
                    background-color: rgba(46, 213, 115, 200);
                    color: white;
                    border-radius: 11px;
                    font-weight: bold;
                    font-size: 10pt;
                """)

            remove_button = QtWidgets.QPushButton('✕')
            remove_button.setFixedSize(16, 16)
            remove_button.setStyleSheet("""
                QPushButton {
                    background-color: rgba(231, 76, 60, 200);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 10pt;
                }
                QPushButton:hover {
                    background-color: rgba(192, 57, 43, 255);
                }
            """)
            course_key = course_data['course_key']
            remove_button.clicked.connect(lambda: self.remove_course(course_key))

            right_layout.addWidget(parity_widget, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
            right_layout.addStretch()
            right_layout.addWidget(remove_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

            layout.addLayout(info_layout, stretch=1)
            layout.addLayout(right_layout)

            section.mousePressEvent = lambda event: self.show_course_details(course_key)
            section.setCursor(QtCore.Qt.PointingHandCursor)

            return section

        def enterEvent(self, event):
            try:
                if self.parent_window and hasattr(self.parent_window, 'highlight_course_sessions'):
                    self.parent_window.highlight_course_sessions([
                        self.odd_data['course_key'],
                        self.even_data['course_key']
                    ])
            except Exception:
                pass
            self.highlight_section('both')
            super().enterEvent(event)

        def leaveEvent(self, event):
            self.clear_highlight()
            try:
                if self.parent_window and hasattr(self.parent_window, 'clear_course_highlights'):
                    self.parent_window.clear_course_highlights()
            except Exception:
                pass
            super().leaveEvent(event)

        def mouseMoveEvent(self, event):
            try:
                pos = event.pos()
                if self.section_widgets.get('odd') and self.section_widgets['odd'].geometry().contains(pos):
                    self.highlight_section('odd')
                elif self.section_widgets.get('even') and self.section_widgets['even'].geometry().contains(pos):
                    self.highlight_section('even')
                else:
                    self.highlight_section('both')
            except Exception:
                pass
            super().mouseMoveEvent(event)

        def remove_course(self, course_key):
            try:
                if hasattr(self.parent_window, 'remove_course_from_dual_widget'):
                    self.parent_window.remove_course_from_dual_widget(course_key, self)
                elif hasattr(self.parent_window, 'remove_course_from_schedule'):
                    self.parent_window.remove_course_from_schedule(course_key)
            except Exception as e:
                logger.error(f"Error removing course from dual widget: {e}")

        def remove_single_course(self, course_key):
            try:
                if hasattr(self.parent_window, 'remove_course_from_dual_widget'):
                    self.parent_window.remove_course_from_dual_widget(course_key, self)
            except Exception as e:
                logger.error(f"Error removing single course from dual widget: {e}")

        def show_course_details(self, course_key):
            try:
                if hasattr(self.parent_window, 'show_course_details'):
                    self.parent_window.show_course_details(course_key)
            except Exception as e:
                logger.error(f"Error showing course details: {e}")

        def highlight_section(self, section):
            if section not in ('odd', 'even', 'both', None):
                return
            if self.current_highlight == section:
                return
            self.current_highlight = section
            self._apply_section_styles()

        def highlight_section_for_course(self, course_key):
            if course_key == self.odd_data['course_key']:
                self.highlight_section('odd')
            elif course_key == self.even_data['course_key']:
                self.highlight_section('even')

        def clear_highlight(self):
            if self.current_highlight is None:
                self._apply_section_styles(force=True)
                self.clear_preview_mode()
                return
            self.current_highlight = None
            self._apply_section_styles(force=True)
            self.clear_preview_mode()

        def _apply_section_styles(self, force=False):
            for key in ('odd', 'even'):
                widget = self.section_widgets.get(key)
                if not widget:
                    continue
                base_style = self.section_styles.get(key, '')
                if force or self.current_highlight not in (key, 'both'):
                    widget.setStyleSheet(base_style)
            if self.current_highlight == 'both':
                for key in ('odd', 'even'):
                    widget = self.section_widgets.get(key)
                    if not widget:
                        continue
                    base_style = self.section_styles.get(key, '')
                    if 'border: 1px solid' in base_style:
                        highlight_style = base_style.replace('border: 1px solid rgba(0, 0, 0, 100);', 'border: 2px solid #e74c3c;')
                    else:
                        highlight_style = base_style + '\nQFrame { border: 2px solid #e74c3c; }'
                    widget.setStyleSheet(highlight_style)
                return
            if self.current_highlight in ('odd', 'even'):
                widget = self.section_widgets.get(self.current_highlight)
                if widget:
                    base_style = self.section_styles.get(self.current_highlight, '')
                    if 'border: 1px solid' in base_style:
                        highlight_style = base_style.replace('border: 1px solid rgba(0, 0, 0, 100);', 'border: 2px solid #e74c3c;')
                    else:
                        highlight_style = base_style + '\nQFrame { border: 2px solid #e74c3c; }'
                    widget.setStyleSheet(highlight_style)

        def set_preview_mode(self, mode):
            if mode not in ('compatible', 'conflict', None):
                return
            if mode == self.preview_mode:
                return

            if mode is None:
                self.preview_mode = None
                self.setStyleSheet(self.original_style)
                return

            color = '#3498db' if mode == 'compatible' else '#e74c3c'
            self.setStyleSheet(
                f"QWidget#dual-course-cell {{\n"
                f"    border: 2px dashed {color};\n"
                f"    border-radius: 8px;\n"
                f"    background-color: rgba(0, 0, 0, 0);\n"
                f"}}"
            )
            self.preview_mode = mode

        def clear_preview_mode(self):
            if self.preview_mode is not None:
                self.preview_mode = None
                self.setStyleSheet(self.original_style)

        def sizeHint(self):
            return QtCore.QSize(120, 76)

        def minimumSizeHint(self):
            return QtCore.QSize(90, 60)

        def get_other_course_key(self, removed_course_key):
            if removed_course_key == self.odd_data['course_key']:
                return self.even_data['course_key']
            return self.odd_data['course_key']

        def get_other_course_data(self, removed_course_key):
            if removed_course_key == self.odd_data['course_key']:
                return self.even_data
            return self.odd_data
    
    return SimpleDualCourseWidget(odd_course_data, even_course_data, parent)


def check_odd_even_compatibility(session1, session2):
    """
    Check if two sessions are compatible (one odd, one even)
    Returns True if they can coexist in the same time slot
    """
    try:
        parity1 = session1.get('parity', '') or ''
        parity2 = session2.get('parity', '') or ''
        
        # Ensure string type
        if not isinstance(parity1, str):
            parity1 = str(parity1)
        if not isinstance(parity2, str):
            parity2 = str(parity2)
        
        # Check if one is odd and one is even
        is_compatible = (
            (parity1 == 'ز' and parity2 == 'ف') or  # زوج and فرد
            (parity1 == 'ف' and parity2 == 'ز')     # فرد and زوج
        )
        
        return is_compatible
        
    except Exception as e:
        logger.error(f"Error checking odd/even compatibility: {e}")
        return False

