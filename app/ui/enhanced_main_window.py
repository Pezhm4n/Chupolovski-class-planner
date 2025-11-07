#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced schedule table cell rendering for Odd/Even week courses
This module modifies the add_course_to_table method to support dual courses
"""

from PyQt5 import QtWidgets, QtGui, QtCore
import sip

from app.core.logger import setup_logging
logger = setup_logging()


def create_dual_course_widget(odd_course_data, even_course_data, parent):
    """Create a widget that displays two courses (odd/even weeks) in the same cell"""
    
    class DualCourseWidget(QtWidgets.QWidget):
        def __init__(self, odd_data, even_data, parent_window):
            super().__init__()
            self.odd_data = odd_data
            self.even_data = even_data
            self.parent_window = parent_window
            self.hover_state = None
            self.is_expanded = False
            self.highlighted_section = None
            
            self.setMouseTracking(True)
            self.setAttribute(QtCore.Qt.WA_Hover)
            
            self.setMinimumHeight(80)
            self.setMinimumWidth(120)
            
            self.setObjectName('dual-course-cell')
            
            self.odd_overlay = None
            self.even_overlay = None
            self.original_style = ""
            
        def paintEvent(self, event):
            """Custom paint for diagonal split"""
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            
            rect = self.rect()
            
            if self.hover_state and self.is_expanded:
                painter.fillRect(rect, QtGui.QColor(255, 255, 255, 240))
            else:
                self.draw_diagonal_split(painter, rect)
                
        def draw_diagonal_split(self, painter, rect):
            """Draw the default diagonal split view"""
            border_width = 0
            inner_rect = rect.adjusted(border_width, border_width, -border_width, -border_width)
            
            odd_path = QtGui.QPainterPath()
            odd_path.moveTo(inner_rect.topLeft())
            odd_path.lineTo(inner_rect.topRight())
            odd_path.lineTo(inner_rect.bottomRight())
            odd_path.closeSubpath()
            
            even_path = QtGui.QPainterPath()
            even_path.moveTo(inner_rect.topLeft())
            even_path.lineTo(inner_rect.bottomLeft())
            even_path.lineTo(inner_rect.bottomRight())
            even_path.closeSubpath()
            
            painter.setClipPath(odd_path)
            odd_color = self.odd_data['color']
            
            odd_gradient = QtGui.QLinearGradient(inner_rect.topLeft(), inner_rect.bottomRight())
            odd_gradient.setColorAt(0, QtGui.QColor(
                min(255, odd_color.red() + 40),
                min(255, odd_color.green() + 40),
                min(255, odd_color.blue() + 40)
            ))
            odd_gradient.setColorAt(1, odd_color)
            painter.fillRect(inner_rect, odd_gradient)
            
            painter.setPen(QtGui.QPen(QtCore.Qt.black))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            font.setFamily("IRANSans UI")
            painter.setFont(font)
            
            odd_text = self.odd_data['course']['name']
            if len(odd_text) > 20:
                odd_text = odd_text[:17] + "..."
            
            text_rect = QtCore.QRect(
                inner_rect.x() + 12, 
                inner_rect.y() + 12, 
                inner_rect.width() - 24, 
                inner_rect.height() // 2 - 20
            )
            painter.drawText(text_rect, QtCore.Qt.AlignCenter | QtCore.Qt.TextWordWrap, odd_text)
            
            painter.setFont(QtGui.QFont("IRANSans UI", 8, QtGui.QFont.Bold))
            painter.setPen(QtGui.QPen(QtGui.QColor(50, 50, 50)))
            painter.drawText(inner_rect.x() + 5, inner_rect.y() + 15, "(ф)")
            
            painter.setClipPath(even_path)
            even_color = self.even_data['color']
            
            even_gradient = QtGui.QLinearGradient(inner_rect.topLeft(), inner_rect.bottomRight())
            even_gradient.setColorAt(0, even_color)
            even_gradient.setColorAt(1, QtGui.QColor(
                max(0, even_color.red() - 40),
                max(0, even_color.green() - 40),
                max(0, even_color.blue() - 40)
            ))
            painter.fillRect(inner_rect, even_gradient)
            
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            even_text = self.even_data['course']['name']
            if len(even_text) > 20:
                even_text = even_text[:17] + "..."
            
            text_rect = QtCore.QRect(
                inner_rect.x() + 12, 
                inner_rect.y() + inner_rect.height() // 2 + 8,
                inner_rect.width() - 24, 
                inner_rect.height() // 2 - 20
            )
            painter.drawText(text_rect, QtCore.Qt.AlignCenter | QtCore.Qt.TextWordWrap, even_text)
            
            painter.setFont(QtGui.QFont("IRANSans UI", 8, QtGui.QFont.Bold))
            painter.setPen(QtGui.QPen(QtGui.QColor(50, 50, 50)))
            painter.drawText(inner_rect.right() - 20, inner_rect.bottom() - 5, "(з)")
            
            painter.setClipping(False)
            pen = QtGui.QPen(QtGui.QColor(180, 180, 180), 1.5, QtCore.Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(inner_rect.topLeft(), inner_rect.bottomRight())
            
            # Highlight only the hovered section
            if self.highlighted_section == 'odd':
                painter.setPen(QtGui.QPen(QtGui.QColor(231, 76, 60), 3))
                painter.setBrush(QtCore.Qt.NoBrush)
                # Draw border only around odd section
                painter.drawPath(odd_path)
            elif self.highlighted_section == 'even':
                painter.setPen(QtGui.QPen(QtGui.QColor(231, 76, 60), 3))
                painter.setBrush(QtCore.Qt.NoBrush)
                # Draw border only around even section
                painter.drawPath(even_path)
            
        def mouseMoveEvent(self, event):
            """Detect which triangle the mouse is over and apply highlight"""
            logger.debug("overlay_hover_move: Dual course widget hover move")
            try:
                if not hasattr(self, 'parent_window') or not self.parent_window:
                    logger.warning("overlay_hover_parent_missing: Parent window not available during hover move")
                    super().mouseMoveEvent(event)
                    return
                    
                rect = self.rect()
                pos = event.pos()
                
                diagonal_y = pos.x() * rect.height() / rect.width()
                
                new_hover = 'odd' if pos.y() < diagonal_y else 'even'
                
                if new_hover != self.hover_state:
                    self.hover_state = new_hover
                    self.is_expanded = True
                    self.create_overlay_widgets()
                    
                    if new_hover == 'odd':
                        self.highlight_section('odd')
                        if hasattr(self.parent_window, 'highlight_course_sessions'):
                            self.parent_window.highlight_course_sessions(self.odd_data['course_key'])
                    else:
                        self.highlight_section('even')
                        if hasattr(self.parent_window, 'highlight_course_sessions'):
                            self.parent_window.highlight_course_sessions(self.even_data['course_key'])
                
                self.update()
            except Exception as e:
                logger.warning(f"overlay_hover_move_error: Error in mouseMoveEvent for DualCourseWidget: {e}")
                
            super().mouseMoveEvent(event)
            
        def enterEvent(self, event):
            """Start hover state"""
            logger.debug("overlay_hover_enter: Dual course widget hover enter")
            try:
                if not hasattr(self, 'parent_window') or not self.parent_window:
                    logger.warning("overlay_hover_parent_missing: Parent window not available during hover enter")
                    return
                    
                super().enterEvent(event)
            except Exception as e:
                logger.warning(f"overlay_hover_enter_error: Error in enterEvent for DualCourseWidget: {e}")
            
        def leaveEvent(self, event):
            """Reset to split view and clear highlights"""
            logger.debug("overlay_hover_leave: Dual course widget hover leave")
            try:
                if not hasattr(self, 'parent_window') or not self.parent_window:
                    logger.warning("overlay_hover_parent_missing: Parent window not available during hover leave")
                    return
                    
                self.hover_state = None
                self.is_expanded = False
                
                self.remove_overlay_widgets()
                self.clear_highlight()
                
                if hasattr(self.parent_window, 'clear_course_highlights'):
                    self.parent_window.clear_course_highlights()
                
                self.update()
            except Exception as e:
                logger.warning(f"overlay_hover_leave_error: Error in leaveEvent for DualCourseWidget: {e}")
            super().leaveEvent(event)
            
        def create_overlay_widgets(self):
            """Create overlay widgets for expanded course view"""
            logger.info("overlay_requested: Creating overlay widgets")
            self.remove_overlay_widgets()
            
            if not hasattr(self, 'parent_window') or not self.parent_window:
                logger.warning("overlay_parent_missing: Parent window not available")
                return
                
            if self.hover_state == 'odd':
                data = self.odd_data
            else:
                data = self.even_data
                
            try:
                overlay = QtWidgets.QWidget(self)
                overlay.setObjectName('expanded-course-overlay')
                
                overlay.setStyleSheet("""
                    QWidget#expanded-course-overlay {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 rgba(255, 255, 255, 250),
                            stop:1 rgba(245, 245, 245, 250));
                        border: 2px solid #3498db;
                        border-radius: 8px;
                        padding: 4px;
                    }
                    QLabel#course-name-label {
                        font-family: 'IRANSans UI';
                        font-size: 11pt;
                        font-weight: bold;
                        color: #2c3e50;
                    }
                    QLabel#professor-label {
                        font-family: 'IRANSans UI';
                        font-size: 9pt;
                        color: #7f8c8d;
                    }
                    QLabel#code-label {
                        font-family: 'IRANSans UI';
                        font-size: 8pt;
                        color: #95a5a6;
                    }
                    QLabel#parity-indicator {
                        font-family: 'IRANSans UI';
                        font-size: 9pt;
                        font-weight: bold;
                        color: #3498db;
                    }
                    QPushButton#close-btn {
                        background: #e74c3c;
                        color: white;
                        border: none;
                        border-radius: 10px;
                        font-weight: bold;
                    }
                    QPushButton#close-btn:hover {
                        background: #c0392b;
                    }
                """)
                
                layout = QtWidgets.QVBoxLayout(overlay)
                layout.setContentsMargins(8, 8, 8, 8)
                layout.setSpacing(4)
                
                top_row = QtWidgets.QHBoxLayout()
                top_row.addStretch()
                
                close_btn = QtWidgets.QPushButton('✕')
                close_btn.setFixedSize(20, 20)
                close_btn.setObjectName('close-btn')
                close_btn.clicked.connect(lambda: self.close_overlay())
                
                top_row.addWidget(close_btn)
                layout.addLayout(top_row)
                
                name_label = QtWidgets.QLabel(data['course']['name'])
                name_label.setObjectName('course-name-label')
                name_label.setWordWrap(True)
                name_label.setAlignment(QtCore.Qt.AlignCenter)
                layout.addWidget(name_label)
                
                inst_label = QtWidgets.QLabel(data['course'].get('instructor', 'نامشخص'))
                inst_label.setObjectName('professor-label')
                inst_label.setAlignment(QtCore.Qt.AlignCenter)
                layout.addWidget(inst_label)
                
                code_label = QtWidgets.QLabel(data['course'].get('code', ''))
                code_label.setObjectName('code-label')
                code_label.setAlignment(QtCore.Qt.AlignCenter)
                layout.addWidget(code_label)
                
                parity_text = "هفته فرد" if data['session'].get('parity') == 'ف' else "هفته زوج"
                parity_label = QtWidgets.QLabel(parity_text)
                parity_label.setObjectName('parity-indicator')
                parity_label.setAlignment(QtCore.Qt.AlignCenter)
                layout.addWidget(parity_label)
                
                layout.addStretch()
                
                overlay.setGeometry(self.rect())
                overlay.show()
                overlay.raise_()
                
                if self.hover_state == 'odd':
                    self.odd_overlay = overlay
                    logger.info("overlay_created: Odd overlay created")
                else:
                    self.even_overlay = overlay
                    logger.info("overlay_created: Even overlay created")
            except Exception as e:
                logger.error(f"overlay_creation_failed: Failed to create overlay widgets: {e}")
                
        def close_overlay(self):
            """Close the overlay and reset to split view"""
            logger.info("overlay_closing: Closing overlay")
            self.hover_state = None
            self.is_expanded = False
            self.remove_overlay_widgets()
            self.update()
            
        def remove_overlay_widgets(self):
            """Remove overlay widgets"""
            logger.info("overlay_removing: Removing overlay widgets")
            if self.odd_overlay is not None:
                try:
                    if not sip.isdeleted(self.odd_overlay):
                        if hasattr(self.odd_overlay, 'setParent'):
                            self.odd_overlay.setParent(None)
                        if hasattr(self.odd_overlay, 'deleteLater'):
                            self.odd_overlay.deleteLater()
                except (RuntimeError, AttributeError) as e:
                    logger.warning(f"overlay_remove_error: Error removing odd overlay: {e}")
                finally:
                    self.odd_overlay = None
                    logger.info("overlay_removed: Odd overlay removed")
        
            if self.even_overlay is not None:
                try:
                    if not sip.isdeleted(self.even_overlay):
                        if hasattr(self.even_overlay, 'setParent'):
                            self.even_overlay.setParent(None)
                        if hasattr(self.even_overlay, 'deleteLater'):
                            self.even_overlay.deleteLater()
                except (RuntimeError, AttributeError) as e:
                    logger.warning(f"overlay_remove_error: Error removing even overlay: {e}")
                finally:
                    self.even_overlay = None
                    logger.info("overlay_removed: Even overlay removed")
        
            self.odd_overlay = None
            self.even_overlay = None
                
        def mouseDoubleClickEvent(self, event):
            """Handle double-click to show course details"""
            rect = self.rect()
            pos = event.pos()
            diagonal_y = pos.x() * rect.height() / rect.width()
            
            if pos.y() < diagonal_y:
                self.parent_window.show_course_details(self.odd_data['course_key'])
            else:
                self.parent_window.show_course_details(self.even_data['course_key'])
                
        def remove_single_course(self, course_key):
            """Remove a single course from the dual widget"""
            if course_key == self.odd_data['course_key']:
                self.convert_to_single_course(self.even_data)
            elif course_key == self.even_data['course_key']:
                self.convert_to_single_course(self.odd_data)
                
        def convert_to_single_course(self, course_data):
            """Convert this dual widget to a single course widget"""
            from .widgets import AnimatedCourseWidget
            from app.core.config import COLOR_MAP
            
            parent_cell = self.parent()
            if parent_cell:
                for (row, col), info in self.parent_window.placed.items():
                    if info.get('widget') == self:
                        self.parent_window.schedule_table.removeCellWidget(row, col)
                        
                        cell_widget = AnimatedCourseWidget(
                            course_data['course_key'], 
                            course_data['color'], 
                            False,
                            self.parent_window
                        )
                        cell_widget.setObjectName('course-cell')
                        
                        cell_widget.setProperty('conflict', False)
                        if course_data['course'].get('code', '').startswith('elective'):
                            cell_widget.setProperty('elective', True)
                        else:
                            cell_widget.setProperty('elective', False)
                        
                        cell_widget.bg_color = course_data['color']
                        cell_widget.border_color = QtGui.QColor(
                            course_data['color'].red()//2, 
                            course_data['color'].green()//2, 
                            course_data['color'].blue()//2
                        )
                        
                        cell_layout = QtWidgets.QVBoxLayout(cell_widget)
                        cell_layout.setContentsMargins(2, 1, 2, 1)
                        cell_layout.setSpacing(0)
                        
                        top_row = QtWidgets.QHBoxLayout()
                        top_row.setContentsMargins(0, 0, 0, 0)
                        top_row.addStretch()
                        
                        x_button = QtWidgets.QPushButton('✕')
                        x_button.setFixedSize(18, 18)
                        x_button.setObjectName('close-btn')
                        x_button.clicked.connect(
                            lambda checked, ck=course_data['course_key']: 
                            self.parent_window.remove_course_silently(ck)
                        )
                        
                        top_row.addWidget(x_button)
                        cell_layout.addLayout(top_row)
                        
                        course_name_label = QtWidgets.QLabel(course_data['course']['name'])
                        course_name_label.setAlignment(QtCore.Qt.AlignCenter)
                        course_name_label.setWordWrap(True)
                        course_name_label.setObjectName('course-name-label')
                        
                        professor_label = QtWidgets.QLabel(course_data['course'].get('instructor', 'نامشخص'))
                        professor_label.setAlignment(QtCore.Qt.AlignCenter)
                        professor_label.setWordWrap(True)
                        professor_label.setObjectName('professor-label')
                        
                        code_label = QtWidgets.QLabel(course_data['course'].get('code', ''))
                        code_label.setAlignment(QtCore.Qt.AlignCenter)
                        code_label.setWordWrap(True)
                        code_label.setObjectName('code-label')
                        
                        cell_layout.addWidget(course_name_label)
                        cell_layout.addWidget(professor_label)
                        cell_layout.addWidget(code_label)
                        
                        bottom_row = QtWidgets.QHBoxLayout()
                        bottom_row.setContentsMargins(0, 0, 0, 0)
                        
                        parity_indicator = ''
                        if course_data['session'].get('parity') == 'ز':
                            parity_indicator = 'ز'
                        elif course_data['session'].get('parity') == 'ف':
                            parity_indicator = 'ف'
                            
                        if parity_indicator:
                            parity_label = QtWidgets.QLabel(parity_indicator)
                            parity_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom)
                            if parity_indicator == 'ز':
                                parity_label.setObjectName('parity-label-even')
                            elif parity_indicator == 'ف':
                                parity_label.setObjectName('parity-label-odd')
                            bottom_row.addWidget(parity_label)
                        
                        bottom_row.addStretch()
                        cell_layout.addLayout(bottom_row)
                        
                        cell_widget.course_key = course_data['course_key']
                        
                        def enter_event(event, widget=cell_widget):
                            self.parent_window.highlight_course_sessions(widget.course_key)
                        
                        def leave_event(event, widget=cell_widget):
                            self.parent_window.clear_course_highlights()
                        
                        def mouse_press_event(event, widget=cell_widget):
                            if event.button() == QtCore.Qt.LeftButton:
                                self.parent_window.show_course_details(widget.course_key)
                        
                        cell_widget.enterEvent = enter_event
                        cell_widget.leaveEvent = leave_event
                        cell_widget.mousePressEvent = mouse_press_event
                        
                        self.parent_window.schedule_table.setCellWidget(row, col, cell_widget)
                        
                        span = info.get('rows', 1)
                        if span > 1:
                            self.parent_window.schedule_table.setSpan(row, col, span, 1)
                        self.parent_window.placed[(row, col)] = {
                            'course': course_data['course_key'], 
                            'rows': span, 
                            'widget': cell_widget
                        }
                        
                        break
                        
        def highlight_section(self, section):
            """Highlight a specific section (odd or even)"""
            self.highlighted_section = section
            self.update()
            
        def clear_highlight(self):
            """Clear any section highlighting"""
            self.highlighted_section = None
            self.update()
            
        def mousePressEvent(self, event):
            """Handle mouse press events for course selection"""
            rect = self.rect()
            pos = event.pos()
            
            diagonal_y = pos.x() * rect.height() / rect.width()
            
            if pos.y() < diagonal_y:
                if hasattr(self.parent_window, 'show_course_details'):
                    self.parent_window.show_course_details(self.odd_data['course_key'])
            else:
                if hasattr(self.parent_window, 'show_course_details'):
                    self.parent_window.show_course_details(self.even_data['course_key'])
            
            super().mousePressEvent(event)
        
        def sizeHint(self):
            """Provide proper size hint"""
            return QtCore.QSize(120, 80)
        
        def minimumSizeHint(self):
            """Provide minimum size"""
            return QtCore.QSize(100, 60)

    return DualCourseWidget(odd_course_data, even_course_data, parent)


def check_odd_even_compatibility(session1, session2):
    """Check if two sessions can coexist in the same cell (one odd, one even)"""
    parity1 = session1.get('parity', '')
    parity2 = session2.get('parity', '')
    
    return (parity1 == 'ف' and parity2 == 'ز') or (parity1 == 'ز' and parity2 == 'ف')


def enhanced_add_course_to_table(self, course_key, ask_on_conflict=True):
    """Enhanced version of add_course_to_table that handles odd/even week compatibility"""
    from app.core.config import COURSES, EXTENDED_TIME_SLOTS, COLOR_MAP, get_days
    DAYS = get_days()
    
    course = COURSES.get(course_key)
    if not course:
        QtWidgets.QMessageBox.warning(self, 'خطا', f'درس با کلید {course_key} یافت نشد.')
        return
    
    placements = []
    for sess in course['schedule']:
        if sess['day'] not in DAYS:
            continue
        col = DAYS.index(sess['day'])
        try:
            srow = EXTENDED_TIME_SLOTS.index(sess['start'])
            erow = EXTENDED_TIME_SLOTS.index(sess['end'])
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'خطا', f'زمان نامعتبر برای درس {course["name"]}: {sess["start"]}-{sess["end"]}')
            continue
        span = max(1, erow - srow)
        placements.append((srow, col, span, sess))

    conflicts = []
    compatible_slots = {}
    
    for (srow, col, span, sess) in placements:
        for (prow, pcol), info in list(self.placed.items()):
            if pcol != col:
                continue
            if info.get('type') == 'dual':
                if course_key in info.get('courses', []):
                    continue
            else:
                if info.get('course') == course_key:
                    continue
            prow_start = prow
            prow_span = info['rows']
            
            if not (srow + span <= prow_start or prow_start + prow_span <= srow):
                existing_course = COURSES.get(info.get('course'), {})
                
                for existing_sess in existing_course.get('schedule', []):
                    if existing_sess['day'] == sess['day']:
                        if check_odd_even_compatibility(sess, existing_sess):
                            compatible_slots[(srow, col)] = {
                                'existing': info,
                                'existing_session': existing_sess,
                                'new_session': sess
                            }
                        else:
                            conflict_course = COURSES.get(info.get('course'), {})
                            conflicts.append(((srow, col), (prow_start, pcol), info.get('course'), conflict_course.get('name', 'نامشخص')))
        
        if conflicts and ask_on_conflict:
            conflict_details = []
            for conf in conflicts:
                (_, _), (_, _), _, conflict_name = conf
                conflict_details.append(conflict_name)
            
            conflict_list = '\n'.join([f"• {name}" for name in conflict_details])
            
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle('تداخل زمان‌بندی دروس')
            msg.setText(f'درس "{course["name"]}" با دروس زیر تداخل دارد:')
            msg.setDetailedText(f'دروس متداخل:\n{conflict_list}')
            msg.setInformativeText('آیا می‌خواهید دروس متداخل حذف شوند و این درس اضافه گردد؟')
            msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
            msg.setDefaultButton(QtWidgets.QMessageBox.No)
            
            res = msg.exec_()
            if res == QtWidgets.QMessageBox.Cancel:
                return
            elif res != QtWidgets.QMessageBox.Yes:
                return
            
            conflicting_courses = set()
            for conf in conflicts:
                (_, _), (rstart, rcol), rcourse, _ = conf
                conflicting_courses.add(rcourse)
            
            for conflicting_course_key in conflicting_courses:
                self.remove_course_from_schedule(conflicting_course_key)
        
        self.clear_preview()
        
        color_idx = len(self.placed) % len(COLOR_MAP)
        bg = COLOR_MAP[color_idx % len(COLOR_MAP)]
        
        for (srow, col, span, sess) in placements:
            if (srow, col) in compatible_slots:
                compat_info = compatible_slots[(srow, col)]
                existing_info = compat_info['existing']
                existing_sess = compat_info['existing_session']
                new_sess = sess
                
                if new_sess.get('parity') == 'ف':
                    odd_data = {
                        'course': course,
                        'course_key': course_key,
                        'session': new_sess,
                        'color': bg
                    }
                    even_data = {
                        'course': COURSES[existing_info.get('course')],
                        'course_key': existing_info.get('course'),
                        'session': existing_sess,
                        'color': existing_info.get('color', COLOR_MAP[0])
                    }
                else:
                    odd_data = {
                        'course': COURSES[existing_info.get('course')],
                        'course_key': existing_info.get('course'),
                        'session': existing_sess,
                        'color': existing_info.get('color', COLOR_MAP[0])
                    }
                    even_data = {
                        'course': course,
                        'course_key': course_key,
                        'session': new_sess,
                        'color': bg
                    }
                
                self.schedule_table.removeCellWidget(srow, col)
                
                dual_widget = create_dual_course_widget(odd_data, even_data, self)
                self.schedule_table.setCellWidget(srow, col, dual_widget)
                
                self.placed[(srow, col)] = {
                    'courses': [odd_data['course_key'], even_data['course_key']],
                    'rows': span,
                    'widget': dual_widget,
                    'type': 'dual',
                    'color': bg
                }
        
        self.update_status()
        self.update_stats_panel()
        self.update_detailed_info_if_open()
