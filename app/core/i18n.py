#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Internationalization (i18n) module for Golestoon Class Planner.

This module provides widget registration and translation management for UI elements.
"""

import logging
from typing import Callable, Optional, Any
from PyQt5.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class TranslationRegistry:
    """Registry for widgets that need translation updates"""
    
    def __init__(self):
        self._widgets = []
        logger.debug("TranslationRegistry initialized")
    
    def register(self, widget, translation_key, method="setText", fallback=None, callback=None):
        """
        Register a widget for translation updates.
        
        Args:
            widget: The widget to register (QWidget or similar)
            translation_key: Translation key string (e.g., "menu.file") or None
            method: Method name to call on widget (default: "setText")
            fallback: Fallback text if translation_key is None
            callback: Optional callback function to get translated text
        """
        if widget is None:
            return
        
        entry = {
            'widget': widget,
            'translation_key': translation_key,
            'method': method,
            'fallback': fallback,
            'callback': callback
        }
        
        self._widgets.append(entry)
        
        self._update_widget(entry)
        
        logger.debug(f"Registered widget: {widget}, key: {translation_key}, method: {method}")
    
    def _update_widget(self, entry):
        """Update a single widget with translation"""
        try:
            widget = entry['widget']
            
            if not hasattr(widget, entry['method']):
                logger.warning(f"Widget {widget} does not have method {entry['method']}")
                return
            
            method = getattr(widget, entry['method'])
            
            if entry['callback']:
                text = entry['callback']()
            elif entry['translation_key']:
                from app.core.translator import translator
                text = translator.t(entry['translation_key'])
            elif entry['fallback']:
                text = entry['fallback']
            else:
                return
            
            method(text)
            
        except Exception as e:
            logger.warning(f"Failed to update widget: {e}")
    
    def refresh_all(self):
        """Refresh all registered widgets with current translations"""
        logger.debug(f"Refreshing {len(self._widgets)} registered widgets")
        
        for entry in self._widgets[:]:
            try:
                widget = entry['widget']
                if widget is None:
                    self._widgets.remove(entry)
                    continue
                
                if not hasattr(widget, entry['method']):
                    continue
                
                self._update_widget(entry)
            except (RuntimeError, AttributeError):
                try:
                    self._widgets.remove(entry)
                except ValueError:
                    pass
            except Exception as e:
                logger.warning(f"Error refreshing widget: {e}")
    
    def unregister(self, widget):
        """Unregister a widget from translation updates"""
        self._widgets = [e for e in self._widgets if e['widget'] != widget]
        logger.debug(f"Unregistered widget: {widget}")
    
    def clear(self):
        """Clear all registered widgets"""
        self._widgets.clear()
        logger.debug("Translation registry cleared")

translation_registry = TranslationRegistry()


def register_widget(widget, translation_key=None, method="setText", fallback=None, callback=None):
    """
    Register a widget for automatic translation updates.
    This is a convenience function that registers a widget with the global
    translation registry. When the application language changes, all registered
    widgets will be automatically updated.
    
    Args:
        widget: The widget to register (QWidget or similar PyQt widget)
        translation_key: Translation key string (e.g., "menu.file") or None
        method: Method name to call on widget to set the text (default: "setText")
        fallback: Fallback text to use if translation_key is None
        callback: Optional callback function that returns the translated text
    """
    if widget is None:
        logger.warning("Attempted to register None widget")
        return
    
    translation_registry.register(
        widget=widget,
        translation_key=translation_key,
        method=method,
        fallback=fallback,
        callback=callback
    )

