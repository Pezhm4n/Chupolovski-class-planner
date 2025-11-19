#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filter Dialog for course search filters
Provides time range, general courses, and gender filters
"""

from PyQt5 import QtWidgets, QtCore, QtGui
from app.core.translator import translator
from app.core.language_manager import language_manager
from app.core.logger import setup_logging

logger = setup_logging()

# Import general courses list from filter_menu
from .filter_menu import GENERAL_COURSES


class FilterDialog(QtWidgets.QDialog):
    """Dialog for course search filters"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(translator.t("filters.title", default="فیلترهای جستجو"))
        self.setModal(True)
        self.setMinimumWidth(350)
        
        # Filter state
        self.time_from = None
        self.time_to = None
        self.general_courses_only = False
        self.gender_filter = None  # 'آقا', 'خانم', 'مختلط', or None
        
        self.setup_ui()
        self.apply_language_direction()
    
    def setup_ui(self):
        """Setup the filter dialog UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Time range filter
        time_group = QtWidgets.QGroupBox(translator.t("filters.time_range", default="بازه زمانی"))
        time_layout = QtWidgets.QHBoxLayout()
        time_layout.setSpacing(8)
        
        # From time
        from_label = QtWidgets.QLabel(translator.t("filters.from", default="از:"))
        self.from_spinbox = QtWidgets.QSpinBox()
        self.from_spinbox.setMinimum(7)
        self.from_spinbox.setMaximum(19)
        self.from_spinbox.setValue(7)
        self.from_spinbox.setSuffix(" " + translator.t("filters.hour", default="ساعت"))
        self.from_spinbox.setMinimumWidth(100)
        
        # To time
        to_label = QtWidgets.QLabel(translator.t("filters.to", default="تا:"))
        self.to_spinbox = QtWidgets.QSpinBox()
        self.to_spinbox.setMinimum(7)
        self.to_spinbox.setMaximum(19)
        self.to_spinbox.setValue(19)
        self.to_spinbox.setSuffix(" " + translator.t("filters.hour", default="ساعت"))
        self.to_spinbox.setMinimumWidth(100)
        
        # Enable/disable checkbox
        self.time_filter_enabled = QtWidgets.QCheckBox(translator.t("filters.enable_time", default="فعال"))
        self.time_filter_enabled.setChecked(False)
        self.time_filter_enabled.toggled.connect(self._on_time_filter_toggled)
        
        time_layout.addWidget(self.time_filter_enabled)
        time_layout.addWidget(from_label)
        time_layout.addWidget(self.from_spinbox)
        time_layout.addWidget(to_label)
        time_layout.addWidget(self.to_spinbox)
        time_layout.addStretch()
        
        time_group.setLayout(time_layout)
        layout.addWidget(time_group)
        
        # Initially disable spinboxes
        self._on_time_filter_toggled(False)
        
        # General courses filter
        self.general_courses_checkbox = QtWidgets.QCheckBox(
            translator.t("filters.general_courses_only", default="فقط دروس عمومی")
        )
        self.general_courses_checkbox.setToolTip(
            translator.t("filters.general_courses_tooltip", 
                        default="نمایش فقط دروس عمومی مانند اندیشه اسلامی، تربیت بدنی و...")
        )
        layout.addWidget(self.general_courses_checkbox)
        
        # Gender filter
        gender_group = QtWidgets.QGroupBox(translator.t("filters.gender", default="جنسیت"))
        gender_layout = QtWidgets.QVBoxLayout()
        
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
        
        self.gender_none_radio.setChecked(True)
        
        gender_layout.addWidget(self.gender_none_radio)
        gender_layout.addWidget(self.gender_male_radio)
        gender_layout.addWidget(self.gender_female_radio)
        gender_layout.addWidget(self.gender_mixed_radio)
        
        gender_group.setLayout(gender_layout)
        layout.addWidget(gender_group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.apply_button = QtWidgets.QPushButton(translator.t("filters.apply", default="اعمال"))
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self.accept)
        
        self.clear_button = QtWidgets.QPushButton(translator.t("filters.clear", default="پاک کردن"))
        self.clear_button.clicked.connect(self.clear_filters)
        
        self.cancel_button = QtWidgets.QPushButton(translator.t("filters.cancel", default="لغو"))
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        
        layout.addLayout(button_layout)
    
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
            filters['gender'] = 'آقا'
        elif self.gender_female_radio.isChecked():
            filters['gender'] = 'خانم'
        elif self.gender_mixed_radio.isChecked():
            filters['gender'] = 'مختلط'
        else:
            filters['gender'] = None
        
        return filters
    
    def set_filters(self, filters):
        """Set filter values"""
        if filters.get('time_from') and filters.get('time_to'):
            self.time_filter_enabled.setChecked(True)
            self.from_spinbox.setValue(filters['time_from'])
            self.to_spinbox.setValue(filters['time_to'])
        else:
            self.time_filter_enabled.setChecked(False)
        
        self.general_courses_checkbox.setChecked(filters.get('general_courses_only', False))
        
        gender = filters.get('gender')
        if gender == 'آقا':
            self.gender_male_radio.setChecked(True)
        elif gender == 'خانم':
            self.gender_female_radio.setChecked(True)
        elif gender == 'مختلط':
            self.gender_mixed_radio.setChecked(True)
        else:
            self.gender_none_radio.setChecked(True)

