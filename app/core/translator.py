#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Translator module for Golestoon Class Planner application.

This module handles loading translation files and providing translated strings.
"""

import json
import os
from pathlib import Path

class Translator:
    """Handles translation of application strings"""
    
    def __init__(self):
        self._translations = {}
        self._current_language = "fa"
        self._meta = {}
        
        self.load_translations("fa")
    
    def _load_translation_file(self, file_path):
        """Load translation file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_translations(self, lang_code):
        """Load translation file for specified language"""
        try:
            # Get the translations directory
            translations_dir = Path(__file__).parent.parent / "translations"
            
            # Construct file path
            file_name = f"{lang_code}_{'IR' if lang_code == 'fa' else 'US'}.json"
            file_path = translations_dir / file_name
            
            # Load translations
            if os.path.exists(file_path):
                data = self._load_translation_file(str(file_path))
                self._translations = data
                self._current_language = lang_code
                
                # Extract meta information
                self._meta = data.get("meta", {})
                return True
            else:
                print(f"Translation file not found: {file_path}")
                return False
        except Exception as e:
            print(f"Error loading translations for {lang_code}: {e}")
            return False
    
    def translate(self, key, **kwargs):
        """Translate a key with optional placeholders"""
        try:
            keys = key.split(".")
            value = self._translations
            
            for k in keys:
                value = value[k]
            
            if isinstance(value, dict):
                if 'en' in value:
                    value = str(value['en'])
                elif 'fa' in value:
                    value = str(value['fa'])
                elif 'default' in value:
                    value = str(value['default'])
                else:
                    print(f"Translation key '{key}' returned a dict: {value}")
                    return key
            
            value = str(value)
            
            if kwargs:
                for placeholder, replacement in kwargs.items():
                    value = value.replace("{" + str(placeholder) + "}", str(replacement))
            
            return value
        except (KeyError, TypeError):
            if self._current_language != "en":
                try:
                    original_lang = self._current_language
                    original_translations = self._translations
                    
                    if self.load_translations("en"):
                        result = self.translate(key, **kwargs)
                        self._current_language = original_lang
                        self._translations = original_translations
                        return result
                except:
                    pass
            
            return key
    
    def get_available_languages(self):
        """Get list of available language codes based on existing translation files"""
        import os
        from pathlib import Path
        translations_dir = Path(__file__).parent.parent / "translations"
        languages = []
        
        if os.path.exists(translations_dir):
            for file in os.listdir(translations_dir):
                if file.endswith(".json") and "_" in file:
                    lang_code = file.split("_")[0]
                    if lang_code not in languages:
                        languages.append(lang_code)
        
        return languages
    
    def get_language_name(self, lang_code):
        """Get the display name for a language code"""
        try:
            # Get the translations directory
            from pathlib import Path
            translations_dir = Path(__file__).parent.parent / "translations"
            
            # Construct file path
            file_name = f"{lang_code}_{'IR' if lang_code == 'fa' else 'US'}.json"
            file_path = translations_dir / file_name
            
            # Load translations
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("meta", {}).get("language", lang_code)
        except:
            pass
        
        # Fallback names
        language_names = {
            "fa": "فارسی",
            "en": "English"
        }
        return language_names.get(lang_code, lang_code)
    
    def t(self, key, **kwargs):
        """Shortcut for translate method"""
        return self.translate(key, **kwargs)
    
    def get_meta(self, key):
        """Get metadata value"""
        return self._meta.get(key, "")
    
    def get_current_language(self):
        """Get current language code"""
        return self._current_language

# Global instance
translator = Translator()

# Convenience functions
def translate(key, **kwargs):
    """Translate a key with optional placeholders"""
    return translator.translate(key, **kwargs)

def t(key, **kwargs):
    """Shortcut for translate method"""
    return translator.t(key, **kwargs)

def get_meta(key):
    """Get metadata value"""
    return translator.get_meta(key)

def get_current_language():
    """Get current language code"""
    return translator.get_current_language()

def get_available_languages():
    """Get list of available language codes"""
    return translator.get_available_languages()

def get_language_name(lang_code):
    """Get the display name for a language code"""
    return translator.get_language_name(lang_code)