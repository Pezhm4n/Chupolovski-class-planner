#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Language manager for Golestoon Class Planner application.

This module handles language switching, persistence, and UI direction changes.
"""

import os
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QSettings, Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

logger = logging.getLogger(__name__)

class LanguageManager(QObject):
    """Manages application language settings and switching"""
    
    # Signal emitted when language changes
    language_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._current_language = "fa"  # Default to Persian
        self._available_languages = ["fa", "en"]
        self._settings = QSettings("Golestoon", "ClassPlanner")
        
        self.load_language_preference()
        logger.info(f"LanguageManager initialized with language: {self._current_language}")
    
    def set_available_languages(self, languages):
        """Set available languages"""
        self._available_languages = languages
    
    def get_current_language(self):
        """Get current language code"""
        return self._current_language
    
    def set_language(self, lang_code):
        """Set application language"""
        if lang_code in self._available_languages:
            old_lang = self._current_language
            self._current_language = lang_code
            
            self.save_language_preference()
            
            from app.core.translator import translator
            translator.load_translations(lang_code)

            try:
                from app.core.i18n import translation_registry
                translation_registry.refresh_all()
            except Exception:
                pass
            
            self.language_changed.emit(lang_code)
            return old_lang != lang_code
        return False
    
    def is_rtl(self):
        """Check if current language is RTL"""
        return self._current_language == "fa"
    
    def get_available_languages(self):
        """Get list of available language codes"""
        return self._available_languages.copy()
    
    def save_language_preference(self):
        """Save language preference to settings"""
        self._settings.setValue("language", self._current_language)
    
    def load_language_preference(self):
        """Load language preference from settings"""
        saved_lang = self._settings.value("language", "fa")
        logger.debug(f"Raw language value from settings: {repr(saved_lang)} (type: {type(saved_lang)})")
        
        if saved_lang:
            saved_lang = str(saved_lang).strip()
        else:
            saved_lang = "fa"
        
        logger.debug(f"Processed language value: {repr(saved_lang)}")
        
        if saved_lang in self._available_languages:
            self._current_language = saved_lang
            logger.info(f"Loaded language preference: {saved_lang}")
        else:
            self._current_language = "fa"
            logger.warning(f"Invalid language code '{saved_lang}' loaded from settings, defaulting to 'fa'")
    
    def apply_layout_direction(self, widget=None):
        """Apply appropriate layout direction based on current language"""
        direction = self.get_layout_direction()
        
        app = QApplication.instance()
        if app is not None:
            if isinstance(app, QApplication):
                try:
                    app.setLayoutDirection(direction)
                except:
                    pass
            else:
                try:
                    app.setLayoutDirection(direction)
                except:
                    pass
        
        if widget is not None:
            widget.setLayoutDirection(direction)
    
    def get_layout_direction(self):
        """Get layout direction for current language"""
        if self._current_language == "fa":
            return getattr(Qt, 'RightToLeft', 1)
        else:
            return getattr(Qt, 'LeftToRight', 0)

    def apply_font(self, app):
        """Apply appropriate font based on current language"""
        from app.core.translator import translator
        font_family = translator.get_meta("font_family")
        if font_family:
            font = QFont(font_family, 10)
            app.setFont(font)

# Global instance
language_manager = LanguageManager()

# Convenience functions
def get_current_language():
    """Get current language code"""
    return language_manager.get_current_language()

def set_language(lang_code):
    """Set application language"""
    return language_manager.set_language(lang_code)

def get_available_languages():
    """Get list of available language codes"""
    return language_manager.get_available_languages()

def apply_layout_direction(widget):
    """Apply appropriate layout direction based on current language"""
    language_manager.apply_layout_direction(widget)

def get_layout_direction():
    """Get layout direction for current language"""
    return language_manager.get_layout_direction()

def apply_font(app):
    """Apply appropriate font based on current language"""
    language_manager.apply_font(app)