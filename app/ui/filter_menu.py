#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Floating Filter Menu for course search filters
Compact popup menu instead of full dialog
"""

from PyQt5 import QtWidgets, QtCore, QtGui
from app.core.translator import translator
from app.core.language_manager import language_manager
from app.core.logger import setup_logging

logger = setup_logging()

GENERAL_COURSES_CORE = [
    "آشنایی با ادبیات فارسی",
    "آشنایی با ارزشهای دفاع مقدس",
    "آشنایی با دفاع مقدس",
    "آشنایی با قانون اساسی",
    "انسان در اسلام",
    "اندیشه اسلامی",
    "اندیشه اسلامی مبدا و معاد",
    "اندیشه اسلامی نبوت و امامت",
    "اندیشه اسلامی ۱",
    "اندیشه اسلامی ۲",
    "اندیشه سیاسی امام",
    "اندیشه سیاسی امام خمینی",
    "آیین زندگی",
    "اخلاق اسلامی",
    "اخلاق اسلامی مبانی و مفاهیم",
    "اخلاق خانواده",
    "عرفان عملی در اسلام",
    "انقلاب اسلامی ایران",
    "تاریخ اسلام",
    "تاریخ فرهنگ و تمدن اسلام",
    "تاریخ فرهنگ و تمدن اسلام و ایران",
    "تاریخ تحلیلی صدر اسلام",
    "تاریخ امامت",
    "تفسیر موضوعی قرآن",
    "تفسیر موضوعی نهج البلاغه",
    "حقوق اجتماعی و سیاسی در اسلام",
    "دانش خانواده و جمعیت",
    "زبان عمومی",
    "زبان خارجی",
    "شناخت محیط زیست",
    "فارسی عمومی",
    "فلسفه اخلاق",
    "کارآفرینی",
    "مبدا و معاد",
    "نبوت و امامت",
    "ورزش",
    "ورزش ویژه",
    "تربیت بدنی",
    "تربیت بدنی ویژه",
    "ورزش 1",
    "ورزش 2",
    "ورزش 3"
]

GENERAL_COURSES = set()
persian_digits_map = {1: '۱', 2: '۲', 3: '۳', 9: '۹'}

for course in GENERAL_COURSES_CORE:
    normalized_course = course.strip()
    if not normalized_course:
        continue
    GENERAL_COURSES.add(normalized_course)
    for num in [1, 2, 3]:
        GENERAL_COURSES.add(f"{normalized_course}{num}")
        GENERAL_COURSES.add(f"{normalized_course} {num}")
        persian_num = persian_digits_map.get(num, str(num))
        GENERAL_COURSES.add(f"{normalized_course}{persian_num}")
        GENERAL_COURSES.add(f"{normalized_course} {persian_num}")

GENERAL_COURSES = sorted(GENERAL_COURSES)


class FilterMenu(QtWidgets.QWidget):
    """Floating filter menu widget"""
    
    filters_changed = QtCore.pyqtSignal(dict)  # Emits filter dictionary when changed
    search_all_courses = QtCore.pyqtSignal()  # Emits when "جستجو در تمام دروس" is clicked
    
    def __init__(self, parent=None, current_filters=None):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self._parent_window = parent
        # Connect to parent window's state changes to close when minimized
        if parent:
            try:
                # Try to connect to changeEvent signal if available
                if hasattr(parent, 'windowStateChanged'):
                    parent.windowStateChanged.connect(self._on_parent_window_state_changed)
                # Also install event filter to monitor parent window
                parent.installEventFilter(self)
            except:
                pass
        
        # Ensure current_filters is a valid dict with proper defaults
        if current_filters is None:
            current_filters = {}
        
        self.current_filters = {
            'time_from': current_filters.get('time_from'),
            'time_to': current_filters.get('time_to'),
            'general_courses_only': current_filters.get('general_courses_only', False),
            'gender': current_filters.get('gender')
        }
        
        self.setup_ui()
        self.apply_language_direction()
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QCheckBox, QRadioButton {
                spacing: 5px;
            }
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton#apply_btn {
                background-color: #1976D2;
                color: white;
            }
            QPushButton#apply_btn:hover {
                background-color: #1565C0;
            }
            QPushButton#clear_btn {
                background-color: #f5f5f5;
                color: #333;
            }
            QPushButton#clear_btn:hover {
                background-color: #e0e0e0;
            }
            QPushButton#search_all_btn {
                background-color: #43A047;
                color: white;
                font-weight: bold;
            }
            QPushButton#search_all_btn:hover {
                background-color: #388E3C;
            }
        """)
    
    def setup_ui(self):
        """Setup the filter menu UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Time range filter (compact)
        time_layout = QtWidgets.QHBoxLayout()
        time_layout.setSpacing(6)
        
        self.time_filter_enabled = QtWidgets.QCheckBox(translator.t("filters.time_range", default="بازه زمانی"))
        time_from = self.current_filters.get('time_from')
        time_to = self.current_filters.get('time_to')
        self.time_filter_enabled.setChecked(time_from is not None and time_to is not None)
        self.time_filter_enabled.toggled.connect(self._on_time_filter_toggled)
        
        # From time
        from_label = QtWidgets.QLabel(translator.t("filters.from", default="از:"))
        self.from_spinbox = QtWidgets.QSpinBox()
        self.from_spinbox.setMinimum(7)
        self.from_spinbox.setMaximum(19)
        time_from = self.current_filters.get('time_from')
        self.from_spinbox.setValue(time_from if time_from is not None else 7)
        self.from_spinbox.setSuffix(" " + translator.t("filters.hour", default="ساعت"))
        self.from_spinbox.setMinimumWidth(70)
        self.from_spinbox.setMaximumWidth(70)
        
        # To time
        to_label = QtWidgets.QLabel(translator.t("filters.to", default="تا:"))
        self.to_spinbox = QtWidgets.QSpinBox()
        self.to_spinbox.setMinimum(7)
        self.to_spinbox.setMaximum(19)
        time_to = self.current_filters.get('time_to')
        self.to_spinbox.setValue(time_to if time_to is not None else 19)
        self.to_spinbox.setSuffix(" " + translator.t("filters.hour", default="ساعت"))
        self.to_spinbox.setMinimumWidth(70)
        self.to_spinbox.setMaximumWidth(70)
        
        time_layout.addWidget(self.time_filter_enabled)
        time_layout.addWidget(from_label)
        time_layout.addWidget(self.from_spinbox)
        time_layout.addWidget(to_label)
        time_layout.addWidget(self.to_spinbox)
        
        layout.addLayout(time_layout)
        
        # Initially disable spinboxes if time filter is not enabled
        self._on_time_filter_toggled(self.time_filter_enabled.isChecked())
        
        # General courses filter
        self.general_courses_checkbox = QtWidgets.QCheckBox(
            translator.t("filters.general_courses_only", default="فقط دروس عمومی")
        )
        self.general_courses_checkbox.setChecked(self.current_filters.get('general_courses_only', False))
        layout.addWidget(self.general_courses_checkbox)
        
        # Gender filter (compact)
        gender_label = QtWidgets.QLabel(translator.t("filters.gender", default="جنسیت:") + " ")
        gender_layout = QtWidgets.QHBoxLayout()
        gender_layout.addWidget(gender_label)
        
        self.gender_none_radio = QtWidgets.QRadioButton(
            translator.t("filters.gender_all", default="همه")
        )
        self.gender_male_radio = QtWidgets.QRadioButton(
            translator.t("filters.gender_male", default="آقا")
        )
        self.gender_female_radio = QtWidgets.QRadioButton(
            translator.t("filters.gender_female", default="خانم")
        )
        self.gender_mixed_radio = QtWidgets.QRadioButton(
            translator.t("filters.gender_mixed", default="مختلط")
        )
        
        # Set current gender selection
        current_gender = self.current_filters.get('gender')
        if current_gender == 'مرد' or current_gender == 'آقا':  # Support both for backward compatibility
            self.gender_male_radio.setChecked(True)
        elif current_gender == 'زن' or current_gender == 'خانم':  # Support both for backward compatibility
            self.gender_female_radio.setChecked(True)
        elif current_gender == 'مختلط':
            self.gender_mixed_radio.setChecked(True)
        else:
            self.gender_none_radio.setChecked(True)
        
        gender_layout.addWidget(self.gender_none_radio)
        gender_layout.addWidget(self.gender_male_radio)
        gender_layout.addWidget(self.gender_female_radio)
        gender_layout.addWidget(self.gender_mixed_radio)
        gender_layout.addStretch()
        
        layout.addLayout(gender_layout)
        
        # Buttons
        button_layout = QtWidgets.QVBoxLayout()
        button_layout.setSpacing(6)
        
        # Search all courses button
        self.search_all_btn = QtWidgets.QPushButton(
            translator.t("filters.search_all_courses", default="جستجو در تمام دروس")
        )
        self.search_all_btn.setObjectName("search_all_btn")
        self.search_all_btn.clicked.connect(self._on_search_all_clicked)
        button_layout.addWidget(self.search_all_btn)
        
        # Apply and Clear buttons
        apply_clear_layout = QtWidgets.QHBoxLayout()
        apply_clear_layout.setSpacing(6)
        
        self.clear_button = QtWidgets.QPushButton(translator.t("filters.clear", default="پاک کردن"))
        self.clear_button.setObjectName("clear_btn")
        self.clear_button.clicked.connect(self.clear_filters)
        
        self.apply_button = QtWidgets.QPushButton(translator.t("filters.apply", default="اعمال"))
        self.apply_button.setObjectName("apply_btn")
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self._on_apply_clicked)
        
        apply_clear_layout.addWidget(self.clear_button)
        apply_clear_layout.addWidget(self.apply_button)
        
        button_layout.addLayout(apply_clear_layout)
        layout.addLayout(button_layout)
        
        # Adjust size
        self.adjustSize()
        self.setMinimumWidth(280)
        self.setMaximumWidth(320)
    
    def _on_time_filter_toggled(self, enabled):
        """Enable/disable time spinboxes"""
        self.from_spinbox.setEnabled(enabled)
        self.to_spinbox.setEnabled(enabled)
    
    def apply_language_direction(self):
        """Apply language direction"""
        current_lang = language_manager.get_current_language()
        if current_lang == 'fa':
            self.setLayoutDirection(QtCore.Qt.RightToLeft)
        else:
            self.setLayoutDirection(QtCore.Qt.LeftToRight)
    
    def clear_filters(self):
        """Clear all filters"""
        self.time_filter_enabled.setChecked(False)
        self.from_spinbox.setValue(7)
        self.to_spinbox.setValue(19)
        self.general_courses_checkbox.setChecked(False)
        self.gender_none_radio.setChecked(True)
        self._on_time_filter_toggled(False)
    
    def _on_apply_clicked(self):
        """Handle apply button click"""
        filters = self.get_filters()
        self.filters_changed.emit(filters)
        self.close()
    
    def _on_search_all_clicked(self):
        """Handle search all courses button click"""
        filters = self.get_filters()
        self.filters_changed.emit(filters)
        self.search_all_courses.emit()
        self.close()
    
    def _on_parent_window_state_changed(self, state):
        """Close filter menu when parent window is minimized or hidden"""
        if state & (QtCore.Qt.WindowMinimized | QtCore.Qt.WindowHidden):
            self.close()
    
    def changeEvent(self, event):
        """Handle window state changes"""
        if event.type() == QtCore.QEvent.WindowStateChange:
            # Close if parent is minimized
            if self._parent_window and (self._parent_window.isMinimized() or not self._parent_window.isVisible()):
                self.close()
        super().changeEvent(event)
    
    def eventFilter(self, obj, event):
        """Event filter to monitor parent window state changes"""
        if obj == self._parent_window:
            if event.type() == QtCore.QEvent.WindowStateChange:
                if self._parent_window.isMinimized() or not self._parent_window.isVisible():
                    self.close()
        return super().eventFilter(obj, event)
    
    def get_filters(self):
        """Get current filter values"""
        filters = {
            'time_from': None,
            'time_to': None,
            'general_courses_only': False,
            'gender': None
        }
        
        # Time filter
        if self.time_filter_enabled.isChecked():
            from_hour = self.from_spinbox.value()
            to_hour = self.to_spinbox.value()
            
            # Validate range
            if from_hour <= to_hour:
                filters['time_from'] = from_hour
                filters['time_to'] = to_hour
            else:
                # Swap if from > to
                filters['time_from'] = to_hour
                filters['time_to'] = from_hour
        
        # General courses filter
        filters['general_courses_only'] = self.general_courses_checkbox.isChecked()
        
        # Gender filter
        if self.gender_male_radio.isChecked():
            filters['gender'] = 'مرد'
        elif self.gender_female_radio.isChecked():
            filters['gender'] = 'زن'
        elif self.gender_mixed_radio.isChecked():
            filters['gender'] = 'مختلط'
        else:
            filters['gender'] = None
        
        return filters

